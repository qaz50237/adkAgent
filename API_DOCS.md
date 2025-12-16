# 多 Agent API 伺服器

基於 Google ADK 框架的多 Agent FastAPI 伺服器，支援動態載入和呼叫多個 AI Agent。

## 📁 專案結構

```
D:\Source\ADK\
├── api_server.py              # FastAPI 伺服器主程式
├── pyproject.toml             # 專案設定
├── .env                       # 環境變數設定
├── meeting_room_agent/        # 會議室預約 Agent
│   ├── __init__.py
│   ├── agent.py               # Agent 定義
│   └── tools.py               # 5 個 Tools 實作
└── my_agent/                  # 智慧助理 Agent
    ├── __init__.py
    └── agent.py               # Agent 定義
```

---

## 🚀 快速開始

### 1. 安裝依賴

```bash
uv sync
```

### 2. 設定環境變數

建立 `.env` 檔案：

```env
AZURE_OPENAI_API_KEY=your_api_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
```

### 3. 啟動伺服器

```bash
# 一般啟動
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000

# 開發模式（自動重載）
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 開啟 API 文件

瀏覽器訪問：http://127.0.0.1:8000/docs

---

## 📡 API 端點

### 通用端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `/` | GET | API 首頁 |
| `/health` | GET | 健康檢查 |
| `/docs` | GET | Swagger UI 文件 |

### Agent 管理

| 端點 | 方法 | 說明 |
|------|------|------|
| `/agents` | GET | 列出所有可用的 Agent |
| `/agents/{agent_id}` | GET | 取得指定 Agent 資訊 |

### Session 管理

| 端點 | 方法 | 說明 |
|------|------|------|
| `/agents/{agent_id}/sessions` | POST | 建立新的對話 Session |

### 對話

| 端點 | 方法 | 說明 |
|------|------|------|
| `/agents/{agent_id}/chat` | POST | 與指定 Agent 對話 |
| `/agents/{agent_id}/chat/stream` | POST | 串流式對話 (SSE) |
| `/chat?agent_id=xxx` | POST | 快捷對話端點 |

---

## 📝 API 使用範例

### 列出所有 Agent

```bash
curl http://127.0.0.1:8000/agents
```

**回應：**
```json
[
  {
    "agent_id": "meeting_room",
    "name": "會議室預約助理",
    "description": "協助查詢、預約和管理會議室"
  },
  {
    "agent_id": "assistant",
    "name": "智慧助理",
    "description": "查詢天氣和時間資訊"
  }
]
```

### 與 Agent 對話

```bash
curl -X POST http://127.0.0.1:8000/agents/meeting_room/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "有哪些大樓可以預約？",
    "user_id": "employee001"
  }'
```

**回應：**
```json
{
  "agent_id": "meeting_room",
  "response": "目前可預約的大樓如下：\n- A棟 - 總部大樓...",
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "user_id": "employee001"
}
```

### 使用 Session 維持對話上下文

```bash
# 第一次對話
curl -X POST http://127.0.0.1:8000/agents/meeting_room/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "有哪些大樓？",
    "user_id": "employee001"
  }'
# 回應會包含 session_id

# 後續對話帶上 session_id
curl -X POST http://127.0.0.1:8000/agents/meeting_room/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "A棟明天有空嗎？",
    "user_id": "employee001",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

### 串流式對話 (SSE)

```bash
curl -X POST http://127.0.0.1:8000/agents/meeting_room/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "查詢可預約大樓",
    "user_id": "employee001"
  }'
```

---

## 🤖 可用的 Agent

### 1. 會議室預約助理 (`meeting_room`)

協助使用者查詢、預約和管理會議室。

**功能 (Tools)：**

| Tool | 說明 | 參數 |
|------|------|------|
| `list_buildings` | 查詢所有可預約大樓 | 無 |
| `list_available_rooms` | 查詢指定大樓/日期的可用會議室 | `building_id`, `date` |
| `book_room` | 預約會議室 | `room_id`, `user_id`, `date`, `time_slot`, `title`, `attendees` |
| `get_my_bookings` | 查詢個人預約記錄 | `user_id` |
| `cancel_booking` | 取消預約 | `booking_id`, `user_id` |

**對話範例：**
```
用戶：有哪些大樓可以預約？
用戶：A棟明天有空嗎？
用戶：幫我預約 A-101，明天下午2點，開專案會議
用戶：我預約了什麼？
用戶：取消早上那場會議
```

### 2. 智慧助理 (`assistant`)

查詢天氣和時間資訊。

**功能 (Tools)：**

| Tool | 說明 | 參數 |
|------|------|------|
| `get_weather` | 查詢城市天氣 | `city` |
| `get_current_time` | 查詢城市時間 | `city` |

**對話範例：**
```
用戶：台北現在天氣如何？
用戶：東京現在幾點？
```

---

## 📊 Log 輸出格式

