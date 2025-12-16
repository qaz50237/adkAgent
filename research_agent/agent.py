"""
研究助理 Agent - 展示 Parallel Workflow（平行工作流）
展示：平行搜尋、資料彙整、多來源整合

工作流程：
                    ┌─────────────┐
                    │  研究主題    │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│   搜尋新聞    │ │  搜尋論文    │ │  搜尋數據    │
└───────┬───────┘ └───────┬───────┘ └───────┬───────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           ▼
                    ┌─────────────┐
                    │  彙整報告   │
                    └─────────────┘
"""

import os
from datetime import datetime, timedelta
from typing import List, Optional
import random

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# ============================================================================
# 模擬資料庫 - 新聞、論文、數據
# ============================================================================

NEWS_DATABASE = [
    {
        "id": "news001",
        "title": "AI 技術突破：GPT-5 展示驚人推理能力",
        "source": "科技日報",
        "date": "2025-12-15",
        "summary": "OpenAI 發布最新 GPT-5 模型，在複雜推理任務上表現優異...",
        "keywords": ["ai", "gpt", "openai", "機器學習"],
    },
    {
        "id": "news002",
        "title": "台積電宣布 2nm 製程量產計畫",
        "source": "經濟日報",
        "date": "2025-12-14",
        "summary": "台積電宣布 2nm 製程將於 2026 年開始量產，領先競爭對手...",
        "keywords": ["半導體", "台積電", "tsmc", "2nm"],
    },
    {
        "id": "news003",
        "title": "電動車市場報告：2025 年銷量創新高",
        "source": "汽車週刊",
        "date": "2025-12-13",
        "summary": "全球電動車銷量突破 2000 萬輛，中國市場佔比超過 50%...",
        "keywords": ["電動車", "ev", "特斯拉", "比亞迪"],
    },
    {
        "id": "news004",
        "title": "區塊鏈技術在金融業的應用持續擴大",
        "source": "金融時報",
        "date": "2025-12-12",
        "summary": "多家銀行採用區塊鏈技術進行跨境支付，交易時間縮短至秒級...",
        "keywords": ["區塊鏈", "金融", "銀行", "支付"],
    },
    {
        "id": "news005",
        "title": "雲端運算市場：AWS、Azure、GCP 三強鼎立",
        "source": "科技新報",
        "date": "2025-12-11",
        "summary": "2025 年雲端運算市場規模突破 8000 億美元，三大雲端商佔據 65% 市場...",
        "keywords": ["雲端", "aws", "azure", "gcp", "cloud"],
    },
]

PAPER_DATABASE = [
    {
        "id": "paper001",
        "title": "Large Language Models: A Survey of Techniques and Applications",
        "authors": ["Zhang et al."],
        "journal": "Nature Machine Intelligence",
        "year": 2025,
        "abstract": "本文綜述了大型語言模型的最新進展，包括架構改進、訓練方法和應用場景...",
        "citations": 1250,
        "keywords": ["llm", "ai", "nlp", "transformer"],
    },
    {
        "id": "paper002",
        "title": "Advances in Semiconductor Manufacturing: From 3nm to 2nm",
        "authors": ["Chen et al."],
        "journal": "IEEE Transactions on Semiconductor Manufacturing",
        "year": 2025,
        "abstract": "探討先進製程節點的技術挑戰與解決方案，包括 EUV 微影技術的應用...",
        "citations": 890,
        "keywords": ["半導體", "製程", "euv", "奈米"],
    },
    {
        "id": "paper003",
        "title": "Electric Vehicle Battery Technology: Current Status and Future Trends",
        "authors": ["Wang et al."],
        "journal": "Energy Storage Materials",
        "year": 2025,
        "abstract": "分析固態電池和鋰硫電池的最新發展，預測未來電動車電池技術走向...",
        "citations": 720,
        "keywords": ["電池", "電動車", "固態電池", "能源"],
    },
    {
        "id": "paper004",
        "title": "Blockchain Scalability Solutions: Layer 2 and Beyond",
        "authors": ["Liu et al."],
        "journal": "ACM Computing Surveys",
        "year": 2025,
        "abstract": "研究區塊鏈擴展性解決方案，包括 Rollups、側鏈和分片技術...",
        "citations": 650,
        "keywords": ["區塊鏈", "擴展性", "layer2", "rollup"],
    },
]

