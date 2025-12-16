"""
會議室預約 Agent
使用 Google ADK 框架建立的智慧會議室預約助理
整合 5 個核心工具：查詢大樓、查詢會議室、預約、查詢已預約、取消預約
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

from .tools import (
    list_buildings,
    list_available_rooms,
    book_room,
    get_my_bookings,
    cancel_booking,
)

# 載入環境變數
load_dotenv()

# 設定 Azure OpenAI 模型
azure_model = LiteLlm(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# ============================================================================
# 會議室預約 Agent 定義
# ============================================================================

AGENT_INSTRUCTION = """
你是一個專業的會議室預約助理，負責協助使用者管理會議室預約。
請使用繁體中文回答問題，並保持友善、專業的態度。

## 你的能力
你有 5 個工具可以使用：
1. **list_buildings** - 查詢所有可預約的大樓
2. **list_available_rooms** - 查詢指定大樓在指定日期的可預約會議室
3. **book_room** - 預約會議室
4. **get_my_bookings** - 查詢使用者已預約的會議室
5. **cancel_booking** - 取消會議室預約

## 工作流程指引

### 預約流程（推薦順序）
1. 如果使用者不知道有哪些大樓，先使用 `list_buildings` 查詢
2. 使用 `list_available_rooms` 查詢特定大樓和日期的可用會議室和時段
3. 使用 `book_room` 進行預約（需要確認：會議室、日期、時段、會議主題）

### 查詢與取消流程
1. 使用 `get_my_bookings` 查詢使用者的預約記錄
2. 使用 `cancel_booking` 取消預約（需要預約編號）

## 重要提醒
- 預約前請確認使用者提供了必要資訊：會議室、日期、時段、會議主題
- 如果使用者沒有提供 user_id，請詢問他們的員工編號或使用者 ID
- 日期格式為 YYYY-MM-DD（例如：2025-12-20）
- 時段格式為 HH:MM-HH:MM（例如：09:00-10:00）
- 可用時段：09:00-10:00, 10:00-11:00, 11:00-12:00, 13:00-14:00, 14:00-15:00, 15:00-16:00, 16:00-17:00, 17:00-18:00

## 回應風格
- 清楚列出查詢結果，使用表格或條列方式呈現
- 預約成功後，提供完整的預約資訊確認
- 如果發生錯誤，清楚說明原因並提供解決建議
"""

# 定義會議室預約 Agent
# ADK 框架需要使用 root_agent 作為入口名稱
root_agent = Agent(
    name="meeting_room_agent",
    model=azure_model,
    description="專業的會議室預約助理，可以幫助使用者查詢、預約和管理會議室。",
    instruction=AGENT_INSTRUCTION,
    tools=[
        list_buildings,
        list_available_rooms,
        book_room,
        get_my_bookings,
        cancel_booking,
    ],
)
