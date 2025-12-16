"""
會議室預約 Agent
使用 Google ADK 框架建立的智慧會議室預約助理
整合 5 個核心工具：查詢大樓、查詢會議室、預約、查詢已預約、取消預約

設計特點：
- 使用者資料由 api_server 自動注入到 session state
- 使用共用的 before_tool_callback 驗證使用者資料並自動注入 user_id
- Agent 可直接使用 state 中的使用者資訊
"""

import os

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext

from .tools import (
    list_buildings,
    list_available_rooms,
    book_room,
    get_my_bookings,
    cancel_booking,
)

# 匯入共用的使用者驗證 callback
from shared.user_service import create_user_validation_callback

# 載入環境變數
load_dotenv()

# 設定 Azure OpenAI 模型
azure_model = LiteLlm(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


# ============================================================================
# 查詢目前使用者工具（供 Agent 確認身份用）
# ============================================================================

def get_current_user(tool_context: ToolContext) -> dict:
    """查詢目前登入的使用者資料。
    
    使用者資料由系統自動注入，不需手動註冊。

    Args:
        tool_context (ToolContext): ADK 提供的工具上下文

    Returns:
        dict: 目前使用者資料
    """
    if not tool_context.state.get("is_registered"):
        return {
            "status": "error",
            "message": "無法取得使用者資料，請聯繫系統管理員。",
        }

    return {
        "status": "success",
        "user_info": {
            "user_id": tool_context.state.get("user_id"),
            "user_name": tool_context.state.get("user_name"),
            "department": tool_context.state.get("department"),
            "email": tool_context.state.get("email"),
        },
    }


# ============================================================================
# 會議室預約 Agent 定義
# ============================================================================

# 建立使用者驗證 callback（只驗證需要 user_id 的工具）
user_validation_callback = create_user_validation_callback(
    tools_requiring_user=["book_room", "get_my_bookings", "cancel_booking"]
)

AGENT_INSTRUCTION = """
你是一個專業的會議室預約助理，負責協助使用者管理會議室預約。
請使用繁體中文回答問題，並保持友善、專業的態度。

## ✅ 使用者身份
使用者資料已由系統自動提供，你可以透過 `get_current_user` 查詢目前使用者的：
- 員工編號 (user_id)
- 姓名 (user_name)
- 部門 (department)
- 電子郵件 (email)

**你不需要詢問使用者的基本資料**，系統已經知道他們是誰。

## 你的能力
你有 6 個工具可以使用：

1. **get_current_user** - 查詢目前登入的使用者資料
2. **list_buildings** - 查詢所有可預約的大樓
3. **list_available_rooms** - 查詢指定大樓在指定日期的可預約會議室
4. **book_room** - 預約會議室（user_id 會自動帶入）
5. **get_my_bookings** - 查詢使用者已預約的會議室
6. **cancel_booking** - 取消會議室預約

## 工作流程指引

### 預約流程
1. 可以先用 `get_current_user` 打招呼，稱呼使用者的姓名
2. 如果使用者不知道有哪些大樓，使用 `list_buildings` 查詢
3. 使用 `list_available_rooms` 查詢特定大樓和日期的可用會議室和時段
4. 使用 `book_room` 進行預約（只需提供：會議室、日期、時段、會議主題）

### 查詢與取消流程
1. 使用 `get_my_bookings` 查詢使用者的預約記錄
2. 使用 `cancel_booking` 取消預約（需要預約編號）

## 重要提醒
- **不需要詢問員工編號**，系統會自動使用
- 日期格式為 YYYY-MM-DD（例如：2025-12-20）
- 時段格式為 HH:MM-HH:MM（例如：09:00-10:00）
- 可用時段：09:00-10:00, 10:00-11:00, 11:00-12:00, 13:00-14:00, 14:00-15:00, 15:00-16:00, 16:00-17:00, 17:00-18:00

## 回應風格
- 親切地稱呼使用者的姓名
- 清楚列出查詢結果，使用表格或條列方式呈現
- 預約成功後，提供完整的預約資訊確認
- 如果發生錯誤，清楚說明原因並提供解決建議
"""

# 定義會議室預約 Agent
# ADK 框架需要使用 root_agent 作為入口名稱
root_agent = Agent(
    name="meeting_room_agent",
    model=azure_model,
    description="專業的會議室預約助理，可以幫助使用者查詢、預約和管理會議室。使用者身份由系統自動識別。",
    instruction=AGENT_INSTRUCTION,
    tools=[
        get_current_user,
        list_buildings,
        list_available_rooms,
        book_room,
        get_my_bookings,
        cancel_booking,
    ],
    before_tool_callback=user_validation_callback,  # 使用共用的驗證 callback
)
