# DayWeave · 日程织

把事情放进真正有空的时间里。排不下时，看清需要改什么。

[English](README.md) · [使用说明](docs/usage.md) · [v0.2.1 预发布](https://github.com/crown-sports/dayweave/releases/tag/v0.2.1)

![记录已完成工时后，DayWeave 只安排剩余工作](docs/assets/remaining-work.png)

*本地运行的真实排程页面，使用可编辑示例。已完成工时由使用者填写。*

写下要做的事、预计时长、期限和已经约好的安排，DayWeave 帮你排出时间表。
有冲突就告诉你哪里放不下，临时有事时尽量少改原计划。排好后可以导出到常用日历。

## 打开就能试

先从 [python.org](https://www.python.org/downloads/) 安装 **Python 3.12**，
再到 [v0.2.1 发布页](https://github.com/crown-sports/dayweave/releases/tag/v0.2.1)下载 **Source code (zip)** 并解压。

- Windows：双击 `Start-DayWeave.cmd`。
- macOS：双击 `Start-DayWeave.command`。
- Linux 或终端：运行 `python3 launch.py`。

首次启动会联网安装依赖。浏览器打开 **http://127.0.0.1:8787** 后，保持终端窗口开启。
不需要账号、模型或显卡。

## 先试一天，再填自己的事情

1. 在 **先体验一下** 选择 **简单排序排不了的一天**，点击 **载入示例**。
2. 点击 **安排这一周**：做题排在 **09:00–12:00**，电话排在 **12:00–13:00**，两件都放得下。
3. 再试 **事情比时间多的上午**：240 分钟的事情，只有 180 分钟可用，看看怎么取舍。

![事情比时间多的上午：需要240分钟、可用180分钟，显示缺口和可选的推迟事项](docs/assets/overload.jpg)

*内置超载示例。只有确认后，才会采用建议的推迟方案。*

## 安排自己的这一周

点击 **新建自己的计划**，填写事情、预计时长和实际期限。按自己的生活修改空闲时段，
导入 `.ics` 日历或手动添加预约。点击 **安排这一周**，检查日程块；有冲突就调整期限、
空闲时间、拆分方式，或选择推迟。

做了一部分？在 **调整详情 → 已完成工时（分钟，累计）** 中记录。
预计 90 分钟、已做 30 分钟，重新安排时只需要找剩下的 60 分钟。
时间不能动的事项可以 **固定安排**。

**保存项目** 下载 JSON 备份，**打开项目** 可以恢复。
**导出到日历** 下载 `.ics`，由你导入日历；程序不会直接修改联网日历。

## 命令行用法

在下载的源码目录运行：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
dayweave plan examples/partial-progress.json --output remaining.json --calendar remaining.ics
```

样例会排出通过检查的 **60 分钟草稿 + 30 分钟审阅**。
Windows 使用 `.venv\Scripts\Activate.ps1` 激活，Python 路径为 `.venv\Scripts\python.exe`。
[JSON 格式、日历支持范围与可选模型](docs/usage.md)。

## 使用范围

本地单人使用。时长是你的估计，程序不会自动记工时或发提醒；清理浏览器数据前要保存备份。
复杂计划可能求解超时，部分日历重复规则尚不支持。[排不下时可以改什么](docs/product.md)。

排程使用 OR-Tools CP-SAT，并独立复核结果。公开的合成案例中，48 个可行案例全部排下，
按截止日期插入的基线排下 34 个。这是排程测试，不代表真实用户效率提升。
[算法与完整结果](docs/results.md) · [设计说明](docs/design.md) · [许可证](NOTICE)
