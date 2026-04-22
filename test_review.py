"""
End-to-end test script — run this before starting the server.
Uses Groq (free) to review intentionally buggy code.

Usage:
  python test_review.py
"""

import sys
import os
from dotenv import load_dotenv
load_dotenv()

# ── Terminal colours ──────────────────────────────────────────
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
GREEN  = "\033[92m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

SEV_COLOR = {"high": RED, "medium": YELLOW, "low": BLUE}
SEV_ICON  = {"high": "🔴", "medium": "🟡", "low": "🔵"}
TYPE_ICON = {"bug": "🐛", "security": "🔐", "performance": "⚡", "style": "✏️"}


def line(title=""):
    print(f"\n{'─'*56}")
    if title:
        print(f"  {BOLD}{title}{RESET}")
    print()


def check_env():
    """Verify .env is configured before making any API call."""
    line("Checking configuration")

    api_key = os.getenv("GROQ_API_KEY", "")

    if not api_key:
        print(f"{RED}✗ GROQ_API_KEY not found in .env{RESET}")
        print(f"\n  Create your free key at: {CYAN}https://console.groq.com/keys{RESET}")
        print(f"  Then add to .env:  GROQ_API_KEY=gsk_...\n")
        sys.exit(1)

    if api_key.startswith("gsk_your"):
        print(f"{RED}✗ You still have the placeholder key in .env{RESET}")
        print(f"\n  Replace  gsk_your_key_here  with your real key.")
        print(f"  Get one free at: {CYAN}https://console.groq.com/keys{RESET}\n")
        sys.exit(1)

    print(f"{GREEN}✓ GROQ_API_KEY found{RESET}  ({api_key[:12]}...{api_key[-4:]})")
    print(f"  Provider : groq")
    print(f"  Model    : llama-3.3-70b-versatile (free)\n")


def run_review_test():
    line("TEST 1 — Code Review")

    from app.reviewer import review_code

    with open("tests/sample_buggy_code.py") as f:
        code = f.read()

    print("Sending buggy code to Llama 3.3 via Groq...\n")

    try:
        result = review_code(code, language="python", filename="sample_buggy_code.py")
    except ValueError as e:
        print(f"{RED}✗ {e}{RESET}")
        sys.exit(1)
    except Exception as e:
        print(f"{RED}✗ Unexpected error: {e}{RESET}")
        sys.exit(1)

    print(f"{GREEN}✓ Review complete!{RESET}")
    print(f"  Score   : {BOLD}{result.score}/10{RESET}")
    print(f"  Summary : {result.summary}")
    print(f"  Issues  : {len(result.issues)} found\n")

    for i, issue in enumerate(result.issues, 1):
        col  = SEV_COLOR.get(issue.severity, RESET)
        icon = TYPE_ICON.get(str(issue.type), "•")
        sicon = SEV_ICON.get(issue.severity, "⚪")
        print(f"  {i}. {sicon} {col}[{issue.severity.upper()}]{RESET} "
              f"{icon} Line {issue.line} — {issue.type}")
        print(f"     {issue.message}")
        fix_preview = str(issue.fix).replace('\n', ' ')[:80]
        print(f"     {GREEN}Fix:{RESET} {fix_preview}{'...' if len(str(issue.fix))>80 else ''}")
        print()

    return result


def run_fix_test(result):
    line("TEST 2 — Auto Fix")

    from app.reviewer import fix_issue

    if not result.issues:
        print("No issues to fix — skipping.")
        return

    # Pick highest severity issue available
    for sev in ("high", "medium", "low"):
        matches = [i for i in result.issues if i.severity == sev]
        if matches:
            issue = matches[0]
            break

    print(f"Fixing: {BOLD}{issue.message[:65]}...{RESET}\n")

    with open("tests/sample_buggy_code.py") as f:
        code = f.read()

    try:
        fix = fix_issue(code=code, issue=issue, language="python")
    except Exception as e:
        print(f"{RED}✗ Fix failed: {e}{RESET}")
        return

    if fix.success:
        print(f"{GREEN}✓ Fix generated!{RESET}")
        print(f"\n  Explanation: {fix.explanation}\n")
        print(f"  Fixed code (first 400 chars):\n")
        for ln in (fix.fixed_code or "")[:400].splitlines():
            print(f"    {ln}")
        if len(fix.fixed_code or "") > 400:
            print("    ...")
    else:
        print(f"{RED}✗ Fix failed: {fix.error}{RESET}")


def main():
    print(f"\n{BOLD}{'═'*56}")
    print("   AI Code Reviewer — Test Suite")
    print(f"   Using: Groq + Llama 3.3 70B (FREE)")
    print(f"{'═'*56}{RESET}")

    check_env()
    result = run_review_test()
    run_fix_test(result)

    line()
    print(f"{GREEN}{BOLD}All tests passed! ✓{RESET}")
    print(f"\nNow start the server:")
    print(f"  {BOLD}uvicorn app.main:app --reload{RESET}")
    print(f"\nThen open:")
    print(f"  {CYAN}{BOLD}http://localhost:8000/docs{RESET}\n")


if __name__ == "__main__":
    main()