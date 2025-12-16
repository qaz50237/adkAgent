"""
訂單處理 Agent - 展示 Human-in-the-Loop（人機協作）工作流
展示：自動化處理 + 人工審核、例外處理、人工介入點

工作流程：
┌─────────────┐
│  接收訂單   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  自動驗證   │──────────▶ ❌ 驗證失敗 ──▶ 人工審核
└──────┬──────┘
       │ ✓ 驗證通過
       ▼
┌─────────────┐
│  庫存檢查   │──────────▶ ⚠️ 庫存不足 ──▶ 人工決策
└──────┬──────┘
       │ ✓ 庫存充足
       ▼
┌─────────────┐
│  風控檢查   │──────────▶ 🚨 高風險 ──▶ 人工審核
└──────┬──────┘
       │ ✓ 風控通過
       ▼
┌─────────────┐
│  自動出貨   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  訂單完成   │
└─────────────┘
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List
import random
import string

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# ============================================================================
# 模擬資料庫
# ============================================================================

# 訂單狀態
ORDER_STATUS = {
    "pending": "待處理",
    "validating": "驗證中",
    "pending_review": "待人工審核",
    "stock_checking": "檢查庫存",
    "stock_issue": "庫存問題-待決策",
    "risk_checking": "風控檢查",
    "risk_alert": "風控警示-待審核",
    "approved": "已核准",
    "processing": "處理中",
    "shipped": "已出貨",
    "completed": "已完成",
    "cancelled": "已取消",
    "rejected": "已拒絕",
}

# 庫存資料
INVENTORY = {
    "SKU001": {"name": "iPhone 15 Pro", "stock": 50, "price": 36900, "reserved": 5},
    "SKU002": {"name": "MacBook Pro 14", "stock": 20, "price": 62900, "reserved": 3},
    "SKU003": {"name": "AirPods Pro 2", "stock": 100, "price": 7490, "reserved": 10},
    "SKU004": {"name": "iPad Air", "stock": 35, "price": 19900, "reserved": 2},
    "SKU005": {"name": "Apple Watch S9", "stock": 2, "price": 12900, "reserved": 0},  # 低庫存
}

# 客戶風險等級
CUSTOMER_RISK = {
    "C001": {"name": "王小明", "risk_level": "low", "credit_limit": 100000, "order_count": 25},
    "C002": {"name": "李小華", "risk_level": "medium", "credit_limit": 50000, "order_count": 5},
    "C003": {"name": "張三", "risk_level": "high", "credit_limit": 10000, "order_count": 1},
    "NEW": {"name": "新客戶", "risk_level": "unknown", "credit_limit": 20000, "order_count": 0},
}

# 訂單資料庫
ORDERS_DB = {
    "ORD-2025-001": {
        "id": "ORD-2025-001",
        "customer_id": "C001",
        "customer_name": "王小明",
        "items": [{"sku": "SKU001", "quantity": 1, "price": 36900}],
        "total_amount": 36900,
        "status": "completed",
        "shipping_address": "台北市信義區...",
        "payment_method": "credit_card",
        "created_at": "2025-11-28T10:00:00",
        "workflow_log": [],
    },
}

# 待審核隊列
REVIEW_QUEUE = []


# ============================================================================
# 訂單處理 Tools
# ============================================================================

def create_order(
    customer_id: str,
    customer_name: str,
    items: List[dict],
    shipping_address: str,
    payment_method: str
) -> dict:
    """建立新訂單。

    Args:
        customer_id: 客戶 ID
        customer_name: 客戶姓名
        items: 訂單項目 [{"sku": "SKU001", "quantity": 1}]
        shipping_address: 配送地址
        payment_method: 付款方式 (credit_card/bank_transfer/cash_on_delivery)

    Returns:
        dict: 建立結果
    """
    # 生成訂單編號
    order_num = len(ORDERS_DB) + 1
    order_id = f"ORD-2025-{order_num:03d}"
    
    # 計算金額
    order_items = []
    total = 0
    for item in items:
        sku = item.get("sku")
        qty = item.get("quantity", 1)
        if sku in INVENTORY:
            price = INVENTORY[sku]["price"]
            order_items.append({
                "sku": sku,
                "name": INVENTORY[sku]["name"],
                "quantity": qty,
                "price": price,
            })
            total += price * qty
    
    order = {
        "id": order_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "items": order_items,
        "total_amount": total,
        "status": "pending",
        "shipping_address": shipping_address,
        "payment_method": payment_method,
        "created_at": datetime.now().isoformat(),
        "workflow_log": [
            {"time": datetime.now().isoformat(), "step": "created", "result": "訂單建立成功"},
        ],
    }
    
    ORDERS_DB[order_id] = order
    
    return {
        "status": "success",
        "order_id": order_id,
        "total_amount": total,
        "message": f"訂單 {order_id} 已建立，金額 ${total:,}",
        "next_step": "validate_order",
    }


def validate_order(order_id: str) -> dict:
    """驗證訂單資料（自動化步驟）。

    Args:
        order_id: 訂單編號

    Returns:
        dict: 驗證結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    order["status"] = "validating"
    issues = []
    
    # 驗證邏輯
    if not order["shipping_address"] or len(order["shipping_address"]) < 10:
        issues.append("配送地址不完整")
    
    if order["total_amount"] <= 0:
        issues.append("訂單金額異常")
    
    if not order["items"]:
        issues.append("訂單項目為空")
    
    # 記錄驗證結果
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "validation",
        "result": "通過" if not issues else f"問題：{', '.join(issues)}",
    })
    
    if issues:
        order["status"] = "pending_review"
        REVIEW_QUEUE.append({
            "type": "validation_failed",
            "order_id": order_id,
            "issues": issues,
            "created_at": datetime.now().isoformat(),
        })
        return {
            "status": "needs_review",
            "message": "訂單驗證有問題，已加入人工審核隊列",
            "issues": issues,
            "action": "請人工審核後使用 approve_order 或 reject_order",
        }
    
    return {
        "status": "success",
        "message": "訂單驗證通過",
        "next_step": "check_inventory",
    }


