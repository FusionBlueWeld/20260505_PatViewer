import json
import numpy as np
from pathlib import Path
from itertools import combinations
from sklearn.cluster import KMeans
import ollama
from src.patent_analyzer import generate_cluster_name

def analyze_cluster_relation(c1_data: dict, c2_data: dict, model_name: str = "gemma4:e4b") -> dict:
    """LLMを用いて、2つの共起クラスタの関係性と方向を定義する"""
    def _format_kw(c_data):
        return ", ".join([item["keyword"] for item in c_data["items"][:10]])

    prompt = f"""
以下の2つの技術クラスタは、同一の特許内で共通して言及されている関連技術です。
これら2つのクラスタの技術的な関係を考察し、以下のJSON形式でのみ出力してください。

【クラスタA】: {c1_data['cluster_name']}
主なキーワード: {_format_kw(c1_data)}

【クラスタB】: {c2_data['cluster_name']}
主なキーワード: {_format_kw(c2_data)}

【方向性のルール（"direction"キーに以下から1つ選ぶ）】
- "A->B" : AがBの構成要素・前提技術である、またはAの処理がBへ入力される
- "B->A" : BがAの構成要素・前提技術である、またはBの処理がAへ入力される
- "A<->B": 相互に依存している、または並列・密接に連携している

【出力JSON形式】
{{
  "direction": "A->B",
  "description": "ここに関係性を簡潔に1〜2文で記述"
}}
"""
    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt,
            format="json",
            options={"temperature": 0.2, "num_ctx": 4096}
        )
        return json.loads(response['response'])
    except Exception as e:
        print(f"      [LLM Relation Error] {e}")
        return {"direction": "A<->B", "description": "関連性が確認されましたが、詳細の生成に失敗しました。"}


# ★追加: min_common_patents 引数（デフォルト4）で共起のカットオフ値を設定できるようにしました
def perform_clustering(output_root: Path, cluster_out_dir: Path, min_common_patents: int = 4):
    print("\n" + "="*40)
    print("【STEP 4】 全キーワードのクラスタリング処理")
    print("="*40)

    # 出力ディレクトリ作成
    cluster_out_dir.mkdir(parents=True, exist_ok=True)
    relations_file = cluster_out_dir / "cluster_relations.json"

    # --- 処理のスキップ判定 ---
    if list(cluster_out_dir.glob("kw*.json")) and relations_file.exists():
        print(f"[Info] 既にクラスタファイル群が存在するため処理をスキップします。")
        print(f"       再計算したい場合は '{cluster_out_dir}' 内のファイルを削除してください。")
        return

    all_keywords = []
    
    # 1. JSONからデータ収集
    json_files = list(output_root.rglob("*.json"))
    for file_path in json_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            patent_name = data.get("patent_name", "")
            category = data.get("category", "")
            extracted_data = data.get("extracted_data", [])
            for i, item in enumerate(extracted_data):
                if "embedding" in item and len(item["embedding"]) > 0:
                    all_keywords.append({
                        "patent_name": patent_name,
                        "category": category,
                        "keyword": item.get("keyword", ""),
                        "description": item.get("description", ""),
                        "embedding": item["embedding"],
                        "file_path": file_path,
                        "item_index": i
                    })
        except Exception as e:
            print(f"  [Error] {file_path.name} の読み込みに失敗: {e}")

    if not all_keywords:
        print("クラスタリング可能なデータがありません。")
        return

    # 2. 行列化とKMeans
    X = np.array([item["embedding"] for item in all_keywords])
    n_clusters = max(2, min(len(all_keywords) // 10, 50))
    print(f"K-means クラスタ数: {n_clusters}")

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    centroids = kmeans.cluster_centers_

    # クラスタID再割当
    cluster_counts = {}
    for label in labels:
        cluster_counts[label] = cluster_counts.get(label, 0) + 1
        
    sorted_labels = sorted(cluster_counts.keys(), key=lambda l: cluster_counts[l], reverse=True)
    label_to_id = {}
    label_to_centroid = {}
    for idx, label in enumerate(sorted_labels):
        c_id = f"kw{idx:03d}"
        label_to_id[label] = c_id
        label_to_centroid[c_id] = centroids[label].tolist()

    # クラスタ構築
    cluster_data_map = {label_to_id[l]: [] for l in sorted_labels}
    for i, item in enumerate(all_keywords):
        c_id = label_to_id[labels[i]]
        item["cluster_id"] = c_id
        cluster_data_map[c_id].append({
            "keyword": item["keyword"],
            "description": item["description"],
            "patent_name": item["patent_name"],
            "category": item["category"]
        })

    print("\n各クラスタの名称を生成し、分割保存します...")
    clusters_dict = {}
    for c_id, members in cluster_data_map.items():
        cluster_name = generate_cluster_name(members)
        cluster_obj = {
            "cluster_id": c_id,
            "cluster_name": cluster_name,
            "centroid": label_to_centroid[c_id],
            "items": members
        }
        clusters_dict[c_id] = cluster_obj
        
        # 1クラスタ＝1JSONで保存
        c_file_path = cluster_out_dir / f"{c_id}.json"
        with open(c_file_path, "w", encoding="utf-8") as f:
            json.dump(cluster_obj, f, ensure_ascii=False, indent=2)
        print(f"  [Saved] {c_id}.json : {cluster_name}")

    # --- 各特許JSON更新 ---
    updates_by_file = {}
    for item in all_keywords:
        path = item["file_path"]
        if path not in updates_by_file:
            updates_by_file[path] = []
        updates_by_file[path].append((item["item_index"], item["cluster_id"]))

    for path, updates in updates_by_file.items():
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item_idx, c_id in updates:
            data["extracted_data"][item_idx]["cluster"] = c_id
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- クラスタ間の関係定義 (共起ルール・カットオフ適用) ---
    print(f"\nクラスタ間の共起関係をLLMで分析中... (共通特許のカットオフ: {min_common_patents}件以上)")
    relations_list = []
    c_ids = list(clusters_dict.keys())
    
    for c1_id, c2_id in combinations(c_ids, 2):
        c1_patents = set(item["patent_name"] for item in clusters_dict[c1_id]["items"])
        c2_patents = set(item["patent_name"] for item in clusters_dict[c2_id]["items"])
        
        common_patents = c1_patents.intersection(c2_patents)
        
        # ★変更: カットオフ値以上の共起がある場合のみ処理する
        if len(common_patents) >= min_common_patents:
            print(f"  [共起発見] {c1_id} と {c2_id} (共通特許数: {len(common_patents)}) ... LLM解析中", end="", flush=True)
            rel_res = analyze_cluster_relation(clusters_dict[c1_id], clusters_dict[c2_id])
            
            relations_list.append({
                "source_cluster_id": c1_id,
                "target_cluster_id": c2_id,
                "common_count": len(common_patents),
                "direction": rel_res.get("direction", "A<->B"),
                "description": rel_res.get("description", "")
            })
            print(" 完了")
    
    # 関係性リストの保存
    with open(relations_file, "w", encoding="utf-8") as f:
        json.dump(relations_list, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] 関係性まとめファイル: {relations_file}")
    
    print("すべてのクラスタリング・関係構築処理が完了しました。")