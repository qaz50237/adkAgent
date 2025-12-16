"""
共用使用者服務模組
提供透過 userId 取得使用者基本資料的功能
以及共用的 before_tool_callback 驗證函數

此模組可被 api_server.py 和所有 Agent 共用
"""

from typing import Optional, Any
from dataclasses import dataclass, asdict


@dataclass
class UserInfo:
    """使用者基本資料"""
    user_id: str
    user_name: str
    department: str
    email: str
    job_title: Optional[str] = None
    phone: Optional[str] = None
    
    def to_dict(self) -> dict:
        """轉換為字典（用於注入 state）"""
        return {k: v for k, v in asdict(self).items() if v is not None}


# ============================================================================
# 模擬的使用者資料庫（實際應替換為 MCP Tool 呼叫）
# ============================================================================

# 模擬企業員工資料庫
_MOCK_USER_DATABASE = {
    "EMP001": UserInfo(
        user_id="EMP001",
        user_name="王小明",
        department="資訊部",
        email="wang.xiaoming@company.com",
        job_title="軟體工程師",
        phone="0912-345-678",
    ),
    "EMP002": UserInfo(
        user_id="EMP002",
        user_name="李小華",
        department="人資部",
        email="li.xiaohua@company.com",
        job_title="人資專員",
        phone="0923-456-789",
    ),
    "EMP003": UserInfo(
        user_id="EMP003",
        user_name="張大偉",
        department="業務部",
        email="zhang.dawei@company.com",
        job_title="業務經理",
        phone="0934-567-890",
    ),
    "EMP004": UserInfo(
        user_id="EMP004",
        user_name="陳美玲",
        department="財務部",
        email="chen.meiling@company.com",
        job_title="財務主管",
        phone="0945-678-901",
    ),
    "EMP005": UserInfo(
        user_id="EMP005",
        user_name="林志豪",
        department="研發部",
        email="lin.zhihao@company.com",
        job_title="技術總監",
        phone="0956-789-012",
    ),
}


# ============================================================================
# User Service - 核心服務函數
# ============================================================================

async def get_user_by_id(user_id: str) -> Optional[UserInfo]:
    """
    透過 userId 取得使用者基本資料
    
    實際應用中，這裡應該呼叫 MCP Tool 或企業 API
    
    Args:
        user_id: 員工編號
        
    Returns:
        UserInfo 或 None（如果找不到）
    """
    # TODO: 替換為實際的 MCP Tool 呼叫
    # 例如：
    # result = await mcp_client.call_tool("get_user_info", {"user_id": user_id})
    # return UserInfo(**result)
    
    # 目前使用模擬資料
    return _MOCK_USER_DATABASE.get(user_id.upper())


async def get_user_by_id_or_create_guest(user_id: str) -> UserInfo:
    """
    取得使用者資料，如果找不到則建立訪客身份
    
    Args:
        user_id: 員工編號或任意 ID
        
    Returns:
        UserInfo（一定會返回，找不到則為訪客）
    """
    user = await get_user_by_id(user_id)
    
    if user is None:
        # 建立訪客身份
        user = UserInfo(
            user_id=user_id,
            user_name=f"訪客_{user_id}",
            department="未知",
            email=f"{user_id}@guest.local",
        )
    
    return user


def get_user_state_dict(user: UserInfo) -> dict:
    """
    將 UserInfo 轉換為可注入 session state 的字典
    
    Args:
        user: UserInfo 物件
        
    Returns:
        包含 is_registered 標記的字典
    """
    state = user.to_dict()
    state["is_registered"] = True  # 標記為已註冊，供 Agent callback 檢查
    return state


# ============================================================================
# 共用的 Before Tool Callback - 驗證使用者並自動注入 user_id
# ============================================================================

def create_user_validation_callback(
    tools_requiring_user: list[str] | None = None,
    error_message: str | None = None,
):
    """
    建立使用者驗證的 before_tool_callback 函數
    
    ADK 的 before_tool_callback 使用關鍵字參數呼叫：
        callback(tool=tool, args=function_args, tool_context=tool_context)
    
    Args:
        tools_requiring_user: 需要驗證使用者的工具名稱列表，None 表示驗證所有工具
        error_message: 自訂錯誤訊息
        
    Returns:
        callback 函數，可直接傳給 Agent 的 before_tool_callback 參數
        
    使用範例:
        from shared.user_service import create_user_validation_callback
        
        root_agent = Agent(
            ...
            before_tool_callback=create_user_validation_callback(
                tools_requiring_user=["book_room", "get_my_bookings"]
            ),
        )
    
    注意事項:
        - 參數名稱必須是 tool, args, tool_context（ADK 使用關鍵字參數）
        - tool 是 BaseTool 物件，用 tool.name 取得工具名稱
        - tool_context.state 用於存取 Session state
    """
    default_error = (
        "⚠️ 無法取得使用者資料！\n\n"
        "請確認您已正確登入系統。如果問題持續，請聯繫 IT 支援。"
    )
    
    def validate_user_before_tool(
        tool: Any,              # BaseTool 物件，用 tool.name 取得工具名稱
        args: dict[str, Any],   # 工具參數
        tool_context: Any,      # ToolContext
        **kwargs,               # 接受其他可能的參數
    ) -> dict | None:
        """在執行工具前驗證使用者是否已註冊，並自動注入 user_id。"""
        
        # 取得工具名稱
        tool_name = getattr(tool, 'name', str(tool))
        
        # 如果有指定工具列表，只檢查這些工具
        if tools_requiring_user is not None and tool_name not in tools_requiring_user:
            return None  # 允許執行
        
        # 檢查是否已有使用者資料（由 api_server 注入）
        # ToolContext 有 state 屬性
        state = tool_context.state
        if not state.get("is_registered"):
            return {
                "status": "blocked",
                "error_message": error_message or default_error,
            }
        
        # ✅ 自動注入 user_id 到工具參數
        args["user_id"] = state.get("user_id")
        
        return None  # 允許執行
    
    return validate_user_before_tool


# 預設的驗證 callback（驗證所有工具）
default_user_validation_callback = create_user_validation_callback()


# ============================================================================
# MCP Tool 定義（可選：如果要讓 Agent 也能查詢使用者資料）
# ============================================================================

async def lookup_user_info(user_id: str) -> dict:
    """
    查詢使用者資訊（可作為 Agent Tool 使用）
    
    Args:
        user_id (str): 員工編號
        
    Returns:
        dict: 使用者資訊或錯誤訊息
    """
    user = await get_user_by_id(user_id)
    
    if user is None:
        return {
            "status": "error",
            "error_message": f"找不到員工編號 '{user_id}' 的使用者資料",
        }
    
    return {
        "status": "success",
        "user_info": user.to_dict(),
    }


# ============================================================================
# 使用範例
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def demo():
        # 查詢存在的使用者
        user = await get_user_by_id("EMP001")
        print(f"查詢 EMP001: {user}")
        
        # 查詢不存在的使用者（會建立訪客）
        guest = await get_user_by_id_or_create_guest("UNKNOWN123")
        print(f"查詢 UNKNOWN123: {guest}")
        
        # 取得 state 字典
        state = get_user_state_dict(user)
        print(f"State dict: {state}")
    
    asyncio.run(demo())
