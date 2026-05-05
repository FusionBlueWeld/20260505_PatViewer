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
    
    # 1. output/patents/ 配下の全JSONからデータを収集
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

    # 2. EmbeddingをNumPy行列に変換
    X = np.array([item["embedding"] for item in all_keywords])

    # クラスタ数の自動決定 (キーワード10個につき1クラスタ程度、最大50)
    n_clusters = max(2, min(len(all_keywords) // 10, 50))
    print(f"K-means クラスタ数: {n_clusters}")

    # 3. K-meansクラスタリングの実行
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(X)
    
    # ★重心（セントロイド）の取得
    centroids = kmeans.cluster_centers_

    # 4. クラスタごとの所属数をカウントし、多い順にソートしてIDを振る
    cluster_counts = {}
    for label in labels:
        cluster_counts[label] = cluster_counts.get(label, 0) + 1
        
    sorted_labels = sorted(cluster_counts.keys(), key=lambda l: cluster_counts[l], reverse=True)
    
    label_to_id = {}
    label_to_centroid = {}
    for idx, label in enumerate(sorted_labels):
        c_id = f"kw{idx:03d}"
        label_to_id[label] = c_id
        # 重心ベクトル（NumPy配列）をJSONで保存可能なPythonのリストに変換
        label_to_centroid[c_id] = centroids[label].tolist()

    # 5. クラスタの構築とLLMによる命名
    cluster_data_map = {label_to_id[l]: [] for l in sorted_labels}
    
    # データをマップに振り分け（JSON更新用のIDも記録）
    for i, item in enumerate(all_keywords):
        c_id = label_to_id[labels[i]]
        item["cluster_id"] = c_id
        cluster_data_map[c_id].append({
            "keyword": item["keyword"],
            "description": item["description"],
            "patent_name": item["patent_name"],
            "category": item["category"],
            # ★UI側で描画時の座標計算に使えるよう、個別のベクトルも保持しておく
            "embedding": item["embedding"]
        })

    cluster_output = []
    print("\n各クラスタの名称をLLMで生成中...")
    
    for c_id, members in cluster_data_map.items():
        # LLMでクラスタ名を生成
        cluster_name = generate_cluster_name(members)
        cluster_output.append({
            "cluster_id": c_id,
            "cluster_name": cluster_name,
            "centroid": label_to_centroid[c_id],  # ★計算した重心ベクトルを保存
            "items": members
        })
        print(f"  [{c_id}] {cluster_name} (所属数: {len(members)})")

    # 6. output/cluster/kw_cluster.json に保存
    cluster_out_dir.mkdir(parents=True, exist_ok=True)
    with open(cluster_file_path, "w", encoding="utf-8") as f:
        json.dump(cluster_output, f, ensure_ascii=False, indent=2)
    print(f"\n[Saved] クラスタまとめファイル: {cluster_file_path}")

    # 7. 各特許のJSONファイルに cluster_id を追記して上書き保存
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