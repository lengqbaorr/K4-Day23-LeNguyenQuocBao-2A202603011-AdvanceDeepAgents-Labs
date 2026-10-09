# Checklist hoàn thành Lab — Deep Research Agent (Deep Agents + Sandbox)

Tổng hợp từ `README.md`, `GUIDE.md`, `RUBRIC.md`, `REPORT_TEMPLATE.md`, `topics.md`.
Thứ tự checkpoint = thứ tự làm bài khuyến nghị. Cột điểm tham chiếu `RUBRIC.md` (tổng 100).

> **Không được sửa:** `model.py`, `sandbox.py`, `self_check.py`, `finalize_citations.py`.
> **Phải cài đặt:** `check_citations.py`, `tools.py`, `agents.py`, `research.py`.

> **Trạng thái kiểm chứng:** Checkpoint 1–4 đánh dấu phần đã cài đặt và kiểm thử mã;
> không đồng nghĩa E2E đã pass. Bộ kiểm thử offline hiện pass 8/8 (`unittest discover -s tests`); đã thử kết nối LLM,
> Daytona và 5 tool nguồn thật. Checkpoint 5: cả 5 topic đã chạy thật, `self_check.py` báo READY; mục 4.2 mới kiểm mẫu (xem ghi chú ở Checkpoint 5).
> Các lần E2E trước bị gate chặn do cấu trúc/họ nguồn; chưa tính là báo cáo hoàn thành.

> **Lệnh kiểm tra** dưới đây viết cho **Git Bash** (Windows), chạy ở thư mục gốc repo với venv đã kích hoạt
> (`source .venv/Scripts/activate`). Trên Linux/macOS dùng `source .venv/bin/activate`.

---

## Checkpoint 0 — Chuẩn bị môi trường

- [x] Python ≥ 3.11; tạo venv: `python -m venv .venv` rồi kích hoạt (Windows: `.venv\Scripts\activate`)
- [x] `pip install -r requirements.txt`
- [x] `.env` đã có cấu hình (không ghi/hiển thị khóa trong repo):
  - [x] `LAB_MODEL` + khóa nhà cung cấp LLM; gọi thử thành công
  - [x] `DAYTONA_API_KEY` — mở/chạy/dọn sandbox thành công
  - [x] `EXA_API_KEY` — web_search và web_fetch gọi thử thành công
- [x] Xác nhận `.env` nằm trong `.gitignore`, `git status` không thấy `.env`
- [x] Đọc mục "Khái niệm nền" (GUIDE §0): subagent chỉ thấy tin nhắn uỷ quyền; khóa API & tool mạng ở **host**, không đưa vào sandbox

**🔎 Lệnh kiểm tra**

```bash
python --version                                   # >= 3.11
pip check                                          # không có xung đột phụ thuộc
python -c "import deepagents, langchain, httpx, dotenv; print('imports OK')"
git check-ignore .env && echo ".env được ignore"   # phải in ra .env
git ls-files | grep -x .env || echo "OK: .env không bị track"

# LLM tạo được và gọi được (tốn rất ít token)
python -c "from model import make_model; print(make_model().invoke('Say OK').content)"

# Sandbox mở/đóng được (Daytona hoặc SANDBOX=docker)
python -c "from sandbox import open_sandbox
with open_sandbox() as b: print(b.execute('python3 --version && echo sandbox OK').output)"

# Exa MCP trả lời (nhìn result._meta, chạy 3-4 lần liên tiếp để thấy cờ rate limit nếu không có khóa)
curl -s -X POST "https://mcp.exa.ai/mcp?exaApiKey=$EXA_API_KEY" \
  -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"web_search_exa","arguments":{"query":"world models survey","objective":"find survey papers","numResults":1}}}' | head -c 800
```
> `$EXA_API_KEY` lấy từ shell: chạy `set -a; source .env; set +a` trước (hoặc bỏ `?exaApiKey=...` để thử bản free).
> Nếu `make_model` không tự đọc `.env` thì cũng `source` như trên.

---

## Checkpoint 1 — `check_citations.py` (GUIDE §4 · RUBRIC 3.1, 4.1)

Chỉ dùng **thư viện chuẩn** (chạy trong sandbox). `check(report_text, sources)` trả list vấn đề (rỗng = ổn).

