"""
GitHub integration — Phase 3 (GitHub Apps are FREE).

Free setup:
  - GitHub App creation: FREE
  - Webhook events: FREE
  - PR comments via API: FREE
  - Local testing: use ngrok free tier (https://ngrok.com)

Steps to set up (do this after Phase 1+2 work):
  1. Go to https://github.com/settings/apps/new
  2. Set webhook URL to: https://your-ngrok-url.ngrok-free.app/github/webhook
  3. Permissions needed: Pull requests (Read & Write), Contents (Read)
  4. Subscribe to: Pull request events
  5. Download private key → save as private-key.pem in project root
  6. Fill .env: GITHUB_APP_ID, GITHUB_WEBHOOK_SECRET
  7. Install the app on your repo
"""

import os
import hmac
import hashlib
import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

router = APIRouter(prefix="/github", tags=["GitHub"])

WEBHOOK_SECRET   = os.getenv("GITHUB_WEBHOOK_SECRET", "")
APP_ID           = os.getenv("GITHUB_APP_ID", "")
PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH", "private-key.pem")

# Only review these file types (skip images, lock files, etc.)
REVIEWABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".go", ".rb",
    ".cpp", ".c", ".cs", ".php", ".rs", ".kt",
}


# ── Verify webhook came from GitHub ──────────────────────────

def _verify_signature(payload: bytes, sig_header: Optional[str]) -> bool:
    if not WEBHOOK_SECRET or not sig_header:
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


# ── Get authenticated GitHub client for this installation ────

def _get_gh_client(installation_id: int):
    from github import GithubIntegration, Github
    with open(PRIVATE_KEY_PATH) as f:
        private_key = f.read()
    integration = GithubIntegration(APP_ID, private_key)
    token = integration.get_access_token(installation_id).token
    return Github(token)


# ── Core: review PR files, post inline comments ──────────────

def _review_pr(gh, repo_full_name: str, pr_number: int):
    from app.reviewer import review_code, detect_language

    repo = gh.get_repo(repo_full_name)
    pr   = repo.get_pull(pr_number)

    all_issues    = []
    high_count    = 0

    for pr_file in pr.get_files():
        ext = os.path.splitext(pr_file.filename)[1].lower()

        if ext not in REVIEWABLE_EXTENSIONS:
            continue
        if pr_file.status == "removed":
            continue

        try:
            content = repo.get_contents(
                pr_file.filename, ref=pr.head.sha
            ).decoded_content.decode("utf-8")
        except Exception as e:
            log.warning(f"Cannot read {pr_file.filename}: {e}")
            continue

        language = detect_language(pr_file.filename)
        log.info(f"Reviewing {pr_file.filename} ({language})")

        try:
            result = review_code(content, language=language, filename=pr_file.filename)
        except Exception as e:
            log.error(f"Review failed for {pr_file.filename}: {e}")
            continue

        all_issues.extend(result.issues)
        high_count += sum(1 for i in result.issues if i.severity == "high")

        # Post one inline comment per issue
        icons = {"high": "🔴", "medium": "🟡", "low": "🔵"}
        for issue in result.issues:
            body = (
                f"{icons.get(issue.severity, '⚪')} "
                f"**[{issue.severity.upper()}] {issue.type.capitalize()}**\n\n"
                f"{issue.message}\n\n"
                f"**Fix:**\n```{language}\n{issue.fix}\n```\n\n"
                f"*— AI Code Reviewer (Llama 3 via Groq)*"
            )
            try:
                pr.create_review_comment(
                    body=body,
                    commit=repo.get_commit(pr.head.sha),
                    path=pr_file.filename,
                    line=issue.line,
                )
            except Exception as e:
                log.warning(f"Could not post comment on line {issue.line}: {e}")

    # Post summary comment
    if all_issues:
        rows = "\n".join(
            f"| {s.capitalize()} | {sum(1 for i in all_issues if i.severity == s)} |"
            for s in ("high", "medium", "low")
            if any(i.severity == s for i in all_issues)
        )
        summary = (
            f"## AI Code Review Summary\n\n"
            f"Found **{len(all_issues)} issue(s)** in this PR.\n\n"
            f"| Severity | Count |\n|---|---|\n{rows}\n\n"
            f"*Powered by Llama 3.3 70B via Groq (free tier)*"
        )
        pr.create_issue_comment(summary)

    # Set commit status (green/red check on the PR)
    state = "failure" if high_count > 0 else "success"
    desc  = (
        f"{high_count} critical issue(s) — please fix before merging"
        if high_count else "No critical issues found"
    )
    repo.get_commit(pr.head.sha).create_status(
        state=state, description=desc, context="ai-code-reviewer"
    )
    log.info(f"PR #{pr_number}: commit status → {state}")


# ── Webhook endpoint ──────────────────────────────────────────

@router.post("/webhook")
async def github_webhook(request: Request):
    """
    Receives pull_request events from GitHub.
    Triggers AI review when a PR is opened or updated.
    """
    if not APP_ID:
        raise HTTPException(
            status_code=503,
            detail=(
                "GitHub integration not configured yet.\n"
                "Set GITHUB_APP_ID and GITHUB_WEBHOOK_SECRET in .env\n"
                "See app/github_handler.py for setup steps."
            ),
        )

    payload_bytes = await request.body()
    signature     = request.headers.get("X-Hub-Signature-256")

    if not _verify_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    event   = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()

    if event != "pull_request":
        return {"message": f"Event '{event}' ignored (only pull_request handled)"}

    action = payload.get("action", "")
    if action not in ("opened", "synchronize"):
        return {"message": f"Action '{action}' ignored"}

    installation_id = payload["installation"]["id"]
    repo_name       = payload["repository"]["full_name"]
    pr_number       = payload["pull_request"]["number"]

    log.info(f"Reviewing PR #{pr_number} in {repo_name}")

    try:
        gh = _get_gh_client(installation_id)
        _review_pr(gh, repo_name, pr_number)
    except Exception as e:
        log.error(f"PR review failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": f"PR #{pr_number} reviewed successfully"}