"""
IT 服務台 Agent - 展示 A2A (Agent-to-Agent) 協作
展示：Coordinator 模式、條件路由、多 Agent 協作

工作流程：
┌─────────────────┐
│  IT 服務台總機   │ (Coordinator Agent)
│   (root_agent)  │
└────────┬────────┘
         │ 根據問題類型路由
    ┌────┼────┬────────┐
    ▼    ▼    ▼        ▼
┌──────┐┌──────┐┌──────┐┌──────┐
│ 網路 ││ 帳號 ││ 硬體 ││ 軟體 │
│ Agent││ Agent││ Agent││ Agent│
└──────┘└──────┘└──────┘└──────┘
"""

import os
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# ============================================================================
# 模擬資料庫
# ============================================================================

# 工單資料庫
TICKETS: dict[str, dict] = {}
_ticket_counter = 0

# 知識庫
KNOWLEDGE_BASE = {
    "wifi": {
        "problem": "無法連接 WiFi",
        "solution": "1. 確認 WiFi 開關已開啟\n2. 忘記網路後重新連接\n3. 重啟電腦\n4. 若仍無法連接，請聯繫 IT 部門",
    },
    "vpn": {
        "problem": "VPN 連線失敗",
        "solution": "1. 確認網路連線正常\n2. 檢查 VPN 帳密是否正確\n3. 嘗試更換 VPN 伺服器\n4. 重新安裝 VPN 客戶端",
    },
    "password": {
        "problem": "忘記密碼",
        "solution": "1. 使用自助密碼重設系統\n2. 點擊登入頁面的「忘記密碼」\n3. 透過 Email 驗證重設\n4. 若無法自助，請攜帶員工證至 IT 部門",
    },
    "email": {
        "problem": "無法收發郵件",
        "solution": "1. 檢查網路連線\n2. 確認郵箱容量未滿\n3. 嘗試網頁版郵箱\n4. 重新設定郵件帳戶",
    },
    "printer": {
        "problem": "無法列印",
        "solution": "1. 檢查印表機是否開機\n2. 確認紙張和墨水充足\n3. 重新安裝印表機驅動\n4. 嘗試其他印表機",
    },
}

# 設備庫存
HARDWARE_INVENTORY = {
    "laptop": {"name": "筆記型電腦", "available": 5},
    "monitor": {"name": "螢幕", "available": 10},
    "keyboard": {"name": "鍵盤", "available": 20},
    "mouse": {"name": "滑鼠", "available": 25},
    "headset": {"name": "耳機", "available": 15},
}


def _generate_ticket_id() -> str:
    global _ticket_counter
    _ticket_counter += 1
    return f"IT{datetime.now().strftime('%Y%m%d')}{_ticket_counter:04d}"


# ============================================================================
# 共用 Tools
# ============================================================================

def create_ticket(
    user_id: str,
    category: str,
    title: str,
    description: str,
    priority: str = "medium"
) -> dict:
    """建立 IT 服務工單。

    Args:
        user_id: 報修人員工編號
        category: 問題類別 (network/account/hardware/software)
        title: 問題標題
        description: 問題描述
        priority: 優先級 (low/medium/high/urgent)

    Returns:
        dict: 工單建立結果
    """
    ticket_id = _generate_ticket_id()
    TICKETS[ticket_id] = {
        "ticket_id": ticket_id,
        "user_id": user_id,
        "category": category,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now().isoformat(),
        "assigned_to": None,
        "resolution": None,
    }
    return {
        "status": "success",
        "ticket": TICKETS[ticket_id],
        "message": f"工單已建立，編號：{ticket_id}",
    }


def get_ticket_status(ticket_id: str) -> dict:
    """查詢工單狀態。

    Args:
        ticket_id: 工單編號

    Returns:
        dict: 工單狀態
    """
    if ticket_id not in TICKETS:
        return {"status": "error", "message": f"找不到工單 {ticket_id}"}
    return {"status": "success", "ticket": TICKETS[ticket_id]}


