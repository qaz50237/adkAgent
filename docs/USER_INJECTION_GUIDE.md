# 使用者資料注入機制說明文件

本文件說明如何在 ADK Agent 系統中實作使用者資料的自動注入機制，讓外部系統（如 LangChain、企業應用）只需傳入 `user_id`，系統就能自動查詢並注入完整的使用者資料。

## 目錄

- [架構概覽](#架構概覽)
- [資料流程](#資料流程)
- [共用模組說明](#共用模組說明)
- [API Server 整合](#api-server-整合)
- [Agent 端設定](#agent-端設定)
- [使用範例](#使用範例)
- [擴展指南](#擴展指南)

---

## 架構概覽

```
┌─────────────────────────────────────────────────────────────────────┐
│                         外部系統                                     │
│            (LangChain / 企業應用 / 前端)                             │
│                                                                      │
│   只需傳入: { "user_id": "EMP001", "message": "..." }               │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        api_server.py                                 │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. 接收 user_id                                              │   │
│  │ 2. 呼叫 User Service 查詢完整資料                            │   │
│  │ 3. 建立 Session 並注入使用者資料到 state                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          Agent                                       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ before_tool_callback:                                        │   │
│  │   • 驗證 state.is_registered                                 │   │
│  │   • 自動注入 user_id 到 tool_args                            │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                │                                     │
│                                ▼                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Tools: 直接使用 user_id，不需詢問使用者                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 資料流程

### 完整流程圖

```
POST /agents/meeting_room/chat
{
  "user_id": "EMP001",
  "message": "幫我預約明天 A 棟的會議室"
}
        │
        ▼
┌───────────────────────────────────────┐
│ api_server.py                         │
│                                       │
│ 1. get_user_by_id("EMP001")          │
│    ↓                                  │
│    返回 UserInfo:                     │
│    - user_id: "EMP001"               │
│    - user_name: "王小明"              │
│    - department: "資訊部"             │
│    - email: "wang@company.com"       │
│                                       │
│ 2. create_session(state={            │
│      "user_id": "EMP001",            │
│      "user_name": "王小明",           │
│      "department": "資訊部",          │
│      "email": "wang@company.com",    │
│      "is_registered": True           │
│    })                                 │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ Agent 執行                            │
│                                       │
│ LLM 決定呼叫 book_room()             │
│        │                              │
│        ▼                              │
│ before_tool_callback:                │
│   ✓ state.is_registered = True       │
│   → tool_args["user_id"] = "EMP001" │
│        │                              │
│        ▼                              │
│ book_room(                           │
│   room_id="A-101",                   │
│   user_id="EMP001",  ← 自動注入      │
│   date="2025-12-17",                 │
│   time_slot="10:00-11:00",           │
│   title="專案會議"                    │
│ )                                     │
└───────────────────────────────────────┘
```

---

## 共用模組說明

### 檔案結構

```
shared/
├── __init__.py
└── user_service.py
```

### UserInfo 資料類別

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class UserInfo:
    """使用者基本資料"""
    user_id: str        # 員工編號（必填）
    user_name: str      # 姓名（必填）
    department: str     # 部門（必填）
    email: str          # 電子郵件（必填）
    job_title: Optional[str] = None   # 職稱（選填）
    phone: Optional[str] = None       # 電話（選填）
```

### 核心函數

#### 1. `get_user_by_id(user_id: str) -> Optional[UserInfo]`

透過 user_id 查詢使用者資料。

```python
from shared.user_service import get_user_by_id

user = await get_user_by_id("EMP001")
if user:
    print(f"找到使用者: {user.user_name}")
else:
    print("使用者不存在")
```

> **注意**: 目前使用模擬資料庫，實際應用中請替換為 MCP Tool 或企業 API 呼叫。

#### 2. `get_user_by_id_or_create_guest(user_id: str) -> UserInfo`

查詢使用者，找不到時自動建立訪客身份。

```python
from shared.user_service import get_user_by_id_or_create_guest

# 永遠會返回 UserInfo，不會是 None
user = await get_user_by_id_or_create_guest("UNKNOWN_ID")
# user.user_name = "訪客_UNKNOWN_ID"
```

#### 3. `get_user_state_dict(user: UserInfo) -> dict`

將 UserInfo 轉換為可注入 Session state 的字典。

```python
from shared.user_service import get_user_state_dict

state = get_user_state_dict(user)
# {
#   "user_id": "EMP001",
#   "user_name": "王小明",
#   "department": "資訊部",
#   "email": "wang@company.com",
#   "is_registered": True  ← 自動加入註冊標記
# }
```

#### 4. `create_user_validation_callback(...)` 

建立共用的 `before_tool_callback` 函數。

```python
from shared.user_service import create_user_validation_callback

# 方式 1: 只驗證特定工具
callback = create_user_validation_callback(
    tools_requiring_user=["book_room", "get_my_bookings", "cancel_booking"]
)

# 方式 2: 驗證所有工具
callback = create_user_validation_callback()

# 方式 3: 自訂錯誤訊息
callback = create_user_validation_callback(
    tools_requiring_user=["submit_expense"],
    error_message="請先登入報銷系統才能進行此操作。"
)
```

---

## API Server 整合

### 關鍵程式碼

在 `api_server.py` 的 `get_or_create_session` 函數中：

```python
from shared.user_service import (
    get_user_by_id_or_create_guest,
    get_user_state_dict,
)

async def get_or_create_session(
    agent_id: str,
    user_id: str,
    session_id: Optional[str] = None
) -> tuple[str, UserInfo]:
    """取得或建立 Session，並自動注入使用者資料"""
    
    # 1. 查詢使用者資料
    user_info = await get_user_by_id_or_create_guest(user_id)
    
    # 2. 建立 Session 並注入使用者資料到 state
    user_state = get_user_state_dict(user_info)
    
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=new_session_id,
        state=user_state,  # ← 使用者資料注入到這裡
    )
    
    return new_session_id, user_info
```

### API 回應

```json
{
  "agent_id": "meeting_room",
  "response": "王小明您好！已成功為您預約...",
  "session_id": "abc-123-def",
  "user_id": "EMP001",
  "user_name": "王小明"  // ← 回傳使用者姓名供前端顯示
}
```

---

## Agent 端設定

### 完整範例

```python
from google.adk.agents import Agent
from google.adk.tools.tool_context import ToolContext
from shared.user_service import create_user_validation_callback

# 1. 建立查詢當前使用者的工具（可選）
def get_current_user(tool_context: ToolContext) -> dict:
    """查詢目前登入的使用者資料"""
    if not tool_context.state.get("is_registered"):
        return {"status": "error", "message": "無法取得使用者資料"}
    
    return {
        "status": "success",
        "user_info": {
            "user_id": tool_context.state.get("user_id"),
            "user_name": tool_context.state.get("user_name"),
            "department": tool_context.state.get("department"),
            "email": tool_context.state.get("email"),
        },
    }

# 2. 建立驗證 callback
user_validation_callback = create_user_validation_callback(
    tools_requiring_user=["book_room", "get_my_bookings", "cancel_booking"]
)

# 3. 定義 Agent
root_agent = Agent(
    name="meeting_room_agent",
    model=azure_model,
    instruction="""
    使用者資料已由系統自動提供，你可以透過 get_current_user 查詢。
    **不需要詢問使用者的員工編號**，系統會自動使用。
    """,
    tools=[
        get_current_user,
        list_buildings,
        list_available_rooms,
        book_room,
        get_my_bookings,
        cancel_booking,
    ],
    before_tool_callback=user_validation_callback,  # ← 關鍵設定
)
```

### Instruction 建議寫法

```markdown
## ✅ 使用者身份
使用者資料已由系統自動提供，你可以透過 `get_current_user` 查詢目前使用者的：
- 員工編號 (user_id)
- 姓名 (user_name)
- 部門 (department)
- 電子郵件 (email)

**你不需要詢問使用者的基本資料**，系統已經知道他們是誰。
```

---

## 使用範例

### Python requests

```python
import requests

response = requests.post(
    "http://localhost:8000/agents/meeting_room/chat",
    json={
        "user_id": "EMP001",  # ← 只需傳這個
        "message": "幫我預約明天 A 棟 10:00-11:00 的大會議室，主題是專案會議"
    }
)

result = response.json()
print(f"回應: {result['response']}")
print(f"使用者: {result['user_name']}")
```

### LangChain Tool

```python
from langchain.tools import Tool
import requests

def call_meeting_agent(message: str) -> str:
    """呼叫會議室預約 Agent"""
    # user_id 從您的身份驗證系統取得
    response = requests.post(
        "http://localhost:8000/agents/meeting_room/chat",
        json={
            "user_id": current_user.employee_id,
            "message": message,
        }
    )
    return response.json()["response"]

meeting_tool = Tool(
    name="meeting_room_booking",
    description="預約、查詢或取消會議室。使用者身份會自動識別。",
    func=call_meeting_agent,
)
```

### cURL

```bash
curl -X POST "http://localhost:8000/agents/meeting_room/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "EMP001",
    "message": "查詢我的預約"
  }'
```

---

## 擴展指南

### 替換為真正的 MCP Tool

修改 `shared/user_service.py` 中的 `get_user_by_id` 函數：

```python
async def get_user_by_id(user_id: str) -> Optional[UserInfo]:
    """透過 MCP Tool 查詢使用者資料"""
    
    # 呼叫 MCP Tool
    result = await mcp_client.call_tool(
        "get_user_info",
        {"user_id": user_id}
    )
    
    if result.get("status") == "error":
        return None
    
    data = result.get("user_info", {})
    return UserInfo(
        user_id=data["user_id"],
        user_name=data["user_name"],
        department=data["department"],
        email=data["email"],
        job_title=data.get("job_title"),
        phone=data.get("phone"),
    )
```

### 新增更多使用者欄位

1. 修改 `UserInfo` 資料類別：

```python
@dataclass
class UserInfo:
    user_id: str
    user_name: str
    department: str
    email: str
    job_title: Optional[str] = None
    phone: Optional[str] = None
    manager_id: Optional[str] = None      # 新增
    cost_center: Optional[str] = None     # 新增
```

2. Agent 的 `get_current_user` 工具會自動包含新欄位。

### 建立新的 Agent

```python
from shared.user_service import create_user_validation_callback

# 報銷系統 Agent
expense_callback = create_user_validation_callback(
    tools_requiring_user=["submit_expense", "approve_expense", "reject_expense"],
    error_message="請先登入報銷系統。"
)

expense_agent = Agent(
    name="expense_agent",
    model=azure_model,
    instruction="...",
    tools=[submit_expense, approve_expense, ...],
    before_tool_callback=expense_callback,
)
```

---

## 常見問題

### Q: 如果使用者不存在怎麼辦？

A: 系統會自動建立訪客身份：
```python
UserInfo(
    user_id="UNKNOWN_ID",
    user_name="訪客_UNKNOWN_ID",
    department="未知",
    email="UNKNOWN_ID@guest.local"
)
```

### Q: 如何驗證所有工具都需要使用者？

A: 不傳入 `tools_requiring_user` 參數：
```python
callback = create_user_validation_callback()  # 驗證所有工具
```

### Q: 使用者資料會保存多久？

A: 資料存在 Session state 中，與 Session 生命週期相同。使用 `InMemorySessionService` 時，伺服器重啟後會清除。

### Q: 可以在對話中途更新使用者資料嗎？

A: 可以，在 `get_or_create_session` 中，如果 Session 已存在，會自動更新 state 中的使用者資料：
```python
if session:
    user_state = get_user_state_dict(user_info)
    for key, value in user_state.items():
        session.state[key] = value
```

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `shared/user_service.py` | 共用使用者服務模組 |
| `shared/__init__.py` | 模組匯出設定 |
| `api_server.py` | FastAPI 伺服器，處理使用者資料注入 |
| `meeting_room_agent/agent.py` | 會議室預約 Agent 範例 |
