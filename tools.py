"""Host-side source tools.  Source tools for the research agents.   Guide: GUIDE.md, part 1.

Rules for every tool:
  * runs on the HOST (not in the sandbox): API keys must never enter the sandbox;
  * returns a STRING (JSON text of compact records) and NEVER raises:
        "NO RESULTS"  when the source answers with nothing,
        "ERROR: ..."  when the source keeps failing after the retries (the agent then tries another source);
  * the docstring is the tool description the LLM reads: keep it precise (what it does, what it returns, when to use it).
Try your tools without any agent:   python tools.py
"""
import json
import os
import random
import re
import threading
import time
import xml.etree.ElementTree

import httpx
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

# ---- constants (given) ----
ARXIV_URL = "https://export.arxiv.org/api/query"  # https only: http answers 301
HF_DAILY_URL = "https://huggingface.co/api/daily_papers"
HF_SEARCH_URL = "https://huggingface.co/api/papers/search"
EXA_URL = "https://mcp.exa.ai/mcp"


class RetryableError(Exception):
    """Given. Raise it inside a call to ask with_retry to wait and try again (retry_after in seconds, optional)."""

    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after


# ---- Retry helper ----
def with_retry(fn, *, attempts=5, base=1.0, cap=30.0):
    """Call fn(); when it raises RetryableError, wait and call it again.

    """
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for attempt in range(attempts):
        try:
            return fn()
        except RetryableError as exc:
            if attempt == attempts - 1:
                raise
            delay = (min(cap, max(0, exc.retry_after)) if exc.retry_after is not None
                     else min(cap, base * 2**attempt) + random.uniform(0, 0.25))
            time.sleep(delay)


def _request(method, url, **kwargs):
    try:
        response = getattr(httpx, method)(url, timeout=60, follow_redirects=True, **kwargs)
    except httpx.TransportError as exc:
        raise RetryableError(str(exc)) from exc
    if response.status_code in {429, 500, 502, 503, 504}:
        try:
            delay = float(response.headers.get("Retry-After", ""))
        except ValueError:
            delay = None
        raise RetryableError(f"HTTP {response.status_code}", retry_after=delay)
    response.raise_for_status()
    return response


def _error(exc):
    message = f"{type(exc).__name__}: {exc}"
    key = os.getenv("EXA_API_KEY", "")
    if key:
        message = message.replace(key, "[REDACTED]")
    message = re.sub(r"(?i)(exaApiKey=)[^\s&\"']+", r"\1[REDACTED]", message)
    return "ERROR: " + message


def _compact(value):
    return " ".join(str(value or "").split())


def _records(records):
    return json.dumps(records, ensure_ascii=False) if records else "NO RESULTS"


_arxiv_lock = threading.Lock()
_arxiv_last_call = None


def _arxiv_request(params):
    global _arxiv_last_call
    with _arxiv_lock:
        if _arxiv_last_call is not None:
            time.sleep(max(0, 3 - (time.monotonic() - _arxiv_last_call)))
        _arxiv_last_call = time.monotonic()
        return _request("get", ARXIV_URL, params=params)


# ---- arXiv ----
@tool
def arxiv_search(query: str, max_results: int = 10) -> str:
    """Search arXiv papers by keywords, newest first. Returns a JSON list of {id, url, published, title, summary}."""
    try:
        terms = [t for t in re.findall(r"[^\W_]+(?:-[^\W_]+)*", query)
                 if t.upper() not in {"AND", "OR", "NOT", "ALL"}]
        if not terms:
            return "NO RESULTS"
        params = {"search_query": " AND ".join("all:" + t for t in terms),
                  "sortBy": "submittedDate", "sortOrder": "descending",
                  "max_results": max(1, min(30, max_results)), "start": 0}
        response = with_retry(lambda: _arxiv_request(params), attempts=7, cap=60)
        root = xml.etree.ElementTree.fromstring(response.text)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        records = []
        for entry in root.findall("a:entry", ns):
            identifier = re.sub(r"v\d+$", "", entry.findtext("a:id", "", ns).split("/abs/")[-1])
            if not identifier:
                continue
            records.append({"id": identifier, "url": f"https://arxiv.org/abs/{identifier}",
                            "published": entry.findtext("a:published", "", ns)[:10],
                            "title": _compact(entry.findtext("a:title", "", ns)),
                            "summary": _compact(entry.findtext("a:summary", "", ns))[:600]})
        return _records(records)
    except Exception as exc:
        return _error(exc)


def _hf_records(items, prefer_ai=False):
    records = []
    for item in items:
        paper = item.get("paper") or {}
        identifier = paper.get("id")
        if not identifier:
            continue
        summary = ((paper.get("ai_summary") or item.get("ai_summary")) if prefer_ai else None)
        records.append({"id": identifier, "url": f"https://huggingface.co/papers/{identifier}",
                        "published": str(paper.get("publishedAt") or item.get("publishedAt") or "")[:10],
                        "title": _compact(paper.get("title") or item.get("title")),
                        "summary": _compact(summary or paper.get("summary") or item.get("summary"))[:600],
                        "upvotes": paper.get("upvotes") or item.get("upvotes") or 0,
                        "github": paper.get("githubRepo") or item.get("githubRepo") or "",
                        "stars": paper.get("githubStars") or item.get("githubStars") or 0})
    return records


