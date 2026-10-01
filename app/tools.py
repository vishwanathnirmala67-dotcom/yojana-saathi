"""Tools the agent can call. Pure Python, no network needed."""
import json
import uuid
from datetime import date
from pathlib import Path

_DATA = json.loads((Path(__file__).parent / "data" / "schemes.json").read_text(encoding="utf-8"))
SCHEMES = {s["id"]: s for s in _DATA["schemes"]}
DISCLAIMER = _DATA["disclaimer"]
DRAFTS: dict[str, str] = {}


def _evaluate(scheme: dict, p: dict):
    """Return (status, missing_fields, fail_reasons) for one scheme."""
    r = scheme["rules"]
    missing, fails = [], []
    age, income = p.get("age"), p.get("annual_income")

    if "min_age" in r:
        if age is None: missing.append("age")
        elif age < r["min_age"]: fails.append(f"minimum age is {r['min_age']}")
    if "max_age" in r:
        if age is None: missing.append("age")
        elif age > r["max_age"]: fails.append(f"maximum age is {r['max_age']}")
    if "max_income" in r:
        waived = age is not None and age >= r.get("income_waiver_age", 999)
        if not waived:
            if income is None: missing.append("annual_income")
            elif income > r["max_income"]: fails.append(f"income limit is about Rs {r['max_income']:,}")
    if "occupations" in r:
        occ = p.get("occupation")
        if occ is None: missing.append("occupation")
        elif occ not in r["occupations"]: fails.append("for " + "/".join(r["occupations"]) + " only")
    if "gender" in r:
        g = p.get("gender")
        if g is None: missing.append("gender")
        elif g != r["gender"]: fails.append(f"for {r['gender']} applicants only")
    if "categories" in r:
        c = p.get("category")
        if c is None: missing.append("category")
        elif c not in r["categories"]: fails.append("for " + "/".join(r["categories"]) + " category only")
    for key, want in r.get("requires", {}).items():
        val = p.get(key)
        if val is None: missing.append(key)
        elif val != want: fails.append(f"requires {key} = {want}")

    if fails: return "not_eligible", [], fails
    if missing: return "need_more_info", sorted(set(missing)), []
    return "likely_eligible", [], []


def check_eligibility(profile: dict) -> dict:
    likely, maybe, no = [], [], []
    for s in SCHEMES.values():
        status, missing, fails = _evaluate(s, profile)
        item = {"id": s["id"], "name": s["name"], "name_hi": s["name_hi"], "benefit": s["benefit"]}
        if status == "likely_eligible": likely.append(item)
        elif status == "need_more_info": maybe.append({**item, "need_info": missing})
        else: no.append({"id": s["id"], "name": s["name"], "why_not": fails})
    return {"likely_eligible": likely, "need_more_info": maybe, "not_eligible": no, "note": DISCLAIMER}


def document_checklist(scheme_id: str) -> dict:
    s = SCHEMES.get(scheme_id)
    if not s:
        return {"error": f"unknown scheme_id. valid: {list(SCHEMES)}"}
    return {
        "scheme": s["name"], "documents": s["documents"], "apply_at": s["office"],
        "official_link": s["link"],
        "steps": ["Collect the documents listed", f"Visit {s['office']} or the official portal",
                  "Fill the application form and attach self-attested copies",
                  "Keep the acknowledgement / application number safe"],
    }


def find_center(state: str, district: str = "") -> dict:
    # Demo data. Replace with a real CSC locator API / dataset.
    place = f"{district}, {state}".strip(", ")
    return {
        "note": "Demo data - verify the address locally",
        "centers": [
            {"name": f"Common Service Centre (CSC) - {place}", "type": "CSC", "services": "most schemes, Aadhaar, bank mitra"},
            {"name": f"Block / Tehsil Office - {place}", "type": "Govt office", "services": "certificates, grievances"},
            {"name": f"Nearest Bank Branch - {place}", "type": "Bank", "services": "Jan Dhan, APY, Mudra"},
        ],
    }


