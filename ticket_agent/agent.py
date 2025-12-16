"""
客服工單 Agent - 展示 Loop Workflow（迴圈工作流）
展示：狀態追蹤、迴圈處理、條件終止

工作流程：
┌─────────────────────────────────────────────────────────┐
│                                                         │
│    ┌──────────┐     ┌──────────┐     ┌──────────┐     │
│    │  建立    │────▶│  處理中  │────▶│  待回覆  │     │
│    │  工單    │     │          │     │          │     │
│    └──────────┘     └────┬─────┘     └────┬─────┘     │
│                          │                 │           │
│                          ▼                 ▼           │
│                    ┌──────────┐     ┌──────────┐     │
│                    │ 等待資訊 │◀───│ 客戶回覆 │     │
│                    │          │     │          │     │
│                    └────┬─────┘     └──────────┘     │
│                          │                           │
│          ┌───────────────┴───────────────┐           │
│          │                               │           │
│          ▼                               ▼           │
│    ┌──────────┐                   ┌──────────┐     │
│    │  已解決  │                   │  已關閉  │     │
│    └──────────┘                   └──────────┘     │
│                                                     │
└─────────────────────────────────────────────────────┘
"""

import os
from datetime import datetime, timedelta
from typing import Optional
import random
import string

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# ============================================================================
# 模擬資料庫
# ============================================================================

# 工單狀態
TICKET_STATUS = {
    "open": "開立",
    "in_progress": "處理中",
    "waiting_customer": "等待客戶回覆",
    "waiting_info": "等待資訊",
    "resolved": "已解決",
    "closed": "已關閉",
}

# 工單優先級
PRIORITY_LEVELS = {
    "low": {"name": "低", "sla_hours": 72},
    "medium": {"name": "中", "sla_hours": 24},
    "high": {"name": "高", "sla_hours": 8},
    "urgent": {"name": "緊急", "sla_hours": 4},
}

# 工單類型
TICKET_CATEGORIES = [
    "帳號問題",
    "付款問題",
    "產品諮詢",
    "技術支援",
    "投訴建議",
    "退款申請",
]

# 工單資料庫
TICKETS_DB = {
    "TK-20251201-001": {
        "id": "TK-20251201-001",
        "customer_id": "C001",
        "customer_name": "王小明",
        "customer_email": "wang@example.com",
        "category": "技術支援",
        "subject": "無法登入系統",
        "description": "輸入正確密碼後仍無法登入，顯示驗證錯誤",
        "status": "in_progress",
        "priority": "high",
        "assigned_to": "tech_team",
        "created_at": "2025-12-01T09:00:00",
        "updated_at": "2025-12-01T10:30:00",
        "sla_deadline": "2025-12-01T17:00:00",
        "history": [
            {"time": "2025-12-01T09:00:00", "action": "created", "note": "工單建立"},
            {"time": "2025-12-01T09:15:00", "action": "assigned", "note": "指派給技術團隊"},
            {"time": "2025-12-01T10:30:00", "action": "status_change", "note": "開始處理"},
        ],
    },
    "TK-20251201-002": {
        "id": "TK-20251201-002",
        "customer_id": "C002",
        "customer_name": "李小華",
        "customer_email": "li@example.com",
        "category": "退款申請",
        "subject": "訂單退款",
        "description": "訂單 ORD-2025-0589 商品有瑕疵，申請退款",
        "status": "waiting_customer",
        "priority": "medium",
        "assigned_to": "cs_team",
        "created_at": "2025-12-01T11:00:00",
        "updated_at": "2025-12-01T14:00:00",
        "sla_deadline": "2025-12-02T11:00:00",
        "history": [
            {"time": "2025-12-01T11:00:00", "action": "created", "note": "工單建立"},
            {"time": "2025-12-01T12:00:00", "action": "status_change", "note": "開始處理"},
            {"time": "2025-12-01T14:00:00", "action": "status_change", "note": "已發送退款確認信，等待客戶回覆"},
        ],
    },
}

# 自動回覆範本
RESPONSE_TEMPLATES = {
    "帳號問題": "您好，關於您的帳號問題，我們已經...",
    "付款問題": "您好，關於您的付款問題，經查詢...",
    "技術支援": "您好，技術團隊已收到您的問題，正在處理中...",
    "退款申請": "您好，您的退款申請已收到，我們將在...",
}


# ============================================================================
# 工單管理 Tools
# ============================================================================

