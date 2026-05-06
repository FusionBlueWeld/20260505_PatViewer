import json
import shutil
from pathlib import Path
import re


def sanitize_filename(name: str) -> str:
    """ファイル名に使えない文字を除去"""
    return re.sub(r'[\\/:*?"<>|#^\[\]]', '_', name)


def generate_obsidian_mapping():
    base_dir = Path(__file__).resolve().parent.parent
    cluster_path = base_dir / "output" / "cluster" / "kw_cluster.json"
    patents_root = base_dir / "output" / "patents"

    obsidian_root = base_dir / "output" / "obsidian"

    # -------------------------------
    # 初期化
    # -------------------------------
    if obsidian_root.exists():
        shutil.rmtree(obsidian_root)

    cluster_dir = obsidian_root / "cluster"
    keyword_dir = obsidian_root / "keyword"
    patent_dir = obsidian_root / "patents"

    cluster_dir.mkdir(parents=True)
    keyword_dir.mkdir()
    patent_dir.mkdir()

    # -------------------------------
    # データ読み込み
    # -------------------------------
    with open(cluster_path, "r", encoding="utf-8") as f:
        clusters = json.load(f)

    keyword_map = {}
    patent_map = {}

    # -------------------------------
    # cluster → keyword
    # -------------------------------
    for cluster in clusters:
        cluster_name_raw = sanitize_filename(cluster["cluster_name"])
        cluster_name = f"cl_{cluster_name_raw}"
        cluster_file = cluster_dir / f"{cluster_name}.md"

        lines = []

        for item in cluster["items"]:
            kw_raw = sanitize_filename(item["keyword"])
            kw = f"kw_{kw_raw}"

            desc = item["description"].replace("\n", " ")

            lines.append(f"[[{kw}]]")
            lines.append(desc)
            lines.append("")

            # keyword集約
            if kw not in keyword_map:
                keyword_map[kw] = {
                    "description": desc,
                    "clusters": set(),
                    "patents": set(),
                    "category": item["category"]
                }

            keyword_map[kw]["clusters"].add(cluster_name)
            keyword_map[kw]["patents"].add(item["patent_name"])

            # patent集約
            p_raw = sanitize_filename(item["patent_name"])
            p = f"pt_{p_raw}"

            if p not in patent_map:
                patent_map[p] = {
                    "keywords": set(),
                    "category": item["category"]
                }
            patent_map[p]["keywords"].add(kw)

        cluster_file.write_text("\n".join(lines), encoding="utf-8")

    # -------------------------------
    # keyword md生成
    # -------------------------------
    for kw, data in keyword_map.items():
        kw_file = keyword_dir / f"{kw}.md"

        lines = []

        # description
        lines.append(data["description"])
        lines.append("")

        # clusterリンク
        for c in data["clusters"]:
            lines.append(f"[[{c}]]")
        lines.append("")

        # patentリンク
        for p_raw in data["patents"]:
            p = f"pt_{sanitize_filename(p_raw)}"
            lines.append(f"[[{p}]]")

        lines.append("")
        lines.append(f"#{data['category']}")

        kw_file.write_text("\n".join(lines), encoding="utf-8")

    # -------------------------------
    # patent md生成
    # -------------------------------
    for p, data in patent_map.items():
        p_file = patent_dir / f"{p}.md"

        lines = []

        # keywordリンク
        for kw in data["keywords"]:
            lines.append(f"[[{kw}]]")

        lines.append("")
        lines.append(f"#{data['category']}")

        p_file.write_text("\n".join(lines), encoding="utf-8")

    print("[Done] Obsidian用マッピング生成完了")