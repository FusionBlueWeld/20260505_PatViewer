import os
import json
import time
from pathlib import Path
from src.patent_extractor import extract_text_from_pdf
from src.patent_analyzer import analyze_patent_with_llm, get_embedding
from src.cluster_analyzer import perform_clustering
from src.obsidian_mapping import generate_obsidian_mapping
# ★追加: 3Dグラフ用データジェネレーター
from src.graph_generator import generate_3d_graph_data

def main():
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    output_patents_dir = base_dir / "output" / "patents"
    output_cluster_dir = base_dir / "output" / "cluster"  # ★クラスタ保存用

    if not data_dir.exists():
        print(f"[Error] データディレクトリが見つかりません: {data_dir}")
        return

    pdf_files = list(data_dir.rglob("*.pdf"))
    if not pdf_files:
        print("PDFファイルが見つかりませんでした。")
        return

    print(f"合計 {len(pdf_files)} 件の特許データ処理を開始します。\n")

    # ==========================================
    # PDF 抽出・LLM解析・Embedding ループ
    # ==========================================
    total_files = len(pdf_files)
    for idx, pdf_path in enumerate(pdf_files, start=1):
        pdf_stem = pdf_path.stem
        category_name = pdf_path.parent.name
        
        save_dir = output_patents_dir / pdf_stem
        save_dir.mkdir(parents=True, exist_ok=True)

        txt_file_path = save_dir / f"{pdf_stem}.txt"
        json_file_path = save_dir / f"{pdf_stem}.json"

        processed_this_turn = False

        # --- STEP 1: テキスト抽出 ---
        if not txt_file_path.exists():
            print(f"\n[{idx}/{total_files}] Processing (Text): {pdf_path.name} [{category_name}]")
            try:
                extracted_text = extract_text_from_pdf(pdf_path)
                txt_file_path.write_text(extracted_text, encoding="utf-8")
                print("    [Done] テキスト抽出")
            except Exception as e:
                print(f"    [Skip] テキスト抽出失敗: {e}")
                continue
        else:
            print(f"[{idx}/{total_files}] スキップ: {pdf_path.name} [{category_name}]")
            extracted_text = txt_file_path.read_text(encoding="utf-8")

        # テキスト抽出完了時点のタイムスタンプ
        process_start_time = time.perf_counter()

        # --- STEP 2: LLM解析とEmbedding ---
        if not json_file_path.exists():
            # 1. キーワード抽出（最大10個）
            analysis_results = analyze_patent_with_llm(extracted_text)

            # 2. Embeddingの実行
            print(f"    [Embed] ベクトル化を実行中", end="", flush=True)
            for item in analysis_results:
                keyword = item.get("keyword", "")
                description = item.get("description", "")
                
                combined_text = f"{keyword}：{description}"
                item["embedding"] = get_embedding(combined_text)
                print(".", end="", flush=True)
                
            print(" 完了")

            output_data = {
                "patent_name": pdf_stem,
                "category": category_name,
                "extracted_data": analysis_results
            }

            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"    [Saved] {json_file_path.name}")
            processed_this_turn = True

        # --- STEP 3: インターバル処理 ---
        if processed_this_turn:
            elapsed = time.perf_counter() - process_start_time
            print(f"    [Elapsed] テキスト抽出から待機まで: {elapsed:.2f}秒")
            print(f"    [Sleep] クールダウンのため90秒待機します...")
            time.sleep(90)


    # ==========================================
    # STEP 4: クラスタリングの実行
    # ★修正: 分割形式のクラスタファイル群(kw*.json) + cluster_relations.json
    #         の存在をもってスキップ判定する
    # ==========================================
    existing_cluster_files = list(output_cluster_dir.glob("kw*.json"))
    relations_file = output_cluster_dir / "cluster_relations.json"
    if existing_cluster_files and relations_file.exists():
        print("\n[Info] クラスタリングは既に完了しています "
              f"(kw*.json: {len(existing_cluster_files)}件, "
              f"cluster_relations.json: 存在)。")
        print(f"       再計算したい場合は '{output_cluster_dir}' 内のファイルを削除してください。")
    else:
        perform_clustering(output_root=output_patents_dir, cluster_out_dir=output_cluster_dir)

    # ==========================================
    # STEP 5: Obsidian用マッピングの生成        
    # ==========================================
    generate_obsidian_mapping()

    # ==========================================
    # STEP 6: 3Dグラフビュー用JSONの生成 (★新規)       
    # ==========================================
    generate_3d_graph_data()

if __name__ == "__main__":
    main()
