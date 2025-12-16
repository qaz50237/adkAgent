"""
自訂 FastAPI 伺服器（多 Agent 版本）
支援動態載入和呼叫多個 ADK Agent
自動透過 userId 查詢使用者資料並注入 Session State
"""

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

# 載入共用的 User Service
from shared.user_service import (
    get_user_by_id,
    get_user_by_id_or_create_guest,
    get_user_state_dict,
    UserInfo,
)

# 載入環境變數
load_dotenv()


# ============================================================================
# Logger 美化輸出
# ============================================================================

class AgentLogger:
    """Agent 執行過程的美化 Logger"""
    
    # ANSI 顏色碼
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "magenta": "\033[95m",
        "cyan": "\033[96m",
        "white": "\033[97m",
        "bg_blue": "\033[44m",
        "bg_green": "\033[42m",
        "bg_yellow": "\033[43m",
        "bg_magenta": "\033[45m",
    }
    
    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]
    
    @staticmethod
    def _colorize(text: str, *colors: str) -> str:
        color_codes = "".join(AgentLogger.COLORS.get(c, "") for c in colors)
        return f"{color_codes}{text}{AgentLogger.COLORS['reset']}"
    
    @staticmethod
    def _truncate(text: str, max_len: int = 200) -> str:
        if len(text) > max_len:
            return text[:max_len] + "..."
        return text
    
    @staticmethod
    def _format_json(data: Any, indent: int = 2) -> str:
        try:
            if isinstance(data, str):
                return data
            return json.dumps(data, ensure_ascii=False, indent=indent, default=str)
        except:
            return str(data)
    
    @classmethod
    def header(cls, title: str, agent_id: str, user_id: str, session_id: str):
        """印出請求標頭"""
        line = "═" * 70
        print(f"\n{cls._colorize(line, 'cyan')}")
        print(cls._colorize(f"  🤖 {title}", "cyan", "bold"))
        print(cls._colorize(line, 'cyan'))
        print(f"  {cls._colorize('⏰ Time:', 'dim')}     {cls._timestamp()}")
        print(f"  {cls._colorize('🎯 Agent:', 'dim')}    {cls._colorize(agent_id, 'green', 'bold')}")
        print(f"  {cls._colorize('👤 User:', 'dim')}     {user_id}")
        print(f"  {cls._colorize('🔗 Session:', 'dim')}  {session_id[:8]}...")
        print(cls._colorize(line, 'cyan'))
    
    @classmethod
    def request(cls, message: str):
        """印出使用者請求"""
        print(f"\n  {cls._colorize('📤 USER REQUEST', 'yellow', 'bold')}")
        print(f"  {cls._colorize('┌' + '─' * 66, 'yellow')}")
        for line in message.split('\n'):
            print(f"  {cls._colorize('│', 'yellow')} {line}")
        print(f"  {cls._colorize('└' + '─' * 66, 'yellow')}")
    
    @classmethod
    def tool_call(cls, tool_name: str, arguments: Dict[str, Any]):
        """印出 Tool 呼叫"""
        print(f"\n  {cls._colorize('🔧 TOOL CALL', 'magenta', 'bold')}")
        print(f"  {cls._colorize('┌' + '─' * 66, 'magenta')}")
        print(f"  {cls._colorize('│', 'magenta')} {cls._colorize('Tool:', 'dim')} {cls._colorize(tool_name, 'magenta', 'bold')}")
        print(f"  {cls._colorize('│', 'magenta')} {cls._colorize('Arguments:', 'dim')}")
        for key, value in arguments.items():
            val_str = cls._truncate(str(value), 50)
            print(f"  {cls._colorize('│', 'magenta')}   • {cls._colorize(key, 'cyan')}: {val_str}")
        print(f"  {cls._colorize('└' + '─' * 66, 'magenta')}")
    
    @classmethod
    def tool_result(cls, tool_name: str, result: Any):
        """印出 Tool 結果"""
        print(f"\n  {cls._colorize('📋 TOOL RESULT', 'blue', 'bold')}")
        print(f"  {cls._colorize('┌' + '─' * 66, 'blue')}")
        print(f"  {cls._colorize('│', 'blue')} {cls._colorize('Tool:', 'dim')} {tool_name}")
        print(f"  {cls._colorize('│', 'blue')} {cls._colorize('Result:', 'dim')}")
        
        result_str = cls._format_json(result)
        for line in result_str.split('\n')[:10]:  # 限制輸出行數
            truncated = cls._truncate(line, 60)
            print(f"  {cls._colorize('│', 'blue')}   {truncated}")
        if result_str.count('\n') > 10:
            print(f"  {cls._colorize('│', 'blue')}   {cls._colorize('... (truncated)', 'dim')}")
        print(f"  {cls._colorize('└' + '─' * 66, 'blue')}")
    
    @classmethod
    def response(cls, text: str):
        """印出 Agent 回應"""
        print(f"\n  {cls._colorize('📥 AGENT RESPONSE', 'green', 'bold')}")
        print(f"  {cls._colorize('┌' + '─' * 66, 'green')}")
        lines = text.split('\n')
        for line in lines[:15]:  # 限制輸出行數
            truncated = cls._truncate(line, 64)
            print(f"  {cls._colorize('│', 'green')} {truncated}")
        if len(lines) > 15:
            print(f"  {cls._colorize('│', 'green')} {cls._colorize('... (truncated)', 'dim')}")
        print(f"  {cls._colorize('└' + '─' * 66, 'green')}")
    
    @classmethod
    def footer(cls, duration_ms: float):
        """印出請求結尾"""
        line = "═" * 70
        print(f"\n  {cls._colorize(f'✅ Completed in {duration_ms:.0f}ms', 'green')}")
        print(f"{cls._colorize(line, 'cyan')}\n")
    
    @classmethod
    def error(cls, error: str):
        """印出錯誤"""
        print(f"\n  {cls._colorize('❌ ERROR', 'red', 'bold')}")
        print(f"  {cls._colorize('┌' + '─' * 66, 'red')}")
        for line in str(error).split('\n'):
            print(f"  {cls._colorize('│', 'red')} {line}")
        print(f"  {cls._colorize('└' + '─' * 66, 'red')}")
    
    @classmethod
    def event(cls, event_type: str, details: str = ""):
        """印出一般事件"""
        print(f"  {cls._colorize('→', 'dim')} {cls._colorize(event_type, 'cyan')}: {details}")
    
    @classmethod
    def debug_event(cls, event: Any):
        """Debug: 印出 event 的完整結構"""
        print(f"\n  {cls._colorize('🔍 DEBUG EVENT', 'yellow', 'bold')}")
        print(f"  {cls._colorize('┌' + '─' * 66, 'yellow')}")
        print(f"  {cls._colorize('│', 'yellow')} Type: {type(event).__name__}")
        
        # 列出所有屬性
        for attr in dir(event):
            if not attr.startswith('_'):
                try:
                    val = getattr(event, attr)
                    if not callable(val) and val is not None:
                        val_str = cls._truncate(str(val), 50)
                        print(f"  {cls._colorize('│', 'yellow')}   {cls._colorize(attr, 'cyan')}: {val_str}")
                except:
                    pass
        print(f"  {cls._colorize('└' + '─' * 66, 'yellow')}")