- [x] Quy tắc 1: `sources` rỗng → báo lỗi
- [x] Quy tắc 2: mỗi nguồn có `n` là số nguyên; `url` bắt đầu `http://`/`https://`; không trùng `url`
- [x] Quy tắc 3: báo cáo phải có tiêu đề `## References`; chỉ phần **trước** tiêu đề là thân (số trong References không tính là trích dẫn)
- [x] Quy tắc 4: mọi `[n]` trong thân có trong `sources`; mọi nguồn được trích dẫn ≥ 1 lần
- [x] Quy tắc 5: References có **đúng một dòng/nguồn**, dòng bắt đầu `[n]`; không thiếu, không trùng, không có số lạ
- [x] Quy tắc 6: mỗi dòng References chứa **đúng 1 URL** và URL == `url` của nguồn `n` (bắt lỗi gộp `[3] Bài A; Bài B`)
- [x] Quy tắc 7: khai triển trích dẫn nhóm `[1, 2]`, `[1-3]`; **bỏ qua** `[n]` trong code block và link Markdown `[n](url)`
- [x] CLI: `python check_citations.py <report.md> <sources.json>` in `OK: N sources, all citations resolve` hoặc liệt kê lỗi (exit code ≠ 0 khi lỗi)
- [x] Tự test vài case tay: báo cáo đúng, thiếu References, `[n]` không tồn tại, nguồn không được trích, dòng gộp nhiều URL

**🔎 Lệnh kiểm tra**

```bash
# Chỉ dùng stdlib (không được import httpx, langchain...)
grep -nE "^\s*(import|from) " check_citations.py

# Bộ test nhanh: mỗi dòng in True là đúng kỳ vọng
python - <<'EOF'
from check_citations import check
S = [{"n":1,"id":"a","url":"https://arxiv.org/abs/2501.00001","title":"A","date":"2025-01-01","source":"arxiv"},
     {"n":2,"id":"b","url":"https://huggingface.co/papers/2501.00002","title":"B","date":"2025-01-02","source":"hf-search"}]
REF = "\n## References\n[1] A. arxiv. https://arxiv.org/abs/2501.00001 (2025-01-01)\n[2] B. hf-search. https://huggingface.co/papers/2501.00002 (2025-01-02)\n"
cases = {
  "hợp lệ":                 ("# T\nX [1]. Y [2].\n" + REF, S, True),
  "trích dẫn nhóm [1, 2]":  ("# T\nX [1, 2].\n" + REF, S, True),
  "trích dẫn dải [1-2]":    ("# T\nX [1-2].\n" + REF, S, True),
  "sources rỗng":           ("# T\nX.\n## References\n", [], False),
  "thiếu ## References":    ("# T\nX [1]. Y [2].\n", S, False),
  "[3] không tồn tại":      ("# T\nX [1]. Y [2]. Z [3].\n" + REF, S, False),
  "nguồn 2 không được trích": ("# T\nX [1].\n" + REF, S, False),
  "thiếu dòng ref [2]":     ("# T\nX [1]. Y [2].\n## References\n[1] A. arxiv. https://arxiv.org/abs/2501.00001\n", S, False),
  "gộp 2 URL một dòng":     ("# T\nX [1]. Y [2].\n## References\n[1] A; B https://arxiv.org/abs/2501.00001 https://huggingface.co/papers/2501.00002\n[2] B. https://huggingface.co/papers/2501.00002\n", S, False),
  "URL ref sai":            ("# T\nX [1]. Y [2].\n## References\n[1] A. https://example.org/x\n[2] B. https://huggingface.co/papers/2501.00002\n", S, False),
  "url trùng":              ("# T\nX [1]. Y [2].\n" + REF, [S[0], {**S[1], "url": S[0]["url"]}], False),
  "url không http":         ("# T\nX [1]. Y [2].\n" + REF, [S[0], {**S[1], "url": "ftp://x"}], False),
  "[n] trong code block":   ("# T\nX [1]. Y [2].\n```\n[9]\n```\n" + REF, S, True),
}
for name, (rep, src, ok) in cases.items():
    p = check(rep, src); print(f"{(not p) == ok!s:5} {name}: {p}")
EOF

# CLI: exit code 1 khi lỗi
python check_citations.py khong_ton_tai.md khong_ton_tai.json; echo "exit=$?"   # phải exit=1
```

---

