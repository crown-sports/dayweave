"""Public synthetic Chinese notes, with hand-specified task and timing annotations."""

from __future__ import annotations

from typing import Any

ANCHOR = "2026-10-05T09:00"
ZONE = "Asia/Shanghai"


def note_cases() -> list[dict[str, Any]]:
    """Use the same intentions in structured lines and prose so parser comparisons stay paired."""
    groups = [
        [
            ("准备面试", "90分钟", 90, "周三18:00", "2026-10-07T18:00"),
            ("提交申请", "半小时", 30, "周五17:00", "2026-10-09T17:00"),
            ("买菜", "", None, "", None),
        ],
        [
            ("复习英语", "两小时", 120, "下周一10:00", "2026-10-12T10:00"),
            ("运动", "45分钟", 45, "明天20:00", "2026-10-06T20:00"),
            ("打电话", "15分钟", 15, "今天16:00", "2026-10-05T16:00"),
        ],
        [
            ("写课程论文", "3小时", 180, "周五17:00", "2026-10-09T17:00"),
            ("洗衣服", "半小时", 30, "后天19:00", "2026-10-07T19:00"),
            ("联系预约", "", None, "", None),
        ],
        [
            ("备份照片", "1小时", 60, "2026-10-09 21:00", "2026-10-09T21:00"),
            ("理发", "45分钟", 45, "周六14:00", "2026-10-10T14:00"),
            ("整理收据", "", None, "周五", None),
        ],
        [
            ("读两章书", "一个半小时", 90, "周五18:00", "2026-10-09T18:00"),
            ("练琴", "30分钟", 30, "明天08:00", "2026-10-06T08:00"),
            ("购买车票", "15分钟", 15, "今天18:00", "2026-10-05T18:00"),
        ],
        [
            ("做饭", "60分钟", 60, "明天19:00", "2026-10-06T19:00"),
            ("打印资料", "20分钟", 20, "今天16:00", "2026-10-05T16:00"),
            ("打包行李", "45分钟", 45, "周日21:00", "2026-10-11T21:00"),
        ],
        [
            ("看论文", "1.5h", 90, "周三14:00", "2026-10-07T14:00"),
            ("交作业", "30分钟", 30, "周四09:00", "2026-10-08T09:00"),
            ("做预算", "60分钟", 60, "周日18:00", "2026-10-11T18:00"),
        ],
        [
            ("学编程", "120分钟", 120, "明天下午3点30分", "2026-10-06T15:30"),
            ("练口语", "半小时", 30, "周三晚上8点", "2026-10-07T20:00"),
            ("给植物浇水", "", None, "", None),
        ],
        [
            ("修改作品集", "90分钟", 90, "周三18:00", "2026-10-07T18:00"),
            ("发送求职信", "15分钟", 15, "周四17:00", "2026-10-08T17:00"),
            ("查路线", "20分钟", 20, "周五09:00", "2026-10-09T09:00"),
        ],
    ]
    cases = []
    for number, group in enumerate(groups):
        gold = [
            {"title": title, "duration": duration, "deadline": deadline + "+08:00" if deadline else None}
            for title, _, duration, _, deadline in group
        ]
        structured = "\n".join(
            f"{title} | {effort or '时长待估计'} | {due + '前' if due else '期限未定'}"
            for title, effort, _, due, _ in group
        )
        prose = (
            "这周要处理几件事。"
            + "；".join(
                f"{due + '前要' if due else '还要'}{title}，{('预计' + effort) if effort else '时长还没有估计'}"
                for title, effort, _, due, _ in group
            )
            + "。"
        )
        for style, source in [("structured", structured), ("prose", prose)]:
            cases.append(
                {
                    "id": f"capture-{number:02d}-{style}",
                    "style": style,
                    "text": source,
                    "anchor": ANCHOR,
                    "timezone": ZONE,
                    "gold": gold,
                }
            )
    return cases
