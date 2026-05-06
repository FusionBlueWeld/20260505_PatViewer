import json
from pathlib import Path
import re

def sanitize_id(name: str) -> str:
    """IDとして扱いやすいように特殊文字をアンダースコアに変換"""
    return re.sub(r'[\\/:*?"<>|#^\[\]\s]', '_', name)

def generate_3d_graph_data():
    print("\n" + "="*40)
    print("【STEP 6】 3Dグラフ用データの生成")
    print("="*40)

    base_dir = Path(__file__).resolve().parent.parent
    cluster_path = base_dir / "output" / "cluster" / "kw_cluster.json"
    graph_view_dir = base_dir / "output" / "graph_view"
    
    # 出力先ディレクトリを作成
    graph_view_dir.mkdir(parents=True, exist_ok=True)
    out_json_path = graph_view_dir / "3d_view.json"

    if not cluster_path.exists():
        print("[Error] kw_cluster.json が見つかりません。先にクラスタリングを実行してください。")
        return

    with open(cluster_path, "r", encoding="utf-8") as f:
        clusters = json.load(f)

    nodes = {}
    links_set = set()
    links = []

    for cluster in clusters:
        cl_name = cluster["cluster_name"]
        cl_id = f"cl_{sanitize_id(cl_name)}"
        
        # 接続している特許のユニーク数をカウント
        unique_patents = set(item["patent_name"] for item in cluster["items"])
        patent_count = len(unique_patents)
        kw_count = len(cluster["items"])
        
        # 1. Cluster Node (上位層: Group 3)
        if cl_id not in nodes:
            # キーワード数が多いほど、非線形にサイズ(体積)を大きくする（差をより強調）
            # 3d-force-graphのvalは「体積」を表すため、半径の差を出すために指数を大きく設定
            val = max(10, int((kw_count ** 2.2) * 1.5))
            nodes[cl_id] = {
                "id": cl_id, 
                "name": cl_name, 
                "group": 3, 
                "val": val,
                "patent_count": patent_count
            }

        for item in cluster["items"]:
            kw_name = item["keyword"]
            kw_id = f"kw_{sanitize_id(kw_name)}"
            
            # 2. Keyword Node (中間層: Group 2)
            if kw_id not in nodes:
                nodes[kw_id] = {"id": kw_id, "name": kw_name, "group": 2, "val": 3}
            
            pt_name = item["patent_name"]
            pt_id = f"pt_{sanitize_id(pt_name)}"
            category = item.get("category", "Unknown")
            
            # 3. Patent Node (下層: Group 1)
            if pt_id not in nodes:
                nodes[pt_id] = {"id": pt_id, "name": pt_name, "group": 1, "val": 5, "category": category}

            # Link: Cluster -> Keyword
            cl_kw_key = (cl_id, kw_id)
            if cl_kw_key not in links_set:
                links_set.add(cl_kw_key)
                links.append({"source": cl_id, "target": kw_id})

            # Link: Keyword -> Patent
            kw_pt_key = (kw_id, pt_id)
            if kw_pt_key not in links_set:
                links_set.add(kw_pt_key)
                links.append({"source": kw_id, "target": pt_id})

    graph_data = {
        "nodes": list(nodes.values()),
        "links": links
    }

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    print(f"[Done] 3Dグラフ用データ生成完了: {out_json_path}")