## Checkpoint 2 — `tools.py` (GUIDE §1 · RUBRIC 1 = 20đ)

Quy ước chung: công cụ trả **chuỗi**, **không bao giờ ném ngoại lệ**, rỗng → `NO RESULTS`, hỏng sau retry → `ERROR: ...`. Cắt `summary` ~600 ký tự. Docstring rõ ràng (LLM đọc để chọn tool).

### TODO 1 — `with_retry` (1.1 · 6đ)
- [x] Retry khi `RetryableError`: HTTP 429/500/502/503/504 và `httpx.TransportError`
- [x] Dùng header `Retry-After` (giây) nếu có
- [x] Nếu không: backoff `base * 2**attempt`, chặn `cap`, **+ jitter ngẫu nhiên**
- [x] Lần thử cuối thất bại → ném lại, **không ngủ thêm**
- [x] Lỗi không phải `RetryableError` → không retry, để nổi lên
- [x] Mỗi tool bọc `with_retry` quanh call mạng, đổi ngoại lệ còn lại thành `ERROR: ...`

### TODO 2 — `arxiv_search` (1.4 · 3đ)
- [x] Endpoint **HTTPS** `https://export.arxiv.org/api/query` (HTTP bị 301)
- [x] Tham số: `search_query` (vd `all:world AND all:model`), `sortBy=submittedDate`, `sortOrder=descending`, `max_results`, `start`
- [x] Parse Atom XML (ns `http://www.w3.org/2005/Atom`): `id`, `published`, `title`, `summary`; chuẩn hóa khoảng trắng
- [x] `id` bỏ hậu tố `vN`; `url = https://arxiv.org/abs/<id>`
- [x] Khoảng cách **≥ 3 giây** giữa 2 lần gọi arXiv
- [x] `cap` dài (~60s) + nhiều lần thử hơn cho 429
- [x] Làm sạch query: chỉ giữ chữ/số/gạch nối; không còn từ nào → `NO RESULTS` **không gọi mạng**

### TODO 3 — Hugging Face
- [x] `hf_daily_papers`: `https://huggingface.co/api/daily_papers` (`limit`, `date`); lọc từ khóa phía client, sắp theo `upvotes`
- [x] `hf_search_papers`: `https://huggingface.co/api/papers/search?q=...` (`limit`); ưu tiên `ai_summary`
- [x] Bản ghi: `{id, url, published, title, summary, upvotes, github, stars}`, `url = https://huggingface.co/papers/<id>`
- [x] Bỏ mục không có `paper.id`

### TODO 4 — Exa MCP qua HTTP thuần (1.3 · 3đ)
- [x] POST JSON-RPC tới `https://mcp.exa.ai/mcp`, header `Accept: application/json, text/event-stream`
- [x] Parse SSE: dòng `data:` → `json.loads`; lấy text ở `result.content[].text` (`type == "text"`)
- [x] Có khóa `error` → coi là lỗi
- [x] `web_search` → `web_search_exa` (`query`, `objective`, `numResults`)
- [x] `web_fetch` → `web_fetch_exa` (`urls` là **mảng**); cắt nội dung ~12000 ký tự
- [x] **Phát hiện rate-limit trả HTTP 200** qua cờ trong `result._meta` (chạy curl vài lần để xem) → raise `RetryableError`; `cap` ~60s
- [x] Gắn `EXA_API_KEY` qua `?exaApiKey=<khóa>`
- [x] **Che khóa** trong mọi chuỗi `ERROR: ...` trả cho agent

### TODO 5 — Đăng ký
- [x] Tên hàm khớp `SOURCE_TOOLS`
- [x] `python tools.py` → cả **5 tool** trả kết quả thật

**🔎 Lệnh kiểm tra**

