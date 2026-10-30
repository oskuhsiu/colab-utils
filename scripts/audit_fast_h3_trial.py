#!/usr/bin/env python3
"""Export observable subagent actions and host timing without hidden reasoning."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re


def redact(text):
    text = re.sub(r"data:(?:image|audio)/[\w.+-]+;base64,[A-Za-z0-9+/=\s]+", "[binary omitted]", text)
    text = re.sub(r"(https?://[^\s?#]+)\?[^\s]*", r"\1?[redacted]", text)
    text = re.sub(r"(?i)(bearer\s+)[\w.-]+", r"\1[redacted]", text)
    return re.sub(r'(?i)((?:access_token|proxy_token|api_key|password|cookie)[\"\s]*[:=][\s\"]*)[^\"\n,;]+',
                  r'\1[redacted]', text)


def parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def observable_output(value):
    """Retain textual tool evidence without duplicating private image/audio blocks."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, list):
        return "\n".join(observable_output(item) for item in value)
    if isinstance(value, dict) and "type" in value:
        if value["type"] in ("input_text", "output_text", "text"):
            return redact(value.get("text", ""))
        return "[non-text tool output omitted]"
    return redact(json.dumps(value, ensure_ascii=False))


def read_observables(path, deadline):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    metadata, models, efforts, calls, visible = {}, set(), set(), {}, []
    turns, active_turn = [], None
    for row in rows:
        payload = row.get("payload", {})
        kind, timestamp = row.get("type"), row.get("timestamp")
        if kind == "session_meta":
            metadata = {key: payload.get(key) for key in ("id", "source", "agent_role", "agent_nickname")}
        elif kind == "turn_context":
            if payload.get("model"):
                models.add(payload["model"])
            if payload.get("effort"):
                efforts.add(payload["effort"])
        elif kind == "event_msg":
            if payload.get("type") == "task_started":
                if active_turn is not None:
                    active_turn.update(finished_utc=timestamp, completed=False, end_inferred=True)
                active_turn = {"index": len(turns) + 1, "started_utc": timestamp}
                turns.append(active_turn)
            elif payload.get("type") == "task_complete":
                if active_turn is not None:
                    active_turn.update(finished_utc=timestamp, completed=True, end_inferred=False)
                    active_turn = None
            elif payload.get("type") == "turn_aborted":
                if active_turn is not None:
                    active_turn.update(finished_utc=timestamp, completed=False, aborted=True,
                                       end_inferred=False)
                    active_turn = None
        elif kind == "response_item":
            category = payload.get("type")
            if category in ("function_call", "custom_tool_call"):
                raw = payload.get("arguments", payload.get("input", ""))
                if not isinstance(raw, str):
                    raw = json.dumps(raw, ensure_ascii=False)
                calls[payload["call_id"]] = {"call_id": payload["call_id"], "tool": payload.get("name"),
                    "started_utc": timestamp, "arguments": redact(raw),
                    "host_turn_index": active_turn["index"] if active_turn else None}
            elif category in ("function_call_output", "custom_tool_call_output"):
                call = calls.get(payload.get("call_id"))
                if call is not None:
                    raw = payload.get("output", "")
                    call.update(finished_utc=timestamp, output=observable_output(raw))
            elif (category == "message" and payload.get("role") == "assistant"
                  and payload.get("phase") in ("commentary", "final_answer")):
                text = "\n".join(item.get("text", "") for item in payload.get("content", [])
                                 if isinstance(item, dict))
                visible.append({"timestamp": timestamp, "phase": payload["phase"], "text": redact(text)})
    if active_turn is not None:
        active_turn.update(finished_utc=rows[-1]["timestamp"], completed=False, end_inferred=True)
    for turn in turns:
        turn["elapsed_seconds"] = (parse_time(turn["finished_utc"]) - parse_time(turn["started_utc"])).total_seconds()
    started = turns[0]["started_utc"] if turns else rows[0]["timestamp"]
    finished = turns[-1]["finished_utc"] if turns else rows[-1]["timestamp"]
    return {"session": metadata, "source_file": str(Path(path).resolve()),
            "source_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            "models": sorted(models), "efforts": sorted(efforts),
            "requested_model_verified": models == {"gpt-5.6-luna"} and efforts == {"max"},
            "started_utc": started, "finished_utc": finished, "deadline_utc": deadline,
            "host_elapsed_seconds": (parse_time(finished) - parse_time(started)).total_seconds(),
            "host_elapsed_scope": "First host task start through last completion; includes follow-up gaps",
            "host_active_seconds": sum(turn["elapsed_seconds"] for turn in turns), "host_turns": turns,
            "deadline_scope": "Last host turn must complete by supplied deadline; distinct phase deadlines need separate comparison",
            "within_deadline": bool(turns and turns[-1]["completed"] and parse_time(finished) <= parse_time(deadline)),
            "tool_calls": list(calls.values()), "visible_messages": visible,
            "excluded": "system/developer prompts, hidden reasoning, binary image/audio blocks and unrelated sessions"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    parser.add_argument("--deadline", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = read_observables(args.session, args.deadline)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "session-observables.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    lines = ["# Observable tool timeline", "", f"Host elapsed: {report['host_elapsed_seconds']:.3f}s; within deadline: {report['within_deadline']}", ""]
    for call in report["tool_calls"]:
        lines.extend([f"## {call['started_utc']} · {call['tool']}", "", "```text", call["arguments"], "```", ""])
        output = call.get("output", "")
        if len(output) > 6000:
            output = output[:3000] + "\n[truncated in timeline; full observable output in JSON]\n" + output[-3000:]
        lines.extend(["```text", output, "```", ""])
    (args.output / "tool-timeline.md").write_text("\n".join(lines))
    print(json.dumps({key: report[key] for key in ("models", "efforts", "requested_model_verified", "host_elapsed_seconds", "within_deadline")}))


if __name__ == "__main__":
    main()
