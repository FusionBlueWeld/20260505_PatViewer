import json
import ollama

def _get_single_keyword(text: str, existing_keywords: list, model_name: str, num_ctx: int):
    excluded_text = ", ".join(existing_keywords) if existing_keywords else "なし"
    prompt = f"""
以下の特許テキストから、核心的な技術用語を【1つ】抽出し、解説を作成してください。

### 重要なルール:
1. 以下の単語は既に抽出済みのため、絶対に選ばないでください。
   既出リスト: [{excluded_text}]
2. テキスト内で既に抽出された単語は「■抽出済■」という伏せ字に置き換わっています。
3. 冗長な表現（「本特許では」等）は禁止。
4. 構成：
   - 1文目：技術分野と対象の明示（例：〇〇加工における△△装置の構成部品である等）。
   - 2-3文目：その用語の具体的な構造、機能、および技術的背景。
5. 文章の意味密度を高め、専門的なトーンで記述すること。

出力は必ず以下のJSON形式のみで行ってください。
{{
  "keyword": "新しい単語",
  "description": "技術分野・背景・機能を凝縮した2〜3文"
}}

【テキスト】
{text}
"""
    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt,
            format="json",
            options={
                "num_ctx": num_ctx,
                "num_predict": 2048,
                "temperature": 0.4,
                "top_p": 0.9,
            }
        )
        return json.loads(response['response'])
    except Exception as e:
        print(f"      [LLM Error] {e}")
        return None

def analyze_patent_with_llm(text: str, model_name: str = "gemma4:e4b", count: int = 10):
    results = []
    existing_keywords = []
    current_text = text

    text_length = len(text)
    calculated_ctx = int(text_length * 1.2) + 1500
    optimal_num_ctx = min(max(calculated_ctx, 4096), 131072)

    print(f"    [LLM] 文字数:{text_length} -> num_ctx:{optimal_num_ctx} | 抽出", end="", flush=True)

    max_attempts = count * 2
    attempts = 0
    duplicate_count = 0

    while len(results) < count and attempts < max_attempts:
        attempts += 1
        res = _get_single_keyword(current_text, existing_keywords, model_name, optimal_num_ctx)
        
        if not res or "keyword" not in res or not res["keyword"]:
            print("e", end="", flush=True)
            continue
            
        kw = res["keyword"].strip()
        if kw in existing_keywords or "抽出済" in kw:
            duplicate_count += 1
            print("r", end="", flush=True)
            if duplicate_count >= 3:
                print(f" [重複3回で早期終了]", end="", flush=True)
                break
            continue
            
        results.append(res)
        existing_keywords.append(kw)
        current_text = current_text.replace(kw, "■抽出済■")
        print(".", end="", flush=True)
        
    print(f" 完了 (抽出: {len(results)})")
    return results

def get_embedding(text: str, model_name: str = "qwen3-embedding:8b") -> list:
    try:
        response = ollama.embeddings(
            model=model_name,
            prompt=text
        )
        return response.get("embedding", [])
    except Exception as e:
        print(f"      [Embedding Error] {e}")
        return []

def generate_cluster_name(cluster_items: list, model_name: str = "gemma4:e4b") -> str:
    """
    【新規追加】クラスタに含まれるキーワード群から、クラスタの名称をLLMで生成する
    """
    # トークン溢れを防ぐため、上位15件程度のキーワードをサンプルとして渡す
    sample_items = cluster_items[:15]
    
    text_list = []
    for item in sample_items:
        text_list.append(f"・{item['keyword']}: {item['description']}")
    joined_text = "\n".join(text_list)

    prompt = f"""
以下のキーワード群は、AIによるベクトル検索によって同じグループに分類された技術用語です。
これらを総括するクラスタ名を生成してください。

### 制約事項
1. 「○○のXXした＊＊＊」や「○○に関する＊＊機構」のような、体言止めの短いフレーズにすること。（例：「レーザ加工におけるノズル保持機構」「ガス流出を制御する弁構造」等）
2. 冗長な説明は不要。出力は必ず以下のJSON形式のみで行うこと。

{{
  "cluster_name": "クラスタ名"
}}

### キーワード群
{joined_text}
"""
    try:
        response = ollama.generate(
            model=model_name,
            prompt=prompt,
            format="json",
            options={"temperature": 0.2, "num_ctx": 8192}
        )
        res_json = json.loads(response['response'])
        return res_json.get("cluster_name", "名称未設定クラスタ")
    except Exception as e:
        print(f"      [LLM Cluster Name Error] {e}")
        return "名称未設定クラスタ"