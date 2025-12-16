"""
報銷審批 Agent - 展示 Sequential Workflow（順序工作流）
展示：順序執行、條件分支、狀態追蹤

工作流程：
┌─────────────┐
│   提交報銷   │
└──────┬──────┘
       ▼
┌─────────────┐     ≤ 1000元
│  金額判斷    │──────────────────┐
└──────┬──────┘                  │
       │ > 1000元                │
       ▼                         │
┌─────────────┐                  │
│  主管審核    │                  │
└──────┬──────┘                  │
       │ 通過                    │
       ▼                         ▼
┌─────────────┐     ┌─────────────┐
│ 金額 > 5000 │ No  │  財務審核    │
└──────┬──────┘────►└──────┬──────┘
       │ Yes                │
       ▼                    │
┌─────────────┐             │
│  總經理審核  │             │
└──────┬──────┘             │
       │ 通過               │
       ▼                    ▼
┌─────────────────────────────┐
│          撥款處理            │
└─────────────────────────────┘
"""

import os
from datetime import datetime
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

load_dotenv()

# ============================================================================
# 資料模型
# ============================================================================

class ExpenseStatus(str, Enum):
    DRAFT = "draft"
    PENDING_MANAGER = "pending_manager"
    PENDING_DIRECTOR = "pending_director"
    PENDING_FINANCE = "pending_finance"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"


class ExpenseCategory(str, Enum):
    TRAVEL = "travel"           # 差旅
    MEAL = "meal"               # 餐費
    TRANSPORT = "transport"     # 交通
    OFFICE = "office"           # 辦公用品
    TRAINING = "training"       # 培訓
    OTHER = "other"             # 其他


# ============================================================================
# 模擬資料庫
# ============================================================================

EXPENSE_REPORTS: dict[str, dict] = {}
_expense_counter = 0

# 審批權限設定
APPROVAL_LIMITS = {
    "auto": 1000,           # ≤ 1000 元自動審批（僅財務確認）
    "manager": 5000,        # ≤ 5000 元主管可審批
    "director": 50000,      # ≤ 50000 元總監可審批
    "ceo": float('inf'),    # 超過 50000 元需總經理審批
}

# 員工資料
EMPLOYEES = {
    "emp001": {"name": "王小明", "department": "研發部", "manager": "mgr001"},
    "emp002": {"name": "李小華", "department": "業務部", "manager": "mgr002"},
    "emp003": {"name": "張小美", "department": "人資部", "manager": "mgr003"},
    "mgr001": {"name": "陳經理", "department": "研發部", "manager": "dir001", "is_manager": True},
    "mgr002": {"name": "林經理", "department": "業務部", "manager": "dir001", "is_manager": True},
    "dir001": {"name": "黃總監", "department": "營運部", "manager": "ceo001", "is_director": True},
    "ceo001": {"name": "總經理", "department": "管理部", "is_ceo": True},
    "fin001": {"name": "財務專員", "department": "財務部", "is_finance": True},
}


def _generate_expense_id() -> str:
    global _expense_counter
    _expense_counter += 1
    return f"EXP{datetime.now().strftime('%Y%m%d')}{_expense_counter:04d}"


def _get_next_approver(expense: dict) -> Optional[str]:
    """根據報銷金額和當前狀態，決定下一個審批者"""
    amount = expense["amount"]
    status = expense["status"]
    user_id = expense["user_id"]
    
    if status == ExpenseStatus.DRAFT:
        if amount <= APPROVAL_LIMITS["auto"]:
            return "fin001"  # 小額直接財務
        return EMPLOYEES[user_id]["manager"]  # 主管審批
    
    if status == ExpenseStatus.PENDING_MANAGER:
        if amount > APPROVAL_LIMITS["manager"]:
            return "dir001"  # 需總監審批
        return "fin001"  # 財務審批
    
    if status == ExpenseStatus.PENDING_DIRECTOR:
        if amount > APPROVAL_LIMITS["director"]:
            return "ceo001"  # 需總經理審批
        return "fin001"
    
    return "fin001"


# ============================================================================
# 報銷提交 Tools
# ============================================================================