```bash
# 1) Chạy thật cả 5 tool (không còn dòng "not implemented yet", không có ERROR)
python tools.py

# 2) with_retry: backoff, Retry-After, cap, không ngủ sau lần cuối, không retry lỗi khác (mock sleep, không tốn thời gian)
python - <<'EOF'
import tools
from unittest import mock
from tools import with_retry, RetryableError
with mock.patch("time.sleep") as sl, mock.patch.object(tools.time, "sleep", sl):
    calls = []
    def f():
        calls.append(1)
        if len(calls) < 3: raise RetryableError("x")
        return "ok"
    print("thành công sau 3 lần:", with_retry(f, attempts=5) == "ok", "| số lần ngủ =", sl.call_count, "(kỳ vọng 2)")
    sl.reset_mock()
    try: with_retry(lambda: (_ for _ in ()).throw(RetryableError("x")), attempts=3)
    except RetryableError: print("hết lượt -> ném lại: True | số lần ngủ =", sl.call_count, "(kỳ vọng 2, không ngủ sau lần cuối)")
    sl.reset_mock()
    try: with_retry(lambda: (_ for _ in ()).throw(RetryableError("x", retry_after=7)), attempts=2)
    except RetryableError: print("Retry-After:", sl.call_args[0][0], "(kỳ vọng ~7)")
    sl.reset_mock()
    try: with_retry(lambda: (_ for _ in ()).throw(RetryableError("x")), attempts=8, base=1, cap=4)
    except RetryableError: print("max delay:", max(c[0][0] for c in sl.call_args_list), "(kỳ vọng ≤ cap + jitter nhỏ)")
    sl.reset_mock()
    try: with_retry(lambda: 1/0)
    except ZeroDivisionError: print("lỗi khác không retry: True | số lần ngủ =", sl.call_count, "(kỳ vọng 0)")
EOF

# 3) Quy ước tool: NO RESULTS, query bẩn, ERROR thay vì ném ngoại lệ
python - <<'EOF'
import json
from tools import arxiv_search, hf_daily_papers, hf_search_papers, web_fetch
print("query rỗng      :", arxiv_search.invoke({"query": "  :: \"\" "}))              # NO RESULTS, không gọi mạng
print("query có dấu    :", arxiv_search.invoke({"query": 'all:"world model" AND OR', "max_results": 2})[:150])
r = json.loads(arxiv_search.invoke({"query": "world model", "max_results": 2}))
print("arxiv id/url    :", r[0]["id"], r[0]["url"])                                  # không có vN, https://arxiv.org/abs/<id>
print("hf-daily kw lạ  :", hf_daily_papers.invoke({"keyword": "zzqqxx-khong-co"}))   # NO RESULTS
h = json.loads(hf_search_papers.invoke({"query": "world model", "limit": 2}))
print("hf keys/url     :", sorted(h[0]), h[0]["url"])  # {github,id,published,stars,summary,title,upvotes,url}
print("fetch URL hỏng  :", web_fetch.invoke({"url": "https://khong-ton-tai.invalid/x"})[:150])  # ERROR: ... hoặc NO RESULTS, không traceback
print("len summary     :", max(len(x["summary"]) for x in r + h), "(≈ ≤ 600)")
EOF

# 4) arXiv cách nhau >= 3 giây
python -c "import time; from tools import arxiv_search as a; t=time.time(); a.invoke({'query':'world model','max_results':1}); a.invoke({'query':'diffusion','max_results':1}); print('2 lần gọi mất', round(time.time()-t,1), 's (>= 3)')"

# 5) Khóa Exa không lọt vào chuỗi ERROR (giả lập lỗi mạng)
python - <<'EOF'
import os, httpx
from unittest import mock
os.environ["EXA_API_KEY"] = "SECRET-TEST-KEY-123"
import tools
with mock.patch.object(httpx, "post", side_effect=httpx.ConnectError("fail https://mcp.exa.ai/mcp?exaApiKey=SECRET-TEST-KEY-123")), \
     mock.patch.object(httpx.Client, "post", side_effect=httpx.ConnectError("fail https://mcp.exa.ai/mcp?exaApiKey=SECRET-TEST-KEY-123")), \
     mock.patch("time.sleep"):
    out = tools.web_search.invoke({"query": "x"})
print(out[:200]); print("KHÓA BỊ LỘ!" if "SECRET-TEST-KEY-123" in out else "OK: khóa đã được che")
EOF
grep -n "_meta" tools.py   # phải có xử lý cờ rate limit của Exa
```

---

## Checkpoint 3 — `agents.py` (GUIDE §2 · RUBRIC 2 = 20đ)

Đường dẫn sandbox: `NOTES_DIR=/tmp/work/research/notes/`, `SOURCES_PATH=/tmp/work/research/sources.json`, `VALIDATOR_PATH`, `FINALIZER_PATH`, `REPORT_PATH=/tmp/work/report/report.md`.