def create_ticket(
    customer_name: str,
    customer_email: str,
    category: str,
    subject: str,
    description: str,
    priority: str = "medium"
) -> dict:
    """建立新工單。

    Args:
        customer_name: 客戶姓名
        customer_email: 客戶 Email
        category: 工單類別
        subject: 主旨
        description: 問題描述
        priority: 優先級 (low/medium/high/urgent)

    Returns:
        dict: 建立結果
    """
    # 生成工單編號
    date_str = datetime.now().strftime("%Y%m%d")
    ticket_num = len(TICKETS_DB) + 1
    ticket_id = f"TK-{date_str}-{ticket_num:03d}"
    
    # 計算 SLA 時限
    sla_hours = PRIORITY_LEVELS.get(priority, PRIORITY_LEVELS["medium"])["sla_hours"]
    sla_deadline = datetime.now() + timedelta(hours=sla_hours)
    
    # 建立工單
    ticket = {
        "id": ticket_id,
        "customer_id": f"C{random.randint(100, 999)}",
        "customer_name": customer_name,
        "customer_email": customer_email,
        "category": category,
        "subject": subject,
        "description": description,
        "status": "open",
        "priority": priority,
        "assigned_to": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "sla_deadline": sla_deadline.isoformat(),
        "history": [
            {"time": datetime.now().isoformat(), "action": "created", "note": "工單建立"},
        ],
    }
    
    TICKETS_DB[ticket_id] = ticket
    
    return {
        "status": "success",
        "message": f"工單 {ticket_id} 已建立",
        "ticket": ticket,
    }


def get_ticket(ticket_id: str) -> dict:
    """查詢工單詳情。

    Args:
        ticket_id: 工單編號

    Returns:
        dict: 工單資訊
    """
    ticket = TICKETS_DB.get(ticket_id)
    
    if not ticket:
        return {
            "status": "not_found",
            "message": f"找不到工單 {ticket_id}",
        }
    
    # 計算 SLA 狀態
    sla_deadline = datetime.fromisoformat(ticket["sla_deadline"])
    now = datetime.now()
    
    if ticket["status"] in ["resolved", "closed"]:
        sla_status = "已完成"
    elif now > sla_deadline:
        sla_status = "已逾時"
    elif now > sla_deadline - timedelta(hours=2):
        sla_status = "即將到期"
    else:
        sla_status = "正常"
    
    return {
        "status": "success",
        "ticket": ticket,
        "status_display": TICKET_STATUS.get(ticket["status"], ticket["status"]),
        "priority_display": PRIORITY_LEVELS.get(ticket["priority"], {}).get("name", ticket["priority"]),
        "sla_status": sla_status,
    }


def list_tickets(
    status_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
    customer_email: Optional[str] = None
) -> dict:
    """列出工單。

    Args:
        status_filter: 狀態過濾 (open/in_progress/waiting_customer/resolved/closed)
        priority_filter: 優先級過濾 (low/medium/high/urgent)
        customer_email: 客戶 Email 過濾

    Returns:
        dict: 工單列表
    """
    results = []
    
    for ticket in TICKETS_DB.values():
        # 過濾
        if status_filter and ticket["status"] != status_filter:
            continue
        if priority_filter and ticket["priority"] != priority_filter:
            continue
        if customer_email and ticket["customer_email"] != customer_email:
            continue
        
        results.append({
            "id": ticket["id"],
            "subject": ticket["subject"],
            "customer_name": ticket["customer_name"],
            "status": TICKET_STATUS.get(ticket["status"], ticket["status"]),
            "priority": PRIORITY_LEVELS.get(ticket["priority"], {}).get("name", ticket["priority"]),
            "created_at": ticket["created_at"],
        })
    
    return {
        "status": "success",
        "count": len(results),
        "tickets": results,
    }


def update_ticket_status(
    ticket_id: str,
    new_status: str,
    note: str
) -> dict:
    """更新工單狀態。

    Args:
        ticket_id: 工單編號
        new_status: 新狀態 (open/in_progress/waiting_customer/waiting_info/resolved/closed)
        note: 備註

    Returns:
        dict: 更新結果
    """
    ticket = TICKETS_DB.get(ticket_id)
    
    if not ticket:
        return {
            "status": "not_found",
            "message": f"找不到工單 {ticket_id}",
        }
    
    if new_status not in TICKET_STATUS:
        return {
            "status": "error",
            "message": f"無效的狀態: {new_status}",
            "valid_statuses": list(TICKET_STATUS.keys()),
        }
    
    old_status = ticket["status"]
    ticket["status"] = new_status
    ticket["updated_at"] = datetime.now().isoformat()
    ticket["history"].append({
        "time": datetime.now().isoformat(),
        "action": "status_change",
        "note": f"{TICKET_STATUS[old_status]} → {TICKET_STATUS[new_status]}: {note}",
    })
    
    return {
        "status": "success",
        "message": f"工單 {ticket_id} 狀態已更新",
        "old_status": TICKET_STATUS[old_status],
        "new_status": TICKET_STATUS[new_status],
        "ticket": ticket,
    }


def add_ticket_response(
    ticket_id: str,
    response_type: str,
    message: str
) -> dict:
    """新增工單回覆。

    Args:
        ticket_id: 工單編號
        response_type: 回覆類型 (agent/customer/system)
        message: 回覆內容

    Returns:
        dict: 新增結果
    """
    ticket = TICKETS_DB.get(ticket_id)
    
    if not ticket:
        return {
            "status": "not_found",
            "message": f"找不到工單 {ticket_id}",
        }
    
    response_label = {
        "agent": "客服回覆",
        "customer": "客戶回覆",
        "system": "系統訊息",
    }.get(response_type, response_type)
    
    ticket["updated_at"] = datetime.now().isoformat()
    ticket["history"].append({
        "time": datetime.now().isoformat(),
        "action": f"response_{response_type}",
        "note": f"[{response_label}] {message}",
    })
    
    # 如果是客戶回覆，自動更新狀態
    if response_type == "customer" and ticket["status"] == "waiting_customer":
        ticket["status"] = "in_progress"
        ticket["history"].append({
            "time": datetime.now().isoformat(),
            "action": "status_change",
            "note": "收到客戶回覆，狀態自動更新為處理中",
        })
    
    return {
        "status": "success",
        "message": "回覆已新增",
        "ticket": ticket,
    }