# Debug 模式開關
DEBUG_MODE = False  # 設為 True 可看到完整 event 結構

logger = AgentLogger()

# ============================================================================
# Agent 註冊表 - 在此註冊所有可用的 Agent
# ============================================================================

def load_agents() -> Dict[str, Dict[str, Any]]:
    """
    載入所有可用的 Agent
    新增 Agent 時，只需在此函數中 import 並加入 registry
    
    Returns:
        Dict[str, Dict]: {
            "agent_id": {
                "agent": Agent 實例,
                "name": 顯示名稱,
                "description": 描述
            }
        }
    """
    registry: Dict[str, Dict[str, Any]] = {}
    
    # === 會議室預約 Agent ===
    try:
        from meeting_room_agent import root_agent as meeting_room_agent
        registry["meeting_room"] = {
            "agent": meeting_room_agent,
            "name": "會議室預約助理",
            "description": "協助查詢、預約和管理會議室",
        }
        print("[✓] 已載入: meeting_room (會議室預約助理)")
    except ImportError as e:
        print(f"[✗] 無法載入 meeting_room_agent: {e}")
    
    # === 天氣/時間助理 Agent ===
    try:
        from my_agent.agent import root_agent as assistant_agent
        registry["assistant"] = {
            "agent": assistant_agent,
            "name": "智慧助理",
            "description": "查詢天氣和時間資訊",
        }
        print("[✓] 已載入: assistant (智慧助理)")
    except ImportError as e:
        print(f"[✗] 無法載入 my_agent: {e}")
    
    # ============================================================
    # 🔽 A2A 和工作流範例 Agents 🔽
    # ============================================================
    
    # === IT 服務台 Agent (A2A Coordinator Pattern) ===
    try:
        from it_helpdesk_agent import root_agent as it_helpdesk_agent
        registry["it_helpdesk"] = {
            "agent": it_helpdesk_agent,
            "name": "IT 服務台",
            "description": "A2A 示範：協調網路、帳號、硬體、軟體等子 Agent",
        }
        print("[✓] 已載入: it_helpdesk (IT 服務台 - A2A 示範)")
    except ImportError as e:
        print(f"[✗] 無法載入 it_helpdesk_agent: {e}")
    
    # === 報銷審批 Agent (Sequential Workflow) ===
    try:
        from expense_agent import root_agent as expense_agent
        registry["expense"] = {
            "agent": expense_agent,
            "name": "報銷審批",
            "description": "Sequential 工作流：提交 → 主管審核 → 總監審核 → 財務 → 付款",
        }
        print("[✓] 已載入: expense (報銷審批 - Sequential Workflow)")
    except ImportError as e:
        print(f"[✗] 無法載入 expense_agent: {e}")
    
    # === 研究助理 Agent (Parallel Workflow) ===
    try:
        from research_agent import root_agent as research_agent
        registry["research"] = {
            "agent": research_agent,
            "name": "研究助理",
            "description": "Parallel 工作流：同時搜尋新聞、論文、市場數據並彙整報告",
        }
        print("[✓] 已載入: research (研究助理 - Parallel Workflow)")
    except ImportError as e:
        print(f"[✗] 無法載入 research_agent: {e}")
    
    # === 客服工單 Agent (Loop Workflow) ===
    try:
        from ticket_agent import root_agent as ticket_agent
        registry["ticket"] = {
            "agent": ticket_agent,
            "name": "客服工單",
            "description": "Loop 工作流：工單生命週期管理，狀態循環追蹤",
        }
        print("[✓] 已載入: ticket (客服工單 - Loop Workflow)")
    except ImportError as e:
        print(f"[✗] 無法載入 ticket_agent: {e}")
    
    # === 訂單處理 Agent (Human-in-the-Loop Workflow) ===
    try:
        from order_agent import root_agent as order_agent
        registry["order"] = {
            "agent": order_agent,
            "name": "訂單處理",
            "description": "Human-in-the-Loop：自動化 + 人工審核的訂單處理流程",
        }
        print("[✓] 已載入: order (訂單處理 - Human-in-the-Loop)")
    except ImportError as e:
        print(f"[✗] 無法載入 order_agent: {e}")
    
    # ============================================================
    
    return registry


