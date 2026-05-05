import os
import json
import time
from pathlib import Path
from src.patent_extractor import extract_text_from_pdf
from src.patent_analyzer import analyze_patent_with_llm, get_embedding
from src.cluster_analyzer import perform_clustering  # ★追加

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

    print(f"合計 {len(pdf_files)} 件の特許データ処理を開始します。")

    # ==========================================
    # PDF 抽出・LLM解析・Embedding ループ
    # ==========================================
    for pdf_path in pdf_files:
        pdf_stem = pdf_path.stem
        category_name = pdf_path.parent.name
        
        save_dir = output_patents_dir / pdf_stem
        save_dir.mkdir(parents=True, exist_ok=True)

        txt_file_path = save_dir / f"{pdf_stem}.txt"
        json_file_path = save_dir / f"{pdf_stem}.json"

        processed_this_turn = False

        # --- STEP 1: テキスト抽出 ---
        if not txt_file_path.exists():
            print(f"\nProcessing (Text): {pdf_path.name}")
            try:
                extracted_text = extract_text_from_pdf(pdf_path)
                txt_file_path.write_text(extracted_text, encoding="utf-8")
            except Exception as e:
                print(f"    [Skip] テキスト抽出失敗: {e}")
                continue
        else:
            extracted_text = txt_file_path.read_text(encoding="utf-8")

        # --- STEP 2: LLM解析とEmbedding ---
        if not json_file_path.exists():
            print(f"Processing (LLM & Embed): {pdf_stem} [{category_name}]")
            
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
            print(f"    [Sleep] クールダウンのため90秒待機します...")
            time.sleep(90)


    # ==========================================
    # STEP 4: クラスタリングの実行
    # ==========================================
    # kw_cluster.json がまだ存在しない場合のみ実行
    # (再計算したい場合は output/cluster/kw_cluster.json を削除してから実行)
    cluster_file = output_cluster_dir / "kw_cluster.json"
    if not cluster_file.exists():
        perform_clustering(output_root=output_patents_dir, cluster_out_dir=output_cluster_dir)
    else:
        print("\n[Info] クラスタリングは既に完了しています (kw_cluster.json が存在します)。")

if __name__ == "__main__":
    main()