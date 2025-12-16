"""
會議室預約系統 - Tools 定義
包含 5 個核心工具：查詢大樓、查詢會議室、預約、查詢已預約、取消預約
"""

from datetime import datetime, timedelta
from typing import Optional

# ============================================================================
# 模擬資料庫（實際應用中請替換為真實的資料庫連接）
# ============================================================================

# 大樓資料
BUILDINGS = {
    "A": {"id": "A", "name": "A棟 - 總部大樓", "floors": 10},
    "B": {"id": "B", "name": "B棟 - 研發中心", "floors": 8},
    "C": {"id": "C", "name": "C棟 - 會議中心", "floors": 5},
}

# 會議室資料
MEETING_ROOMS = {
    "A-101": {"id": "A-101", "building": "A", "name": "大會議室", "capacity": 20},
    "A-102": {"id": "A-102", "building": "A", "name": "小會議室A", "capacity": 8},
    "A-201": {"id": "A-201", "building": "A", "name": "董事會議室", "capacity": 30},
    "B-101": {"id": "B-101", "building": "B", "name": "研發討論室", "capacity": 10},
    "B-102": {"id": "B-102", "building": "B", "name": "技術簡報室", "capacity": 15},
    "C-101": {"id": "C-101", "building": "C", "name": "多功能廳", "capacity": 50},
    "C-201": {"id": "C-201", "building": "C", "name": "VIP會議室", "capacity": 12},
}

# 預約記錄（模擬資料庫）
BOOKINGS: dict[str, dict] = {}
_booking_counter = 0


def _generate_booking_id() -> str:
    """產生唯一的預約編號"""
    global _booking_counter
    _booking_counter += 1
    return f"BK{datetime.now().strftime('%Y%m%d')}{_booking_counter:04d}"


# ============================================================================
# Tool 1: 查詢可預約大樓
# ============================================================================

def list_buildings() -> dict:
    """查詢所有可預約的大樓列表。

    Returns:
        dict: 包含狀態和大樓列表或錯誤訊息。
              成功時返回 {"status": "success", "buildings": [...]}
    """
    try:
        buildings_list = [
            {
                "id": b["id"],
                "name": b["name"],
                "floors": b["floors"],
            }
            for b in BUILDINGS.values()
        ]
        return {
            "status": "success",
            "buildings": buildings_list,
            "message": f"共有 {len(buildings_list)} 棟大樓可供預約。",
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"查詢大樓時發生錯誤：{str(e)}",
        }


# ============================================================================
# Tool 2: 查詢可預約會議室 (by 大樓、日期)
# ============================================================================

def list_available_rooms(building_id: str, date: str) -> dict:
    """查詢指定大樓在指定日期的可預約會議室。

    Args:
        building_id (str): 大樓代碼（例如："A", "B", "C"）
        date (str): 查詢日期，格式為 YYYY-MM-DD（例如："2025-12-20"）

    Returns:
        dict: 包含狀態和可用會議室列表或錯誤訊息。
    """
    try:
        # 驗證大樓是否存在
        building_id = building_id.upper()
        if building_id not in BUILDINGS:
            return {
                "status": "error",
                "error_message": f"找不到大樓 '{building_id}'。請使用 list_buildings 查詢可用大樓。",
            }

        # 驗證日期格式
        try:
            query_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return {
                "status": "error",
                "error_message": "日期格式錯誤，請使用 YYYY-MM-DD 格式（例如：2025-12-20）。",
            }

        # 檢查日期是否為過去
        if query_date < datetime.now().date():
            return {
                "status": "error",
                "error_message": "無法查詢過去的日期。",
            }

        # 取得該大樓的會議室
        rooms_in_building = [
            room for room in MEETING_ROOMS.values()
            if room["building"] == building_id
        ]

        # 檢查每個會議室的可用時段
        available_rooms = []
        time_slots = [
            "09:00-10:00", "10:00-11:00", "11:00-12:00",
            "13:00-14:00", "14:00-15:00", "15:00-16:00",
            "16:00-17:00", "17:00-18:00",
        ]

        for room in rooms_in_building:
            # 檢查該會議室在該日期已被預約的時段
            booked_slots = []
            for booking in BOOKINGS.values():
                if (booking["room_id"] == room["id"] and
                    booking["date"] == date and
                    booking["status"] == "confirmed"):
                    booked_slots.append(booking["time_slot"])

            # 計算可用時段
            available_slots = [slot for slot in time_slots if slot not in booked_slots]

            available_rooms.append({
                "room_id": room["id"],
                "room_name": room["name"],
                "capacity": room["capacity"],
                "available_slots": available_slots,
                "booked_slots": booked_slots,
            })

        building_name = BUILDINGS[building_id]["name"]
        return {
            "status": "success",
            "building": building_name,
            "date": date,
            "rooms": available_rooms,
            "message": f"{building_name} 在 {date} 共有 {len(available_rooms)} 間會議室。",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"查詢會議室時發生錯誤：{str(e)}",
        }


# ============================================================================
# Tool 3: 預約會議室
# ============================================================================

