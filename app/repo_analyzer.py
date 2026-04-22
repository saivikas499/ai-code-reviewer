"""
GitHub public repo analyzer — no auth needed for public repos.
Uses GitHub's REST API (unauthenticated: 60 req/hour, enough for demos).
"""

import os
import re
import httpx
from typing import Optional
from dotenv import load_dotenv
load_dotenv()

# Optional: set GITHUB_TOKEN in .env for 5000 req/hour (still free via GitHub account)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "ai-code-reviewer",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

# File types we can meaningfully review
REVIEWABLE_EXT = {
    ".py", ".js", ".ts", ".java", ".go", ".rb",
    ".cpp", ".c", ".cs", ".php", ".rs", ".kt",
    ".jsx", ".tsx", ".vue", ".swift",
}

# Skip files that are too large or auto-generated
SKIP_PATTERNS = [
    "package-lock.json", "yarn.lock", "poetry.lock",
    "node_modules", ".min.js", ".bundle.js",
    "dist/", "build/", "__pycache__",
]

MAX_FILE_SIZE = 50_000  # 50KB — skip very large files


def _parse_github_url(url: str) -> tuple[str, str]:
    """Extract owner and repo from a GitHub URL."""
    url = url.strip().rstrip("/")
    # Handle formats: https://github.com/owner/repo or owner/repo
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if match:
        return match.group(1), match.group(2).replace(".git", "")
    parts = url.split("/")
    if len(parts) >= 2:
        return parts[-2], parts[-1].replace(".git", "")
    raise ValueError(f"Cannot parse GitHub URL: {url}")


def get_repo_info(url: str) -> dict:
    """Fetch basic repo metadata."""
    owner, repo = _parse_github_url(url)
    api_url = f"https://api.github.com/repos/{owner}/{repo}"

    with httpx.Client(headers=HEADERS, timeout=15) as client:
        r = client.get(api_url)
        if r.status_code == 404:
            raise ValueError(f"Repo not found: {owner}/{repo} — is it public?")
        if r.status_code == 403:
            raise ValueError("GitHub API rate limit hit. Add GITHUB_TOKEN to .env for higher limits.")
        r.raise_for_status()
        data = r.json()

    return {
        "owner":       owner,
        "repo":        repo,
        "full_name":   data["full_name"],
        "description": data.get("description", ""),
        "language":    data.get("language", "Unknown"),
        "stars":       data["stargazers_count"],
        "forks":       data["forks_count"],
        "url":         data["html_url"],
        "default_branch": data["default_branch"],
    }


def get_repo_files(url: str, max_files: int = 30) -> list[dict]:
    """
    List all reviewable files in a repo using the Git Tree API.
    Returns list of {path, size, download_url} dicts.
    """
    owner, repo = _parse_github_url(url)

    # Get default branch
    info = get_repo_info(url)
    branch = info["default_branch"]

    # Fetch full recursive file tree
    tree_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"

    with httpx.Client(headers=HEADERS, timeout=20) as client:
        r = client.get(tree_url)
        if r.status_code == 403:
            raise ValueError("GitHub API rate limit. Add GITHUB_TOKEN to .env.")
        r.raise_for_status()
        tree = r.json().get("tree", [])

    files = []
    for item in tree:
        if item["type"] != "blob":
            continue

        path = item["path"]
        size = item.get("size", 0)

        # Skip unreviewed types
        ext = "." + path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in REVIEWABLE_EXT:
            continue

        # Skip auto-generated / huge files
        if any(skip in path for skip in SKIP_PATTERNS):
            continue
        if size > MAX_FILE_SIZE:
            continue

        files.append({
            "path": path,
            "size": size,
            "ext":  ext,
            "download_url": f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}",
        })

    # Sort by path, limit count
    files.sort(key=lambda f: f["path"])
    return files[:max_files]


def get_file_content(download_url: str) -> str:
    """Fetch raw file content from GitHub."""
    with httpx.Client(timeout=10) as client:
        r = client.get(download_url)
        r.raise_for_status()
        return r.text