# AI Code Reviewer

An AI-powered code review agent built entirely on **free tools**.
Detects bugs, security holes, and bad practices — then generates corrected code.

## Everything here is FREE

| Component | Free Tool | Details |
|---|---|---|
| LLM | Groq (Llama 3.3 70B) | 6,000 requests/day free |
| Backend | FastAPI + Uvicorn | Open source |
| GitHub integration | GitHub Apps | Free to create |
| Local webhook testing | ngrok free tier | Free public URL |
| Deployment | Railway / Render | Free tier available |
| Database | SQLite | Built into Python |

## Quickstart

### 1. Clone and set up venv

```powershell
git clone https://github.com/yourusername/ai-code-reviewer
cd ai-code-reviewer

python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt
```

### 2. Get your free Groq API key

1. Go to https://console.groq.com/keys
2. Sign up (no credit card needed)
3. Click "Create API Key"

### 3. Configure .env

```bash
cp .env.example .env
```

Open `.env` and set:
```
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

### 4. Test the AI engine

```powershell
python test_review.py
```

### 5. Start the API server

```powershell
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs — interactive API docs, ready to use.

## API Endpoints

### POST /review
```json
{
  "code": "def divide(a, b):\n    return a / b",
  "language": "python",
  "filename": "math.py"
}
```

### POST /fix
Pass back the original code + one issue from `/review` response. Gets corrected code.

### POST /review-file
Upload a `.py`, `.js`, `.ts` etc. file directly — language auto-detected.

## GitHub Integration (Phase 3 — all free)

```
GitHub PR opened
       ↓
GitHub sends webhook → your server /github/webhook
       ↓
Fetch changed files from PR diff
       ↓
Run AI review on each file (Groq/Llama)
       ↓
Post inline comments on specific lines
       ↓
Set green ✓ or red ✗ status check on the PR
```

**Setup steps:**
1. Start ngrok: `ngrok http 8000` → copy the `https://xxx.ngrok-free.app` URL
2. Create GitHub App at https://github.com/settings/apps/new
3. Set webhook URL to: `https://xxx.ngrok-free.app/github/webhook`
4. Set a webhook secret (any random string)
5. Give permissions: Pull requests (Read & Write), Contents (Read)
6. Download private key → save as `private-key.pem`
7. Fill in `.env`: `GITHUB_APP_ID` and `GITHUB_WEBHOOK_SECRET`
8. Install the app on your test repo

## Deploy for free

### Railway (recommended, easiest)
```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init
railway up
```

### Render free tier
1. Push to GitHub
2. Go to https://render.com
3. New → Web Service → connect your repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add environment variables (GROQ_API_KEY etc.)

## Project structure

```
ai-code-reviewer/
├── app/
│   ├── main.py             FastAPI app + all endpoints
│   ├── reviewer.py         Groq/Llama AI review engine
│   ├── models.py           Pydantic request/response schemas
│   └── github_handler.py   GitHub webhook + PR comment logic
├── tests/
│   └── sample_buggy_code.py  8 intentional bugs for testing
├── test_review.py          CLI test script (run this first)
├── requirements.txt
├── .env.example
└── Dockerfile
```

## License
MIT