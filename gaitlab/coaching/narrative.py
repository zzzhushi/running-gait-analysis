"""Optional: rephrase the structured findings as a natural-language summary via a LOCAL LLM.

Uses Ollama (https://ollama.com) if it is running on localhost:11434 — fully local, free,
no API key. If Ollama isn't reachable, returns {available: False} and the app simply falls
back to the rule-based findings, which remain the source of truth. Nothing here is required.

Enable it (optional):
    # install Ollama from ollama.com, then:
    ollama run llama3.2
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.2"


def build_prompt(result: dict) -> str:
    s = result.get("summary", {})
    lines = [
        "You are a friendly, concise running coach. In 3-4 short sentences of plain language,",
        "summarize this gait analysis: encouraging but honest. Use ONLY the numbers given; do",
        "not invent any. End with one line 'Focus this week:' naming the single highest-priority cue.",
        "",
        f"View: {s.get('view')}. Cadence: {s.get('cadence')} spm. "
        f"Overall grade {s.get('grade')} ({s.get('overall_score')}/100).",
    ]
    findings = result.get("feedback", [])
    if findings:
        lines.append("Findings (most important first):")
        for f in findings[:5]:
            lines.append(f"- [{f.get('severity')}] {f.get('title')}: {f.get('detail')}")
    asym = [a for a in result.get("asymmetry", []) if a.get("status") in ("warn", "bad")]
    if asym:
        lines.append("Notable left/right differences:")
        for a in asym[:3]:
            lines.append(f"- {a.get('label')}: {a.get('diff_pct')}% (L {a.get('left')} vs R {a.get('right')} {a.get('unit')})")
    return "\n".join(lines)


def generate(result: dict, model: str = DEFAULT_MODEL, timeout: float = 45.0) -> dict:
    payload = json.dumps({"model": model, "prompt": build_prompt(result), "stream": False}).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"available": True, "model": model, "text": (data.get("response") or "").strip()}
    except urllib.error.URLError:
        return {
            "available": False, "text": None, "model": model,
            "error": "Local LLM not reachable. This feature is optional — install Ollama from "
                     "ollama.com and run `ollama run llama3.2` to enable a plain-English summary.",
        }
    except Exception as e:  # noqa: BLE001
        return {"available": False, "text": None, "model": model, "error": str(e)}