STATISTICS_DATABASE = {
    "ai_market": {
        "name": "AI 市場規模",
        "data": [
            {"year": 2023, "value": 1500, "unit": "億美元"},
            {"year": 2024, "value": 2000, "unit": "億美元"},
            {"year": 2025, "value": 2800, "unit": "億美元"},
        ],
        "growth_rate": "40%",
        "source": "Gartner",
    },
    "semiconductor_market": {
        "name": "半導體市場規模",
        "data": [
            {"year": 2023, "value": 5200, "unit": "億美元"},
            {"year": 2024, "value": 5800, "unit": "億美元"},
            {"year": 2025, "value": 6500, "unit": "億美元"},
        ],
        "growth_rate": "12%",
        "source": "IC Insights",
    },
    "ev_sales": {
        "name": "全球電動車銷量",
        "data": [
            {"year": 2023, "value": 1400, "unit": "萬輛"},
            {"year": 2024, "value": 1750, "unit": "萬輛"},
            {"year": 2025, "value": 2100, "unit": "萬輛"},
        ],
        "growth_rate": "20%",
        "source": "IEA",
    },
    "cloud_market": {
        "name": "雲端運算市場規模",
        "data": [
            {"year": 2023, "value": 5500, "unit": "億美元"},
            {"year": 2024, "value": 6800, "unit": "億美元"},
            {"year": 2025, "value": 8200, "unit": "億美元"},
        ],
        "growth_rate": "21%",
        "source": "Synergy Research",
    },
}

COMPANY_DATABASE = {
    "tsmc": {
        "name": "台積電",
        "stock_code": "2330.TW",
        "market_cap": "15.2 兆台幣",
        "revenue_2024": "2.3 兆台幣",
        "employees": 73000,
        "industry": "半導體",
    },
    "nvidia": {
        "name": "NVIDIA",
        "stock_code": "NVDA",
        "market_cap": "3.2 兆美元",
        "revenue_2024": "1100 億美元",
        "employees": 29000,
        "industry": "半導體/AI",
    },
    "tesla": {
        "name": "Tesla",
        "stock_code": "TSLA",
        "market_cap": "1.2 兆美元",
        "revenue_2024": "980 億美元",
        "employees": 140000,
        "industry": "電動車",
    },
}


# ============================================================================
# 搜尋 Tools
# ============================================================================

def search_news(keywords: List[str], limit: int = 5) -> dict:
    """搜尋相關新聞。

    Args:
        keywords: 搜尋關鍵字列表
        limit: 回傳筆數上限

    Returns:
        dict: 新聞搜尋結果
    """
    results = []
    keywords_lower = [k.lower() for k in keywords]
    
    for news in NEWS_DATABASE:
        score = 0
        for kw in keywords_lower:
            if any(kw in nkw.lower() for nkw in news["keywords"]):
                score += 2
            if kw in news["title"].lower():
                score += 1
            if kw in news["summary"].lower():
                score += 1
        if score > 0:
            results.append({"score": score, **news})
    
    results.sort(key=lambda x: x["score"], reverse=True)
    
    return {
        "status": "success",
        "source": "新聞資料庫",
        "count": len(results[:limit]),
        "results": results[:limit],
    }


def search_papers(keywords: List[str], limit: int = 5) -> dict:
    """搜尋學術論文。

    Args:
        keywords: 搜尋關鍵字列表
        limit: 回傳筆數上限

    Returns:
        dict: 論文搜尋結果
    """
    results = []
    keywords_lower = [k.lower() for k in keywords]
    
    for paper in PAPER_DATABASE:
        score = 0
        for kw in keywords_lower:
            if any(kw in pkw.lower() for pkw in paper["keywords"]):
                score += 2
            if kw in paper["title"].lower():
                score += 1
            if kw in paper["abstract"].lower():
                score += 1
        if score > 0:
            results.append({"relevance_score": score, **paper})
    
    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    return {
        "status": "success",
        "source": "學術論文資料庫",
        "count": len(results[:limit]),
        "results": results[:limit],
    }


