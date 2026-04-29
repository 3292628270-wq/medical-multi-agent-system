"""CMeIE 知识图谱导入脚本。

解析 CMeIE 训练/验证/测试数据，提取疾病→症状/药物/检查等三元组，
构建 SQLite 知识图谱数据库。

用法：
    python scripts/import_cmeie_kg.py data/CMeIE/ data/cmeie_kg.db
"""

import sys
import json
import sqlite3
from pathlib import Path
from collections import defaultdict


# 我们关心的谓词（用于临床辅助决策）
TARGET_PREDICATES = {
    "临床表现": "symptom",           # 疾病→症状
    "药物治疗": "drug",              # 疾病→药物
    "实验室检查": "lab_test",        # 疾病→检查
    "影像学检查": "imaging",         # 疾病→影像检查
    "鉴别诊断": "diff_diagnosis",    # 疾病→鉴别疾病
    "并发症": "complication",        # 疾病→并发症
    "手术治疗": "surgery",           # 疾病→手术
    "辅助治疗": "auxiliary_treatment",  # 疾病→辅助治疗
    "相关（导致）": "causes",        # 疾病→导致疾病
    "相关（症状）": "related_symptom",  # 疾病→相关疾病(症状层面)
    "辅助检查": "auxiliary_test",    # 疾病→辅助检查
    "病理分型": "pathology_type",    # 疾病→病理分型
}


def parse_file(filepath: Path) -> list[dict]:
    """解析一个 CMeIE JSONL 文件，返回三元组列表。"""
    triples = []
    if not filepath.exists():
        print(f"  警告: 文件不存在 {filepath}")
        return triples

    with open(filepath, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            for spo in rec.get("spo_list", []):
                s = spo.get("subject", "")
                st = spo.get("subject_type", "")
                p = spo.get("predicate", "")
                obj = spo.get("object", {})
                o = obj.get("@value", "")
                ot = obj.get("@value", "") if isinstance(
                    spo.get("object_type"), dict
                ) else spo.get("object_type", "")

                if s and p and o and p in TARGET_PREDICATES:
                    triples.append({
                        "subject": s.strip(),
                        "subject_type": st,
                        "predicate": p,
                        "object": o.strip(),
                        "object_type": ot,
                        "relation_type": TARGET_PREDICATES[p],
                    })
    return triples


def build_kg(data_dir: str, db_path: str):
    """构建知识图谱数据库。"""
    data_path = Path(data_dir)
    all_triples = []

    for filename in ["CMeIE_train.jsonl", "CMeIE_dev.jsonl", "CMeIE_test.jsonl"]:
        fp = data_path / filename
        triples = parse_file(fp)
        print(f"  {filename}: {len(triples)} 条有效三元组")
        all_triples.extend(triples)

    print(f"  总计: {len(all_triples)} 条三元组")

    # ---- 统计 ----
    diseases = set()
    symptoms = set()
    drugs = set()
    by_disease = defaultdict(lambda: defaultdict(list))

    for t in all_triples:
        diseases.add(t["subject"])
        rel = t["relation_type"]
        by_disease[t["subject"]][rel].append(t["object"])
        if rel == "symptom":
            symptoms.add(t["object"])
        elif rel == "drug":
            drugs.add(t["object"])

    print(f"  疾病: {len(diseases)}")
    print(f"  症状: {len(symptoms)}")
    print(f"  药物: {len(drugs)}")

    # ---- 聚合（合并同义疾病，去重） ----
    disease_kg = {}
    for disease, rels in by_disease.items():
        merged = {}
        for rel, values in rels.items():
            # 去重 + 按出现次数降序排列
            counts = {}
            for v in values:
                counts[v] = counts.get(v, 0) + 1
            merged[rel] = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        disease_kg[disease] = merged

    # 症状→疾病倒排索引
    symptom_to_diseases = defaultdict(lambda: defaultdict(int))
    for disease, rels in disease_kg.items():
        for symptom_name, count in rels.get("symptom", []):
            symptom_to_diseases[symptom_name][disease] += count

    # ---- 写入 SQLite ----
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")

    # 疾病表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS diseases (
            name TEXT PRIMARY KEY,
            symptom_count INTEGER DEFAULT 0,
            drug_count INTEGER DEFAULT 0,
            lab_count INTEGER DEFAULT 0
        )
    """)

    # 关系表（三元组）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS relations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT NOT NULL,
            relation_type TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            frequency INTEGER DEFAULT 1
        )
    """)

    # 症状→疾病倒排索引
    conn.execute("""
        CREATE TABLE IF NOT EXISTS symptom_disease (
            symptom TEXT NOT NULL,
            disease TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            PRIMARY KEY (symptom, disease)
        )
    """)

    conn.execute("DELETE FROM diseases")
    conn.execute("DELETE FROM relations")
    conn.execute("DELETE FROM symptom_disease")

    # 插入关系
    rel_rows = []
    for disease, rels in disease_kg.items():
        symptom_c = sum(c for _, c in rels.get("symptom", []))
        drug_c = sum(c for _, c in rels.get("drug", []))
        lab_c = sum(c for _, c in rels.get("lab_test", []))
        conn.execute(
            "INSERT OR REPLACE INTO diseases VALUES(?,?,?,?)",
            (disease, symptom_c, drug_c, lab_c),
        )

        for rel_type, values in rels.items():
            pred = [k for k, v in TARGET_PREDICATES.items() if v == rel_type][0]
            for obj, freq in values:
                rel_rows.append((disease, rel_type, pred, obj, freq))

    conn.executemany(
        "INSERT INTO relations(subject, relation_type, predicate, object, frequency) VALUES(?,?,?,?,?)",
        rel_rows,
    )

    # 插入症状倒排
    sd_rows = [
        (symptom, disease, freq)
        for symptom, diseases_dict in symptom_to_diseases.items()
        for disease, freq in diseases_dict.items()
    ]
    conn.executemany(
        "INSERT INTO symptom_disease(symptom, disease, frequency) VALUES(?,?,?)",
        sd_rows,
    )

    # 建索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_subject ON relations(subject)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_type ON relations(relation_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rel_object ON relations(object)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sd_symptom ON symptom_disease(symptom)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sd_disease ON symptom_disease(disease)")

    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    sd_count = conn.execute("SELECT COUNT(*) FROM symptom_disease").fetchone()[0]
    dis_count = conn.execute("SELECT COUNT(*) FROM diseases").fetchone()[0]

    print(f"\n知识图谱已构建: {db_path}")
    print(f"  疾病节点: {dis_count}")
    print(f"  关系三元组: {row_count}")
    print(f"  症状倒排索引: {sd_count}")

    # 展示样例
    print("\n样例查询（肺炎）：")
    for row in conn.execute(
        "SELECT relation_type, object, frequency FROM relations WHERE subject='肺炎' ORDER BY frequency DESC LIMIT 10"
    ).fetchall():
        print(f"  {row[0]:12s} → {row[1][:40]:40s} (×{row[2]})")

    conn.close()
    return row_count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python scripts/import_cmeie_kg.py <CMeIE数据目录> <输出SQLite路径>")
        sys.exit(1)

    build_kg(sys.argv[1], sys.argv[2])