# 全域 Agent 註冊表
AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {}

# Session 管理
session_service = InMemorySessionService()

# ============================================================================
# Pydantic Models
# ============================================================================

class AgentInfo(BaseModel):
    """Agent 資訊"""
    agent_id: str
    name: str
    description: str


class ChatRequest(BaseModel):
    """對話請求"""
    message: str
    user_id: str  # 必填：前端系統傳入的 userId
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    """對話回應"""
    agent_id: str
    response: str
    session_id: str
    user_id: str
    user_name: Optional[str] = None  # 回傳使用者姓名供前端顯示


class SessionInfo(BaseModel):
    """Session 資訊"""
    agent_id: str
    session_id: str
    user_id: str


# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """應用程式生命週期管理"""
    global AGENT_REGISTRY
    
    print("=" * 60)
    print("多 Agent API 伺服器啟動中...")
    print("=" * 60)
    
    # 載入所有 Agent
    AGENT_REGISTRY = load_agents()
    
    print("=" * 60)
    print(f"共載入 {len(AGENT_REGISTRY)} 個 Agent")
    print("伺服器已就緒！")
    print("=" * 60)
    
    yield
    
    print("伺服器已關閉")


app = FastAPI(
    title="多 Agent API 伺服器",
    description="""
## 支援多個 ADK Agent 的 FastAPI 伺服器

### 功能
- 動態載入多個 Agent
- 每個 Agent 有獨立的對話端點
- 支援 Session 管理，維持對話上下文
- 支援串流式回應 (SSE)

### 使用流程
1. `GET /agents` - 查看所有可用的 Agent
2. `POST /agents/{agent_id}/chat` - 與指定 Agent 對話
    """,
    version="2.0.0",
    lifespan=lifespan,
)

