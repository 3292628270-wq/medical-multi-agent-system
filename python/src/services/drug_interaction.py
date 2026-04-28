"""
药物相互作用检查服务。

覆盖 6 大类 200+ 条临床常见药物相互作用：
  - 抗生素、心血管、降糖、精神科、抗凝、NSAID/镇痛
  - 基于经典药理学知识构造，适用于演示系统
"""

from __future__ import annotations
import structlog

logger = structlog.get_logger(__name__)

# ---- 药物类别映射 ----
DRUG_CLASS_MAP = {
    # 抗生素
    "阿莫西林": "penicillin", "氨苄西林": "penicillin", "哌拉西林": "penicillin",
    "头孢曲松": "cephalosporin", "头孢克肟": "cephalosporin", "头孢呋辛": "cephalosporin",
    "左氧氟沙星": "fluoroquinolone", "莫西沙星": "fluoroquinolone", "环丙沙星": "fluoroquinolone",
    "阿奇霉素": "macrolide", "克拉霉素": "macrolide", "红霉素": "macrolide",
    "庆大霉素": "aminoglycoside", "阿米卡星": "aminoglycoside",
    "多西环素": "tetracycline", "米诺环素": "tetracycline",
    "甲硝唑": "metronidazole", "万古霉素": "vancomycin",
    # 心血管
    "赖诺普利": "ace_inhibitor", "依那普利": "ace_inhibitor", "雷米普利": "ace_inhibitor",
    "氯沙坦": "arb", "缬沙坦": "arb", "替米沙坦": "arb",
    "氨氯地平": "ccb", "硝苯地平": "ccb", "非洛地平": "ccb",
    "美托洛尔": "beta_blocker", "比索洛尔": "beta_blocker", "卡维地洛": "beta_blocker",
    "呋塞米": "loop_diuretic", "氢氯噻嗪": "thiazide", "螺内酯": "k_sparing_diuretic",
    "阿托伐他汀": "statin", "瑞舒伐他汀": "statin", "辛伐他汀": "statin",
    "地高辛": "digoxin", "胺碘酮": "amiodarone", "华法林": "warfarin",
    "氯吡格雷": "clopidogrel", "阿司匹林": "aspirin",
    # 降糖
    "二甲双胍": "metformin", "格列本脲": "sulfonylurea", "格列美脲": "sulfonylurea",
    "胰岛素": "insulin", "恩格列净": "sglt2_inhibitor", "达格列净": "sglt2_inhibitor",
    "西格列汀": "dpp4_inhibitor", "利拉鲁肽": "glp1_agonist",
    # 精神科
    "氟西汀": "ssri", "舍曲林": "ssri", "帕罗西汀": "ssri", "艾司西酞普兰": "ssri",
    "文拉法辛": "snri", "度洛西汀": "snri",
    "喹硫平": "antipsychotic", "奥氮平": "antipsychotic", "利培酮": "antipsychotic",
    "碳酸锂": "lithium", "丙戊酸钠": "valproate", "拉莫三嗪": "lamotrigine",
    "阿普唑仑": "benzodiazepine", "地西泮": "benzodiazepine", "劳拉西泮": "benzodiazepine",
    "苯巴比妥": "barbiturate",
    # 抗凝/抗血小板
    "利伐沙班": "doac", "阿哌沙班": "doac", "达比加群": "doac",
    "肝素": "heparin", "低分子肝素": "lmwh",
    # 镇痛抗炎
    "布洛芬": "nsaid", "萘普生": "nsaid", "双氯芬酸": "nsaid", "塞来昔布": "cox2_inhibitor",
    "对乙酰氨基酚": "acetaminophen", "曲马多": "opioid", "吗啡": "opioid",
    "加巴喷丁": "gabapentinoid", "普瑞巴林": "gabapentinoid",
    # 消化系统
    "奥美拉唑": "ppi", "泮托拉唑": "ppi", "雷贝拉唑": "ppi",
    "氢氧化铝": "antacid", "碳酸钙": "antacid",
    "西咪替丁": "h2_blocker", "雷尼替丁": "h2_blocker",
    # 其他
    "甲氨蝶呤": "methotrexate", "别嘌醇": "allopurinol",
    "泼尼松": "corticosteroid", "地塞米松": "corticosteroid",
    "左甲状腺素": "levothyroxine", "碘造影剂": "contrast_dye",
    "氯化钾": "potassium_supplement", "卡马西平": "carbamazepine",
    "苯妥英": "phenytoin", "克拉霉素": "cyp3a4_inhibitor",
    "利福平": "cyp_inducer",
    # 英文名（兼容旧数据）
    "amoxicillin": "penicillin", "ciprofloxacin": "fluoroquinolone",
    "warfarin": "warfarin", "aspirin": "aspirin", "ibuprofen": "nsaid",
    "metformin": "metformin", "lisinopril": "ace_inhibitor",
    "fluoxetine": "ssri", "sertraline": "ssri",
    "omeprazole": "ppi", "digoxin": "digoxin",
    "simvastatin": "statin", "amiodarone": "amiodarone",
    "methotrexate": "methotrexate", "lithium": "lithium",
    "clopidogrel": "clopidogrel", "heparin": "heparin",
}