### TODO 1 — `LEAD_PROMPT` (2.3 · 3đ)
- [x] (1) Lập kế hoạch bằng `write_todos`, chia chủ đề thành **N ≥ 3** câu hỏi con độc lập
- [x] (2) Giao từng câu cho `researcher` qua `task`, **song song**, kèm đủ ngữ cảnh (chủ đề, câu hỏi con, đường dẫn file ghi chú `<NN>-<slug>.md`, định dạng ghi chú)
- [x] (3) Kiểm tra kết quả subagent trước khi dùng (đọc file ghi chú)
- [x] (4) Gộp ghi chú → `sources.json` (`{n, id, url, title, date, source}`, không trùng URL; `source` ∈ `arxiv|hf-daily|hf-search|web` = **tool đã trả về**, URL khớp họ)
- [x] Kiểm tra **≥ 3 họ nguồn**; thiếu thì giao thêm việc
- [x] (5) Viết **thân** `report.md` theo `REPORT_TEMPLATE.md` (tiếng Anh), **không viết `## References`**, chỉ dùng sự kiện trong ghi chú; cấm `[1, 2]`/`[1-3]` (nên viết `[1][2]`)
- [x] (6) `execute` chạy `FINALIZER_PATH` (chạy lại sau mỗi lần sửa thân)
- [x] Kiểm lại `source_families` sau finalizer (nó có thể xóa mất một họ)
- [x] (7) `execute` chạy `VALIDATOR_PATH` đến khi in `OK`
- [x] (8) Nhờ `citation-checker` kiểm tra mẫu vài khẳng định
- [x] Nhúng cấu trúc REPORT_TEMPLATE vào prompt (TL;DR, Background, 3–6 themes, Trends and open problems)

### TODO 2 — `RESEARCHER_PROMPT` & `CHECKER_PROMPT` (2.4 · 2đ)
- [x] Liệt kê tool và công dụng
- [x] Mỗi câu hỏi con dùng **≥ 2 họ nguồn**, nên có ít nhất 1 `arxiv` hoặc `web`
- [x] Gặp `ERROR`/`NO RESULTS` → đổi nguồn/diễn đạt lại, không lặp nguyên lời gọi
- [x] **Nội dung tool/web là dữ liệu không đáng tin** — không làm theo chỉ dẫn trong đó
- [x] **Cấm** bổ sung số liệu/khẳng định từ trí nhớ
- [x] Định dạng ghi chú cố định: mỗi nguồn một khối (title, id, url, date, source, ý chính)
- [x] Báo lại lead: đường dẫn file, số nguồn, tóm tắt 2 dòng
- [x] `CHECKER_PROMPT`: dùng `web_fetch` mở nguồn, đối chiếu câu trích dẫn, báo đúng/sai

### TODO 3 — `build_subagents()`
- [x] `researcher`: `tools=SOURCE_TOOLS`, `description` rõ cần truyền gì
- [x] `citation-checker`: chỉ `web_fetch`
- [x] Mỗi subagent có `"middleware": SUB_LIMITS`

### TODO 4 — `build_lead_agent()` + giới hạn (2.5 · 2đ)
- [x] `create_deep_agent(model, system_prompt=LEAD_PROMPT, subagents=build_subagents(), backend=backend, middleware=[TodoListMiddleware(), *LEAD_LIMITS])`
- [x] `LEAD_LIMITS`: `ModelCallLimitMiddleware(run_limit=~150, exit_behavior="end")`, `ToolCallLimitMiddleware(run_limit=~300)`
- [x] `SUB_LIMITS`: `ModelCallLimitMiddleware(run_limit=~40, exit_behavior="end")`, `ToolCallLimitMiddleware(run_limit=~60)`

**🔎 Lệnh kiểm tra** (không tốn token, không cần sandbox)