# CORS 設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_agent(agent_id: str) -> Agent:
    """取得指定的 Agent"""
    if agent_id not in AGENT_REGISTRY:
        available = list(AGENT_REGISTRY.keys())
        raise HTTPException(
            status_code=404,
            detail=f"找不到 Agent '{agent_id}'。可用的 Agent: {available}"
        )
    return AGENT_REGISTRY[agent_id]["agent"]


async def get_or_create_session(
    agent_id: str,
    user_id: str,
    session_id: Optional[str] = None
) -> tuple[str, UserInfo]:
    """
    取得或建立 Session，並自動注入使用者資料到 state
    
    Returns:
        tuple[str, UserInfo]: (session_id, user_info)
    """
    app_name = f"agent_{agent_id}"
    
    # 1. 透過 userId 查詢使用者資料（呼叫 MCP Tool / 企業 API）
    user_info = await get_user_by_id_or_create_guest(user_id)
    
    # 2. 檢查 session 是否已存在
    if session_id:
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if session:
            # Session 已存在，更新使用者資料到 state（確保最新）
            user_state = get_user_state_dict(user_info)
            for key, value in user_state.items():
                session.state[key] = value
            return session_id, user_info
    
    # 3. 建立新 Session，並初始化使用者資料到 state
    new_session_id = session_id or str(uuid.uuid4())
    user_state = get_user_state_dict(user_info)
    
    await session_service.create_session(
        app_name=app_name,
        user_id=user_id,
        session_id=new_session_id,
        state=user_state,  # ✅ 使用者資料注入到 state
    )
    
    logger.event("User Registered", f"{user_info.user_name} ({user_id}) - {user_info.department}")
    
    return new_session_id, user_info


