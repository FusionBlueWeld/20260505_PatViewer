import json
import numpy as np
from pathlib import Path
from sklearn.cluster import KMeans
from src.patent_analyzer import generate_cluster_name

def perform_clustering(output_root: Path, cluster_out_dir: Path):
    print("\n" + "="*40)
    print("【STEP 4】 全キーワードのクラスタリング処理")
    print("="*40)

    # --- 処理のスキップ判定 ---
    cluster_file_path = cluster_out_dir / "kw_cluster.json"
    if cluster_file_path.exists():
        print(f"[Info] 既にクラスタファイルが存在するため処理をスキップします。")
        print(f"       再計算したい場合は '{cluster_file_path}' を削除してから実行してください。")
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

    print(f"収集されたキーワード総数: {len(all_keywords)} 件")

    # 2. 行列化
    X = np.array([item["embedding"] for item in all_keywords])

    # クラスタ数決定
    n_clusters = max(2, min(len(all_keywords) // 10, 50))
    print(f"K-means クラスタ数: {n_clusters}")

    # 3. KMeans
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    
    # 重心取得
    centroids = kmeans.cluster_centers_

    # 4. クラスタID再割当
    cluster_counts = {}
    for label in labels:
        cluster_counts[label] = cluster_counts.get(label, 0) + 1
        
    sorted_labels = sorted(cluster_counts.keys(), key=lambda l: cluster_counts[l], reverse=True)
    
    label_to_id = {}
    label_to_centroid = {}
    for idx, label in enumerate(sorted_labels):
        c_id = f"kw{idx:03d}"
        label_to_id[label] = c_id
        label_to_centroid[c_id] = centroids[label].tolist()  # JSON用変換

    # 5. クラスタ構築（embedding除去）
    cluster_data_map = {label_to_id[l]: [] for l in sorted_labels}
    
    for i, item in enumerate(all_keywords):
        c_id = label_to_id[labels[i]]
        item["cluster_id"] = c_id
        cluster_data_map[c_id].append({
            "keyword": item["keyword"],
            "description": item["description"],
            "patent_name": item["patent_name"],
            "category": item["category"]
            # embeddingは保存しない（軽量化）
        })

    cluster_output = []
    print("\n各クラスタの名称をLLMで生成中...")
    
    for c_id, members in cluster_data_map.items():
        cluster_name = generate_cluster_name(members)
        cluster_output.append({
            "cluster_id": c_id,
            "cluster_name": cluster_name,
            "centroid": label_to_centroid[c_id],
            "items": members
        })
        print(f"  [{c_id}] {cluster_name} (所属数: {len(members)})")

    # 6. 保存
    cluster_out_dir.mkdir(parents=True, exist_ok=True)
    with open(cluster_file_path, "w", encoding="utf-8") as f:
        json.dump(cluster_output, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] クラスタまとめファイル: {cluster_file_path}")

    # 7. 各特許JSON更新
    print("各特許のJSONファイルに所属クラスタIDを追記中...")
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

    print("すべてのクラスタリング処理とJSONの更新が完了しました。")