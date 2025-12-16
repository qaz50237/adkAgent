"""
Google ADK Agent 範本
這是一個基本的 multi-tool agent 範本，包含天氣和時間查詢功能
使用 Azure OpenAI 作為 LLM 後端
"""

import datetime
import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# 載入環境變數
load_dotenv()


def get_weather(city: str) -> dict:
    """取得指定城市的天氣報告。

    Args:
        city (str): 要查詢天氣的城市名稱。

    Returns:
        dict: 包含狀態和結果或錯誤訊息。
    """
    # 這是範例資料，實際應用中可以串接真實的天氣 API
    weather_data = {
        "taipei": {
            "status": "success",
            "report": "台北目前天氣晴朗，氣溫 28 度（攝氏），濕度 65%。",
        },
        "new york": {
            "status": "success",
            "report": "紐約目前天氣晴朗，氣溫 25 度（攝氏），濕度 55%。",
        },
        "tokyo": {
            "status": "success",
            "report": "東京目前多雲，氣溫 22 度（攝氏），濕度 70%。",
        },
    }

    city_lower = city.lower()
    if city_lower in weather_data:
        return weather_data[city_lower]
    else:
        return {
            "status": "error",
            "error_message": f"抱歉，目前沒有 '{city}' 的天氣資訊。",
        }


def get_current_time(city: str) -> dict:
    """取得指定城市的目前時間。

    Args:
        city (str): 要查詢時間的城市名稱。

    Returns:
        dict: 包含狀態和結果或錯誤訊息。
    """
    timezone_map = {
        "taipei": "Asia/Taipei",
        "new york": "America/New_York",
        "tokyo": "Asia/Tokyo",
        "london": "Europe/London",
        "paris": "Europe/Paris",
    }

    city_lower = city.lower()
    if city_lower not in timezone_map:
        return {
            "status": "error",
            "error_message": f"抱歉，目前沒有 '{city}' 的時區資訊。",
        }

    tz = ZoneInfo(timezone_map[city_lower])
    now = datetime.datetime.now(tz)
    report = f"{city} 目前的時間是 {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"

    return {"status": "success", "report": report}


# 設定 Azure OpenAI 模型
azure_model = LiteLlm(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


# 定義根 Agent
root_agent = Agent(
    name="assistant_agent",
    model=azure_model,  # 使用 Azure OpenAI
    description="一個可以回答天氣和時間問題的智慧助理。",
    instruction=(
        "你是一個友善的助理，可以幫助使用者查詢城市的天氣和時間。"
        "請使用繁體中文回答問題。"
        "當使用者詢問天氣或時間時，使用對應的工具來取得資訊。"
    ),
    tools=[get_weather, get_current_time],
)