async def run_agent(
    agent_id: str,
    user_id: str,
    session_id: str,
    message: str
) -> str:
    """執行 Agent 並取得回應（含詳細 logging）"""
    import time
    start_time = time.time()
    
    agent = get_agent(agent_id)
    app_name = f"agent_{agent_id}"
    
    # 印出請求標頭
    logger.header("AGENT INVOCATION", agent_id, user_id, session_id)
    logger.request(message)
    
    runner = Runner(
        agent=agent,
        app_name=app_name,
        session_service=session_service,
    )
    
    from google.genai import types
    user_message = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )
    
    response_parts = []
    
    try:
        async for event in runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
        ):
            event_type = type(event).__name__
            
            # Debug 模式：印出所有 event 結構
            if DEBUG_MODE:
                logger.debug_event(event)
            
            # 偵測所有可能的 Tool/Function Call 屬性
            # 檢查 function_calls (直接屬性)
            if hasattr(event, 'function_calls') and event.function_calls:
                for fc in event.function_calls:
                    tool_name = getattr(fc, 'name', None) or getattr(fc, 'id', str(fc))
                    tool_args = getattr(fc, 'args', None) or getattr(fc, 'arguments', {})
                    if not isinstance(tool_args, dict):
                        try:
                            tool_args = dict(tool_args) if tool_args else {}
                        except:
                            tool_args = {"raw": str(tool_args)}
                    logger.tool_call(tool_name, tool_args)
            
            # 檢查 content.parts 中的 function_call
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts') and event.content.parts:
                    for part in event.content.parts:
                        # Function Call in part
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            tool_name = getattr(fc, 'name', 'unknown')
                            tool_args = getattr(fc, 'args', {})
                            if not isinstance(tool_args, dict):
                                try:
                                    tool_args = dict(tool_args) if tool_args else {}
                                except:
                                    tool_args = {"raw": str(tool_args)}
                            logger.tool_call(tool_name, tool_args)
                        
                        # Function Response in part
                        if hasattr(part, 'function_response') and part.function_response:
                            fr = part.function_response
                            tool_name = getattr(fr, 'name', 'unknown')
                            tool_result = getattr(fr, 'response', None) or getattr(fr, 'result', str(fr))
                            logger.tool_result(tool_name, tool_result)
            
            # 檢查 function_responses (直接屬性)
            if hasattr(event, 'function_responses') and event.function_responses:
                for fr in event.function_responses:
                    tool_name = getattr(fr, 'name', 'unknown')
                    tool_result = getattr(fr, 'response', None) or getattr(fr, 'result', str(fr))
                    logger.tool_result(tool_name, tool_result)
            
            # 檢查 actions (ADK 特有)
            if hasattr(event, 'actions') and event.actions:
                if hasattr(event.actions, 'tool_calls') and event.actions.tool_calls:
                    for tc in event.actions.tool_calls:
                        tool_name = getattr(tc, 'name', None) or getattr(tc, 'tool', 'unknown')
                        tool_args = getattr(tc, 'args', None) or getattr(tc, 'arguments', {})
                        if not isinstance(tool_args, dict):
                            tool_args = {"raw": str(tool_args)}
                        logger.tool_call(tool_name, tool_args)
            
            # 檢查 tool_calls (直接屬性)
            if hasattr(event, 'tool_calls') and event.tool_calls:
                for tc in event.tool_calls:
                    tool_name = getattr(tc, 'name', None) or getattr(tc, 'function', {}).get('name', 'unknown')
                    tool_args = getattr(tc, 'args', None) or getattr(tc, 'function', {}).get('arguments', {})
                    if not isinstance(tool_args, dict):
                        tool_args = {"raw": str(tool_args)}
                    logger.tool_call(tool_name, tool_args)
            
            # 檢查 tool_results (直接屬性)
            if hasattr(event, 'tool_results') and event.tool_results:
                for tr in event.tool_results:
                    tool_name = getattr(tr, 'name', 'unknown')
                    tool_result = getattr(tr, 'result', None) or getattr(tr, 'content', str(tr))
                    logger.tool_result(tool_name, tool_result)
            
            # Agent 文字回應
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response_parts.append(part.text)
        
        final_response = "".join(response_parts) if response_parts else "抱歉，我無法處理這個請求。"
        
        # 印出最終回應
        logger.response(final_response)
        
        # 印出結尾
        duration_ms = (time.time() - start_time) * 1000
        logger.footer(duration_ms)
        
        return final_response
        
    except Exception as e:
        logger.error(str(e))
        raise


# ============================================================================
# API Endpoints - 通用
# ============================================================================

@app.get("/", tags=["General"])
async def root():
    """API 首頁"""
    return {
        "message": "多 Agent API 伺服器",
        "version": "2.0.0",
        "docs": "/docs",
        "available_agents": list(AGENT_REGISTRY.keys()),
    }


@app.get("/health", tags=["General"])
async def health_check():
    """健康檢查"""
    return {
        "status": "healthy",
        "agents_loaded": len(AGENT_REGISTRY),
        "available_agents": list(AGENT_REGISTRY.keys()),
    }


# ============================================================================
# API Endpoints - Agent 管理
# ============================================================================

@app.get("/agents", response_model=List[AgentInfo], tags=["Agents"])
async def list_agents():
    """
    列出所有可用的 Agent
    """
    return [
        AgentInfo(
            agent_id=agent_id,
            name=info["name"],
            description=info["description"],
        )
        for agent_id, info in AGENT_REGISTRY.items()
    ]