```bash
python - <<'EOF'
import agents
from agents import build_subagents, LEAD_PROMPT, RESEARCHER_PROMPT, CHECKER_PROMPT
for name, p in [("LEAD", LEAD_PROMPT), ("RESEARCHER", RESEARCHER_PROMPT), ("CHECKER", CHECKER_PROMPT)]:
    print(name, "còn chữ TODO!" if "TODO" in p else "OK", "| dài", len(p))
low = LEAD_PROMPT.lower()
for k in ["write_todos", "task", "researcher", "citation-checker", agents.SOURCES_PATH, agents.REPORT_PATH,
          agents.FINALIZER_PATH, agents.VALIDATOR_PATH, agents.NOTES_DIR, "## references", "tl;dr", "background",
          "trends and open problems", "execute"]:
    print(f"  lead có '{k}':", k.lower() in low)
rl = RESEARCHER_PROMPT.lower()
for k in ["untrusted", "memory", "arxiv_search", "hf_daily_papers", "hf_search_papers", "web_search", "web_fetch", "no results", "error"]:
    print(f"  researcher có '{k}':", k in rl)
subs = {s["name"]: s for s in build_subagents()}
print("subagents:", list(subs))                                                  # ['researcher', 'citation-checker']
print("researcher tools:", [t.name for t in subs["researcher"]["tools"]])        # đủ 5
print("checker tools   :", [t.name for t in subs["citation-checker"]["tools"]])  # ['web_fetch']
for n, s in subs.items():
    print(n, "middleware:", [type(m).__name__ for m in s.get("middleware", [])])  # ModelCallLimit + ToolCallLimit
print("LEAD_LIMITS:", [type(m).__name__ for m in getattr(agents, "LEAD_LIMITS", [])])
EOF

# Lead agent dựng được với backend thật và có write_todos/task/execute
python - <<'EOF'
from model import make_model
from sandbox import open_sandbox
from agents import build_lead_agent
with open_sandbox() as b:
    g = build_lead_agent(b, make_model())
    print("build_lead_agent OK:", type(g).__name__)
EOF
```
> Từ khóa trong prompt chỉ là gợi ý (prompt có thể diễn đạt khác) — mục đích là nhanh chóng phát hiện bước bị thiếu.

---

## Checkpoint 4 — `research.py` (GUIDE §3 · RUBRIC 3 = 10đ)

- [x] TODO 1 `slugify(topic)`: chống path traversal (`../../x` không thoát `reports/`), rỗng → `topic`, cắt 60 ký tự
- [x] TODO 2 `build_prompt`: tin nhắn đầu cho lead chứa chủ đề
- [x] TODO 3 `summarize`: đếm `subagent_calls` (số lần lead gọi `task`), `tool_calls`, `tokens` (tin nhắn lead)
- [x] TODO 4 `save_outputs` → `reports/<slug>.md`, `<slug>.sources.json`, `<slug>.meta.json`
  - [x] `meta.json`: `topic, model, elapsed_s, subagent_calls, tool_calls, tokens, n_sources, source_families`
  - [x] Report thiếu/rỗng hoặc `sources.json` hỏng → **báo lỗi, không ghi gì**
- [x] TODO 5 `main`:
  - [x] `make_model()`
  - [x] `with open_sandbox() as backend:` (luôn dọn sandbox)
  - [x] `backend.execute("mkdir -p /tmp/work/research/notes /tmp/work/report")`
  - [x] `upload(backend, {VALIDATOR_PATH: bytes check_citations.py, FINALIZER_PATH: bytes finalize_citations.py})` — **không** upload `.env`/khóa
  - [x] `agent.invoke({...}, config={"recursion_limit": 1000})`
  - [x] `download(backend, [REPORT_PATH, SOURCES_PATH])` (giá trị `None` = thiếu file)
  - [x] Thất bại → `sys.exit(1)`
- [x] Chạy thử 1 chủ đề: `python research.py "survey about world model"`; xem `meta.json` có hợp lý (≈2 phút, ~170k token)

**🔎 Lệnh kiểm tra**