# ---- Hugging Face ----
@tool
def hf_daily_papers(limit: int = 30, date: str = "", keyword: str = "") -> str:
    """Hugging Face Daily Papers = what is trending in AI research. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars} sorted by upvotes. `date` is YYYY-MM-DD (empty = latest).
    `keyword` filters title/summary; there is no topic search on this endpoint (use hf_search_papers for a topic)."""
    try:
        params = {"limit": max(1, min(100, limit))}
        if date:
            params["date"] = date
        items = with_retry(lambda: _request("get", HF_DAILY_URL, params=params).json())
        records = _hf_records(items)
        if keyword.strip():
            records = [r for r in records if keyword.casefold() in (r["title"] + " " + r["summary"]).casefold()]
        return _records(sorted(records, key=lambda r: r["upvotes"], reverse=True))
    except Exception as exc:
        return _error(exc)


@tool
def hf_search_papers(query: str, limit: int = 10) -> str:
    """Search Hugging Face papers by topic. Returns a JSON list of
    {id, url, published, title, summary, upvotes, github, stars}."""
    try:
        if not query.strip():
            return "NO RESULTS"
        items = with_retry(lambda: _request("get", HF_SEARCH_URL,
                           params={"q": query, "limit": max(1, min(50, limit))}).json())
        return _records(_hf_records(items, prefer_ai=True))
    except Exception as exc:
        return _error(exc)


def _exa_call(name, arguments):
    def call():
        key = os.getenv("EXA_API_KEY", "")
        response = _request("post", EXA_URL, params={"exaApiKey": key} if key else {},
                            headers={"Accept": "application/json, text/event-stream"},
                            json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": name, "arguments": arguments}})
        if response.text.lstrip().startswith("{"):
            messages = [response.json()]
        else:
            messages = [json.loads(line[5:].strip()) for line in response.text.splitlines()
                        if line.startswith("data:") and line[5:].strip()]
        texts = []
        for message in messages:
            if "error" in message:
                error = str(message["error"])
                if re.search(r"rate.?limit|too many requests", error, re.I):
                    raise RetryableError("Exa JSON-RPC rate limit")
                raise RuntimeError(error)
            result = message.get("result", {})
            content = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
            # The free tier answers HTTP 200 and flags the rate limit in result._meta (GUIDE 1.4).
            if re.search(r"rate.?limit", json.dumps(result.get("_meta", {})), re.I) \
                    or re.search(r"rate.?limit(?:ed| exceeded)|too many requests", content, re.I):
                raise RetryableError("Exa rate limit")
            if result.get("isError"):
                raise RuntimeError(content or "Exa tool error")
            if content:
                texts.append(content)
        return "\n".join(texts) or "NO RESULTS"
    return with_retry(call, attempts=7, cap=60)


# ---- Web search / fetch through the Exa MCP endpoint ----
@tool
def web_search(query: str, objective: str = "", num_results: int = 5) -> str:
    """Search the web (Exa). Describe the ideal page in natural language. Returns clean text of the top results with URLs."""
    try:
        if not query.strip():
            return "NO RESULTS"
        content = _exa_call("web_search_exa", {"query": query, "objective": objective or f"Find reliable sources about {query}",
                                             "numResults": max(1, min(10, num_results))})
        return content
    except Exception as exc:
        return _error(exc)


@tool
def web_fetch(url: str) -> str:
    """Read the full content of one web page (e.g. an arXiv abstract page) as markdown. Long pages are truncated."""
    try:
        if not re.match(r"https?://", url):
            return "ERROR: URL must use HTTP or HTTPS"
        content = _exa_call("web_fetch_exa", {"urls": [url]})[:12000]
        return content
    except Exception as exc:
        return _error(exc)


# ---- Registry (the researcher subagent gets exactly these) ----
SOURCE_TOOLS = [arxiv_search, hf_daily_papers, hf_search_papers, web_search, web_fetch]


if __name__ == "__main__":
    for name, fn, args in [
        ("arxiv_search", arxiv_search, {"query": "world model", "max_results": 3}),
        ("hf_daily_papers", hf_daily_papers, {"limit": 20}),
        ("hf_search_papers", hf_search_papers, {"query": "world model", "limit": 3}),
        ("web_search", web_search, {"query": "survey paper on world models", "num_results": 2}),
        ("web_fetch", web_fetch, {"url": "https://arxiv.org/abs/1803.10122"}),
    ]:
        print(f"== {name}\n{fn.invoke(args)[:400]}\n")