def search_knowledge_base(keyword: str) -> dict:
    """搜尋 IT 知識庫。

    Args:
        keyword: 搜尋關鍵字

    Returns:
        dict: 搜尋結果
    """
    results = []
    keyword_lower = keyword.lower()
    for key, article in KNOWLEDGE_BASE.items():
        if (keyword_lower in key or 
            keyword_lower in article["problem"].lower() or
            keyword_lower in article["solution"].lower()):
            results.append(article)
    
    if results:
        return {"status": "success", "articles": results}
    return {"status": "not_found", "message": "找不到相關知識庫文章"}


# ============================================================================
# 網路問題 Sub-Agent Tools
# ============================================================================

def diagnose_network(user_id: str, issue_type: str) -> dict:
    """診斷網路問題。

    Args:
        user_id: 使用者 ID
        issue_type: 問題類型 (wifi/vpn/internet/dns)

    Returns:
        dict: 診斷結果
    """
    diagnoses = {
        "wifi": {
            "diagnosis": "WiFi 連線問題",
            "possible_causes": ["WiFi 密碼錯誤", "訊號不良", "AP 故障"],
            "recommended_action": "嘗試重新連接或靠近 AP",
        },
        "vpn": {
            "diagnosis": "VPN 連線問題",
            "possible_causes": ["帳號密碼錯誤", "VPN 伺服器維護中", "防火牆阻擋"],
            "recommended_action": "確認帳密後重試，或嘗試其他 VPN 伺服器",
        },
        "internet": {
            "diagnosis": "網際網路連線問題",
            "possible_causes": ["ISP 問題", "路由器故障", "網路線鬆脫"],
            "recommended_action": "檢查網路線，重啟路由器",
        },
        "dns": {
            "diagnosis": "DNS 解析問題",
            "possible_causes": ["DNS 伺服器故障", "DNS 設定錯誤"],
            "recommended_action": "嘗試使用 8.8.8.8 作為 DNS",
        },
    }
    
    if issue_type in diagnoses:
        return {"status": "success", **diagnoses[issue_type]}
    return {"status": "error", "message": f"未知的問題類型：{issue_type}"}


def check_network_status() -> dict:
    """檢查公司網路狀態。

    Returns:
        dict: 網路狀態
    """
    return {
        "status": "success",
        "network_status": {
            "internal_network": "正常",
            "internet": "正常",
            "vpn_server_1": "正常",
            "vpn_server_2": "維護中",
            "wifi_floor_1": "正常",
            "wifi_floor_2": "正常",
            "wifi_floor_3": "訊號不穩",
        },
    }


# ============================================================================
# 帳號權限 Sub-Agent Tools
# ============================================================================

def reset_password(user_id: str, target_user_id: str) -> dict:
    """重設使用者密碼（發送重設連結）。

    Args:
        user_id: 請求者 ID
        target_user_id: 要重設密碼的使用者 ID

    Returns:
        dict: 重設結果
    """
    return {
        "status": "success",
        "message": f"已發送密碼重設連結至 {target_user_id} 的註冊郵箱",
        "note": "連結有效期限 24 小時",
    }


def request_system_access(
    user_id: str,
    system_name: str,
    access_level: str,
    reason: str
) -> dict:
    """申請系統權限。

    Args:
        user_id: 申請人 ID
        system_name: 系統名稱
        access_level: 權限等級 (read/write/admin)
        reason: 申請原因

    Returns:
        dict: 申請結果
    """
    request_id = f"ACC{datetime.now().strftime('%Y%m%d%H%M%S')}"
    return {
        "status": "success",
        "request_id": request_id,
        "message": "權限申請已提交，等待主管審核",
        "details": {
            "user_id": user_id,
            "system": system_name,
            "level": access_level,
            "reason": reason,
        },
    }


def check_user_permissions(user_id: str) -> dict:
    """查詢使用者目前的系統權限。

    Args:
        user_id: 使用者 ID

    Returns:
        dict: 權限列表
    """
    # 模擬權限資料
    permissions = {
        "email": "read/write",
        "erp": "read",
        "hr_system": "none",
        "file_server": "read/write",
        "source_control": "read/write",
    }
    return {
        "status": "success",
        "user_id": user_id,
        "permissions": permissions,
    }