```bash
# slugify an toàn
python - <<'EOF'
from research import slugify
for t in ["survey about world model", "../../x", "", "   ", "a/b\\c..d", "x" * 200, "Ñoño ÉTÉ!!"]:
    s = slugify(t); print(repr(t[:30]), "->", repr(s), "| OK" if s and "/" not in s and "\\" not in s and ".." not in s and len(s) <= 60 else "| LỖI")
EOF

# save_outputs: report rỗng / sources hỏng -> RuntimeError và KHÔNG ghi file nào
python - <<'EOF'
import tempfile, pathlib
from unittest import mock
import research
from agents import REPORT_PATH, SOURCES_PATH
for name, files in [("report thiếu", {REPORT_PATH: None, SOURCES_PATH: b"[]"}),
                    ("report rỗng", {REPORT_PATH: b"  ", SOURCES_PATH: b"[]"}),
                    ("sources hỏng", {REPORT_PATH: b"# T\n", SOURCES_PATH: b"{not json"})]:
    d = pathlib.Path(tempfile.mkdtemp())
    with mock.patch.object(research, "download", return_value=files):
        try: research.save_outputs(None, "t", [], 1.0, "m", reports_dir=d); print(name, ": LỖI - không raise")
        except RuntimeError: print(name, ": raise OK | file đã ghi:", list(d.iterdir()), "(phải rỗng)")
EOF

# main: không có topic -> exit 2
python research.py; echo "exit=$?"                         # exit=2

# Chạy thật 1 chủ đề + kiểm tra kết quả
python research.py "survey about world model"; echo "exit=$?"   # exit=0
ls reports/survey-about-world-model.*                           # .md  .sources.json  .meta.json
cat reports/survey-about-world-model.meta.json                  # đủ khóa topic, model, elapsed_s, subagent_calls, tool_calls, tokens, n_sources, source_families

# Không upload bí mật lên sandbox; có recursion_limit
grep -nE "\.env|API_KEY" research.py agents.py || echo "OK: không đụng tới .env/khóa"
grep -n "recursion_limit" research.py
```

---

## Checkpoint 5 — Chạy đủ 5 chủ đề (RUBRIC 2.1, 2.2, 4, 5 = 68đ)

- [x] `python research.py "survey about world model"`
- [x] `python research.py "survey about reinforcement learning for LLM reasoning"`
- [x] `python research.py "survey about LLM agents and tool use"`
- [x] `python research.py "survey about video and multimodal generation"`
- [x] `python research.py "survey about efficient inference and small language models"`

Với **từng** báo cáo:
- [x] `meta.json`: `subagent_calls >= 3` (2.1 · 8đ)
- [x] `meta.json`: `source_families` ≥ 3 họ, URL khớp họ (2.2 · 5đ)
- [x] `python check_citations.py reports/<slug>.md reports/<slug>.sources.json` → `OK` (4.1 · 7đ)
- [x] Mở trích dẫn mẫu, xác nhận câu đúng với nguồn, không có URL bịa (4.2 · 8đ) — đã kiểm mẫu số liệu của 3 báo cáo; phát hiện 1 câu gán sai nguồn (RL) -> siết prompt + chạy lại; còn lệch phiên bản R1-Zero 71.0% vs 77.9% (arXiv hiện hành)
- [x] Đúng cấu trúc: TL;DR (3–5 bullet có `[n]`), Background, 3–6 theme, Trends and open problems, References (5 · 1đ)
- [ ] Tổng hợp/so sánh theo chủ đề, không mỗi bài một đoạn (1.5đ)
- [ ] Cụ thể: tên, năm, số liệu lấy từ nguồn (1.5đ)
- [ ] Có nguồn gần đây (2 năm) + nguồn nền tảng (0.5đ)
- [ ] Xu hướng & vấn đề mở rõ ràng (0.5đ)

> Lỗi? **Sửa prompt/mã rồi chạy lại** — tuyệt đối không sửa tay báo cáo (gian lận). Xem bảng sự cố GUIDE §5.

**🔎 Lệnh kiểm tra**