def get_market_statistics(topic: str) -> dict:
    """取得市場統計數據。

    Args:
        topic: 主題 (ai_market/semiconductor_market/ev_sales/cloud_market)

    Returns:
        dict: 統計數據
    """
    topic_mapping = {
        "ai": "ai_market",
        "人工智慧": "ai_market",
        "半導體": "semiconductor_market",
        "semiconductor": "semiconductor_market",
        "電動車": "ev_sales",
        "ev": "ev_sales",
        "雲端": "cloud_market",
        "cloud": "cloud_market",
    }
    
    # 嘗試匹配
    matched_topic = None
    for key, value in topic_mapping.items():
        if key in topic.lower():
            matched_topic = value
            break
    
    if not matched_topic and topic in STATISTICS_DATABASE:
        matched_topic = topic
    
    if not matched_topic:
        return {
            "status": "not_found",
            "message": f"找不到 '{topic}' 的統計數據",
            "available_topics": list(STATISTICS_DATABASE.keys()),
        }
    
    return {
        "status": "success",
        "source": "市場研究資料庫",
        "data": STATISTICS_DATABASE[matched_topic],
    }


def get_company_info(company_name: str) -> dict:
    """取得公司資訊。

    Args:
        company_name: 公司名稱

    Returns:
        dict: 公司資訊
    """
    company_lower = company_name.lower()
    
    for key, company in COMPANY_DATABASE.items():
        if key in company_lower or company["name"].lower() in company_lower:
            return {
                "status": "success",
                "source": "公司資料庫",
                "company": company,
            }
    
    return {
        "status": "not_found",
        "message": f"找不到 '{company_name}' 的資訊",
        "available_companies": [c["name"] for c in COMPANY_DATABASE.values()],
    }


def generate_research_report(
    topic: str,
    news_results: dict,
    paper_results: dict,
    statistics: dict
) -> dict:
    """生成研究報告摘要。

    Args:
        topic: 研究主題
        news_results: 新聞搜尋結果
        paper_results: 論文搜尋結果
        statistics: 統計數據

    Returns:
        dict: 報告摘要
    """
    report = {
        "title": f"{topic} 研究報告",
        "generated_at": datetime.now().isoformat(),
        "sections": {
            "latest_news": {
                "count": news_results.get("count", 0),
                "highlights": [n["title"] for n in news_results.get("results", [])[:3]],
            },
            "academic_research": {
                "count": paper_results.get("count", 0),
                "key_papers": [p["title"] for p in paper_results.get("results", [])[:3]],
            },
            "market_data": statistics.get("data", {}),
        },
    }
    
    return {
        "status": "success",
        "report": report,
    }


# ============================================================================
# 設定模型
# ============================================================================

azure_model = LiteLlm(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


# ============================================================================
# Agent 定義
# ============================================================================

root_agent = Agent(
    name="research_agent",
    model=azure_model,
    description="研究助理，可搜尋新聞、論文和市場數據，生成研究報告",
    instruction="""你是專業的研究助理，負責幫助使用者進行資訊蒐集和研究分析。

## 你的能力

1. **搜尋新聞** (search_news)
   - 搜尋最新相關新聞
   - 輸入關鍵字列表

2. **搜尋論文** (search_papers)
   - 搜尋學術論文
   - 輸入關鍵字列表

3. **取得市場數據** (get_market_statistics)
   - 可用主題：ai_market, semiconductor_market, ev_sales, cloud_market

4. **取得公司資訊** (get_company_info)
   - 可查詢：台積電、NVIDIA、Tesla

5. **生成報告** (generate_research_report)
   - 整合多來源資料生成報告

## 研究流程

當使用者詢問某個主題時，你應該：

1. **平行蒐集資料**
   - 同時搜尋新聞、論文、統計數據
   
2. **彙整分析**
   - 整理各來源的重點
   - 找出共同趨勢
   
3. **生成報告**
   - 提供結構化的研究摘要
   - 標註資料來源

## 回覆格式

請用結構化的方式呈現研究結果：

### 📰 最新動態
- 相關新聞摘要

### 📚 學術研究
- 重要論文發現

### 📊 市場數據
- 統計數據和趨勢

### 💡 分析總結
- 綜合分析和建議

請用繁體中文回答。""",
    tools=[
        search_news,
        search_papers,
        get_market_statistics,
        get_company_info,
        generate_research_report,
    ],
)