def check_inventory(order_id: str) -> dict:
    """檢查庫存（自動化步驟 + 可能需人工決策）。

    Args:
        order_id: 訂單編號

    Returns:
        dict: 庫存檢查結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    order["status"] = "stock_checking"
    stock_issues = []
    
    for item in order["items"]:
        sku = item["sku"]
        qty = item["quantity"]
        
        if sku not in INVENTORY:
            stock_issues.append({
                "sku": sku,
                "issue": "商品不存在",
                "available": 0,
                "required": qty,
            })
            continue
        
        inv = INVENTORY[sku]
        available = inv["stock"] - inv["reserved"]
        
        if available < qty:
            stock_issues.append({
                "sku": sku,
                "name": inv["name"],
                "issue": "庫存不足",
                "available": available,
                "required": qty,
            })
    
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "inventory_check",
        "result": "庫存充足" if not stock_issues else f"庫存問題：{len(stock_issues)} 項",
    })
    
    if stock_issues:
        order["status"] = "stock_issue"
        REVIEW_QUEUE.append({
            "type": "stock_issue",
            "order_id": order_id,
            "issues": stock_issues,
            "created_at": datetime.now().isoformat(),
        })
        return {
            "status": "needs_decision",
            "message": "庫存不足，需要人工決策",
            "stock_issues": stock_issues,
            "options": [
                "partial_ship: 部分出貨",
                "backorder: 等待補貨",
                "cancel: 取消訂單",
            ],
            "action": "請使用 handle_stock_decision 做出決策",
        }
    
    return {
        "status": "success",
        "message": "庫存充足",
        "next_step": "check_risk",
    }


def check_risk(order_id: str) -> dict:
    """風控檢查（自動化步驟 + 可能需人工審核）。

    Args:
        order_id: 訂單編號

    Returns:
        dict: 風控檢查結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    order["status"] = "risk_checking"
    risk_flags = []
    
    customer_id = order["customer_id"]
    customer = CUSTOMER_RISK.get(customer_id, CUSTOMER_RISK["NEW"])
    
    # 風控規則
    # 規則1: 新客戶大額訂單
    if customer["order_count"] < 3 and order["total_amount"] > 30000:
        risk_flags.append({
            "rule": "new_customer_high_value",
            "description": f"新客戶（訂單數: {customer['order_count']}）大額訂單 ${order['total_amount']:,}",
            "severity": "high",
        })
    
    # 規則2: 超過信用額度
    if order["total_amount"] > customer["credit_limit"]:
        risk_flags.append({
            "rule": "exceed_credit_limit",
            "description": f"訂單金額 ${order['total_amount']:,} 超過信用額度 ${customer['credit_limit']:,}",
            "severity": "high",
        })
    
    # 規則3: 高風險客戶
    if customer["risk_level"] == "high":
        risk_flags.append({
            "rule": "high_risk_customer",
            "description": "客戶被標記為高風險",
            "severity": "high",
        })
    
    # 規則4: 貨到付款大額
    if order["payment_method"] == "cash_on_delivery" and order["total_amount"] > 20000:
        risk_flags.append({
            "rule": "cod_high_value",
            "description": f"貨到付款大額訂單 ${order['total_amount']:,}",
            "severity": "medium",
        })
    
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "risk_check",
        "result": "風控通過" if not risk_flags else f"風控警示：{len(risk_flags)} 項",
    })
    
    # 判斷是否需要人工審核
    high_severity = any(f["severity"] == "high" for f in risk_flags)
    
    if high_severity:
        order["status"] = "risk_alert"
        REVIEW_QUEUE.append({
            "type": "risk_alert",
            "order_id": order_id,
            "risk_flags": risk_flags,
            "customer_info": customer,
            "created_at": datetime.now().isoformat(),
        })
        return {
            "status": "needs_review",
            "message": "風控警示，需要人工審核",
            "risk_flags": risk_flags,
            "customer_info": {
                "risk_level": customer["risk_level"],
                "credit_limit": customer["credit_limit"],
                "order_count": customer["order_count"],
            },
            "action": "請人工審核後使用 approve_order 或 reject_order",
        }
    
    order["status"] = "approved"
    return {
        "status": "success",
        "message": "風控檢查通過" + (f"（有 {len(risk_flags)} 項低風險警示）" if risk_flags else ""),
        "next_step": "process_order",
    }


