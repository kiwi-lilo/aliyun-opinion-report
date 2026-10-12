"""Policy date, type and summary helpers."""
from datetime import date, datetime, timedelta
import re
from urllib.parse import urlparse

POLICY_WORDS = ("政策", "办法", "方案", "通知", "意见", "条例", "行动计划", "实施细则", "措施")
MEASURE_WORDS = ("支持", "鼓励", "提出", "明确", "推动", "建设", "实施", "到20", "目标", "补贴", "奖励")
TOPICS = ("产业", "营商环境", "金融", "人才", "民政", "就业", "人工智能", "数据", "科技", "教育", "医疗", "生态", "交通", "农业", "知识产权")


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    match = re.search(r"(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})", value)
    if not match:
        return None
    try:
        return date(*map(int, match.groups()))
    except ValueError:
        return None


def extract_policy_date(text: str, fallback: str | None = None) -> tuple[date | None, str]:
    """Use the document's落款 date first, then a page date, then unknown."""
    text = text or ""
    # Match document issue dates specifically. Generic "发布" matching can
    # accidentally capture "有效期至 2031年..." and misclassify expired items.
    patterns = (
        r"(?:发布日期|发布时间|印发日期|成文日期|签发日期|落款日期)\s*[:：]?\s*(20\d{2})\s*[年./-]\s*(\d{1,2})\s*[月./-]\s*(\d{1,2})",
        r"(?:发布|印发|成文|签发)\s*(?:于|日期)?\s*(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    )
    matches = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text[:6000]))
    if matches:
        try:
            return date(*map(int, matches[-1])), "document"
        except ValueError:
            pass
    # Avoid mistaking an effective/expiry date (e.g. 2031-09-30) for the
    # publication date. Page/list date is the only fallback when no document
    # date is present.
    parsed = parse_date(fallback)
    return (parsed, "page") if parsed else (None, "unknown")


def timeliness(published: date | None, today: date | None = None) -> str:
    today = today or date.today()
    if not published:
        return "日期不明"
    age = (today - published).days
    return {0: "当日", 1: "昨日", 2: "近三日"}.get(age, "过期") if age >= 0 else "过期"


def is_recent(published: date | None, today: date | None = None) -> bool:
    return timeliness(published, today) in ("当日", "昨日")


def classify_topic(title: str, text: str) -> str:
    haystack = f"{title} {text}"
    return next((topic for topic in TOPICS if topic in haystack), "综合")


def looks_like_policy(title: str, text: str) -> bool:
    haystack = f"{title} {text}"
    return (any(word in title for word in POLICY_WORDS)
            or any(word in text[:800] for word in POLICY_WORDS)
            or bool(re.search(r"规划|发展|公共服务|专项行动", title))) and (
                sum(word in haystack for word in MEASURE_WORDS) >= 1 or len(text) >= 200
            )


def summarize(title: str, text: str, source_name: str) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    sentences = re.split(r"(?<=[。！？；])", clean)
    useful = [s.strip() for s in sentences if any(word in s for word in MEASURE_WORDS)]
    body = "".join(useful[:4]) or clean
    summary = f"△{source_name}{title}。{body}".replace("。。", "。")
    return summary[:800].rstrip("。；，") + ("。" if summary else "")


def normalize_item(item: dict, today: date | None = None) -> dict | None:
    published, confidence = extract_policy_date(item.get("text", ""), item.get("published_at"))
    # Date-less official articles are retained as candidates. They are not
    # silently discarded; the UI marks them as date unknown for review.
    title = (item.get("title") or "").strip()
    text = (item.get("text") or item.get("summary") or "").strip()
    url = (item.get("url") or "").strip()
    if not title or not text or not url or not urlparse(url).scheme:
        return None
    if not looks_like_policy(title, text):
        return None
    summary = item.get("summary") or summarize(title, text, item.get("source_name", ""))
    return {
        "title": title, "region": item.get("region", ""), "source_name": item.get("source_name", ""),
        "published_at": published.isoformat() if published else "", "date_confidence": confidence,
        "summary": summary.strip(), "url": url,
        "source_type": item.get("source_type", ""),
        "topic": item.get("topic") or classify_topic(title, text),
        "timeliness": timeliness(published, today),
    }