def escalate_ticket(
    ticket_id: str,
    escalate_to: str,
    reason: str
) -> dict:
    """升級工單。

    Args:
        ticket_id: 工單編號
        escalate_to: 升級對象 (supervisor/manager/tech_lead)
        reason: 升級原因

    Returns:
        dict: 升級結果
    """
    ticket = TICKETS_DB.get(ticket_id)
    
    if not ticket:
        return {
            "status": "not_found",
            "message": f"找不到工單 {ticket_id}",
        }
    
    escalate_levels = {
        "supervisor": "主管",
        "manager": "經理",
        "tech_lead": "技術主管",
    }
    
    if escalate_to not in escalate_levels:
        return {
            "status": "error",
            "message": f"無效的升級對象: {escalate_to}",
            "valid_options": list(escalate_levels.keys()),
        }
    
    # 提升優先級
    priority_upgrade = {"low": "medium", "medium": "high", "high": "urgent", "urgent": "urgent"}
    old_priority = ticket["priority"]
    ticket["priority"] = priority_upgrade[old_priority]
    
    ticket["updated_at"] = datetime.now().isoformat()
    ticket["history"].append({
        "time": datetime.now().isoformat(),
        "action": "escalated",
        "note": f"升級至{escalate_levels[escalate_to]}，原因: {reason}",
    })
    
    return {
        "status": "success",
        "message": f"工單已升級至{escalate_levels[escalate_to]}",
        "new_priority": PRIORITY_LEVELS[ticket["priority"]]["name"],
        "ticket": ticket,
    }


def get_ticket_history(ticket_id: str) -> dict:
    """取得工單處理歷程。

    Args:
        ticket_id: 工單編號

    Returns:
        dict: 處理歷程
    """
    ticket = TICKETS_DB.get(ticket_id)
    
    if not ticket:
        return {
            "status": "not_found",
            "message": f"找不到工單 {ticket_id}",
        }
    
    return {
        "status": "success",
        "ticket_id": ticket_id,
        "subject": ticket["subject"],
        "current_status": TICKET_STATUS.get(ticket["status"], ticket["status"]),
        "history": ticket["history"],
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
    name="ticket_agent",
    model=azure_model,
    description="客服工單管理系統，處理工單的完整生命週期",
    instruction="""你是客服工單管理助手，負責處理客戶工單的完整生命週期。

## 工單狀態流程（Loop Workflow）

```
open → in_progress → waiting_customer → (客戶回覆) → in_progress → resolved → closed
                  ↘ waiting_info ↗
```

狀態說明：
- **open**: 新建立的工單
- **in_progress**: 處理中
- **waiting_customer**: 等待客戶提供資訊或確認
- **waiting_info**: 等待內部資訊
- **resolved**: 已解決（等待客戶確認）
- **closed**: 已關閉

## 你的能力

1. **建立工單** (create_ticket)
   - 類別：帳號問題、付款問題、產品諮詢、技術支援、投訴建議、退款申請
   - 優先級：low（低）、medium（中）、high（高）、urgent（緊急）

2. **查詢工單** (get_ticket)
   - 查看工單詳情和 SLA 狀態

3. **列出工單** (list_tickets)
   - 可依狀態、優先級、客戶 Email 過濾

4. **更新狀態** (update_ticket_status)
   - 推進工單至下一個狀態

5. **新增回覆** (add_ticket_response)
   - agent: 客服回覆
   - customer: 客戶回覆（會自動觸發狀態更新）
   - system: 系統訊息

6. **升級工單** (escalate_ticket)
   - 可升級至：supervisor（主管）、manager（經理）、tech_lead（技術主管）

7. **查看歷程** (get_ticket_history)
   - 查看工單的完整處理歷程

## 處理原則

1. **新工單**：根據問題類型和緊急程度設定適當優先級
2. **SLA 管理**：注意 SLA 時限，即將到期的要優先處理
3. **狀態追蹤**：確保工單狀態正確反映當前處理進度
4. **升級時機**：
   - SLA 即將逾時
   - 客戶重複反映問題
   - 問題超出權限範圍

## 回覆格式

### 工單資訊
- 📋 **工單編號**: TK-XXXXXXXX-XXX
- 📝 **主旨**: ...
- 👤 **客戶**: ...
- 🔄 **狀態**: ...
- ⚡ **優先級**: ...
- ⏰ **SLA**: ...

請用繁體中文回答。""",
    tools=[
        create_ticket,
        get_ticket,
        list_tickets,
        update_ticket_status,
        add_ticket_response,
        escalate_ticket,
        get_ticket_history,
    ],
)