# ============================================================================
# 硬體報修 Sub-Agent Tools
# ============================================================================

def report_hardware_issue(
    user_id: str,
    device_type: str,
    serial_number: str,
    issue_description: str
) -> dict:
    """報修硬體問題。

    Args:
        user_id: 報修人 ID
        device_type: 設備類型 (laptop/monitor/keyboard/mouse/printer)
        serial_number: 設備序號
        issue_description: 問題描述

    Returns:
        dict: 報修結果
    """
    ticket = create_ticket(
        user_id=user_id,
        category="hardware",
        title=f"{device_type} 故障報修",
        description=f"序號：{serial_number}\n問題：{issue_description}",
        priority="medium",
    )
    return {
        "status": "success",
        "ticket_id": ticket["ticket"]["ticket_id"],
        "message": "硬體報修單已建立，IT 人員將於 1-2 個工作天內聯繫您",
    }


def request_hardware(user_id: str, device_type: str, reason: str) -> dict:
    """申請硬體設備。

    Args:
        user_id: 申請人 ID
        device_type: 設備類型
        reason: 申請原因

    Returns:
        dict: 申請結果
    """
    if device_type not in HARDWARE_INVENTORY:
        return {"status": "error", "message": f"無此設備類型：{device_type}"}
    
    item = HARDWARE_INVENTORY[device_type]
    if item["available"] <= 0:
        return {
            "status": "out_of_stock",
            "message": f"{item['name']} 目前無庫存，已加入等待清單",
        }
    
    return {
        "status": "success",
        "message": f"{item['name']} 申請已提交",
        "available_stock": item["available"],
        "estimated_delivery": "2-3 個工作天",
    }


def check_hardware_inventory() -> dict:
    """查詢硬體庫存。

    Returns:
        dict: 庫存狀態
    """
    return {
        "status": "success",
        "inventory": [
            {"type": k, "name": v["name"], "available": v["available"]}
            for k, v in HARDWARE_INVENTORY.items()
        ],
    }


# ============================================================================
# 軟體問題 Sub-Agent Tools
# ============================================================================

def request_software_install(
    user_id: str,
    software_name: str,
    reason: str
) -> dict:
    """申請安裝軟體。

    Args:
        user_id: 申請人 ID
        software_name: 軟體名稱
        reason: 申請原因

    Returns:
        dict: 申請結果
    """
    approved_software = ["vscode", "chrome", "firefox", "7zip", "notepad++"]
    
    if software_name.lower() in approved_software:
        return {
            "status": "auto_approved",
            "message": f"{software_name} 是預核准軟體，將自動部署到您的電腦",
            "estimated_time": "30 分鐘內",
        }
    
    return {
        "status": "pending_approval",
        "message": f"{software_name} 需要主管審核，申請已提交",
        "request_id": f"SW{datetime.now().strftime('%Y%m%d%H%M%S')}",
    }