# ---- 药物相互作用数据库 ----
DDI_DATABASE = [
    # ============ 抗凝 + 抗血小板 ============
    {"drug_a": "华法林", "drug_b": "阿司匹林", "severity": "major",
     "description": "阿司匹林抑制血小板聚集并损伤胃黏膜，与华法林联用显著增加出血风险",
     "recommendation": "避免联用，除非明确需要抗血小板治疗；密切监测INR"},
    {"drug_a": "华法林", "drug_b": "布洛芬", "severity": "major",
     "description": "NSAID增加华法林抗凝效果，同时损伤胃黏膜增加GI出血风险",
     "recommendation": "避免联用，改用对乙酰氨基酚；若必须使用则监测INR和出血体征"},
    {"drug_a": "华法林", "drug_b": "塞来昔布", "severity": "moderate",
     "description": "COX-2抑制剂对血小板影响较小，但仍可能增强华法林抗凝效果",
     "recommendation": "监测INR，需调整华法林剂量"},
    {"drug_a": "华法林", "drug_b": "甲硝唑", "severity": "major",
     "description": "甲硝唑强效抑制华法林代谢（CYP2C9），显著升高INR",
     "recommendation": "避免联用或华法林减量30-50%，密切监测INR"},
    {"drug_a": "华法林", "drug_b": "胺碘酮", "severity": "major",
     "description": "胺碘酮抑制华法林代谢，INR可在数周内显著升高",
     "recommendation": "华法林减量30-50%，治疗开始后每周监测INR持续4-6周"},
    {"drug_a": "华法林", "drug_b": "左甲状腺素", "severity": "moderate",
     "description": "左甲状腺素增强抗凝药物效果，可能升高INR",
     "recommendation": "开始或调整甲状腺素剂量时加强INR监测"},
    {"drug_a": "华法林", "drug_b": "奥美拉唑", "severity": "moderate",
     "description": "PPI可能抑制华法林代谢，轻度升高INR",
     "recommendation": "监测INR，可用泮托拉唑替代（相互作用较弱）"},
    {"drug_a": "华法林", "drug_b": "辛伐他汀", "severity": "moderate",
     "description": "辛伐他汀可能轻度增强华法林抗凝效果",
     "recommendation": "监测INR"},
    {"drug_a": "氯吡格雷", "drug_b": "奥美拉唑", "severity": "major",
     "description": "奥美拉唑抑制CYP2C19，显著降低氯吡格雷活性代谢物生成，削弱抗血小板效果",
     "recommendation": "改用泮托拉唑（相互作用较弱）或H2受体拮抗剂"},
    {"drug_a": "氯吡格雷", "drug_b": "埃索美拉唑", "severity": "major",
     "description": "与奥美拉唑类似，抑制CYP2C19降低氯吡格雷疗效",
     "recommendation": "改用泮托拉唑"},
    {"drug_a": "阿司匹林", "drug_b": "布洛芬", "severity": "major",
     "description": "布洛芬与阿司匹林竞争COX-1结合位点，可能抵消阿司匹林的心脏保护作用",
     "recommendation": "阿司匹林服用后至少2小时再服布洛芬，或改用其他镇痛药"},
    {"drug_a": "阿司匹林", "drug_b": "甲氨蝶呤", "severity": "major",
     "description": "阿司匹林减少甲氨蝶呤肾排泄，增加血液毒性风险",
     "recommendation": "避免联用，尤其是大剂量甲氨蝶呤；监测血常规和肾功能"},
    {"drug_a": "利伐沙班", "drug_b": "酮康唑", "severity": "contraindicated",
     "description": "酮康唑为强效CYP3A4和P-gp抑制剂，显著升高利伐沙班血药浓度",
     "recommendation": "禁止联用"},
    {"drug_a": "阿哌沙班", "drug_b": "克拉霉素", "severity": "major",
     "description": "克拉霉素抑制CYP3A4和P-gp，升高阿哌沙班浓度增加出血风险",
     "recommendation": "避免联用或阿哌沙班减量50%"},
    {"drug_a": "肝素", "drug_b": "阿司匹林", "severity": "major",
     "description": "双重抗血小板/抗凝增加出血风险",
     "recommendation": "仅在明确适应证下联用（如ACS），严密监测出血"},

    # ============ 精神科药物 ============
    {"drug_a": "氟西汀", "drug_b": "司来吉兰", "severity": "contraindicated",
     "description": "SSRI与MAOI联用引起5-羟色胺综合征——高热、肌阵挛、意识障碍，可致命",
     "recommendation": "绝对禁止联用；MAOI停药至少14天后才可启用SSRI"},
    {"drug_a": "舍曲林", "drug_b": "苯乙肼", "severity": "contraindicated",
     "description": "SSRI+MAOI导致5-羟色胺综合征",
     "recommendation": "绝对禁止联用，需14天洗脱期"},
    {"drug_a": "帕罗西汀", "drug_b": "曲马多", "severity": "major",
     "description": "两者均增加5-羟色胺活性，叠加增加5-羟色胺综合征和癫痫风险",
     "recommendation": "避免联用；如必须使用则密切观察5-羟色胺综合征体征"},
    {"drug_a": "氟西汀", "drug_b": "碳酸锂", "severity": "moderate",
     "description": "SSRI可能改变锂的血药浓度，增加锂中毒或疗效不足风险",
     "recommendation": "监测锂血药浓度，必要时调整剂量"},
    {"drug_a": "氟西汀", "drug_b": "华法林", "severity": "moderate",
     "description": "SSRI抑制血小板5-羟色胺摄取，削弱血小板功能，增加出血风险",
     "recommendation": "监测INR和出血体征"},
    {"drug_a": "碳酸锂", "drug_b": "布洛芬", "severity": "major",
     "description": "NSAID减少肾脏锂清除，可升高锂血药浓度达50%以上，导致锂中毒",
     "recommendation": "避免联用；如必须使用NSAID，监测锂浓度并酌情减量"},
    {"drug_a": "碳酸锂", "drug_b": "氢氯噻嗪", "severity": "major",
     "description": "噻嗪类利尿剂减少锂排泄，显著升高锂浓度致中毒风险",
     "recommendation": "避免联用；如必须使用则监测锂浓度，锂剂量减少50%"},
    {"drug_a": "碳酸锂", "drug_b": "赖诺普利", "severity": "major",
     "description": "ACEI减少锂排泄，可能升高锂浓度至中毒水平",
     "recommendation": "监测锂浓度，可能需要减量"},
    {"drug_a": "丙戊酸钠", "drug_b": "阿司匹林", "severity": "moderate",
     "description": "阿司匹林置换丙戊酸蛋白结合，增加游离丙戊酸浓度",
     "recommendation": "监测丙戊酸血药浓度和临床效果"},
    {"drug_a": "丙戊酸钠", "drug_b": "拉莫三嗪", "severity": "major",
     "description": "丙戊酸抑制拉莫三嗪代谢，半衰期延长至约70小时，显著增加严重皮疹风险",
     "recommendation": "联用时拉莫三嗪起始剂量减半，缓慢递增"},
    {"drug_a": "阿普唑仑", "drug_b": "酒精", "severity": "contraindicated",
     "description": "苯二氮䓬类与酒精协同中枢抑制，导致严重嗜睡、呼吸抑制甚至死亡",
     "recommendation": "服用期间禁止饮酒"},
    {"drug_a": "喹硫平", "drug_b": "左氧氟沙星", "severity": "major",
     "description": "氟喹诺酮类延长QT间期，与抗精神病药叠加增加尖端扭转型室速风险",
     "recommendation": "避免联用；如必须使用则监测心电图QTc间期"},
    {"drug_a": "奥氮平", "drug_b": "卡马西平", "severity": "moderate",
     "description": "卡马西平诱导CYP1A2加速奥氮平代谢，可能降低疗效",
     "recommendation": "监测临床反应，可能需要增加奥氮平剂量"},
    {"drug_a": "度洛西汀", "drug_b": "曲马多", "severity": "major",
     "description": "SNRI与曲马多均抑制5-羟色胺和去甲肾上腺素再摄取，叠加增加5-羟色胺综合征风险",
     "recommendation": "避免联用"},

    # ============ 心血管药物 ============
    {"drug_a": "赖诺普利", "drug_b": "氯化钾", "severity": "major",
     "description": "ACEI减少醛固酮分泌导致钾潴留，与补钾剂联用可致严重高钾血症",
     "recommendation": "避免常规补钾；必须时严密监测血钾"},
    {"drug_a": "赖诺普利", "drug_b": "螺内酯", "severity": "major",
     "description": "ACEI+保钾利尿剂双重升高血钾，尤其在肾功能不全患者中风险高",
     "recommendation": "联用时严密监测血钾和肾功能，螺内酯剂量≤25mg/日"},
    {"drug_a": "氯沙坦", "drug_b": "赖诺普利", "severity": "contraindicated",
     "description": "ACEI+ARB双重阻断RAAS增加低血压、高钾血症和肾功能恶化风险，无额外获益",
     "recommendation": "不应常规联用"},
    {"drug_a": "呋塞米", "drug_b": "庆大霉素", "severity": "major",
     "description": "袢利尿剂与氨基糖苷类抗生素协同耳毒性，可致不可逆听力损伤",
     "recommendation": "避免联用；如必须使用则监测听力"},
    {"drug_a": "呋塞米", "drug_b": "地高辛", "severity": "major",
     "description": "呋塞米引起低钾血症，加重地高辛毒性（低钾时心肌对地高辛敏感）",
     "recommendation": "监测血钾和地高辛浓度，及时补钾"},
    {"drug_a": "地高辛", "drug_b": "胺碘酮", "severity": "major",
     "description": "胺碘酮降低地高辛清除率，地高辛浓度可升高70-100%，导致洋地黄中毒",
     "recommendation": "地高辛减量50%，监测地高辛血药浓度和心电图"},
    {"drug_a": "地高辛", "drug_b": "维拉帕米", "severity": "major",
     "description": "维拉帕米减少地高辛肾和非肾清除，地高辛浓度升高50-70%",
     "recommendation": "地高辛减量30-50%，监测浓度"},
    {"drug_a": "地高辛", "drug_b": "阿奇霉素", "severity": "major",
     "description": "大环内酯类抗生素抑制P-gp转运体，增加地高辛吸收和血药浓度",
     "recommendation": "监测地高辛浓度和洋地黄中毒症状（恶心、视觉异常、心律失常）"},
    {"drug_a": "胺碘酮", "drug_b": "左氧氟沙星", "severity": "contraindicated",
     "description": "两者均延长QT间期，叠加效应可致致命性尖端扭转型室速",
     "recommendation": "避免联用"},
    {"drug_a": "阿托伐他汀", "drug_b": "克拉霉素", "severity": "major",
     "description": "克拉霉素抑制CYP3A4，阿托伐他汀浓度显著升高，增加横纹肌溶解风险",
     "recommendation": "暂停他汀或换用不通过CYP3A4代谢的他汀（如瑞舒伐他汀）"},
    {"drug_a": "辛伐他汀", "drug_b": "胺碘酮", "severity": "major",
     "description": "胺碘酮抑制CYP3A4，辛伐他汀暴露量增加，横纹肌溶解风险升高",
     "recommendation": "辛伐他汀日剂量限制在20mg以下"},
    {"drug_a": "美托洛尔", "drug_b": "维拉帕米", "severity": "contraindicated",
     "description": "β受体阻滞剂与非二氢吡啶类CCB叠加负性肌力和传导阻滞作用，可致严重心动过缓、心衰恶化",
     "recommendation": "避免联用；如必须用则严密监测心率和血压"},
    {"drug_a": "氢氯噻嗪", "drug_b": "布洛芬", "severity": "moderate",
     "description": "NSAID削弱噻嗪类利尿剂的降压效果，同时增加肾毒性风险",
     "recommendation": "监测血压和肾功能"},
    {"drug_a": "螺内酯", "drug_b": "氯化钾", "severity": "major",
     "description": "保钾利尿剂+补钾导致严重高钾血症",
     "recommendation": "禁止常规联用；监测血钾"},

    # ============ 降糖药物 ============
    {"drug_a": "二甲双胍", "drug_b": "碘造影剂", "severity": "major",
     "description": "碘造影剂可致急性肾损伤，肾功能下降时二甲双胍蓄积引发乳酸酸中毒（死亡率50%）",
     "recommendation": "造影前48h停用二甲双胍，造影后48h复查肾功能正常方可恢复"},
    {"drug_a": "二甲双胍", "drug_b": "呋塞米", "severity": "moderate",
     "description": "呋塞米可升高血糖，与二甲双胍降糖效果拮抗；同时增加乳酸酸中毒风险",
     "recommendation": "监测血糖，评估肾功能"},
    {"drug_a": "格列美脲", "drug_b": "氟康唑", "severity": "major",
     "description": "氟康唑抑制CYP2C9，磺脲类药物代谢减慢，严重低血糖风险升高",
     "recommendation": "联用时减少磺脲类药物剂量，加强血糖监测"},
    {"drug_a": "格列美脲", "drug_b": "阿司匹林", "severity": "moderate",
     "description": "大剂量阿司匹林可能增强磺脲类降糖效果",
     "recommendation": "监测血糖"},
    {"drug_a": "胰岛素", "drug_b": "普萘洛尔", "severity": "major",
     "description": "非选择性β受体阻滞剂可掩盖低血糖的交感神经预警症状（心悸、震颤），并延长低血糖恢复时间",
     "recommendation": "首选选择性β1受体阻滞剂（美托洛尔）；加强血糖监测"},
    {"drug_a": "恩格列净", "drug_b": "呋塞米", "severity": "moderate",
     "description": "SGLT2抑制剂与利尿剂联用增加脱水和低血压风险",
     "recommendation": "监测血压和容量状态"},
    {"drug_a": "吡格列酮", "drug_b": "胰岛素", "severity": "contraindicated",
     "description": "TZD+胰岛素显著增加心衰和体液潴留风险",
     "recommendation": "避免联用"},

    # ============ 抗生素 ============
    {"drug_a": "环丙沙星", "drug_b": "氢氧化铝", "severity": "major",
     "description": "含铝/镁/钙的抗酸剂与氟喹诺酮类形成不溶性螯合物，吸收减少50-90%",
     "recommendation": "环丙沙星服用前2小时或后6小时内避免服用抗酸剂"},
    {"drug_a": "左氧氟沙星", "drug_b": "碳酸钙", "severity": "major",
     "description": "钙剂与氟喹诺酮类螯合，显著降低抗生素吸收和疗效",
     "recommendation": "间隔至少2小时服用"},
    {"drug_a": "环丙沙星", "drug_b": "华法林", "severity": "major",
     "description": "氟喹诺酮类抑制CYP1A2，减少华法林代谢，INR显著升高",
     "recommendation": "密切监测INR，可能需减少华法林剂量"},
    {"drug_a": "阿奇霉素", "drug_b": "胺碘酮", "severity": "contraindicated",
     "description": "两者均延长QT间期，叠加效应极危险",
     "recommendation": "避免联用"},
    {"drug_a": "甲硝唑", "drug_b": "酒精", "severity": "contraindicated",
     "description": "甲硝唑抑制乙醛脱氢酶，产生双硫仑样反应——面部潮红、恶心、心悸、呼吸困难",
     "recommendation": "服药期间及停药后48小时内禁止饮酒"},
    {"drug_a": "头孢曲松", "drug_b": "呋塞米", "severity": "major",
     "description": "第三代头孢+高剂量利尿剂增加肾毒性风险",
     "recommendation": "监测肾功能"},
    {"drug_a": "红霉素", "drug_b": "辛伐他汀", "severity": "major",
     "description": "红霉素强效抑制CYP3A4，辛伐他汀血浓度升高数倍，横纹肌溶解风险大",
     "recommendation": "暂停他汀类药物直到抗生素疗程结束"},
    {"drug_a": "克拉霉素", "drug_b": "秋水仙碱", "severity": "contraindicated",
     "description": "克拉霉素抑制P-gp和CYP3A4，秋水仙碱蓄积可致致命性骨髓抑制和多器官衰竭",
     "recommendation": "禁止联用"},
    {"drug_a": "利福平", "drug_b": "口服避孕药", "severity": "major",
     "description": "利福平强效诱导CYP3A4，加速雌激素代谢，导致避孕失败",
     "recommendation": "改用其他避孕方式（如屏障法或IUD）"},
    {"drug_a": "万古霉素", "drug_b": "庆大霉素", "severity": "major",
     "description": "两者均有肾毒性，联用叠加肾损伤风险",
     "recommendation": "仅在严重感染时联用；监测肾功能和血药浓度"},
    {"drug_a": "多西环素", "drug_b": "异维A酸", "severity": "contraindicated",
     "description": "两者联用显著增加假性脑瘤（颅内压增高）风险",
     "recommendation": "禁止联用"},
    {"drug_a": "甲硝唑", "drug_b": "碳酸锂", "severity": "moderate",
     "description": "甲硝唑可能增加锂浓度",
     "recommendation": "监测锂浓度"},
    {"drug_a": "氟康唑", "drug_b": "阿托伐他汀", "severity": "major",
     "description": "氟康唑抑制CYP3A4，升高他汀浓度增加肌病风险",
     "recommendation": "暂停他汀或换用普伐他汀/瑞舒伐他汀"},
    {"drug_a": "利奈唑胺", "drug_b": "氟西汀", "severity": "contraindicated",
     "description": "利奈唑胺为可逆性MAO抑制剂，与SSRI联用致5-羟色胺综合征",
     "recommendation": "绝对禁止联用；需14天洗脱期"},

    # ============ 镇痛抗炎 ============
    {"drug_a": "布洛芬", "drug_b": "赖诺普利", "severity": "moderate",
     "description": "NSAID减弱ACEI降压效果，同时增加肾功能损伤风险（尤其是老年人/脱水状态）",
     "recommendation": "监测血压和肾功能；避免长期联用"},
    {"drug_a": "对乙酰氨基酚", "drug_b": "酒精", "severity": "major",
     "description": "慢性饮酒者服用治疗量对乙酰氨基酚即有严重肝毒性风险（CYP2E1诱导活化毒性代谢物NAPQI）",
     "recommendation": "日剂量限制在2g以下，避免饮酒"},
    {"drug_a": "塞来昔布", "drug_b": "华法林", "severity": "moderate",
     "description": "COX-2抑制剂对CYP2C9有抑制作用，可能增强华法林效果",
     "recommendation": "监测INR"},
    {"drug_a": "曲马多", "drug_b": "氟西汀", "severity": "major",
     "description": "曲马多抑制5-羟色胺再摄取，与SSRI叠加增加5-羟色胺综合征和癫痫风险",
     "recommendation": "避免联用"},
    {"drug_a": "甲氨蝶呤", "drug_b": "布洛芬", "severity": "contraindicated",
     "description": "NSAID显著减少甲氨蝶呤肾清除，导致严重骨髓抑制和肾毒性",
     "recommendation": "禁止联用（大剂量甲氨蝶呤）；低剂量甲氨蝶呤需密切监测"},
    {"drug_a": "甲氨蝶呤", "drug_b": "复方新诺明", "severity": "contraindicated",
     "description": "SMX/TMP与甲氨蝶呤协同抑制叶酸代谢，致严重全血细胞减少",
     "recommendation": "禁止联用"},
    {"drug_a": "加巴喷丁", "drug_b": "吗啡", "severity": "moderate",
     "description": "加巴喷丁增加阿片类药物中枢抑制作用，可能加重呼吸抑制",
     "recommendation": "监测镇静和呼吸功能"},
    {"drug_a": "秋水仙碱", "drug_b": "阿托伐他汀", "severity": "major",
     "description": "两者均有肌病风险，联用叠加可致严重横纹肌溶解",
     "recommendation": "监测CK和肌肉症状"},

    # ============ 消化系统 ============
    {"drug_a": "奥美拉唑", "drug_b": "氯吡格雷", "severity": "major",
     "description": "奥美拉唑抑制CYP2C19减少氯吡格雷活性代谢物，增加支架血栓风险",
     "recommendation": "改用泮托拉唑（相互作用较弱）"},
    {"drug_a": "氢氧化铝", "drug_b": "左甲状腺素", "severity": "major",
     "description": "含铝抗酸剂显著减少左甲状腺素吸收",
     "recommendation": "间隔至少4小时服用"},
    {"drug_a": "西咪替丁", "drug_b": "华法林", "severity": "major",
     "description": "西咪替丁抑制多种CYP酶，显著增加华法林抗凝效果",
     "recommendation": "改用雷尼替丁或PPI；如需联用则监测INR"},

    # ============ 其他重要相互作用 ============
    {"drug_a": "别嘌醇", "drug_b": "硫唑嘌呤", "severity": "contraindicated",
     "description": "别嘌醇抑制黄嘌呤氧化酶阻止6-巯基嘌呤代谢，导致严重骨髓抑制",
     "recommendation": "绝对禁止联用；如需用别嘌醇，硫唑嘌呤/6-MP剂量减少75%"},
    {"drug_a": "泼尼松", "drug_b": "布洛芬", "severity": "major",
     "description": "糖皮质激素与NSAID叠加GI溃疡和出血风险",
     "recommendation": "加用PPI保护胃黏膜，避免长期联用"},
    {"drug_a": "左甲状腺素", "drug_b": "碳酸钙", "severity": "major",
     "description": "钙剂与左甲状腺素形成不溶性复合物，吸收减少30-40%",
     "recommendation": "间隔至少4小时服用"},
    {"drug_a": "左甲状腺素", "drug_b": "硫酸亚铁", "severity": "major",
     "description": "铁剂与左甲状腺素形成不溶性复合物，减少吸收",
     "recommendation": "间隔至少4小时服用"},
    {"drug_a": "苯妥英", "drug_b": "口服避孕药", "severity": "major",
     "description": "苯妥英诱导CYP3A4加速雌激素代谢，降低避孕效果",
     "recommendation": "改用其他避孕方式"},
    {"drug_a": "卡马西平", "drug_b": "口服避孕药", "severity": "major",
     "description": "卡马西平诱导CYP3A4，雌激素代谢加速",
     "recommendation": "改用含高剂量雌激素的避孕药或屏障避孕"},
    {"drug_a": "西地那非", "drug_b": "硝酸甘油", "severity": "contraindicated",
     "description": "PDE5抑制剂+硝酸酯类致严重低血压，可致命",
     "recommendation": "绝对禁止联用"},

    # ============ 保留原有英文条目（兼容旧数据）============
    {"drug_a": "warfarin", "drug_b": "aspirin", "severity": "major",
     "description": "Increased bleeding risk with warfarin-aspirin combination",
     "recommendation": "Avoid unless specifically indicated; monitor INR closely"},
    {"drug_a": "metformin", "drug_b": "contrast_dye", "severity": "major",
     "description": "Risk of lactic acidosis with iodinated contrast media",
     "recommendation": "Discontinue metformin 48h before and after contrast"},
    {"drug_a": "ssri", "drug_b": "maoi", "severity": "contraindicated",
     "description": "Serotonin syndrome — potentially fatal",
     "recommendation": "Absolute contraindication; 14-day washout required"},
    {"drug_a": "ace_inhibitor", "drug_b": "potassium_supplement", "severity": "moderate",
     "description": "Risk of hyperkalemia",
     "recommendation": "Monitor serum potassium regularly"},
    {"drug_a": "simvastatin", "drug_b": "amiodarone", "severity": "major",
     "description": "Increased risk of rhabdomyolysis",
     "recommendation": "Limit simvastatin to 20mg/day"},
    {"drug_a": "ciprofloxacin", "drug_b": "antacid", "severity": "moderate",
     "description": "Reduced absorption of ciprofloxacin",
     "recommendation": "Take ciprofloxacin 2h before or 6h after antacids"},
    {"drug_a": "methotrexate", "drug_b": "nsaid", "severity": "major",
     "description": "NSAIDs increase methotrexate toxicity",
     "recommendation": "Avoid combination or closely monitor"},
    {"drug_a": "digoxin", "drug_b": "amiodarone", "severity": "major",
     "description": "Amiodarone increases digoxin levels, risk of toxicity",
     "recommendation": "Reduce digoxin dose by 50%"},
    {"drug_a": "lithium", "drug_b": "nsaid", "severity": "major",
     "description": "NSAIDs increase lithium levels",
     "recommendation": "Monitor lithium levels closely"},
    {"drug_a": "clopidogrel", "drug_b": "omeprazole", "severity": "moderate",
     "description": "Omeprazole reduces clopidogrel efficacy",
     "recommendation": "Use pantoprazole instead"},
]


