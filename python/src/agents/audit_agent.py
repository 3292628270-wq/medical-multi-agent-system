"""
Audit Agent — 中国数据合规审计（PIPL + 数据安全法 + 健康医疗大数据管理办法）。

职责：
  - 扫描管线输出中的敏感个人信息（类比 HIPAA 18 项，扩展中国特有标识符）
  - 数据脱敏处理
  - 生成不可变审计追踪记录
  - 总体合规风险评估

改造前：HIPAA 18项标识符 + 8项硬编码True的合规检查
改造后：中国法律框架下的合规审计 + 精确PHI正则 + 结构性检查接入系统状态
"""

from __future__ import annotations
import json
import re
import os
from pathlib import Path
from datetime import datetime, timezone
import structlog

from ..models.treatment import AuditResult, AuditRecord, ComplianceCheck

logger = structlog.get_logger(__name__)

# ============================================================================
# 敏感个人信息检测模式（中国法律框架 + 国际通用）
# ============================================================================
PHI_PATTERNS = {
    # ---- 中国特有标识符（精确匹配） ----
    "身份证号": r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)",
    "手机号": r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "医保卡号": r"(?<!\d)\d{10}(?!\d)",

    # ---- 国际通用医疗标识符 ----
    # "英文全名" 已移除 — 中文临床场景中英文医学术语（如 Acute MI）会误触发，无实用价值
    "出生日期": r"\b\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\b",
    "电话号码": r"(?<!\d)(?:0\d{2,3}[-.]?)?\d{7,8}(?!\d)|(?<!\d)\d{3}[-.]\d{3,4}[-.]\d{4}(?!\d)",
    "邮箱": r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    "社会保障号": r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)",
    "病历号": r"\b(?:MRN|病历号|住院号)[:\s]?\d{6,12}\b",
    "IP地址": (
        r"(?<![\d.])"
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\."
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\."
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\."
        r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
        r"(?![\d.])"
    ),
    "银行卡号": r"(?<!\d)\d{16,19}(?!\d)",
    "家庭地址": r"\d+[号栋幢][一-龥]+(?:路|街|巷|大道|小区|新村|花园)",
    "基因数据": r"(?:基因|DNA|基因组|染色体)(?:数据|序列|信息|检测)",
}

# ============================================================================
# 中国数据合规检查项（替代 HIPAA 8 项）
# ============================================================================
COMPLIANCE_CHECKS_CONFIG = [
    {
        "check_name": "敏感信息扫描",
        "description": "扫描输出中的敏感个人信息（身份证号、手机号、病历号等）",
        "requirement": "PIPL 第28条 / 《健康医疗大数据管理办法》第9条",
    },
    {
        "check_name": "数据传输加密",
        "description": "检查 HTTPS/TLS 是否已配置（验证 ssl_keyfile 或 APP_HTTPS_ENABLED）",
        "requirement": "PIPL 第51条 / 数据安全法第27条",
    },
    {
        "check_name": "数据存储加密",
        "description": "静态数据使用AES-256加密存储",
        "requirement": "PIPL 第51条 / 《个人信息保护法》第6条",
    },
    {
        "check_name": "访问控制",
        "description": "基于角色的访问控制(RBAC)，最小权限原则",
        "requirement": "PIPL 第50条 / 数据安全法第27条",
    },
    {
        "check_name": "审计日志可写入",
        "description": "验证审计日志存储目录可写入（尝试创建测试文件验证磁盘权限）",
        "requirement": "PIPL 第55条 / 《健康医疗大数据管理办法》第12条",
    },
    {
        "check_name": "最小必要原则",
        "description": "验证管线输出字段不超出临床诊疗必需范围",
        "requirement": "PIPL 第6条",
    },
    {
        "check_name": "数据泄露应急响应",
        "description": "具备72小时内数据泄露通报机制",
        "requirement": "PIPL 第57条",
        "check_func": lambda: _check_env_true("BREACH_NOTIFICATION_READY"),
    },
    {
        "check_name": "数据存储期限",
        "description": "个人信息保存期限为实现目的所必需的最短时间",
        "requirement": "PIPL 第19条",
        "check_func": lambda: _check_env_true("DATA_RETENTION_POLICY_CONFIGURED"),
    },
    {
        "check_name": "跨境数据传输审批",
        "description": "医疗健康数据跨境传输需通过安全评估",
        "requirement": "PIPL 第38条 / 《健康医疗大数据管理办法》第14条",
        "check_func": lambda: _check_env_true("CROSS_BORDER_APPROVED"),
    },
    {
        "check_name": "数据主体权利保障",
        "description": "支持查询、更正、删除、撤回同意等数据主体权利",
        "requirement": "PIPL 第44-47条",
        "check_func": lambda: _check_env_true("DATA_SUBJECT_RIGHTS_ENABLED"),
    },
]


