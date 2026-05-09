import json
import shutil
from pathlib import Path
import re

def sanitize_filename(name: str) -> str:
    """ファイル名に使えない文字を除去"""
    return re.sub(r'[\\/:*?"<>|#^\[\]]', '_', name)

def generate_obsidian_mapping():
    base_dir = Path(__file__).resolve().parent.parent
    cluster_dir = base_dir / "output" / "cluster"
    obsidian_root = base_dir / "output" / "obsidian"

    if obsidian_root.exists():
        shutil.rmtree(obsidian_root)

    obs_cl_dir = obsidian_root / "cluster"
    keyword_dir = obsidian_root / "keyword"
    patent_dir = obsidian_root / "patents"

    obs_cl_dir.mkdir(parents=True)
    keyword_dir.mkdir()
    patent_dir.mkdir()

    keyword_map = {}
    patent_map = {}

    cluster_files = list(cluster_dir.glob("kw*.json"))
    
    for c_path in cluster_files:
        with open(c_path, "r", encoding="utf-8") as f:
            cluster = json.load(f)

        cluster_name_raw = sanitize_filename(cluster["cluster_name"])
        cluster_name = f"cl_{cluster_name_raw}"
        cluster_file = obs_cl_dir / f"{cluster_name}.md"

        lines = []
        for item in cluster["items"]:
            kw_raw = sanitize_filename(item["keyword"])
            kw = f"kw_{kw_raw}"
            desc = item["description"].replace("\n", " ")

            lines.append(f"[[{kw}]]")
            lines.append(desc)
            lines.append("")

            if kw not in keyword_map:
                keyword_map[kw] = {
                    "description": desc, "clusters": set(), "patents": set(), "category": item["category"]
                }
            keyword_map[kw]["clusters"].add(cluster_name)
            keyword_map[kw]["patents"].add(item["patent_name"])

            p_raw = sanitize_filename(item["patent_name"])
            p = f"pt_{p_raw}"

            if p not in patent_map:
                patent_map[p] = {"keywords": set(), "category": item["category"]}
            patent_map[p]["keywords"].add(kw)

        cluster_file.write_text("\n".join(lines), encoding="utf-8")

    # Keyword MD生成
    for kw, data in keyword_map.items():
        kw_file = keyword_dir / f"{kw}.md"
        lines = [data["description"], ""]
        for c in data["clusters"]: lines.append(f"[[{c}]]")
        lines.append("")
        for p_raw in data["patents"]: lines.append(f"[[pt_{sanitize_filename(p_raw)}]]")
        lines.extend(["", f"#{data['category']}"])
        kw_file.write_text("\n".join(lines), encoding="utf-8")

    # Patent MD生成
    for p, data in patent_map.items():
        p_file = patent_dir / f"{p}.md"
        lines = []
        for kw in data["keywords"]: lines.append(f"[[{kw}]]")
        lines.extend(["", f"#{data['category']}"])
        p_file.write_text("\n".join(lines), encoding="utf-8")

    print("[Done] Obsidian用マッピング生成完了")