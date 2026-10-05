"""Editable everyday examples, clearly separate from a person's actual calendar."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .contracts import InputError


def example(kind: str, day: str = "2026-10-05", timezone: str = "Asia/Shanghai") -> dict[str, Any]:
    """Build real solver inputs for ordinary work, a sorting counterexample, and an overloaded morning."""
    try:
        first = date.fromisoformat(day)
        zone = ZoneInfo(timezone)
    except (ValueError, KeyError) as exc:
        raise InputError("Choose a valid starting date and timezone") from exc

    def iso(offset: int, clock: str) -> str:
        return datetime.combine(first + timedelta(days=offset), time.fromisoformat(clock), zone).isoformat(
            timespec="minutes"
        )

    result: dict[str, Any] = {
        "timezone": timezone,
        "start": iso(0, "00:00"),
        "end": iso(7, "00:00"),
        "not_before": iso(0, "00:00"),
        "available": [],
        "tasks": [],
        "appointments": [],
        "previous": [],
        "example": kind,
    }
    if kind == "sorting":
        result["available"] = [{"start": iso(0, "09:00"), "end": iso(0, "14:00")}]
        result["tasks"] = [
            {
                "id": "phone",
                "title": "打预约电话",
                "duration": 60,
                "priority": 5,
                "release": iso(0, "11:00"),
                "deadline": iso(0, "13:00"),
            },
            {"id": "study", "title": "完成一套模拟题", "duration": 180, "priority": 3, "deadline": iso(0, "14:00")},
        ]
    elif kind == "overload":
        result["available"] = [{"start": iso(0, "09:00"), "end": iso(0, "12:00")}]
        result["tasks"] = [
            {"id": "interview", "title": "准备面试", "duration": 90, "priority": 5, "deadline": iso(0, "12:00")},
            {"id": "paperwork", "title": "整理申请材料", "duration": 90, "priority": 4, "deadline": iso(0, "12:00")},
            {"id": "reading", "title": "读完一章书", "duration": 60, "priority": 2, "deadline": iso(0, "12:00")},
        ]
    elif kind == "balanced":
        for offset in range(7):
            if (first + timedelta(days=offset)).weekday() < 5:
                result["available"].extend(
                    [
                        {"start": iso(offset, "09:00"), "end": iso(offset, "12:00")},
                        {"start": iso(offset, "13:00"), "end": iso(offset, "18:00")},
                    ]
                )
        specs = [
            ("resume", "更新简历", 60, 0, "18:00", 5, [], 60),
            ("interview", "准备面试", 120, 2, "18:00", 5, ["resume"], 60),
            ("application", "提交两份申请", 45, 3, "17:00", 4, ["resume"], 45),
            ("reading", "读完一章书", 90, 4, "18:00", 2, [], 45),
            ("writing", "完成课程小论文", 180, 4, "17:00", 4, [], 60),
            ("exercise", "运动和拉伸", 45, 4, "18:00", 3, [], 45),
            ("groceries", "买菜并准备晚餐", 60, 2, "18:00", 3, [], 60),
            ("phone", "办理预约电话", 30, 1, "12:00", 4, [], 30),
        ]
        result["tasks"] = [
            {
                "id": key,
                "title": title,
                "duration": duration,
                "deadline": iso(due, clock),
                "priority": priority,
                "after": after,
                "chunk": chunk,
            }
            for key, title, duration, due, clock, priority, after, chunk in specs
        ]
        result["appointments"] = [
            {"id": "class", "title": "已约好的课程", "start": iso(0, "11:00"), "end": iso(0, "12:00")},
            {"id": "appointment", "title": "线下预约", "start": iso(1, "14:00"), "end": iso(1, "15:00")},
        ]
    else:
        raise InputError("Unknown example")
    return result