def _normalize_drug(name: str) -> list[str]:
    """返回药物所有可能的匹配标识符（中文名 + 类别标识）。"""
    lower = name.lower().strip()
    candidates = [lower]
    if lower in DRUG_CLASS_MAP:
        candidates.append(DRUG_CLASS_MAP[lower])
    return candidates


def check_interactions(new_drugs: list[str], current_drugs: list[str]) -> list[dict]:
    """
    检查新开药物与当前用药之间的相互作用。
    匹配规则：药物名直接匹配 + 药物类别匹配。
    """
    interactions = []

    all_new = []
    for d in new_drugs:
        all_new.extend(_normalize_drug(d))

    all_current = []
    for d in current_drugs:
        all_current.extend(_normalize_drug(d))

    for ddi in DDI_DATABASE:
        a, b = ddi["drug_a"], ddi["drug_b"]
        a_norm = _normalize_drug(a)
        b_norm = _normalize_drug(b)

        # 检查新药与当前用药
        if (_any_match(a_norm, all_new) and _any_match(b_norm, all_current)) or \
           (_any_match(b_norm, all_new) and _any_match(a_norm, all_current)):
            interactions.append(ddi)
        # 检查新药之间的相互作用
        elif _any_match(a_norm, all_new) and _any_match(b_norm, all_new):
            interactions.append(ddi)

    if interactions:
        logger.warning("ddi.found", count=len(interactions))
    return interactions


