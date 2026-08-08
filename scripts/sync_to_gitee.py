#!/usr/bin/env python3
"""Mirror the gh-pages report JSON files to a public Gitee repository."""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


REPORT_FILES = ("personal.json", "media.json")
DEFAULT_SOURCE_BASE_URL = "https://kiwi-lilo.github.io/aliyun-opinion-report"
USER_AGENT = "aliyun-opinion-report-gitee-sync/1.0"


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_repo(value: str) -> tuple[str, str]:
    parts = [part.strip() for part in value.split("/", 1)]
    if len(parts) != 2 or not all(parts):
        raise ValueError("GITEE_REPO must use the owner/repository format")
    return parts[0], parts[1]


def validate_report(file_name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{file_name} must contain a JSON object")
    if not isinstance(value.get("stats"), dict):
        raise ValueError(f"{file_name} is missing the stats object")

    expected = ("recommendations", "items", "monitored_posts") if file_name == "personal.json" else ("items", "top10", "rss_candidates")
    if not any(isinstance(value.get(key), list) for key in expected):
        raise ValueError(f"{file_name} does not contain a recognized report list")
    return value


def read_local_report(source_dir: str, file_name: str) -> bytes:
    path = Path(source_dir).resolve() / file_name
    if not path.is_file():
        raise FileNotFoundError(f"Missing report file: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_report(file_name, value)
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def download_report(base_url: str, file_name: str) -> bytes:
    url = f"{base_url.rstrip('/')}/{urllib.parse.quote(file_name)}?sync={int(time.time())}"
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read()
    value = json.loads(content.decode("utf-8"))
    validate_report(file_name, value)
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"


def gitee_api_url(owner: str, repo: str, file_name: str) -> str:
    owner_part = urllib.parse.quote(owner, safe="")
    repo_part = urllib.parse.quote(repo, safe="")
    file_part = urllib.parse.quote(file_name, safe="/")
    return f"https://gitee.com/api/v5/repos/{owner_part}/{repo_part}/contents/{file_part}"


def request_json(method: str, url: str, *, payload: dict[str, Any] | None = None, timeout: int = 30) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    return json.loads(body.decode("utf-8")) if body else {}


def get_remote_file(owner: str, repo: str, file_name: str, branch: str, token: str) -> dict[str, Any] | None:
    query = urllib.parse.urlencode({"access_token": token, "ref": branch})
    url = f"{gitee_api_url(owner, repo, file_name)}?{query}"
    try:
        return request_json("GET", url)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def decode_remote_content(remote: dict[str, Any] | None) -> bytes | None:
    if not remote or not remote.get("content"):
        return None
    return base64.b64decode(str(remote["content"]).replace("\n", ""))


def upsert_file(owner: str, repo: str, file_name: str, branch: str, token: str, content: bytes) -> str:
    remote = get_remote_file(owner, repo, file_name, branch, token)
    if decode_remote_content(remote) == content:
        return "unchanged"

    payload: dict[str, Any] = {
        "access_token": token,
        "content": base64.b64encode(content).decode("ascii"),
        "message": f"Update {file_name}",
        "branch": branch,
    }
    method = "POST"
    if remote and remote.get("sha"):
        payload["sha"] = remote["sha"]
        method = "PUT"
    request_json(method, gitee_api_url(owner, repo, file_name), payload=payload)
    return "updated" if method == "PUT" else "created"


def main() -> int:
    token = require_env("GITEE_TOKEN")
    owner, repo = parse_repo(require_env("GITEE_REPO"))
    branch = os.environ.get("GITEE_BRANCH", "master").strip() or "master"
    source_dir = os.environ.get("SOURCE_DIR", "").strip()
    source_base_url = os.environ.get("SOURCE_BASE_URL", DEFAULT_SOURCE_BASE_URL).strip()
    if not source_dir and not source_base_url.startswith("https://"):
        raise RuntimeError("SOURCE_BASE_URL must use HTTPS")

    for file_name in REPORT_FILES:
        content = read_local_report(source_dir, file_name) if source_dir else download_report(source_base_url, file_name)
        result = upsert_file(owner, repo, file_name, branch, token, content)
        print(f"{file_name}: {result} ({len(content)} bytes)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Sync failed: {error}", file=sys.stderr)
        raise SystemExit(1)