def approve_order(order_id: str, reviewer: str, note: str) -> dict:
    """人工核准訂單。

    Args:
        order_id: 訂單編號
        reviewer: 審核人員
        note: 審核備註

    Returns:
        dict: 核准結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    if order["status"] not in ["pending_review", "risk_alert"]:
        return {
            "status": "error",
            "message": f"訂單狀態 {ORDER_STATUS[order['status']]} 不需要審核",
        }
    
    order["status"] = "approved"
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "manual_approval",
        "result": f"審核通過 by {reviewer}: {note}",
    })
    
    # 從審核隊列移除
    global REVIEW_QUEUE
    REVIEW_QUEUE = [r for r in REVIEW_QUEUE if r.get("order_id") != order_id]
    
    return {
        "status": "success",
        "message": f"訂單 {order_id} 已由 {reviewer} 核准",
        "next_step": "process_order",
    }


def reject_order(order_id: str, reviewer: str, reason: str) -> dict:
    """人工拒絕訂單。

    Args:
        order_id: 訂單編號
        reviewer: 審核人員
        reason: 拒絕原因

    Returns:
        dict: 拒絕結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    order["status"] = "rejected"
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "manual_rejection",
        "result": f"審核拒絕 by {reviewer}: {reason}",
    })
    
    # 從審核隊列移除
    global REVIEW_QUEUE
    REVIEW_QUEUE = [r for r in REVIEW_QUEUE if r.get("order_id") != order_id]
    
    return {
        "status": "success",
        "message": f"訂單 {order_id} 已被拒絕",
        "reason": reason,
    }


def handle_stock_decision(
    order_id: str,
    decision: str,
    reviewer: str,
    note: str
) -> dict:
    """處理庫存不足的人工決策。

    Args:
        order_id: 訂單編號
        decision: 決策 (partial_ship/backorder/cancel)
        reviewer: 決策人員
        note: 備註

    Returns:
        dict: 決策結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    if order["status"] != "stock_issue":
        return {"status": "error", "message": "訂單不在庫存問題狀態"}
    
    decisions = {
        "partial_ship": "部分出貨",
        "backorder": "等待補貨",
        "cancel": "取消訂單",
    }
    
    if decision not in decisions:
        return {
            "status": "error",
            "message": f"無效決策: {decision}",
            "valid_options": list(decisions.keys()),
        }
    
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "stock_decision",
        "result": f"決策: {decisions[decision]} by {reviewer}: {note}",
    })
    
    if decision == "cancel":
        order["status"] = "cancelled"
        return {
            "status": "success",
            "message": "訂單已取消",
        }
    elif decision == "partial_ship":
        order["status"] = "approved"
        return {
            "status": "success",
            "message": "決定部分出貨",
            "next_step": "process_order",
        }
    else:  # backorder
        order["status"] = "pending"
        return {
            "status": "success",
            "message": "訂單將等待補貨後處理",
        }


def process_order(order_id: str) -> dict:
    """處理訂單出貨（自動化步驟）。

    Args:
        order_id: 訂單編號

    Returns:
        dict: 處理結果
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    if order["status"] != "approved":
        return {"status": "error", "message": f"訂單狀態必須是已核准，目前是 {ORDER_STATUS.get(order['status'], order['status'])}"}
    
    # 扣庫存
    for item in order["items"]:
        sku = item["sku"]
        qty = item["quantity"]
        if sku in INVENTORY:
            INVENTORY[sku]["stock"] -= qty
    
    order["status"] = "processing"
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "processing",
        "result": "訂單處理中，準備出貨",
    })
    
    # 模擬出貨
    tracking_number = "SF" + "".join(random.choices(string.digits, k=12))
    
    order["status"] = "shipped"
    order["tracking_number"] = tracking_number
    order["shipped_at"] = datetime.now().isoformat()
    order["workflow_log"].append({
        "time": datetime.now().isoformat(),
        "step": "shipped",
        "result": f"已出貨，追蹤編號: {tracking_number}",
    })
    
    return {
        "status": "success",
        "message": "訂單已出貨",
        "tracking_number": tracking_number,
    }


