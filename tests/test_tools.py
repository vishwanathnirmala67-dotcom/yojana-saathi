from app.tools import check_eligibility, document_checklist, draft_letter
from app.agent import offline_agent


def ids(res, key):
    return {s["id"] for s in res[key]}


def test_farmer_gets_pm_kisan():
    res = check_eligibility({"age": 45, "occupation": "farmer", "annual_income": 150000})
    assert "pm-kisan" in ids(res, "likely_eligible")


def test_sc_student_scholarship():
    res = check_eligibility({"age": 20, "occupation": "student", "category": "SC", "annual_income": 200000})
    assert "post-matric-sc" in ids(res, "likely_eligible")


def test_over_income_not_eligible():
    res = check_eligibility({"age": 20, "occupation": "student", "category": "SC", "annual_income": 900000})
    assert "post-matric-sc" in ids(res, "not_eligible")


def test_missing_info_asks_more():
    res = check_eligibility({"age": 30})
    assert "apy" in ids(res, "need_more_info")


def test_documents_and_letter():
    assert "Aadhaar card" in document_checklist("pm-kisan")["documents"]
    d = draft_letter("application", "Ramesh", "Village X", scheme_id="pm-kisan")
    assert d["draft_id"] and "PM-KISAN" in d["text"]


def test_offline_agent():
    r = offline_agent("t1", "Main 45 saal ka kisan hoon, income 1.5 lakh")
    assert "PM-KISAN" in r["reply"]