def troubleshoot_software(software_name: str, error_message: str) -> dict:
    """軟體問題排錯建議。

    Args:
        software_name: 軟體名稱
        error_message: 錯誤訊息

    Returns:
        dict: 排錯建議
    """
    return {
        "status": "success",
        "suggestions": [
            "1. 嘗試重新啟動軟體",
            "2. 清除軟體快取",
            "3. 檢查是否有更新版本",
            "4. 嘗試以系統管理員身份執行",
            "5. 重新安裝軟體",
        ],
        "note": "如果問題持續，請建立工單由 IT 人員協助",
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
# Sub-Agents 定義
# ============================================================================

network_agent = Agent(
    name="network_support_agent",
    model=azure_model,
    description="處理網路相關問題：WiFi、VPN、網路連線等",
    instruction="""你是網路支援專員，專門處理網路相關問題。
    
你可以：
1. 診斷網路問題 (diagnose_network)
2. 檢查公司網路狀態 (check_network_status)
3. 搜尋知識庫 (search_knowledge_base)
4. 建立工單 (create_ticket)

處理流程：
1. 先了解用戶的網路問題
2. 檢查公司網路狀態
3. 嘗試診斷問題
4. 提供解決方案
5. 如果無法解決，建立工單

請用繁體中文回答。""",
    tools=[
        diagnose_network,
        check_network_status,
        search_knowledge_base,
        create_ticket,
    ],
)

account_agent = Agent(
    name="account_support_agent",
    model=azure_model,
    description="處理帳號權限問題：密碼重設、權限申請等",
    instruction="""你是帳號權限專員，專門處理帳號和權限問題。
    
你可以：
1. 重設密碼 (reset_password)
2. 申請系統權限 (request_system_access)
3. 查詢用戶權限 (check_user_permissions)
4. 搜尋知識庫 (search_knowledge_base)
5. 建立工單 (create_ticket)

處理流程：
1. 確認用戶身份
2. 了解需求（重設密碼/申請權限）
3. 執行對應操作
4. 確認結果

請用繁體中文回答。""",
    tools=[
        reset_password,
        request_system_access,
        check_user_permissions,
        search_knowledge_base,
        create_ticket,
    ],
)

hardware_agent = Agent(
    name="hardware_support_agent",
    model=azure_model,
    description="處理硬體問題：設備報修、硬體申請等",
    instruction="""你是硬體支援專員，專門處理硬體相關問題。
    
你可以：
1. 報修硬體 (report_hardware_issue)
2. 申請硬體 (request_hardware)
3. 查詢庫存 (check_hardware_inventory)
4. 建立工單 (create_ticket)

處理流程：
1. 了解是報修還是申請
2. 如果是報修，收集設備資訊和問題描述
3. 如果是申請，確認設備類型和原因
4. 執行對應操作

請用繁體中文回答。""",
    tools=[
        report_hardware_issue,
        request_hardware,
        check_hardware_inventory,
        create_ticket,
    ],
)

software_agent = Agent(
    name="software_support_agent",
    model=azure_model,
    description="處理軟體問題：軟體安裝、軟體故障等",
    instruction="""你是軟體支援專員，專門處理軟體相關問題。
    
你可以：
1. 申請安裝軟體 (request_software_install)
2. 軟體問題排錯 (troubleshoot_software)
3. 搜尋知識庫 (search_knowledge_base)
4. 建立工單 (create_ticket)

處理流程：
1. 了解是安裝需求還是故障問題
2. 如果是安裝，確認軟體名稱和原因
3. 如果是故障，提供排錯建議
4. 如果無法解決，建立工單

請用繁體中文回答。""",
    tools=[
        request_software_install,
        troubleshoot_software,
        search_knowledge_base,
        create_ticket,
    ],
)


# ============================================================================
# Coordinator Agent (Root Agent)
# ============================================================================

root_agent = Agent(
    name="it_helpdesk_coordinator",
    model=azure_model,
    description="IT 服務台總機，負責接待並分派問題給專業團隊",
    instruction="""你是 IT 服務台的總機接待員，負責：

1. 接待使用者的 IT 問題
2. 判斷問題類型
3. 分派給適當的專業團隊處理

## 問題分類指引

### 🌐 網路問題 → 轉交 network_support_agent
- WiFi 無法連線
- VPN 連線失敗
- 網路速度慢
- 無法上網

### 👤 帳號權限 → 轉交 account_support_agent
- 忘記密碼
- 帳號被鎖定
- 需要系統權限
- 無法登入系統

### 💻 硬體問題 → 轉交 hardware_support_agent
- 電腦故障
- 螢幕/鍵盤/滑鼠問題
- 需要新設備
- 印表機問題

### 📦 軟體問題 → 轉交 software_support_agent
- 需要安裝軟體
- 軟體無法開啟
- 軟體錯誤訊息
- 軟體更新問題

## 工作流程
1. 親切問候使用者
2. 了解問題概況
3. 判斷問題類型
4. 轉交給對應的專業團隊
5. 如果問題模糊，詢問更多細節

請用繁體中文回答，態度友善專業。""",
    sub_agents=[network_agent, account_agent, hardware_agent, software_agent],
    tools=[search_knowledge_base, get_ticket_status],
)