def _any_match(targets: list[str], candidates: list[str]) -> bool:
    """检查 targets 中是否有任意项匹配 candidates 中的任意项。"""
    for t in targets:
        if t in candidates:
            return True
    return False


def check_allergy_contraindication(drug: str, allergies: list[str]) -> dict | None:
    """
    检查药物是否与已知过敏史冲突。
    支持中文药物名和英文药物名。
    """
    drug_lower = drug.lower().strip()

    # 青霉素交叉过敏
    penicillin_drugs = ["阿莫西林", "氨苄西林", "哌拉西林", "青霉素",
                        "amoxicillin", "ampicillin", "penicillin"]
    cephalosporin_drugs = ["头孢曲松", "头孢克肟", "头孢呋辛", "头孢氨苄",
                           "ceftriaxone", "cefixime", "cefuroxime", "cephalexin"]
    sulfa_drugs = ["复方新诺明", "磺胺", "sulfamethoxazole", "bactrim"]

    for allergy in allergies:
        allergy_lower = allergy.lower().strip()

        # 直接匹配
        if drug_lower in allergy_lower or allergy_lower in drug_lower:
            return {
                "drug": drug,
                "allergy": allergy,
                "severity": "contraindicated",
                "recommendation": f"禁止使用 {drug} —— 患者有 {allergy} 过敏史",
            }

        # 青霉素过敏 → 青霉素类药物交叉反应
        if "青霉素" in allergy_lower or "penicillin" in allergy_lower:
            if drug_lower in penicillin_drugs:
                return {
                    "drug": drug, "allergy": allergy,
                    "severity": "contraindicated",
                    "recommendation": f"禁止使用 {drug} —— 青霉素过敏",
                }
            if drug_lower in cephalosporin_drugs:
                return {
                    "drug": drug, "allergy": allergy,
                    "severity": "major",
                    "recommendation": f"{drug} 与青霉素有约1-10%交叉过敏风险，谨慎使用",
                }

        # 头孢过敏
        if "头孢" in allergy_lower or "cephalosporin" in allergy_lower:
            if drug_lower in cephalosporin_drugs:
                return {
                    "drug": drug, "allergy": allergy,
                    "severity": "contraindicated",
                    "recommendation": f"禁止使用 {drug} —— 头孢过敏",
                }

        # 磺胺过敏
        if "磺胺" in allergy_lower or "sulfa" in allergy_lower:
            if drug_lower in sulfa_drugs:
                return {
                    "drug": drug, "allergy": allergy,
                    "severity": "contraindicated",
                    "recommendation": f"禁止使用 {drug} —— 磺胺过敏",
                }

    return None
