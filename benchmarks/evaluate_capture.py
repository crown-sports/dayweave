"""Source-capture evaluation that counts missing tasks and unsupported times as actual errors."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import statistics
import time
from contextlib import suppress
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from capture_cases import note_cases
from evaluate import source_fingerprint

from dayweave.capture import capture_note


def score(gold: list[dict[str, Any]], items: list[dict[str, Any]]) -> dict[str, int]:
    """Match a quote to exactly one annotated intention and count full timing correctness on all gold tasks."""
    matches = {}
    false_positive = 0
    exact_titles = 0
    for item in items:
        candidates = [index for index, task in enumerate(gold) if task["title"] in item["quotes"]["title_quote"]]
        if len(candidates) != 1 or candidates[0] in matches:
            false_positive += 1
            continue
        matches[candidates[0]] = item
        exact_titles += item["title"] == gold[candidates[0]]["title"]
    duration_correct = sum(
        index in matches and matches[index]["duration"] == task["duration"] for index, task in enumerate(gold)
    )
    deadline_correct = sum(
        index in matches and matches[index]["deadline"] == task["deadline"] for index, task in enumerate(gold)
    )
    full_correct = sum(
        index in matches
        and matches[index]["duration"] == task["duration"]
        and matches[index]["deadline"] == task["deadline"]
        for index, task in enumerate(gold)
    )
    return {
        "gold_tasks": len(gold),
        "returned_items": len(items),
        "matched_tasks": len(matches),
        "false_positive_items": false_positive,
        "exact_title_matches": exact_titles,
        "duration_correct": duration_correct,
        "deadline_correct": deadline_correct,
        "all_fields_correct": full_correct,
        "unresolved_fields_in_gold": sum(task[field] is None for task in gold for field in ("duration", "deadline")),
        "invented_absent_fields": sum(
            task[field] is None and matches[index][field] is not None
            for index, task in enumerate(gold)
            if index in matches
            for field in ("duration", "deadline")
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmark-runs/capture"))
    parser.add_argument("--model-url")
    parser.add_argument("--model", default="qwen3:4b")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    cases = note_cases()
    (args.output / "cases.json").write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n")
    records = []
    with (args.output / "results.jsonl").open("w") as stream:
        for case in cases:
            methods = {}
            for label, endpoint in [
                ("offline", None),
                *(([("configured_model", args.model_url)]) if args.model_url else []),
            ]:
                started = time.monotonic()
                result = capture_note(case["text"], case["anchor"], case["timezone"], endpoint, args.model)
                methods[label] = {
                    "result": result,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    "metrics": score(case["gold"], result["items"]),
                }
            record = {"case": case["id"], "style": case["style"], "methods": methods}
            records.append(record)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            print(f"Captured {len(records)}/{len(cases)} notes", flush=True)
    versions = {}
    for name in ("dayweave", "torch", "transformers", "ortools"):
        with suppress(PackageNotFoundError):
            versions[name] = version(name)
    summary = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_sha256": source_fingerprint(),
        "python": platform.python_version(),
        "platform": {"system": platform.system(), "machine": platform.machine()},
        "versions": versions,
        "case_count": len(cases),
        "model": args.model if args.model_url else None,
        "styles": {},
        "limits": (
            "18 synthetic public notes; no real-user extraction accuracy claim. "
            "Source membership is not semantic correctness."
        ),
    }
    for style in ("structured", "prose", "all"):
        subset = [record for record in records if style == "all" or record["style"] == style]
        summary["styles"][style] = {}
        for method in methods:
            values = [record["methods"][method] for record in subset]
            total = {key: sum(value["metrics"][key] for value in values) for key in values[0]["metrics"]}
            total.update(
                {
                    "notes": len(values),
                    "direct_model_accepted": sum(value["result"]["provider"] == "local_model" for value in values),
                    "fallback_notes": sum(value["result"]["rejection"] is not None for value in values),
                    "median_ms": round(statistics.median(value["duration_ms"] for value in values), 3),
                    "task_precision": total["matched_tasks"] / total["returned_items"]
                    if total["returned_items"]
                    else 0,
                    "task_recall": total["matched_tasks"] / total["gold_tasks"],
                    "all_fields_correct_rate": total["all_fields_correct"] / total["gold_tasks"],
                }
            )
            summary["styles"][style][method] = total
    summary["artifact_sha256"] = {
        name: hashlib.sha256((args.output / name).read_bytes()).hexdigest() for name in ("cases.json", "results.jsonl")
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