def submit_expense(
    user_id: str,
    category: str,
    amount: float,
    description: str,
    receipt_count: int = 1
) -> dict:
    """提交報銷申請。

    Args:
        user_id: 申請人員工編號
        category: 報銷類別 (travel/meal/transport/office/training/other)
        amount: 報銷金額
        description: 報銷說明
        receipt_count: 收據數量

    Returns:
        dict: 提交結果
    """
    if user_id not in EMPLOYEES:
        return {"status": "error", "message": f"找不到員工 {user_id}"}
    
    if amount <= 0:
        return {"status": "error", "message": "金額必須大於 0"}
    
    expense_id = _generate_expense_id()
    
    # 根據金額決定初始狀態和審批流程
    if amount <= APPROVAL_LIMITS["auto"]:
        initial_status = ExpenseStatus.PENDING_FINANCE
        workflow = ["財務審核", "撥款"]
    elif amount <= APPROVAL_LIMITS["manager"]:
        initial_status = ExpenseStatus.PENDING_MANAGER
        workflow = ["主管審核", "財務審核", "撥款"]
    elif amount <= APPROVAL_LIMITS["director"]:
        initial_status = ExpenseStatus.PENDING_MANAGER
        workflow = ["主管審核", "總監審核", "財務審核", "撥款"]
    else:
        initial_status = ExpenseStatus.PENDING_MANAGER
        workflow = ["主管審核", "總監審核", "總經理審核", "財務審核", "撥款"]
    
    EXPENSE_REPORTS[expense_id] = {
        "expense_id": expense_id,
        "user_id": user_id,
        "user_name": EMPLOYEES[user_id]["name"],
        "department": EMPLOYEES[user_id]["department"],
        "category": category,
        "amount": amount,
        "description": description,
        "receipt_count": receipt_count,
        "status": initial_status,
        "workflow": workflow,
        "current_step": 0,
        "approval_history": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    
    next_approver = _get_next_approver(EXPENSE_REPORTS[expense_id])
    next_approver_name = EMPLOYEES[next_approver]["name"] if next_approver else "無"
    
    return {
        "status": "success",
        "expense_id": expense_id,
        "amount": amount,
        "workflow": workflow,
        "next_approver": next_approver_name,
        "message": f"報銷申請已提交，單號：{expense_id}，等待 {next_approver_name} 審核",
    }


def get_expense_status(expense_id: str) -> dict:
    """查詢報銷單狀態。

    Args:
        expense_id: 報銷單編號

    Returns:
        dict: 報銷單詳情
    """
    if expense_id not in EXPENSE_REPORTS:
        return {"status": "error", "message": f"找不到報銷單 {expense_id}"}
    
    expense = EXPENSE_REPORTS[expense_id]
    return {
        "status": "success",
        "expense": expense,
    }


def list_my_expenses(user_id: str) -> dict:
    """查詢我的報銷記錄。

    Args:
        user_id: 使用者 ID

    Returns:
        dict: 報銷記錄列表
    """
    my_expenses = [
        exp for exp in EXPENSE_REPORTS.values()
        if exp["user_id"] == user_id
    ]
    
    return {
        "status": "success",
        "count": len(my_expenses),
        "expenses": my_expenses,
    }


# ============================================================================
# 審批 Tools
# ============================================================================

def list_pending_approvals(approver_id: str) -> dict:
    """查詢待審批的報銷單（給審批者使用）。

    Args:
        approver_id: 審批者 ID

    Returns:
        dict: 待審批列表
    """
    if approver_id not in EMPLOYEES:
        return {"status": "error", "message": f"找不到員工 {approver_id}"}
    
    approver = EMPLOYEES[approver_id]
    pending = []
    
    for expense in EXPENSE_REPORTS.values():
        # 判斷是否是該審批者需要審批的單據
        if expense["status"] == ExpenseStatus.PENDING_MANAGER:
            if approver.get("is_manager") and expense["user_id"] in [
                uid for uid, emp in EMPLOYEES.items() if emp.get("manager") == approver_id
            ]:
                pending.append(expense)
        elif expense["status"] == ExpenseStatus.PENDING_DIRECTOR:
            if approver.get("is_director"):
                pending.append(expense)
        elif expense["status"] == ExpenseStatus.PENDING_FINANCE:
            if approver.get("is_finance"):
                pending.append(expense)
    
    return {
        "status": "success",
        "approver": approver["name"],
        "count": len(pending),
        "pending_expenses": pending,
    }


def approve_expense(
    expense_id: str,
    approver_id: str,
    decision: str,
    comment: str = ""
) -> dict:
    """審批報銷單。

    Args:
        expense_id: 報銷單編號
        approver_id: 審批者 ID
        decision: 審批決定 (approve/reject)
        comment: 審批意見

    Returns:
        dict: 審批結果
    """
    if expense_id not in EXPENSE_REPORTS:
        return {"status": "error", "message": f"找不到報銷單 {expense_id}"}
    
    if approver_id not in EMPLOYEES:
        return {"status": "error", "message": f"找不到審批者 {approver_id}"}
    
    expense = EXPENSE_REPORTS[expense_id]
    approver = EMPLOYEES[approver_id]
    
    # 記錄審批歷史
    expense["approval_history"].append({
        "approver_id": approver_id,
        "approver_name": approver["name"],
        "decision": decision,
        "comment": comment,
        "timestamp": datetime.now().isoformat(),
    })
    expense["updated_at"] = datetime.now().isoformat()
    
    if decision == "reject":
        expense["status"] = ExpenseStatus.REJECTED
        return {
            "status": "success",
            "expense_id": expense_id,
            "result": "rejected",
            "message": f"報銷單已被 {approver['name']} 退回",
            "comment": comment,
        }
    
    # 審批通過，更新狀態
    expense["current_step"] += 1
    
    # 判斷下一步
    if expense["status"] == ExpenseStatus.PENDING_MANAGER:
        if expense["amount"] > APPROVAL_LIMITS["manager"]:
            expense["status"] = ExpenseStatus.PENDING_DIRECTOR
            next_step = "等待總監審核"
        else:
            expense["status"] = ExpenseStatus.PENDING_FINANCE
            next_step = "等待財務審核"
    elif expense["status"] == ExpenseStatus.PENDING_DIRECTOR:
        if expense["amount"] > APPROVAL_LIMITS["director"]:
            # 需要總經理審核（這裡簡化，直接到財務）
            expense["status"] = ExpenseStatus.PENDING_FINANCE
            next_step = "等待財務審核"
        else:
            expense["status"] = ExpenseStatus.PENDING_FINANCE
            next_step = "等待財務審核"
    elif expense["status"] == ExpenseStatus.PENDING_FINANCE:
        expense["status"] = ExpenseStatus.APPROVED
        next_step = "審批完成，等待撥款"
    else:
        next_step = "流程異常"
    
    return {
        "status": "success",
        "expense_id": expense_id,
        "result": "approved",
        "next_step": next_step,
        "message": f"報銷單已被 {approver['name']} 核准，{next_step}",
    }


# ============================================================================
# 財務處理 Tools
# ============================================================================

def process_payment(expense_id: str, finance_id: str) -> dict:
    """處理撥款（財務使用）。

    Args:
        expense_id: 報銷單編號
        finance_id: 財務人員 ID

    Returns:
        dict: 撥款結果
    """
    if expense_id not in EXPENSE_REPORTS:
        return {"status": "error", "message": f"找不到報銷單 {expense_id}"}
    
    expense = EXPENSE_REPORTS[expense_id]
    
    if expense["status"] != ExpenseStatus.APPROVED:
        return {"status": "error", "message": "只有已核准的報銷單才能撥款"}
    
    expense["status"] = ExpenseStatus.PAID
    expense["paid_at"] = datetime.now().isoformat()
    expense["paid_by"] = finance_id
    
    return {
        "status": "success",
        "expense_id": expense_id,
        "amount": expense["amount"],
        "message": f"已完成撥款 ${expense['amount']} 元至 {expense['user_name']} 的薪資帳戶",
    }


def get_expense_summary(start_date: str = None, end_date: str = None) -> dict:
    """取得報銷統計摘要。

    Args:
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)

    Returns:
        dict: 統計摘要
    """
    total_submitted = len(EXPENSE_REPORTS)
    total_amount = sum(exp["amount"] for exp in EXPENSE_REPORTS.values())
    
    by_status = {}
    for exp in EXPENSE_REPORTS.values():
        status = exp["status"]
        if status not in by_status:
            by_status[status] = {"count": 0, "amount": 0}
        by_status[status]["count"] += 1
        by_status[status]["amount"] += exp["amount"]
    
    by_category = {}
    for exp in EXPENSE_REPORTS.values():
        category = exp["category"]
        if category not in by_category:
            by_category[category] = {"count": 0, "amount": 0}
        by_category[category]["count"] += 1
        by_category[category]["amount"] += exp["amount"]
    
    return {
        "status": "success",
        "summary": {
            "total_submitted": total_submitted,
            "total_amount": total_amount,
            "by_status": by_status,
            "by_category": by_category,
        },
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
    name="expense_agent",
    model=azure_model,
    description="報銷審批助理，處理報銷申請、審批和查詢",
    instruction="""你是報銷審批助理，負責處理公司的報銷流程。

## 報銷流程說明

### 審批層級（依金額）
- ≤ $1,000：自動審批，僅需財務確認
- $1,001 ~ $5,000：主管審批 → 財務確認
- $5,001 ~ $50,000：主管審批 → 總監審批 → 財務確認
- > $50,000：主管審批 → 總監審批 → 總經理審批 → 財務確認

### 報銷類別
- travel: 差旅費
- meal: 餐費
- transport: 交通費
- office: 辦公用品
- training: 培訓費
- other: 其他

## 你的功能

### 員工可以：
1. 提交報銷 (submit_expense)
2. 查詢報銷狀態 (get_expense_status)
3. 查詢我的報銷記錄 (list_my_expenses)

### 審批者可以：
1. 查詢待審批清單 (list_pending_approvals)
2. 審批報銷單 (approve_expense)

### 財務可以：
1. 處理撥款 (process_payment)
2. 查看統計報表 (get_expense_summary)

## 對話指引

1. 提交報銷時，需要確認：
   - 員工 ID (user_id)
   - 報銷類別 (category)
   - 金額 (amount)
   - 報銷說明 (description)
   - 收據數量 (receipt_count)

2. 查詢時，需要報銷單編號或員工 ID

3. 審批時，需要確認：
   - 報銷單編號
   - 審批者 ID
   - 審批決定 (approve/reject)
   - 審批意見

請用繁體中文回答，態度專業親切。""",
    tools=[
        submit_expense,
        get_expense_status,
        list_my_expenses,
        list_pending_approvals,
        approve_expense,
        process_payment,
        get_expense_summary,
    ],
)