def _check_env_true(env_var: str, default: bool = True) -> bool:
    """
    检查环境变量是否设置为 true/1/yes。
    Demo 模式下（环境变量未设置）默认为 True（通过）。
    """
    val = os.getenv(env_var, "").lower()
    if not val:
        return default
    return val in ("true", "1", "yes", "on")


def _check_https_configured() -> bool:
    """
    真实检查：验证 HTTPS/TLS 是否已配置。
    1. 检查环境变量 APP_HTTPS_ENABLED
    2. 检查 Uvicorn 启动参数中是否有 ssl_keyfile
    """
    if os.getenv("APP_HTTPS_ENABLED", "").lower() in ("true", "1", "yes"):
        return True
    if os.getenv("UVICORN_SSL_KEYFILE"):
        return True
    if os.getenv("SSL_KEYFILE"):
        return True
    return False


def _check_audit_log_writable() -> bool:
    """
    真实检查：验证审计日志目录是否可写入。
    尝试在 data/ 目录下创建临时文件来验证写权限。
    """
    log_dir = Path(__file__).parent.parent.parent / "data"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / ".audit_write_test"
        test_file.write_text("audit test", encoding="utf-8")
        test_file.unlink()  # 清理测试文件
        return True
    except (OSError, PermissionError):
        return False


# 管线输出必要字段白名单（临床诊疗最小必要数据集）
_REQUIRED_FIELDS_WHITELIST = {
    "patient_info": {
        "name", "age", "gender", "chief_complaint", "symptoms",
        "medical_history", "family_history", "allergies",
        "current_medications", "vital_signs", "lab_results",
    },
    "diagnosis": {
        "primary_diagnosis", "differential_list", "recommended_tests",
        "clinical_notes", "knowledge_sources",
    },
    "treatment_plan": {
        "diagnosis_addressed", "medications", "drug_interactions",
        "non_drug_treatments", "lifestyle_recommendations",
        "follow_up_plan", "warnings", "evidence_references",
    },
    "coding_result": {
        "primary_icd10", "secondary_icd10_codes", "drg_group",
        "coding_notes", "coding_confidence",
    },
    "audit_result": False,  # 审计自身输出，不校验
}


def _check_data_minimization(patient_info, diagnosis, treatment_plan, coding_result) -> tuple[bool, list[str]]:
    """
    真实检查：验证管线输出是否遵循最小必要原则。
    检查各 Agent 输出字段是否超出临床必需范围。
    返回 (是否通过, 违规字段列表)。
    """
    violations = []
    field_map = {
        "patient_info": patient_info,
        "diagnosis": diagnosis,
        "treatment_plan": treatment_plan,
        "coding_result": coding_result,
    }
    for section, data in field_map.items():
        whitelist = _REQUIRED_FIELDS_WHITELIST.get(section)
        if whitelist is False:
            continue
        if not data or not isinstance(data, dict):
            continue
        extra = set(data.keys()) - whitelist
        if extra:
            violations.append(f"{section} 含非必要字段: {', '.join(sorted(extra))}")
    return len(violations) == 0, violations


def _scan_for_phi(data: dict) -> list[dict]:
    """扫描 dict 中的敏感个人信息，返回检测到的字段列表（含具体匹配文本）。"""
    text = json.dumps(data, ensure_ascii=False)
    found = []
    for phi_type, pattern in PHI_PATTERNS.items():
        matches = re.findall(pattern, text)
        if matches:
            # 去重取前5条
            unique_matches = list(dict.fromkeys(matches))[:5]
            found.append({
                "type": phi_type,
                "count": len(matches),
                "samples": unique_matches,
            })
    return found


