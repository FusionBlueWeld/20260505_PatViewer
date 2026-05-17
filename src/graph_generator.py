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
    cluster_dir = base_dir / "output" / "cluster"
    relations_path = cluster_dir / "cluster_relations.json"
    graph_view_dir = base_dir / "output" / "graph_view"
    
    # 出力先ディレクトリを作成
    graph_view_dir.mkdir(parents=True, exist_ok=True)
    out_json_path = graph_view_dir / "3d_view.json"

    # ★修正: 分割形式のクラスタファイル群 (kw000.json, kw001.json, ...) を読み込む
    cluster_files = sorted(cluster_dir.glob("kw*.json"))
    if not cluster_files:
        print(f"[Error] {cluster_dir} 内にクラスタファイル (kw*.json) が見つかりません。")
        print("       先にクラスタリングを実行してください。")
        return

    clusters = []
    for c_path in cluster_files:
        try:
            with open(c_path, "r", encoding="utf-8") as f:
                cluster_obj = json.load(f)
            clusters.append(cluster_obj)
        except Exception as e:
            print(f"  [Warn] {c_path.name} の読み込みに失敗: {e}")

    if not clusters:
        print("[Error] 有効なクラスタデータが読み込めませんでした。")
        return

    print(f"[Info] 読み込んだクラスタ数: {len(clusters)}")

    # cluster_id (例: "kw000") から ノードID (例: "cl_xxx") への対応表
    cluster_id_to_node_id = {}

    nodes = {}
    links_set = set()
    links = []

    for cluster in clusters:
        cl_name = cluster.get("cluster_name", "Unnamed Cluster")
        cl_id_raw = cluster.get("cluster_id", "")  # 例: "kw000"
        cl_id = f"cl_{sanitize_id(cl_name)}"

        if cl_id_raw:
            cluster_id_to_node_id[cl_id_raw] = cl_id

        items = cluster.get("items", [])
        
        # 接続している特許のユニーク数をカウント
        unique_patents = set(item["patent_name"] for item in items)
        patent_count = len(unique_patents)
        kw_count = len(items)
        
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

        for item in items:
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
                links.append({"source": cl_id, "target": kw_id, "type": "cluster-keyword"})

            # Link: Keyword -> Patent
            kw_pt_key = (kw_id, pt_id)
            if kw_pt_key not in links_set:
                links_set.add(kw_pt_key)
                links.append({"source": kw_id, "target": pt_id, "type": "keyword-patent"})

    # ==========================================
    # ★追加: クラスタ間リンク (cluster-cluster)
    # cluster_relations.json から関係性を読み込んで反映
    # ==========================================
    cluster_link_count = 0
    if relations_path.exists():
        try:
            with open(relations_path, "r", encoding="utf-8") as f:
                relations = json.load(f)
        except Exception as e:
            print(f"  [Warn] cluster_relations.json の読み込みに失敗: {e}")
            relations = []

        for rel in relations:
            src_raw = rel.get("source_cluster_id", "")
            tgt_raw = rel.get("target_cluster_id", "")
            direction = rel.get("direction", "A<->B")
            description = rel.get("description", "")
            common_count = rel.get("common_count", 0)

            src_node_id = cluster_id_to_node_id.get(src_raw)
            tgt_node_id = cluster_id_to_node_id.get(tgt_raw)

            if not src_node_id or not tgt_node_id:
                continue
            if src_node_id not in nodes or tgt_node_id not in nodes:
                continue

            # direction に応じて source/target を決定
            if direction == "B->A":
                a, b = tgt_node_id, src_node_id
            else:
                # "A->B" および "A<->B" は src->tgt の並びを維持
                a, b = src_node_id, tgt_node_id

            cl_cl_key = ("CC", a, b) if direction != "A<->B" else ("CC", *sorted([a, b]))
            if cl_cl_key in links_set:
                continue
            links_set.add(cl_cl_key)

            links.append({
                "source": a,
                "target": b,
                "type": "cluster-cluster",
                "direction": direction,
                "desc": description,
                "common_count": common_count
            })
            cluster_link_count += 1

        print(f"[Info] クラスタ間リンクを追加: {cluster_link_count} 件")
    else:
        print(f"[Warn] {relations_path.name} が見つかりません。クラスタ間リンクは生成されません。")

    graph_data = {
        "nodes": list(nodes.values()),
        "links": links
    }

    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    print(f"[Done] 3Dグラフ用データ生成完了: {out_json_path}")
    print(f"       Nodes: {len(graph_data['nodes'])}, Links: {len(graph_data['links'])}")
