"""
Core AI review engine — uses Groq (FREE).
Model: llama-3.3-70b-versatile
Free tier: 6,000 requests/day, no credit card needed.
"""

import os
import json
import re
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from app.models import ReviewResult, CodeIssue, FixResponse

# ── Config ────────────────────────────────────────────────────
PROVIDER = "groq"
MODEL    = "llama-3.3-70b-versatile"

# ── Lazy Groq client (created on first API call) ──────────────
_client = None

def _get_client():
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key or api_key.startswith("gsk_your"):
        raise ValueError(
            "\n\nGROQ_API_KEY is missing!\n"
            "Fix it in 30 seconds:\n"
            "  1. Go to https://console.groq.com/keys\n"
            "  2. Sign up free (no credit card)\n"
            "  3. Click 'Create API Key'\n"
            "  4. Open your .env file and set:\n"
            "     GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx\n"
        )
    from groq import Groq
    _client = Groq(api_key=api_key)
    return _client


# ── Prompts ───────────────────────────────────────────────────

REVIEW_SYSTEM = """You are a senior software engineer doing a thorough code review.
Identify bugs, security vulnerabilities, performance issues, and bad practices.
You MUST respond with ONLY a valid JSON object — no markdown, no explanation, no code fences.
"""

REVIEW_PROMPT = """Review this {language} code and return ONLY this exact JSON structure:

{{
  "issues": [
    {{
      "line": <integer>,
      "severity": "<high|medium|low>",
      "type": "<bug|security|performance|style>",
      "message": "<what is wrong>",
      "fix": "<corrected code>"
    }}
  ],
  "summary": "<one sentence overall verdict>",
  "score": <integer 0-10>
}}

Severity guide:
  high   = crash / data loss / security hole
  medium = logic error / bad practice
  low    = style / minor improvement

Return ONLY the JSON. No markdown. No extra text.

File: {filename}
```{language}
{code}
```"""

FIX_SYSTEM = """You are a senior engineer who writes clean bug fixes.
Return ONLY a JSON object. No markdown. No extra text outside the JSON."""

FIX_PROMPT = """Fix this specific issue in the {language} code below.

Issue   : {issue_message}
Type    : {issue_type}
Severity: {issue_severity}

```{language}
{code}
```

Return ONLY this JSON:
{{
  "fixed_code": "<full corrected code>",
  "explanation": "<what you changed and why, in 1-2 sentences>"
}}"""


# ── Helpers ───────────────────────────────────────────────────

def _clean_json(raw: str) -> dict:
    """Remove any accidental markdown fences and parse JSON."""
    text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
    text = re.sub(r"\s*```$", "", text).strip()
    return json.loads(text)


def _call_llm(system: str, user: str, max_tokens: int = 2048) -> str:
    """Call Groq and return the response text."""
    client = _get_client()
    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=0.1,        # low temp = more consistent JSON output
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return response.choices[0].message.content


# ── Public API ────────────────────────────────────────────────

def review_code(
    code: str,
    language: str = "python",
    filename: Optional[str] = None,
) -> ReviewResult:
    """
    Review code using Groq/Llama.
    Returns a ReviewResult with issues, summary, and quality score.
    """
    prompt = REVIEW_PROMPT.format(
        language=language,
        filename=filename or "unknown",
        code=code,
    )
    raw = _call_llm(REVIEW_SYSTEM, prompt)

    try:
        data = _clean_json(raw)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"LLM returned invalid JSON.\n"
            f"JSONDecodeError: {e}\n"
            f"Raw LLM output:\n{raw}"
        )
    return ReviewResult(**data)


def fix_issue(
    code: str,
    issue: CodeIssue,
    language: str = "python",
) -> FixResponse:
    """
    Fix a specific issue using Groq/Llama.
    Returns fixed code and an explanation of the change.
    """
    prompt = FIX_PROMPT.format(
        language=language,
        issue_message=issue.message,
        issue_type=issue.type,
        issue_severity=issue.severity,
        code=code,
    )
    raw = _call_llm(FIX_SYSTEM, prompt)

    try:
        data = _clean_json(raw)
    except json.JSONDecodeError as e:
        return FixResponse(
            success=False,
            original=code,
            error=f"LLM returned invalid JSON: {e}",
        )

    return FixResponse(
        success=True,
        original=code,
        fixed_code=data.get("fixed_code"),
        explanation=data.get("explanation"),
    )


# ── Language detection ────────────────────────────────────────

EXTENSION_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".java": "java",  ".go": "go",         ".rb": "ruby",
    ".cpp": "cpp",    ".c": "c",           ".cs": "csharp",
    ".php": "php",    ".rs": "rust",       ".kt": "kotlin",
}

def detect_language(filename: str) -> str:
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXTENSION_MAP.get(ext, "python")