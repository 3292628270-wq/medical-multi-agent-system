"""ICD-10-CM XML 解析导入脚本。

将 CMS 官方 ICD-10-CM XML 文件解析为 SQLite 数据库，
供 icd10_service 查询使用。

用法：
    python scripts/import_icd10.py data/icd10cm-April-1-2026-XML/icd10c-tabular-April-1-2026.xml data/icd10.db
"""

import sys
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_diag(element: ET.Element, codes: list, chapter_name: str = "") -> str | None:
    """
    递归解析 <diag> 元素树。
    只收集叶子节点（没有子 <diag> 的编码），因为这些才是可计费编码。
    返回分类名称（用于非叶子节点）。
    """
    name_el = element.find("name")
    desc_el = element.find("desc")
    child_diags = element.findall("diag")

    code = name_el.text.strip() if name_el is not None and name_el.text else ""
    desc = desc_el.text.strip() if desc_el is not None and desc_el.text else ""

    if not child_diags and code and desc:
        # 叶子节点 → 可计费编码
        codes.append((code, desc, chapter_name))
        return None
    elif child_diags:
        # 非叶子节点 → 递归处理子节点
        for child in child_diags:
            parse_diag(child, codes, chapter_name)
        return desc
    return None


def import_xml_to_sqlite(xml_path: str, db_path: str):
    """解析 ICD-10-CM XML 文件，导入 SQLite。"""
    print(f"解析 XML: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    all_codes = []
    chapter_count = 0

    for chapter in root.findall("chapter"):
        chapter_desc = chapter.findtext("desc", "").strip()
        if not chapter_desc:
            continue
        chapter_count += 1

        # 编码在 section → diag 层级下
        for section in chapter.findall("section"):
            for diag in section.findall("diag"):
                parse_diag(diag, all_codes, chapter_desc)

    print(f"解析完成: {chapter_count} 个章节, {len(all_codes)} 条可计费编码")

    # 写入 SQLite
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS icd10 (
            code TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            category TEXT NOT NULL
        )
    """)
    conn.execute("DELETE FROM icd10")  # 清空旧数据
    conn.executemany(
        "INSERT INTO icd10 (code, description, category) VALUES (?, ?, ?)",
        all_codes,
    )
    conn.commit()

    # 建索引
    conn.execute("CREATE INDEX IF NOT EXISTS idx_icd10_category ON icd10(category)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_icd10_desc ON icd10(description)")
    conn.commit()

    row_count = conn.execute("SELECT COUNT(*) FROM icd10").fetchone()[0]
    conn.close()

    print(f"导入 SQLite 完成: {row_count} 条记录 → {db_path}")
    return row_count


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python scripts/import_icd10.py <XML文件路径> <输出SQLite路径>")
        sys.exit(1)

    import_xml_to_sqlite(sys.argv[1], sys.argv[2])
