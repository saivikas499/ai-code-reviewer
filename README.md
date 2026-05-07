# CodeScope — AI Code Reviewer

> Scan any public GitHub repo for bugs, security vulnerabilities, and bad practices.
> Powered by **Llama 3.3 70B** via Groq. Entirely free.

---

## What it does

Paste any public GitHub URL. CodeScope fetches every source file, runs each one through an LLM, and gives you:

- **Bugs & crashes** — division by zero, null dereference, unhandled exceptions
- **Security vulnerabilities** — SQL injection, hardcoded secrets, insecure patterns
- **Performance issues** — O(n²) loops, inefficient string ops, unnecessary blocking calls
- **Bad practices** — mutable defaults, bare excepts, dead code
- **Auto-generated fixes** — not just "this is wrong" but the corrected code

Everything runs on free tools. No credit card anywhere.

---

## Tech stack

| Layer | Tool | Cost |
|---|---|---|
| LLM | Groq — Llama 3.3 70B | Free (6,000 req/day) |
| Backend | FastAPI + Uvicorn | Free / open source |
| Frontend | Vanilla HTML/CSS/JS | Free |
| GitHub repo fetch | GitHub REST API | Free for public repos |
| GitHub PR integration | GitHub Apps | Free to create |
| Local webhook testing | ngrok free tier | Free |
| Deployment | Railway / Render | Free tier |

---

## Project structure

```
ai-code-reviewer/
├── app/
│   ├── main.py              # FastAPI app — all endpoints + serves frontend
│   ├── reviewer.py          # Core AI engine — calls Groq, parses results
│   ├── models.py            # Pydantic request/response schemas
│   ├── repo_analyzer.py     # Fetches files from any public GitHub repo
│   └── github_handler.py    # GitHub webhook — reviews PRs automatically
├── frontend/
│   └── index.html           # Full UI — search, file browser, results, export
├── tests/
│   └── sample_buggy_code.py # 8 intentional bugs for testing
├── test_review.py           # CLI test — run this before starting the server
├── requirements.txt
├── .env.example
└── Dockerfile
```

---

## Getting started

### Prerequisites

- Python 3.11+
- A free [Groq API key](https://console.groq.com/keys) — no credit card needed

### 1. Clone the repo

```bash
git clone https://github.com/saivikas499/ai-code-reviewer.git
cd ai-code-reviewer
```

### 2. Create and activate a virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python -m venv venv
source venv/bin/activate
```

You'll see `(venv)` at the start of your prompt. Run all commands from inside the venv.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
# Windows
copy .env.example .env

# Mac / Linux
cp .env.example .env
```

Open `.env` and add your Groq key:

```env
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

### 5. Verify everything works

```bash
python test_review.py
```

This runs the AI engine against a file with 8 intentional bugs. You should see each one detected with a suggested fix.

### 6. Start the server

```bash
uvicorn app.main:app --reload
```

Open **http://localhost:8000** — the UI loads directly.

---

## Using the app

1. Enter any public GitHub repo — e.g. `tiangolo/fastapi` or the full URL
2. The file browser lists all reviewable source files (auto-selected)
3. Deselect any files you want to skip, then click **Run Analysis**
4. Watch each file get reviewed in real time
5. Filter results by severity or category, expand any issue to see the fix
6. Click **Export JSON** to download the full report

---

## API endpoints

The backend exposes a REST API you can call directly or explore at `/docs`.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Server status and model info |
| `POST` | `/review` | Review code passed as plain text |
| `POST` | `/review-file` | Upload a file for review |
| `POST` | `/fix` | Auto-fix one specific issue |
| `GET` | `/repo/info?url=` | Fetch metadata for a public repo |
| `GET` | `/repo/files?url=` | List reviewable files in a repo |
| `POST` | `/repo/analyze-file` | Fetch and review one file from a repo |

Interactive docs: **http://localhost:8000/docs**

---

## GitHub PR integration

When set up, CodeScope automatically reviews every pull request and posts inline comments.

```
PR opened on GitHub
        ↓
GitHub sends webhook to /github/webhook
        ↓
CodeScope fetches changed files from the diff
        ↓
Each file reviewed by Llama 3.3 via Groq
        ↓
Inline comments posted on specific lines
        ↓
Green ✓ or Red ✗ status check set on the PR
```

**Setup (all free):**

1. Run `ngrok http 8000` — copy the `https://xxx.ngrok-free.app` URL
2. Go to [github.com/settings/apps/new](https://github.com/settings/apps/new)
3. Set webhook URL: `https://xxx.ngrok-free.app/github/webhook`
4. Set a webhook secret (any random string — add to `.env` as `GITHUB_WEBHOOK_SECRET`)
5. Permissions: Pull requests → Read & Write, Contents → Read
6. Subscribe to: Pull request events
7. Download the private key → save as `private-key.pem` in the project root
8. Copy the App ID into `.env` as `GITHUB_APP_ID`
9. Install the app on your repo from the app's settings page

---

## Deploy for free

### Railway (recommended)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Add your environment variables in the Railway dashboard under Variables.

### Render

1. Push the repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your repo
4. Build command: `pip install -r requirements.txt`
5. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add `GROQ_API_KEY` and `LLM_PROVIDER` under Environment

---

## License

MIT