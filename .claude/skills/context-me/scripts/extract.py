#!/usr/bin/env python3
"""context-me extractor.

Reads the N most recent Claude Code session transcripts and keeps only the
USER-side signal: every human prompt in full (system-injected blocks and
image bytes removed), slash commands, URLs, image counts, pasted-block sizes,
plus the tools / MCP servers / CLI commands used per session. Assistant prose
and tool results are dropped. Output is sharded JSON for reader subagents.
"""
import argparse
import glob
import json
import os
import re
from collections import Counter
from datetime import datetime

INJECTED = re.compile(
    r"<system-reminder>.*?</system-reminder>"
    r"|<local-command-caveat>.*?</local-command-caveat>"
    r"|<local-command-stdout>.*?</local-command-stdout>"
    r"|<command-message>.*?</command-message>",
    re.S,
)
CMD_NAME = re.compile(r"<command-name>(.*?)</command-name>", re.S)
CMD_ARGS = re.compile(r"<command-args>(.*?)</command-args>", re.S)
URL = re.compile(r"https?://[^\s\"'<>)]+")
DOMAIN = re.compile(r"https?://([^/\s\"'<>)]+)")
EXT = re.compile(
    r"\b[\w-]+\.(xlsx|xls|csv|pdf|docx|pptx|png|jpg|jpeg|json|yaml|yml|md|sql|ipynb|log|zip)\b",
    re.I,
)
PASTED_MIN = 1200  # chars; beyond this a prompt very likely contains pasted content


def scan(path):
    prompts, tools, cli_cmds, mcp = [], Counter(), [], Counter()
    meta = {"cwd": None, "branch": None, "first_ts": None, "last_ts": None}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("isSidechain"):
                continue
            ts = o.get("timestamp")
            if ts:
                meta["first_ts"] = meta["first_ts"] or ts
                meta["last_ts"] = ts
            meta["cwd"] = meta["cwd"] or o.get("cwd")
            meta["branch"] = meta["branch"] or o.get("gitBranch")
            m = o.get("message")
            if not isinstance(m, dict):
                continue
            content = m.get("content")
            if o.get("type") == "user":
                texts, images, has_tool_result = [], 0, False
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for b in content:
                        bt = b.get("type")
                        if bt == "text":
                            texts.append(b.get("text", ""))
                        elif bt == "image":
                            images += 1
                        elif bt == "tool_result":
                            has_tool_result = True
                if has_tool_result and not texts:
                    continue  # pure tool result, not a human prompt
                raw = "\n".join(texts)
                cmds = CMD_NAME.findall(raw)
                args = CMD_ARGS.findall(raw)
                clean = INJECTED.sub("", raw)
                clean = re.sub(r"<command-(?:name|args)>.*?</command-(?:name|args)>", "", clean, flags=re.S).strip()
                # A skill invocation arrives as the skill's own body injected into the
                # user turn. That is harness text, not something the user pasted.
                skill_expansion = clean.startswith("Base directory for this skill")
                if skill_expansion:
                    clean = clean.splitlines()[0]
                if not clean and not images and not cmds:
                    continue
                prompts.append(
                    {
                        "idx": len(prompts),
                        "ts": ts,
                        "chars": len(clean),
                        "pasted_block": len(clean) >= PASTED_MIN and not skill_expansion,
                        "skill_expansion": skill_expansion,
                        "images": images,
                        "slash_commands": cmds,
                        "slash_args": [a.strip()[:200] for a in args],
                        "urls": URL.findall(clean)[:10],
                        "domains": sorted({d for d in DOMAIN.findall(clean) if re.fullmatch(r"[\w.:-]+", d)}),
                        "file_refs": sorted(set(x.lower() for x in EXT.findall(clean))),
                        "text": clean,
                    }
                )
            elif o.get("type") == "assistant" and isinstance(content, list):
                for b in content:
                    if b.get("type") != "tool_use":
                        continue
                    name = b.get("name", "?")
                    tools[name] += 1
                    if name.startswith("mcp__"):
                        mcp[name.split("__")[1]] += 1
                    if name in ("Bash", "PowerShell"):
                        cmd = (b.get("input") or {}).get("command", "")
                        cli_cmds.append(cmd.strip()[:300])
    return prompts, tools, cli_cmds, mcp, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=20)
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--shards", type=int, default=3)
    ap.add_argument("--min-prompts", type=int, default=2, help="skip near-empty sessions")
    a = ap.parse_args()

    files = [
        p
        for p in glob.glob(os.path.join(a.root, "*", "*.jsonl"))
        if os.sep + "subagents" + os.sep not in p
    ]
    files.sort(key=os.path.getmtime, reverse=True)
    os.makedirs(a.out, exist_ok=True)

    sessions, raw_bytes = [], 0
    for path in files:
        if len(sessions) >= a.sessions:
            break
        prompts, tools, cli_cmds, mcp, meta = scan(path)
        if len(prompts) < a.min_prompts:
            continue
        raw_bytes += os.path.getsize(path)
        sessions.append(
            {
                "session_id": os.path.splitext(os.path.basename(path))[0],
                "project": os.path.basename(os.path.dirname(path)),
                "cwd": meta["cwd"],
                "branch": meta["branch"],
                "first_ts": meta["first_ts"],
                "last_ts": meta["last_ts"],
                "prompt_count": len(prompts),
                "images_total": sum(p["images"] for p in prompts),
                "pasted_blocks": sum(p["pasted_block"] for p in prompts),
                "tools_used": dict(tools.most_common()),
                "mcp_servers_used": dict(mcp.most_common()),
                "cli_commands": cli_cmds,
                "prompts": prompts,
            }
        )

    shards = [[] for _ in range(max(1, a.shards))]
    for i, s in enumerate(sessions):
        shards[i % len(shards)].append(s)
    extracted_bytes = 0
    for i, shard in enumerate(shards, 1):
        p = os.path.join(a.out, f"shard-{i}.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump({"shard": i, "sessions": shard}, fh, ensure_ascii=False, indent=1)
        extracted_bytes += os.path.getsize(p)

    def total(key_fn):
        return dict(Counter(k for s in sessions for k in key_fn(s)).most_common())

    summary = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "sessions": len(sessions),
        "prompts": sum(s["prompt_count"] for s in sessions),
        "images": sum(s["images_total"] for s in sessions),
        "pasted_blocks": sum(s["pasted_blocks"] for s in sessions),
        "raw_mb": round(raw_bytes / 1e6, 1),
        "extracted_kb": round(extracted_bytes / 1e3, 1),
        "est_tokens": int(extracted_bytes / 4),
        "reduction": f"{(1 - extracted_bytes / raw_bytes) * 100:.1f}%" if raw_bytes else "n/a",
        "tools_total": dict(sum((Counter(s["tools_used"]) for s in sessions), Counter()).most_common()),
        "mcp_servers_total": dict(sum((Counter(s["mcp_servers_used"]) for s in sessions), Counter()).most_common()),
        "slash_commands_total": total(lambda s: [c for p in s["prompts"] for c in p["slash_commands"]]),
        "domains_total": total(lambda s: [d for p in s["prompts"] for d in p["domains"]]),
        "file_refs_total": total(lambda s: [f for p in s["prompts"] for f in p["file_refs"]]),
        "shards": len(shards),
    }
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
