# 🇮🇳 Yojana Saathi — Sarkari Yojana AI Agent
**BharatAgentic Hackathon (aiKart) · Category: Citizen & GovTech**

Citizen apni situation Hindi/Hinglish/English me batata hai. Agent khud:
1. profile samajhta hai aur missing info poochta hai
2. **tools** se eligibility check karta hai (`check_eligibility`)
3. documents + apply karne ki jagah batata hai (`document_checklist`, `find_center`)
4. **action:** application / grievance letter draft karta hai (`draft_letter`)

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # ANTHROPIC_API_KEY daalein (bina key ke offline demo mode chalta hai)
export ANTHROPIC_API_KEY=your_key
uvicorn app.main:app --reload
```
Open http://localhost:8000

## API
`POST /chat` `{ "message": "...", "session_id": "abc" }` → `{ reply, steps, drafts }`
`GET /health` · `GET /schemes` · `GET /draft/{id}`

## Docker
```bash
docker build -t yojana-saathi .
docker run -p 8000:8000 -e ANTHROPIC_API_KEY=your_key yojana-saathi
```

## Deploy (Method 2 — API endpoint)
Push to GitHub → Render/Railway → New Web Service → Docker → set `ANTHROPIC_API_KEY`. Endpoint: `https://<app>.onrender.com/chat`

## Tests
`pytest -q`

## Responsible AI
- Aadhaar / OTP / bank details kabhi nahi maange jaate
- Scheme data demo hai (approximate) — official portal par verify karein
- Eligibility "likely" hota hai, final decision sarkari office ka
