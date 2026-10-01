"""Yojana Saathi agent: LLM tool-calling loop + offline rule-based fallback."""
import json
import os
import re

from .tools import TOOL_SCHEMAS, check_eligibility, run_tool

MODEL = os.getenv("MODEL", "claude-sonnet-5-5")
MAX_STEPS = 6

SYSTEM = """You are Yojana Saathi, an AI agent that helps Indian citizens find and apply for government schemes.
Reply in the user's language (Hindi, Hinglish or English). Keep replies short and simple - many users are first-time smartphone users.

Workflow:
1. Understand the user's situation. Extract profile facts (age, gender, state, occupation, income, category, etc).
2. If key facts are missing, ask at most 2 short questions. Never ask for Aadhaar numbers, OTPs, passwords or bank details.
3. Call check_eligibility with everything known. Never invent schemes - only use tool results.
4. For the best 1-3 matches, call document_checklist. If the user gave a state/district call find_center.
5. If the user wants to apply or complain, call draft_letter and tell them the download link.
6. Finish with a clear next step. Remind the user to verify details on the official portal."""

SESSIONS: dict[str, list] = {}
PROFILES: dict[str, dict] = {}


def _summarize(out) -> str:
    if not isinstance(out, dict):
        return str(out)[:120]
    if "likely_eligible" in out:
        return f"{len(out['likely_eligible'])} likely, {len(out['need_more_info'])} need info, {len(out['not_eligible'])} not eligible"
    if "scheme" in out:
        return f"{len(out['documents'])} documents for {out['scheme']}"
    if "centers" in out:
        return f"{len(out['centers'])} centres found"
    if "draft_id" in out:
        return "letter drafted"
    return json.dumps(out, ensure_ascii=False)[:120]


def run_agent(session_id: str, user_text: str) -> dict:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return offline_agent(session_id, user_text)
    try:
        return _llm_agent(session_id, user_text)
    except Exception as e:  # keep the demo alive if the API fails
        res = offline_agent(session_id, user_text)
        res["steps"].insert(0, {"tool": "llm_error", "input": {}, "summary": f"fallback mode ({type(e).__name__})"})
        return res


def _llm_agent(session_id: str, user_text: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    msgs = SESSIONS.setdefault(session_id, [])
    msgs.append({"role": "user", "content": user_text})
    steps, drafts = [], []

    for _ in range(MAX_STEPS):
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                      tools=TOOL_SCHEMAS, messages=msgs)
        msgs.append({"role": "assistant", "content": [b.model_dump(exclude_none=True) for b in resp.content]})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return {"reply": text, "steps": steps, "drafts": drafts}
        results = []
        for b in resp.content:
            if b.type != "tool_use":
                continue
            out = run_tool(b.name, b.input)
            steps.append({"tool": b.name, "input": b.input, "summary": _summarize(out)})
            if isinstance(out, dict) and out.get("draft_id"):
                drafts.append(out["draft_id"])
            results.append({"type": "tool_result", "tool_use_id": b.id,
                            "content": json.dumps(out, ensure_ascii=False)})
        msgs.append({"role": "user", "content": results})
    return {"reply": "Maaf kijiye, request poori nahi ho paayi. Dobara try karein.", "steps": steps, "drafts": drafts}


# ---------- offline fallback (no API key) ----------
_OCC = {
    "farmer": ["kisan", "kheti", "farmer", "किसान", "खेती"],
    "student": ["student", "padhai", "chhatra", "छात्र", "विद्यार्थी"],
    "street_vendor": ["thela", "vendor", "rehdi", "ठेला", "रेहड़ी"],
    "self_employed": ["dukan", "business", "vyapar", "दुकान", "व्यापार"],
    "homemaker": ["housewife", "homemaker", "grihini", "गृहिणी"],
}


def _parse_profile(text: str) -> dict:
    t, p = text.lower(), {}
    m = re.search(r"(\d{1,3})\s*(?:saal|sal|years?|yrs?|वर्ष|साल)", t) or re.search(r"age\s*[:=]?\s*(\d{1,3})", t)
    if m: p["age"] = int(m.group(1))
    for occ, words in _OCC.items():
        if any(w in t for w in words): p["occupation"] = occ; break
    if re.search(r"mahila|woman|female|ladki|महिला|लड़की", t): p["gender"] = "female"
    elif re.search(r"\bmale\b|aadmi|purush|ladka|पुरुष", t): p["gender"] = "male"
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:lakh|lac|लाख)", t)
    if m: p["annual_income"] = int(float(m.group(1)) * 100000)
    else:
        m = re.search(r"(?:income|aay|आय)\D{0,12}(\d{4,8})", t)
        if m: p["annual_income"] = int(m.group(1))
    for c in ("sc", "st", "obc", "general"):
        if re.search(rf"\b{c}\b", t): p["category"] = c.upper() if c != "general" else "General"
    if re.search(r"pregnant|garbhwati|गर्भवती", t): p["is_pregnant"] = True
    return p


def offline_agent(session_id: str, user_text: str) -> dict:
    prof = PROFILES.setdefault(session_id, {})
    prof.update(_parse_profile(user_text))
    res = check_eligibility(prof)
    steps = [{"tool": "check_eligibility", "input": {"profile": dict(prof)}, "summary": _summarize(res)}]
    lines = []
    if res["likely_eligible"]:
        lines.append("Aap in yojanaon ke liye eligible lag rahe hain:")
        lines += [f"- {s['name_hi']} ({s['name']}): {s['benefit']}" for s in res["likely_eligible"]]
    else:
        lines.append("Abhi tak koi yojana pakki match nahi hui.")
    if res["need_more_info"]:
        need = sorted({f for s in res["need_more_info"] for f in s["need_info"]})
        lines.append("Aur sahi result ke liye bataiye: " + ", ".join(need[:4]))
    lines.append("(Offline mode - details official portal par verify karein.)")
    return {"reply": "\n".join(lines), "steps": steps, "drafts": []}