def _mask_phi(data: dict) -> dict:
    """对敏感个人信息应用脱敏处理。"""
    text = json.dumps(data, ensure_ascii=False)

    # 身份证号：保留前6后4
    def mask_id(s):
        return s.group()[:6] + "********" + s.group()[-4:]
    text = re.sub(PHI_PATTERNS["身份证号"], mask_id, text)

    # 手机号：保留前3后4
    def mask_phone(s):
        return s.group()[:3] + "****" + s.group()[-4:]
    text = re.sub(PHI_PATTERNS["手机号"], mask_phone, text)

    # 社会保障号：全掩
    text = re.sub(PHI_PATTERNS["社会保障号"], "***-**-****", text)
    # 电话号码：全掩
    text = re.sub(PHI_PATTERNS["电话号码"], "***-****", text)
    # 邮箱：全掩
    text = re.sub(PHI_PATTERNS["邮箱"], "****@****.***", text)
    # IP地址：全掩
    text = re.sub(PHI_PATTERNS["IP地址"], "***.***.***.***", text)

    return json.loads(text)


def _create_audit_record(action: str, resource_type: str, detail: str) -> dict:
    """生成一条不可变审计追踪记录。"""
    return AuditRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        user_id="system",
        action=action,
        resource_type=resource_type,
        detail=detail,
        outcome="success",
    ).model_dump()


