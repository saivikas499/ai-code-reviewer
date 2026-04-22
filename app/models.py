from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class Severity(str, Enum):
    HIGH   = "high"
    MEDIUM = "medium"
    LOW    = "low"


class IssueType(str, Enum):
    BUG         = "bug"
    SECURITY    = "security"
    PERFORMANCE = "performance"
    STYLE       = "style"


# ── Individual issue found in code ──────────────────────────
class CodeIssue(BaseModel):
    line:     int                = Field(..., description="Line number where the issue occurs")
    severity: Severity           = Field(..., description="How critical is this issue")
    type:     IssueType          = Field(..., description="Category of the issue")
    message:  str                = Field(..., description="Human-readable description of the problem")
    fix:      str                = Field(..., description="Corrected code snippet or suggestion")


# ── Full review result ───────────────────────────────────────
class ReviewResult(BaseModel):
    issues:  List[CodeIssue]     = Field(default_factory=list)
    summary: str                 = Field(..., description="One-sentence overall assessment")
    score:   int                 = Field(..., ge=0, le=10, description="Code quality score out of 10")


# ── HTTP request body for /review endpoint ──────────────────
class ReviewRequest(BaseModel):
    code:     str                = Field(..., description="Source code to review")
    language: str                = Field(default="python", description="Programming language")
    filename: Optional[str]      = Field(default=None, description="Optional filename for context")


# ── HTTP response from /review endpoint ─────────────────────
class ReviewResponse(BaseModel):
    success:    bool
    language:   str
    filename:   Optional[str]
    result:     Optional[ReviewResult]
    error:      Optional[str]        = None
    model_used: str


# ── HTTP request body for /fix endpoint ─────────────────────
class FixRequest(BaseModel):
    code:     str                = Field(..., description="Original code with bugs")
    issue:    CodeIssue          = Field(..., description="The specific issue to fix")
    language: str                = Field(default="python")


# ── HTTP response from /fix endpoint ────────────────────────
class FixResponse(BaseModel):
    success:      bool
    original:     str
    fixed_code:   Optional[str]  = None
    explanation:  Optional[str]  = None
    error:        Optional[str]  = None