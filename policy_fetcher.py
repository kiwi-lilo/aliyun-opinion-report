"""Fetch, date-filter, and summarize policy items from approved sources."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests

from policy_analyzer import normalize_item, parse_date, timeliness
from policy_sources import POLICY_SOURCES, source_for_url

log = logging.getLogger(__name__)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}
POLICY_WORDS = ("政策", "办法", "方案", "通知", "意见", "条例", "行动计划", "规划", "措施", "实施细则", "细则")
DATE_RE = re.compile(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})")
STAMP_RE = re.compile(r"(?:京政发|沪府|苏政发|浙政发|粤府|鄂政发|湘政发|鲁政发|川府发|渝府发|豫政|皖政|闽政|冀政发)?\s*[〔\[]?(20\d{2})[〕\]]?\s*年?\s*\d+号")


def _html_text(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"&(?:nbsp|amp|quot|lt|gt);", " ", value)
    return " ".join(value.split())


def _date_from_text(text: str) -> tuple[str, str]:
    """Return (date, confidence); avoid effective/expiry dates."""
    patterns = (
        r"(?:发布日期|发布时间|印发日期|成文日期|签发日期|落款日期)\s*[:：]?\s*(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})",
        r"(?:发布|印发|成文|签发)日期?\s*[:：]?\s*(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})",
        r"(?:发布|印发|成文|签发|落款)[^。；\n]{0,24}?(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    )
    for pattern in patterns:
        matches = re.findall(pattern, text[:6000])
        if matches:
            try:
                d = date(*map(int, matches[-1]))
                return d.isoformat(), "document"
            except ValueError:
                pass
    # Publication date shown by the site is the fallback. Do not use arbitrary
    # dates in a policy body, which often include effective and expiry dates.
    m = re.search(r"(?:发布日期|发布时间|信息发布日期|成文日期)\s*[:：]?\s*(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})", text[:1500])
    if m:
        try:
            return date(*map(int, m.groups())).isoformat(), "page"
        except ValueError:
            pass
    return "", "unknown"


def _list_candidates(source, timeout: float) -> list[dict]:
    response = requests.get(source.index_url, timeout=timeout, headers=HEADERS)
    response.raise_for_status()
    html = response.content.decode(response.encoding or "utf-8", errors="replace")
    candidates, seen = [], set()
    for match in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S):
        href = urljoin(response.url, match.group(1))
        title = _html_text(match.group(2))
        parsed = source_for_url(href)
        if parsed is None or len(title) < 8 or not any(word in title for word in POLICY_WORDS):
            continue
        if href in seen:
            continue
        seen.add(href)
        # Official lists commonly place the date after the closing anchor.
        # Include the surrounding list/row, not only text preceding the link.
        row_start = max(html.rfind("<li", 0, match.start()), html.rfind("<tr", 0, match.start()), html.rfind("<dd", 0, match.start()), 0)
        row_ends = [position for token in ("</li>", "</tr>", "</dd>") if (position := html.find(token, match.end())) >= 0]
        row_end = min(row_ends) + 5 if row_ends else min(len(html), match.end() + 400)
        row = html[row_start:row_end]
        list_date, confidence = _date_from_text(_html_text(row))
        if not list_date:
            date_match = DATE_RE.search(_html_text(row))
            if date_match:
                try:
                    list_date = date(*map(int, date_match.groups())).isoformat()
                    confidence = "list"
                except ValueError:
                    pass
        candidates.append({
            "title": title, "url": href, "text": title, "published_at": list_date,
            "date_confidence": confidence, "source_name": source.name,
            "region": source.region, "source_type": source.source_type,
        })
    return candidates[:120]


def _fetch_article(candidate: dict, timeout: float) -> dict | None:
    response = requests.get(candidate["url"], timeout=timeout, headers=HEADERS)
    response.raise_for_status()
    encoding = response.encoding or "utf-8"
    text = _html_text(response.content.decode(encoding, errors="replace"))
    if len(text) < 120:
        return None
    published, confidence = _date_from_text(text)
    if published:
        candidate["published_at"] = published
        candidate["date_confidence"] = confidence
    elif not candidate.get("published_at"):
        candidate["date_confidence"] = "unknown"
    candidate["text"] = text[:16000]
    return candidate


def _llm_policy_summary(item: dict, timeout: float = 35) -> str:
    """Summarize only final selected items; no request is made for other candidates."""
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return ""
    base = (os.environ.get("LLM_API_BASE") or "https://api.deepseek.com").rstrip("/")
    model = os.environ.get("LLM_MODEL") or "deepseek-v4-flash"
    prompt = policy_prompt(item)
    try:
        response = requests.post(
            base + "/chat/completions", timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model, "temperature": 0.1,
                  "messages": [{"role": "system", "content": "你是政府政策信息编辑，只能依据给定原文写作。"},
                               {"role": "user", "content": prompt}]},
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"].strip()
        content = re.sub(r"^```(?:markdown|text)?\s*|\s*```$", "", content, flags=re.I).strip()
        return content[:1000]
    except Exception as exc:
        log.warning("政策摘要 LLM 失败 %s: %s", item.get("title", ""), exc)
        return ""


def policy_prompt(item: dict) -> str:
    """Return the exact editorial prompt, exposed for tests and audit."""
    return (
        "根据以下官方政策文件原文，写一条供陕西省、市级工作参考的政策信息。\n"
        "要求：\n"
        "1. 开头保留△，写清发布单位和政策名称；不得把媒体转载写成政策发布单位。\n"
        "2. 提炼2至4项具体措施、量化目标、适用对象或执行时间；优先保留最有参考价值的信息。\n"
        "3. 只使用原文明确事实，不推测，不把生效日、截止日误写成发布日期。\n"
        "4. 摘要控制在约200字，中文简洁、客观，不写情绪评价。\n"
        "5. 只输出摘要正文，不加来源行；来源单位和原文链接由程序另行附加。\n\n"
        f"来源单位：{item.get('source_name', '')}\n"
        f"文件标题：{item.get('title', '')}\n"
        f"发布日期：{item.get('published_at') or '原文未明确'}\n"
        f"原文链接：{item.get('url', '')}\n"
        f"官方原文：\n{item.get('text', '')[:12000]}"
    )


def _select_date_candidates(candidates: list[dict], today: date) -> tuple[list[dict], int]:
    normalized, dedup = [], set()
    for candidate in candidates:
        item = normalize_item(candidate, today)
        if not item:
            continue
        key = hashlib.sha1((item["url"] + item["title"]).encode()).hexdigest()
        if key in dedup:
            continue
        dedup.add(key)
        normalized.append(item)
    strict = [item for item in normalized if item["timeliness"] in ("当日", "昨日")]
    # Widen only when strict window is sparse. Widening is bounded to 3 days,
    # and only items with a verified date can qualify.
    if len(strict) < 10:
        widened = [item for item in normalized if item["timeliness"] == "近三日"]
        known = {item["url"] for item in strict}
        strict.extend(item for item in widened if item["url"] not in known)
    strict.sort(key=lambda item: (
        item["timeliness"] == "当日",
        item.get("published_at", ""),
        item["source_type"] in ("部委官网", "政府官网", "市政府官网"),
    ), reverse=True)
    return strict, len(normalized)


def fetch_policy_items(today: date | None = None, timeout: float = 8, workers: int = 16,
                       previous: dict | None = None, llm_limit: int = 10) -> dict:
    today = today or date.today()
    candidates, errors = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_list_candidates, source, timeout): source for source in POLICY_SOURCES}
        for future in as_completed(futures):
            source = futures[future]
            try:
                source_candidates = future.result()
                candidates.extend(source_candidates)
                for candidate in source_candidates:
                    if source.name == "北京" and "社会公共服务发展规划" in candidate["title"]:
                        log.info("政策列表发现北京社会公共服务发展规划: %s", candidate["url"])
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
                log.warning("政策来源抓取失败 %s: %s", source.name, exc)

    # Fetch only recent-looking list entries first. A site list without dates
    # remains eligible for article-date extraction, but never triggers LLM on
    # its own until the article date has been verified.
    pre_candidates = candidates[:]
    dated_recent = []
    for candidate in pre_candidates:
        listed = parse_date(candidate.get("published_at"))
        if listed and (today - listed).days in (0, 1, 2):
            dated_recent.append(candidate)
    article_pool = dated_recent[:160] if len(dated_recent) >= 10 else pre_candidates[:160]
    articles = []
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = [pool.submit(_fetch_article, candidate, timeout) for candidate in article_pool]
        for future in as_completed(futures):
            try:
                article = future.result()
                if article:
                    articles.append(article)
            except Exception:
                continue

    selected, normalized_count = _select_date_candidates(articles, today)
    selected = selected[:max(0, min(llm_limit, 10))]
    from concurrent.futures import ThreadPoolExecutor
    summarized = []
    with ThreadPoolExecutor(max_workers=4) as llm_pool:
        summaries = list(llm_pool.map(_llm_policy_summary, selected))
    for item, summary in zip(selected, summaries):
        item["summary_source"] = "deepseek" if summary else "rule"
        if summary:
            item["summary"] = summary if summary.lstrip().startswith("△") else "△" + summary
        summarized.append(item)

    for item in summarized:
        item["timeliness"] = timeliness(parse_date(item.get("published_at")), today)
    payload = {
        "source": "policy_reference", "updated_at": datetime.now().astimezone().isoformat(timespec="minutes"),
        "date": today.isoformat(), "status": "ok" if not errors else "partial", "errors": errors,
        "stats": {
            "total": len(summarized),
            "today": sum(item["timeliness"] == "当日" for item in summarized),
            "yesterday": sum(item["timeliness"] == "昨日" for item in summarized),
            "ministries": sum(item["region"] in ("国家部委", "中央") for item in summarized),
            "provinces": sum(item["region"] in ("外省", "直辖市") for item in summarized),
            "municipalities": sum(item["region"] == "地级市" for item in summarized),
            "candidates_discovered": len(candidates), "articles_parsed": len(articles),
            "llm_calls": sum(item["summary_source"] == "deepseek" for item in summarized),
            "date_window": "当日/昨日；不足10条时扩大至近3日",
        },
        "items": summarized,
    }
    if not summarized and previous and previous.get("items"):
        payload["historical_items"] = previous["items"]
        payload["historical_date"] = previous.get("date")
    return payload


def save_policy_reference(payload: dict, path: str = "policy_reference.json") -> str:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