def book_room(
    room_id: str,
    user_id: str,
    date: str,
    time_slot: str,
    title: str,
    attendees: Optional[int] = None,
) -> dict:
    """預約會議室。

    Args:
        room_id (str): 會議室代碼（例如："A-101"）
        user_id (str): 預約者的使用者 ID
        date (str): 預約日期，格式為 YYYY-MM-DD（例如："2025-12-20"）
        time_slot (str): 預約時段（例如："09:00-10:00", "14:00-15:00"）
        title (str): 會議主題
        attendees (int, optional): 預計出席人數

    Returns:
        dict: 包含狀態和預約結果或錯誤訊息。
    """
    try:
        # 驗證會議室是否存在
        room_id = room_id.upper()
        if room_id not in MEETING_ROOMS:
            return {
                "status": "error",
                "error_message": f"找不到會議室 '{room_id}'。請先查詢可用會議室。",
            }

        room = MEETING_ROOMS[room_id]

        # 驗證日期格式
        try:
            booking_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            return {
                "status": "error",
                "error_message": "日期格式錯誤，請使用 YYYY-MM-DD 格式。",
            }

        # 檢查日期是否為過去
        if booking_date < datetime.now().date():
            return {
                "status": "error",
                "error_message": "無法預約過去的日期。",
            }

        # 驗證時段格式
        valid_slots = [
            "09:00-10:00", "10:00-11:00", "11:00-12:00",
            "13:00-14:00", "14:00-15:00", "15:00-16:00",
            "16:00-17:00", "17:00-18:00",
        ]
        if time_slot not in valid_slots:
            return {
                "status": "error",
                "error_message": f"無效的時段 '{time_slot}'。可用時段：{', '.join(valid_slots)}",
            }

        # 檢查該時段是否已被預約
        for booking in BOOKINGS.values():
            if (booking["room_id"] == room_id and
                booking["date"] == date and
                booking["time_slot"] == time_slot and
                booking["status"] == "confirmed"):
                return {
                    "status": "error",
                    "error_message": f"會議室 {room_id} 在 {date} {time_slot} 已被預約。",
                }

        # 檢查出席人數是否超過容量
        if attendees and attendees > room["capacity"]:
            return {
                "status": "error",
                "error_message": f"出席人數 ({attendees}) 超過會議室容量 ({room['capacity']})。",
            }

        # 建立預約
        booking_id = _generate_booking_id()
        BOOKINGS[booking_id] = {
            "booking_id": booking_id,
            "room_id": room_id,
            "room_name": room["name"],
            "building": room["building"],
            "user_id": user_id,
            "date": date,
            "time_slot": time_slot,
            "title": title,
            "attendees": attendees or 0,
            "status": "confirmed",
            "created_at": datetime.now().isoformat(),
        }

        return {
            "status": "success",
            "booking": BOOKINGS[booking_id],
            "message": f"預約成功！預約編號：{booking_id}",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"預約時發生錯誤：{str(e)}",
        }


# ============================================================================
# Tool 4: 查詢已預約會議室 (by user_id)
# ============================================================================

def get_my_bookings(user_id: str) -> dict:
    """查詢指定使用者的所有預約記錄。

    Args:
        user_id (str): 使用者 ID

    Returns:
        dict: 包含狀態和預約記錄列表或錯誤訊息。
    """
    try:
        # 篩選該使用者的預約
        user_bookings = [
            booking for booking in BOOKINGS.values()
            if booking["user_id"] == user_id and booking["status"] == "confirmed"
        ]

        # 依日期和時間排序
        user_bookings.sort(key=lambda x: (x["date"], x["time_slot"]))

        if not user_bookings:
            return {
                "status": "success",
                "bookings": [],
                "message": f"使用者 {user_id} 目前沒有任何預約。",
            }

        return {
            "status": "success",
            "user_id": user_id,
            "bookings": user_bookings,
            "message": f"使用者 {user_id} 共有 {len(user_bookings)} 筆預約。",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"查詢預約時發生錯誤：{str(e)}",
        }


# ============================================================================
# Tool 5: 取消會議室預約
# ============================================================================

def cancel_booking(booking_id: str, user_id: str) -> dict:
    """取消指定的會議室預約。

    Args:
        booking_id (str): 預約編號
        user_id (str): 使用者 ID（用於驗證權限）

    Returns:
        dict: 包含狀態和取消結果或錯誤訊息。
    """
    try:
        # 檢查預約是否存在
        booking_id = booking_id.upper()
        if booking_id not in BOOKINGS:
            return {
                "status": "error",
                "error_message": f"找不到預約編號 '{booking_id}'。",
            }

        booking = BOOKINGS[booking_id]

        # 檢查是否已取消
        if booking["status"] == "cancelled":
            return {
                "status": "error",
                "error_message": f"預約 {booking_id} 已經被取消。",
            }

        # 驗證權限（只有預約者可以取消）
        if booking["user_id"] != user_id:
            return {
                "status": "error",
                "error_message": "您沒有權限取消此預約。只有預約者可以取消預約。",
            }

        # 檢查是否為過去的預約
        booking_date = datetime.strptime(booking["date"], "%Y-%m-%d").date()
        if booking_date < datetime.now().date():
            return {
                "status": "error",
                "error_message": "無法取消過去的預約。",
            }

        # 執行取消
        booking["status"] = "cancelled"
        booking["cancelled_at"] = datetime.now().isoformat()

        return {
            "status": "success",
            "booking_id": booking_id,
            "message": f"預約 {booking_id} 已成功取消。（{booking['room_name']}，{booking['date']} {booking['time_slot']}）",
        }

    except Exception as e:
        return {
            "status": "error",
            "error_message": f"取消預約時發生錯誤：{str(e)}",
        }