@app.get("/agents/{agent_id}", response_model=AgentInfo, tags=["Agents"])
async def get_agent_info(
    agent_id: str = Path(..., description="Agent ID")
):
    """
    取得指定 Agent 的資訊
    """
    if agent_id not in AGENT_REGISTRY:
        raise HTTPException(status_code=404, detail=f"找不到 Agent '{agent_id}'")
    
    info = AGENT_REGISTRY[agent_id]
    return AgentInfo(
        agent_id=agent_id,
        name=info["name"],
        description=info["description"],
    )


# ============================================================================
# API Endpoints - Session 管理
# ============================================================================

@app.post("/agents/{agent_id}/sessions", response_model=SessionInfo, tags=["Sessions"])
async def create_session(
    agent_id: str = Path(..., description="Agent ID"),
    user_id: str = Query("default_user", description="使用者 ID"),
):
    """
    為指定 Agent 建立新的對話 Session
    """
    # 驗證 Agent 存在
    get_agent(agent_id)
    
    session_id = await get_or_create_session(agent_id, user_id)
    return SessionInfo(
        agent_id=agent_id,
        session_id=session_id,
        user_id=user_id,
    )


# ============================================================================
# API Endpoints - 對話
# ============================================================================

@app.post("/agents/{agent_id}/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_with_agent(
    request: ChatRequest,
    agent_id: str = Path(..., description="Agent ID"),
):
    """
    與指定的 Agent 對話
    
    - **agent_id**: Agent 識別碼（從 /agents 取得）
    - **message**: 使用者的訊息
    - **user_id**: 員工編號（系統會自動查詢使用者資料）
    - **session_id**: Session ID（可選，用於維持對話上下文）
    
    系統會自動：
    1. 透過 user_id 查詢使用者基本資料（姓名、部門、email 等）
    2. 將使用者資料注入到 Agent 的 session state
    3. Agent 可直接使用這些資料，不需使用者再次輸入
    """
    try:
        # 驗證 Agent 存在
        get_agent(agent_id)
        
        # 取得或建立 session（自動查詢並注入使用者資料）
        session_id, user_info = await get_or_create_session(
            agent_id=agent_id,
            user_id=request.user_id,
            session_id=request.session_id,
        )
        
        # 執行 Agent
        response = await run_agent(
            agent_id=agent_id,
            user_id=request.user_id,
            session_id=session_id,
            message=request.message,
        )
        
        return ChatResponse(
            agent_id=agent_id,
            response=response,
            session_id=session_id,
            user_id=request.user_id,
            user_name=user_info.user_name,  # 回傳使用者姓名
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/chat/stream", tags=["Chat"])
async def chat_stream_with_agent(
    request: ChatRequest,
    agent_id: str = Path(..., description="Agent ID"),
):
    """
    與指定的 Agent 進行串流式對話（SSE）
    即時返回 Agent 的回應
    
    系統會自動透過 user_id 查詢使用者資料並注入
    """
    # 驗證 Agent 存在
    agent = get_agent(agent_id)
    app_name = f"agent_{agent_id}"
    
    async def event_generator():
        try:
            # 取得或建立 session（自動查詢並注入使用者資料）
            session_id, user_info = await get_or_create_session(
                agent_id=agent_id,
                user_id=request.user_id,
                session_id=request.session_id,
            )
            
            runner = Runner(
                agent=agent,
                app_name=app_name,
                session_service=session_service,
            )
            
            from google.genai import types
            user_message = types.Content(
                role="user",
                parts=[types.Part(text=request.message)],
            )
            
            async for event in runner.run_async(
                user_id=request.user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts'):
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                yield f"data: {part.text}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            yield f"data: Error: {str(e)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# ============================================================================
# 快捷端點 - 直接對話（不需要指定 agent_id 在 path）
# ============================================================================

@app.post("/chat", response_model=ChatResponse, tags=["Chat (Quick)"])
async def quick_chat(
    request: ChatRequest,
    agent_id: str = Query(..., description="Agent ID"),
):
    """
    快捷對話端點
    
    用法：POST /chat?agent_id=meeting_room
    """
    return await chat_with_agent(request, agent_id)


# ============================================================================
# 直接執行
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
