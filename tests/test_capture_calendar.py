"""Calendar recurrence behavior and source-grounded note interpretation."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from icalendar import Calendar

from dayweave.calendar_io import export_calendar, import_calendar
from dayweave.capture import capture_note, deadline_time, duration_minutes, make_draft
from dayweave.contracts import InputError, PlanningInput
from dayweave.scheduler import schedule


def week():
    return PlanningInput.from_dict(
        {
            "start": "2026-10-05T00:00",
            "end": "2026-10-12T00:00",
            "available": [{"start": "2026-10-05T09:00", "end": "2026-10-05T18:00"}],
            "tasks": [{"id": "a", "title": "完成材料", "duration": 60}],
        }
    )


def test_recurring_calendar_with_exclusion_override_and_cancelled_instance():
    data = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Test//EN
BEGIN:VEVENT
UID:course
DTSTART;TZID=Asia/Shanghai:20261005T100000
DTEND;TZID=Asia/Shanghai:20261005T110000
RRULE:FREQ=DAILY;COUNT=5
EXDATE;TZID=Asia/Shanghai:20261006T100000
SUMMARY:课程
END:VEVENT
BEGIN:VEVENT
UID:course
RECURRENCE-ID;TZID=Asia/Shanghai:20261007T100000
DTSTART;TZID=Asia/Shanghai:20261007T140000
DTEND;TZID=Asia/Shanghai:20261007T150000
SUMMARY:调课
END:VEVENT
BEGIN:VEVENT
UID:course
RECURRENCE-ID;TZID=Asia/Shanghai:20261008T100000
DTSTART;TZID=Asia/Shanghai:20261008T100000
DTEND;TZID=Asia/Shanghai:20261008T110000
STATUS:CANCELLED
SUMMARY:取消的课
END:VEVENT
END:VCALENDAR
"""
    result = import_calendar(data, week())
    assert len(result["appointments"]) == 3
    assert any(item["title"] == "调课" and "14:00" in item["start"] for item in result["appointments"])
    assert not any("2026-10-06" in item["start"] or "2026-10-08" in item["start"] for item in result["appointments"])


def test_all_day_calendar_and_transparent_event():
    data = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:off
DTSTART;VALUE=DATE:20261006
DTEND;VALUE=DATE:20261007
SUMMARY:外出
END:VEVENT
BEGIN:VEVENT
UID:birthday
DTSTART;VALUE=DATE:20261007
DTEND;VALUE=DATE:20261008
SUMMARY:生日提醒
TRANSP:TRANSPARENT
END:VEVENT
END:VCALENDAR
"""
    result = import_calendar(data, week())
    assert len(result["appointments"]) == 1 and "2026-10-06T00:00" in result["appointments"][0]["start"]


def test_export_roundtrip_contains_only_scheduled_work_and_refuses_missing_required():
    plan = week()
    result = schedule(plan)
    data = export_calendar(plan, result["slots"])
    events = Calendar.from_ical(data).walk("VEVENT")
    assert len(events) == 1 and str(events[0]["SUMMARY"]) == "完成材料"
    assert import_calendar(data.decode(), plan)["appointments"][0]["start"] == result["slots"][0]["start"]
    with pytest.raises(InputError):
        export_calendar(plan, [])


@pytest.mark.parametrize(
    "phrase,expected", [("90分钟", 90), ("1.5小时", 90), ("2h", 120), ("半小时", 30), ("未写", None)]
)
def test_duration_interpretation(phrase, expected):
    assert duration_minutes(phrase) == expected


def test_relative_dates_do_not_invent_missing_clock_times():
    zone = ZoneInfo("Asia/Shanghai")
    anchor = datetime(2026, 10, 5, 9, tzinfo=zone)
    assert deadline_time("下周三18:00", anchor, zone) == "2026-10-14T18:00+08:00"
    assert deadline_time("明天下午3点", anchor, zone) == "2026-10-06T15:00+08:00"
    assert deadline_time("周三", anchor, zone) is None
    assert deadline_time("周三8点", anchor, zone) is None


def test_offline_capture_keeps_unresolved_duration_and_exact_source():
    source = "准备面试 | 90分钟 | 周三18:00前\n买菜 | 明天\n写文章 | 1.5小时 | 2026-10-09 17:00"
    result = capture_note(source, "2026-10-05T09:00")
    assert result["provider"] == "offline" and len(result["items"]) == 3
    assert result["items"][0]["duration"] == 90 and "2026-10-07T18:00" in result["items"][0]["deadline"]
    assert result["items"][1]["duration"] is None and result["items"][1]["deadline"] is None
    assert "2026-10-09T17:00" in result["items"][2]["deadline"]
    assert all(quote in source for item in result["items"] for quote in item["quotes"].values())


def test_model_cannot_supply_invented_quotes():
    zone = ZoneInfo("Asia/Shanghai")
    with pytest.raises(InputError, match="substring"):
        make_draft(
            "读书 30分钟",
            {"title_quote": "读书", "duration_quote": "60分钟"},
            0,
            datetime(2026, 10, 5, 9, tzinfo=zone),
            zone,
        )