```bash
# Chạy cả 5 chủ đề (lấy trực tiếp từ topics.md)
grep -E '^[0-9]+\. ' topics.md | sed 's/^[0-9]*\. //' | while read -r t; do
  echo "=== $t"; python research.py "$t" || echo "!!! FAILED: $t"
done

# Validator cho từng báo cáo -> phải in OK cho cả 5
for f in reports/*.sources.json; do s="${f%.sources.json}"; echo -n "$s: "; python check_citations.py "$s.md" "$f"; done

# Bảng tóm tắt meta: subagent_calls >= 3, >= 3 họ nguồn, họ khớp URL
python - <<'EOF'
import json, glob, re
FAM = {"arxiv": "https://arxiv.org/abs/", "hf-daily": "https://huggingface.co/papers/", "hf-search": "https://huggingface.co/papers/"}
for m in sorted(glob.glob("reports/*.meta.json")):
    meta = json.load(open(m, encoding="utf-8")); stem = m[:-len(".meta.json")]
    src = json.load(open(stem + ".sources.json", encoding="utf-8"))
    rep = open(stem + ".md", encoding="utf-8").read()
    bad = [s["n"] for s in src if s["source"] in FAM and not s["url"].startswith(FAM[s["source"]])]
    heads = re.findall(r"^## (.+)$", rep, re.M)
    years = sorted({s.get("date", "")[:4] for s in src if s.get("date")})
    print(f"{meta['topic'][:45]:45} sub={meta['subagent_calls']:<3} fam={meta['source_families']} "
          f"n={meta['n_sources']} sai_họ={bad} themes={len(heads)-4} năm={years[0] if years else '?'}..{years[-1] if years else '?'}")
    for h in ["TL;DR", "Background", "Trends and open problems", "References"]:
        if h not in heads: print("   THIẾU mục:", h)
EOF

# Kiểm tra mẫu thủ công: in 5 câu có trích dẫn + URL để mở đối chiếu (đổi tên file)
python - <<'EOF'
import json, re, random
stem = "reports/survey-about-world-model"
src = {s["n"]: s["url"] for s in json.load(open(stem + ".sources.json", encoding="utf-8"))}
body = open(stem + ".md", encoding="utf-8").read().split("## References")[0]
sents = [s for s in re.split(r"(?<=[.!?])\s+", body) if re.search(r"\[\d+\]", s)]
for s in random.sample(sents, min(5, len(sents))):
    print("-", s.strip()[:200]); [print("   ", src.get(int(n))) for n in re.findall(r"\[(\d+)\]", s)]
EOF
```

---

## Checkpoint 6 — Repo & nộp bài (RUBRIC 6 = 10đ)

- [x] 6.1 Không lộ bí mật: `git status` sạch `.env`; `git log -p | grep -i key` không ra khóa (lộ khóa = 0 cả mục 6)
- [x] 6.2 README: cách cài, cấu hình `.env`, chạy, cách đọc `reports/`
- [x] 6.3 Mã sạch, không mã chết, không sửa `model.py`/`sandbox.py`
- [x] 6.4 `requirements.txt` đủ để cài & chạy
- [x] (Khuyến khích) test cho `with_retry`, `slugify`, `check_citations` (mock `time.sleep`; bộ test hiện dùng `unittest`, không cần pytest)
- [x] `python self_check.py` → pass toàn bộ
- [ ] Commit mã + toàn bộ `reports/` (đúng bản tải từ sandbox)
- [ ] Push lên **public repo** GitHub, nộp link

**🔎 Lệnh kiểm tra**

```bash
# Kiểm tra tự động toàn bộ phần chấm máy (không tốn token)
python self_check.py

# Bí mật
git ls-files | grep -E '(^|/)\.env$' && echo "!!! .env bị track" || echo "OK: .env không bị track"
git log -p | grep -inE "(sk-[A-Za-z0-9_-]{20,}|(api_key|exaApiKey|token|secret)\s*[=:]\s*['\"]?[A-Za-z0-9_-]{16,})" | head \
  || echo "OK: không thấy khóa trong lịch sử git"

# Không sửa các tệp CÓ SẴN (so với commit gốc của đề)
git diff --stat 48a1223 -- model.py sandbox.py self_check.py finalize_citations.py   # phải trống

# Không còn TODO / NotImplementedError / mã chết
grep -nE "NotImplementedError|TODO" tools.py agents.py research.py check_citations.py || echo "OK: không còn TODO"

# requirements.txt cài sạch trong venv mới
python -m venv /tmp/venv-check && /tmp/venv-check/Scripts/pip install -q -r requirements.txt \
  && /tmp/venv-check/Scripts/python -c "import research, tools, agents; print('requirements OK')"
# (Linux/macOS: /tmp/venv-check/bin/pip và /tmp/venv-check/bin/python)

# Đủ 15 file báo cáo đã commit
git ls-files reports/ | wc -l          # >= 15
git status --short                     # trống trước khi push

# Repo public
gh repo view --json visibility,url     # visibility = PUBLIC
```

---

## Tùy chọn (không tính điểm — GUIDE §6)
- [ ] `thread_limit`, giới hạn token per-subagent, không retry 400/401
- [ ] Ngân sách token dùng chung (có khóa luồng)
- [ ] Bộ nhớ dài hạn `memory=["/memory/AGENTS.md"]` + `CompositeBackend`
- [ ] `compact_conversation` qua `create_summarization_tool_middleware`
