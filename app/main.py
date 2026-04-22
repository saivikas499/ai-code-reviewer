"""
FastAPI — AI Code Reviewer
http://localhost:8000        → frontend UI
http://localhost:8000/docs   → API docs
"""

import os
import time
import pathlib
from collections import defaultdict

from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from app.models          import ReviewRequest, ReviewResponse, FixRequest, FixResponse
from app.reviewer        import review_code, fix_issue, detect_language
from app.repo_analyzer   import get_repo_info, get_repo_files, get_file_content
from app.github_handler  import router as github_router   # ← registers /github/webhook
import app.reviewer as _rev

# ── App ───────────────────────────────────────────────────────

app = FastAPI(
    title="AI Code Reviewer",
    description="AI-powered code review using Groq + Llama 3.3 (free).",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register GitHub webhook routes (/github/webhook)
app.include_router(github_router)

_FRONTEND = pathlib.Path(__file__).parent.parent / "frontend"

# ── Simple in-memory rate limiter ─────────────────────────────
# Max 30 review requests per IP per hour

_request_counts: dict = defaultdict(list)
RATE_LIMIT = 30
RATE_WINDOW = 3600  # seconds

def _check_rate_limit(request: Request):
    ip  = request.client.host
    now = time.time()
    # Keep only timestamps within the window
    _request_counts[ip] = [t for t in _request_counts[ip] if now - t < RATE_WINDOW]
    if len(_request_counts[ip]) >= RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded — max {RATE_LIMIT} reviews per hour per IP.",
        )
    _request_counts[ip].append(now)


# ── Root → serve frontend ─────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    index = _FRONTEND / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "AI Code Reviewer API is running", "docs": "/docs"}


# ── Health ────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health():
    return {
        "status":    "ok",
        "provider":  _rev.PROVIDER,
        "model":     _rev.MODEL,
        "timestamp": time.time(),
    }


# ── Code review endpoints ─────────────────────────────────────

@app.post("/review", response_model=ReviewResponse, tags=["Review"])
def review_endpoint(request: ReviewRequest, req: Request):
    """Review code submitted as plain text."""
    _check_rate_limit(req)
    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")
    try:
        result = review_code(
            code=request.code,
            language=request.language,
            filename=request.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}")

    return ReviewResponse(
        success=True,
        language=request.language,
        filename=request.filename,
        result=result,
        model_used=_rev.MODEL,
    )


@app.post("/review-file", response_model=ReviewResponse, tags=["Review"])
async def review_file_endpoint(req: Request, file: UploadFile = File(...)):
    """Upload a source code file directly for review."""
    _check_rate_limit(req)
    content = await file.read()
    try:
        code = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.")

    if not code.strip():
        raise HTTPException(status_code=400, detail="File is empty.")

    language = detect_language(file.filename or "unknown.py")
    try:
        result = review_code(code=code, language=language, filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}")

    return ReviewResponse(
        success=True,
        language=language,
        filename=file.filename,
        result=result,
        model_used=_rev.MODEL,
    )


@app.post("/fix", response_model=FixResponse, tags=["Fix"])
def fix_endpoint(request: FixRequest, req: Request):
    """Auto-fix one specific issue returned from /review."""
    _check_rate_limit(req)
    if not request.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")
    try:
        result = fix_issue(
            code=request.code,
            issue=request.issue,
            language=request.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fix failed: {str(e)}")

    if not result.success:
        raise HTTPException(status_code=422, detail=result.error)

    return result


# ── GitHub repo analysis ──────────────────────────────────────

@app.get("/repo/info", tags=["Repo"])
def repo_info(url: str):
    """Fetch metadata for any public GitHub repo."""
    try:
        return get_repo_info(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/repo/files", tags=["Repo"])
def repo_files(url: str, max_files: int = 40):
    """List all reviewable source files in a public GitHub repo."""
    try:
        return {"files": get_repo_files(url, max_files=max_files)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/repo/analyze-file", tags=["Repo"])
def analyze_repo_file(payload: dict, req: Request):
    """
    Fetch and review one file from a public GitHub repo.
    Body: { "download_url": "...", "path": "src/app.py" }
    """
    _check_rate_limit(req)
    download_url = payload.get("download_url", "")
    path         = payload.get("path", "unknown")

    if not download_url:
        raise HTTPException(status_code=400, detail="download_url is required.")

    try:
        code     = get_file_content(download_url)
        language = detect_language(path)
        result   = review_code(code, language=language, filename=path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "path":       path,
        "language":   language,
        "char_count": len(code),
        "result":     result.model_dump(),
    }


# ── Serve static frontend assets ─────────────────────────────

if _FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(_FRONTEND)), name="static")


# ── Dev entry point ───────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=True,
    )