伺服器會在終端機輸出美化的執行 log：

```
══════════════════════════════════════════════════════════════════════
  🤖 AGENT INVOCATION
══════════════════════════════════════════════════════════════════════
  ⏰ Time:     10:15:23.456
  🎯 Agent:    meeting_room
  👤 User:     employee001
  🔗 Session:  a1b2c3d4...
══════════════════════════════════════════════════════════════════════

  📤 USER REQUEST
  ┌──────────────────────────────────────────────────────────────────
  │ 有哪些大樓可以預約？
  └──────────────────────────────────────────────────────────────────

  🔧 TOOL CALL
  ┌──────────────────────────────────────────────────────────────────
  │ Tool: list_buildings
  │ Arguments:
  └──────────────────────────────────────────────────────────────────

  📋 TOOL RESULT
  ┌──────────────────────────────────────────────────────────────────
  │ Tool: list_buildings
  │ Result:
  │   {"status": "success", "buildings": [...]}
  └──────────────────────────────────────────────────────────────────

  📥 AGENT RESPONSE
  ┌──────────────────────────────────────────────────────────────────
  │ 目前可預約的大樓如下：
  │ - A棟 - 總部大樓
  │ - B棟 - 研發中心
  │ - C棟 - 會議中心
  └──────────────────────────────────────────────────────────────────

  ✅ Completed in 5802ms
══════════════════════════════════════════════════════════════════════
```

### Log 區塊說明

| 區塊 | 圖示 | 顏色 | 說明 |
|------|------|------|------|
| Header | 🤖 | 青色 | Agent ID、User、Session、時間戳記 |
| User Request | 📤 | 黃色 | 使用者的輸入訊息（上行） |
| Tool Call | 🔧 | 紫色 | Agent 呼叫的 Tool 和參數 |
| Tool Result | 📋 | 藍色 | Tool 返回的結果 |
| Agent Response | 📥 | 綠色 | Agent 的最終回應（下行） |
| Error | ❌ | 紅色 | 錯誤訊息 |
| Footer | ✅ | 綠色 | 執行完成時間 (毫秒) |

### Debug 模式

如需查看完整的 ADK Event 結構，可在 `api_server.py` 中開啟：

```python
DEBUG_MODE = True
```

---

## 🆕 新增 Agent

### 步驟 1：建立 Agent 目錄

```
new_agent/
├── __init__.py
├── agent.py
└── tools.py (可選)
```

### 步驟 2：定義 Agent (`agent.py`)

```python
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
import os

# 設定模型
azure_model = LiteLlm(
    model=f"azure/{os.getenv('AZURE_OPENAI_DEPLOYMENT_NAME')}",
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_base=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

# 定義 Tool (可選)
def my_tool(param: str) -> dict:
    """Tool 說明"""
    return {"result": "..."}

# 定義 Agent (必須命名為 root_agent)
root_agent = Agent(
    name="new_agent",
    model=azure_model,
    description="Agent 描述",
    instruction="Agent 指令...",
    tools=[my_tool],  # 可選
)
```

### 步驟 3：匯出 Agent (`__init__.py`)

```python
from .agent import root_agent
__all__ = ["root_agent"]
```

### 步驟 4：註冊到 API 伺服器

編輯 `api_server.py` 的 `load_agents()` 函數：

```python
def load_agents() -> Dict[str, Dict[str, Any]]:
    registry: Dict[str, Dict[str, Any]] = {}
    
    # ... 現有的 Agent ...
    
    # === 新增的 Agent ===
    try:
        from new_agent import root_agent as new_agent
        registry["new_agent"] = {
            "agent": new_agent,
            "name": "新 Agent 名稱",
            "description": "新 Agent 描述",
        }
        print("[✓] 已載入: new_agent (新 Agent 名稱)")
    except ImportError as e:
        print(f"[✗] 無法載入 new_agent: {e}")
    
    return registry
```

### 步驟 5：重啟伺服器

```bash
# 如果使用 --reload，會自動重載
# 否則需要手動重啟
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000
```

---

## ⚙️ 環境變數

| 變數名稱 | 說明 | 範例 |
|----------|------|------|
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API 金鑰 | `abc123...` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI 端點 | `https://xxx.openai.azure.com/` |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | 部署名稱 | `gpt-4` |

---

## 🔧 開發指令

```bash
# 安裝依賴
uv sync

# 啟動開發伺服器（自動重載）
uv run uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

# 使用 ADK Web UI 測試單一 Agent
uv run adk web meeting_room_agent

# 執行 ADK CLI
uv run adk run meeting_room_agent
```

---

## 📦 依賴套件

```toml
[project]
dependencies = [
    "google-adk>=1.21.0",
    "litellm>=1.80.10",
    "python-dotenv>=1.2.1",
    "fastapi",
    "uvicorn",
]
```

---

## 📄 授權

MIT License