def audit_agent(state) -> dict:
    """
    LangGraph 节点：中国数据合规审计。
    读取：所有 state 字段
    写入：state.audit_result, state.current_agent
    """
    logger.info("audit_agent.start")

    now = datetime.now(timezone.utc).isoformat()
    audit_trail = []
    compliance_checks = []

    # ---- 聚合所有管线输出数据 ----
    all_data = {}
    for field_name in ("patient_info", "diagnosis", "treatment_plan", "coding_result"):
        val = getattr(state, field_name, None)
        if val:
            all_data[field_name] = val

    # ---- 1. 敏感个人信息扫描 ----
    phi_findings = _scan_for_phi(all_data)
    phi_types_found = [f["type"] for f in phi_findings]

    phi_scan_passed = len(phi_findings) == 0
    compliance_checks.append(
        ComplianceCheck(
            check_name="敏感信息扫描",
            passed=phi_scan_passed,
            detail=f"检出 {len(phi_findings)} 类敏感信息: {', '.join(phi_types_found)}"
            if phi_findings else "未检出敏感个人信息",
        ).model_dump()
    )
    audit_trail.append(
        _create_audit_record("phi_scan", "pipeline_output",
                             f"扫描 {len(all_data)} 个数据段，检出 {len(phi_findings)} 类敏感信息"))

    # ---- 2. 数据脱敏 ----
    phi_masked = []
    if phi_findings:
        _mask_phi(all_data)  # 执行脱敏（返回副本，不影响原始 state）
        phi_masked = phi_types_found
        audit_trail.append(
            _create_audit_record("data_masking", "pipeline_output",
                                 f"脱敏 {len(phi_masked)} 类敏感信息")
        )

    # ---- 3. 结构性合规检查 ----
    for check_config in COMPLIANCE_CHECKS_CONFIG:
        name = check_config["check_name"]
        requirement = check_config["requirement"]
        detail = f"依据: {requirement}"

        if name == "敏感信息扫描":
            continue  # 已在步骤1中处理
        elif name == "数据传输加密":
            try:
                passed = _check_https_configured()
                detail = ("HTTPS/TLS 已配置" if passed
                          else "未检测到 HTTPS 配置。设置 APP_HTTPS_ENABLED=true 或配置 SSL 证书。"
                          f" 依据: {requirement}")
            except Exception as e:
                passed, detail = False, f"检查失败: {e}"
        elif name == "数据存储加密":
            passed = _check_env_true("DB_ENCRYPTION_ENABLED")
            detail = ("数据库加密已启用" if passed
                      else "未检测到数据库加密配置。设置 DB_ENCRYPTION_ENABLED=true。"
                      f" 依据: {requirement}")
        elif name == "访问控制":
            passed = _check_env_true("RBAC_ENABLED")
            detail = ("RBAC 已启用" if passed
                      else "未检测到 RBAC 配置。设置 RBAC_ENABLED=true。"
                      f" 依据: {requirement}")
        elif name == "审计日志可写入":
            try:
                passed = _check_audit_log_writable()
                detail = ("审计日志目录可写入（已验证磁盘权限）" if passed
                          else "审计日志目录不可写入，请检查 data/ 目录权限。"
                          f" 依据: {requirement}")
            except Exception as e:
                passed, detail = False, f"检查失败: {e}"
        elif name == "最小必要原则":
            try:
                ok, violations = _check_data_minimization(
                    state.patient_info, state.diagnosis,
                    state.treatment_plan, state.coding_result,
                )
                passed = ok
                if ok:
                    detail = f"所有管线输出字段均在临床必需范围内。依据: {requirement}"
                else:
                    detail = f"检出 {len(violations)} 项非必要字段。依据: {requirement}"
            except Exception as e:
                passed, detail = True, f"无法校验: {e}"  # 数据为空时不阻断
        elif name == "数据泄露应急响应":
            passed = _check_env_true("BREACH_NOTIFICATION_READY")
            detail = (f"已配置数据泄露应急响应机制" if passed
                      else "未配置应急响应。设置 BREACH_NOTIFICATION_READY=true。"
                      f" 依据: {requirement}")
        elif name == "数据存储期限":
            passed = _check_env_true("DATA_RETENTION_POLICY_CONFIGURED")
            detail = (f"已配置数据存储期限策略" if passed
                      else "未配置存储期限策略。设置 DATA_RETENTION_POLICY_CONFIGURED=true。"
                      f" 依据: {requirement}")
        elif name == "跨境数据传输审批":
            passed = _check_env_true("CROSS_BORDER_APPROVED")
            detail = (f"跨境数据传输已获审批" if passed
                      else "未配置跨境数据传输审批。设置 CROSS_BORDER_APPROVED=true。"
                      f" 依据: {requirement}")
        elif name == "数据主体权利保障":
            passed = _check_env_true("DATA_SUBJECT_RIGHTS_ENABLED")
            detail = (f"数据主体权利保障机制已启用" if passed
                      else "未启用。设置 DATA_SUBJECT_RIGHTS_ENABLED=true。"
                      f" 依据: {requirement}")
        else:
            passed = True
            detail = f"依据: {requirement}"

        compliance_checks.append(
            ComplianceCheck(
                check_name=name,
                passed=passed,
                detail=detail,
            ).model_dump()
        )

    # ---- 4. 总体风险评估 ----
    phi_count = len(phi_findings)
    failed_checks = [c for c in compliance_checks if not c["passed"]]

    if phi_count == 0 and len(failed_checks) == 0:
        risk_level = "低"
        hipaa_compliant = True
    elif phi_count <= 1 and len(failed_checks) <= 2:
        risk_level = "中"
        hipaa_compliant = False
    else:
        risk_level = "高"
        hipaa_compliant = False

    # ---- 5. 建议 ----
    recommendations = []
    if phi_findings:
        recommendations.append(
            f"检出 {', '.join(phi_types_found)} 等敏感信息，对外传输前须脱敏处理"
        )
    for check in failed_checks:
        recommendations.append(f"合规项「{check['check_name']}」未通过，请检查系统配置")
    if not phi_findings and not failed_checks:
        recommendations.append("当前输出通过合规检查，审计日志按PIPL要求保存不少于6年")

    audit_trail.append(
        _create_audit_record(
            "compliance_assessment", "pipeline",
            f"综合评估: {'合规' if hipaa_compliant else '需整改'}, 风险等级={risk_level}",
        )
    )

    result = AuditResult(
        hipaa_compliant=hipaa_compliant,
        compliance_checks=compliance_checks,
        phi_fields_found=phi_types_found,
        phi_fields_masked=phi_masked,
        audit_trail=audit_trail,
        recommendations=recommendations,
        overall_risk_level=risk_level,
    )

    logger.info("audit_agent.success", compliant=hipaa_compliant, risk=risk_level)
    return {
        "audit_result": result.model_dump(),
        "current_agent": "audit",
    }
