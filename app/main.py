"""
FastAPI — AI Code Reviewer
Opening http://localhost:8000 serves the frontend UI directly.
API docs: http://localhost:8000/docs
"""

import os
import time
import pathlib

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from dotenv import load_dotenv

load_dotenv()

from app.models        import ReviewRequest, ReviewResponse, FixRequest, FixResponse
from app.reviewer      import review_code, fix_issue, detect_language
from app.repo_analyzer import get_repo_info, get_repo_files, get_file_content
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

_FRONTEND = pathlib.Path(__file__).parent.parent / "frontend"

# ── Root → serve frontend ─────────────────────────────────────

@app.get("/", include_in_schema=False)
def root():
    """Serve the frontend UI at localhost:8000"""
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
def review_endpoint(request: ReviewRequest):
    """Submit code as plain text for AI review."""
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
async def review_file_endpoint(file: UploadFile = File(...)):
    """Upload a source code file directly for review."""
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
def fix_endpoint(request: FixRequest):
    """Auto-fix a specific issue returned from /review."""
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


# ── GitHub repo analysis endpoints ───────────────────────────

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
def analyze_repo_file(payload: dict):
    """
    Fetch and review one file from a public GitHub repo.
    Body: { "download_url": "...", "path": "src/app.py" }
    """
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


# ── Serve static frontend assets (CSS/JS if split later) ─────

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