def get_order_status(order_id: str) -> dict:
    """查詢訂單狀態和工作流程記錄。

    Args:
        order_id: 訂單編號

    Returns:
        dict: 訂單狀態
    """
    order = ORDERS_DB.get(order_id)
    if not order:
        return {"status": "error", "message": f"訂單 {order_id} 不存在"}
    
    return {
        "status": "success",
        "order": {
            "id": order["id"],
            "customer_name": order["customer_name"],
            "total_amount": order["total_amount"],
            "status": ORDER_STATUS.get(order["status"], order["status"]),
            "status_code": order["status"],
            "tracking_number": order.get("tracking_number"),
            "created_at": order["created_at"],
        },
        "workflow_log": order["workflow_log"],
    }


def get_review_queue() -> dict:
    """取得待審核隊列。

    Returns:
        dict: 審核隊列
    """
    return {
        "status": "success",
        "count": len(REVIEW_QUEUE),
        "queue": REVIEW_QUEUE,
    }


def get_inventory_status() -> dict:
    """取得庫存狀態。

    Returns:
        dict: 庫存狀態
    """
    inventory_list = []
    for sku, info in INVENTORY.items():
        available = info["stock"] - info["reserved"]
        status = "充足" if available > 10 else ("低庫存" if available > 0 else "缺貨")
        inventory_list.append({
            "sku": sku,
            "name": info["name"],
            "stock": info["stock"],
            "reserved": info["reserved"],
            "available": available,
            "status": status,
        })
    
    return {
        "status": "success",
        "inventory": inventory_list,
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
    name="order_agent",
    model=azure_model,
    description="訂單處理系統，展示 Human-in-the-Loop 工作流",
    instruction="""你是訂單處理助手，負責管理訂單的完整處理流程。

## Human-in-the-Loop 工作流

這是一個結合自動化和人工審核的訂單處理系統：

```
訂單建立 → 自動驗證 → 庫存檢查 → 風控檢查 → 處理出貨
              ↓           ↓           ↓
         [人工審核]   [人工決策]   [人工審核]
```

### 自動化步驟
1. **validate_order**: 自動驗證訂單資料
2. **check_inventory**: 自動檢查庫存
3. **check_risk**: 自動風控檢查
4. **process_order**: 自動處理出貨

### 人工介入點
1. **驗證失敗** → 需要人工審核 → approve_order / reject_order
2. **庫存不足** → 需要人工決策 → handle_stock_decision
3. **風控警示** → 需要人工審核 → approve_order / reject_order

## 你的能力

### 訂單管理
- **create_order**: 建立新訂單
- **get_order_status**: 查詢訂單狀態和工作流程

### 自動化流程
- **validate_order**: 驗證訂單
- **check_inventory**: 檢查庫存
- **check_risk**: 風控檢查
- **process_order**: 處理出貨

### 人工介入
- **approve_order**: 核准訂單
- **reject_order**: 拒絕訂單
- **handle_stock_decision**: 庫存問題決策

### 監控
- **get_review_queue**: 查看待審核隊列
- **get_inventory_status**: 查看庫存狀態

## 處理訂單的標準流程

1. 建立訂單 (create_order)
2. 驗證訂單 (validate_order) 
   - 如果需要審核 → approve_order / reject_order
3. 檢查庫存 (check_inventory)
   - 如果庫存不足 → handle_stock_decision
4. 風控檢查 (check_risk)
   - 如果有風險 → approve_order / reject_order
5. 處理出貨 (process_order)

## 回覆格式

### 訂單狀態
- 📦 **訂單編號**: ORD-XXXX-XXX
- 👤 **客戶**: ...
- 💰 **金額**: $XX,XXX
- 🔄 **狀態**: ...

### 待辦事項
如果有待審核的項目，請提醒使用者處理。

請用繁體中文回答。""",
    tools=[
        create_order,
        validate_order,
        check_inventory,
        check_risk,
        approve_order,
        reject_order,
        handle_stock_decision,
        process_order,
        get_order_status,
        get_review_queue,
        get_inventory_status,
    ],
)