def draft_letter(kind: str, name: str, address: str = "", scheme_id: str = "",
                 department: str = "", issue: str = "") -> dict:
    today = date.today().strftime("%d %B %Y")
    if kind == "application":
        s = SCHEMES.get(scheme_id)
        if not s:
            return {"error": "unknown scheme_id"}
        docs = "\n".join(f"  {i+1}. {d}" for i, d in enumerate(s["documents"]))
        text = (f"To,\nThe Concerned Officer,\n{s['office']}\n\n"
                f"Subject: Application for {s['name']}\n\nRespected Sir/Madam,\n\n"
                f"I, {name}, resident of {address or '[address]'}, request you to kindly enrol me "
                f"under {s['name']}. I believe I meet the eligibility conditions of the scheme.\n\n"
                f"Documents enclosed:\n{docs}\n\nKindly process my application at the earliest.\n\n"
                f"Yours faithfully,\n{name}\nDate: {today}\nMobile: [mobile number]\n")
    elif kind == "grievance":
        text = (f"To,\nThe Grievance Officer,\n{department or '[Department]'}\n\n"
                f"Subject: Complaint regarding {issue[:80] or '[issue]'}\n\nRespected Sir/Madam,\n\n"
                f"I, {name}, resident of {address or '[address]'}, wish to bring the following issue "
                f"to your notice:\n\n  {issue or '[describe issue]'}\n\n"
                f"I request you to take necessary action and inform me of the status. "
                f"Supporting documents are attached.\n\nYours faithfully,\n{name}\nDate: {today}\n")
    else:
        return {"error": "kind must be 'application' or 'grievance'"}
    did = uuid.uuid4().hex[:10]
    DRAFTS[did] = text
    return {"draft_id": did, "download": f"/draft/{did}", "text": text}


TOOL_SCHEMAS = [
    {
        "name": "check_eligibility",
        "description": "Check which government schemes the citizen is eligible for. Pass every profile field known so far; unknown fields are simply omitted.",
        "input_schema": {"type": "object", "properties": {"profile": {"type": "object", "properties": {
            "age": {"type": "integer"},
            "gender": {"type": "string", "enum": ["male", "female", "other"]},
            "state": {"type": "string"},
            "occupation": {"type": "string", "enum": ["farmer", "student", "street_vendor", "self_employed", "salaried", "unemployed", "homemaker", "other"]},
            "annual_income": {"type": "integer", "description": "Household income in rupees per year"},
            "category": {"type": "string", "enum": ["General", "OBC", "SC", "ST"]},
            "is_pregnant": {"type": "boolean"},
            "has_bank_account": {"type": "boolean"},
            "owns_pucca_house": {"type": "boolean"},
            "has_lpg": {"type": "boolean"}}}}, "required": ["profile"]},
    },
    {
        "name": "document_checklist",
        "description": "Get required documents, where to apply and steps for one scheme.",
        "input_schema": {"type": "object", "properties": {"scheme_id": {"type": "string"}}, "required": ["scheme_id"]},
    },
    {
        "name": "find_center",
        "description": "Find nearby service centres (CSC, govt office, bank) for the user's area.",
        "input_schema": {"type": "object", "properties": {"state": {"type": "string"}, "district": {"type": "string"}}, "required": ["state"]},
    },
    {
        "name": "draft_letter",
        "description": "Create a ready-to-print application letter for a scheme or a grievance letter to a department. Returns a download link.",
        "input_schema": {"type": "object", "properties": {
            "kind": {"type": "string", "enum": ["application", "grievance"]},
            "name": {"type": "string"}, "address": {"type": "string"},
            "scheme_id": {"type": "string"}, "department": {"type": "string"}, "issue": {"type": "string"}},
            "required": ["kind", "name"]},
    },
]

_FUNCS = {"check_eligibility": check_eligibility, "document_checklist": document_checklist,
          "find_center": find_center, "draft_letter": draft_letter}


def run_tool(name: str, args: dict):
    fn = _FUNCS.get(name)
    if not fn:
        return {"error": f"unknown tool {name}"}
    try:
        return fn(**args)
    except TypeError as e:
        return {"error": f"bad arguments: {e}"}
