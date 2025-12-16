"""
會議室預約 Agent 測試入口
使用此檔案測試會議室預約功能
"""

# 使用方式：
# 1. 在命令列執行: adk web
# 2. 或直接 import 使用

# 匯出 agent 供 ADK 使用
from meeting_room_agent import meeting_room_agent

# 若要在 ADK web 介面中測試，確保 agent 是 root_agent
root_agent = meeting_room_agent

if __name__ == "__main__":
    print("=" * 60)
    print("會議室預約 Agent 已就緒")
    print("=" * 60)
    print("\n可用功能：")
    print("  1. 查詢可預約大樓")
    print("  2. 查詢可預約會議室 (by 大樓、日期)")
    print("  3. 預約會議室")
    print("  4. 查詢已預約會議室 (by user_id)")
    print("  5. 取消會議室預約")
    print("\n執行方式：")
    print("  adk web meeting_room_agent")
    print("=" * 60)
