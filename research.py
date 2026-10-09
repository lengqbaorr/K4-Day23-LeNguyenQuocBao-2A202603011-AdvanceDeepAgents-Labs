"""research.py - the main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from deepagents.backends.protocol import FileUploadResponse

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent
from model import make_model
from sandbox import download, open_sandbox, upload

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def slugify(topic):
    """Safe file name: lower case, runs of non-word characters become one "-", max 60 chars, never empty."""
    return re.sub(r"\W+", "-", topic.lower()).strip("-")[:60].strip("-") or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return f"Research topic: {topic}\nFollow your workflow and finish only when the validator prints OK."


def summarize(messages, elapsed, model_name):
    """Count the lead's tool calls and tokens (lead messages only: subagent tokens are not included)."""
    calls, tokens = Counter(), {"input": 0, "output": 0}
    for message in messages:
        for call in getattr(message, "tool_calls", None) or []:
            calls[call["name"]] += 1
        usage = getattr(message, "usage_metadata", None) or {}
        tokens["input"] += usage.get("input_tokens", 0)
        tokens["output"] += usage.get("output_tokens", 0)
    return {"model": model_name, "elapsed_s": round(elapsed, 1), "subagent_calls": calls["task"],
            "tool_calls": dict(calls), "tokens": tokens}


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report, raw_sources = files.get(REPORT_PATH), files.get(SOURCES_PATH)
    if not report or not report.strip():
        raise RuntimeError("the agent produced no report")
    try:
        sources = json.loads(raw_sources)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"sources.json is missing or invalid: {exc}") from exc
    if not isinstance(sources, list) or not sources:
        raise RuntimeError("sources.json is empty")
    meta = {"topic": topic, **summarize(messages, elapsed, model_name), "n_sources": len(sources),
            "source_families": sorted({s.get("source", "") for s in sources})}
    reports_dir.mkdir(parents=True, exist_ok=True)
    stem = reports_dir / slugify(topic)
    Path(f"{stem}.sources.json").write_bytes(raw_sources)  # the exact bytes downloaded from the sandbox
    Path(f"{stem}.meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    Path(f"{stem}.md").write_bytes(report)
    return Path(f"{stem}.md")


def soft_upload_errors(backend):
    """Daytona raises when the agent writes outside a writable dir (e.g. "/notes.md"), which would kill the run.
    Turn that into a normal tool error so the agent can retry with the right path."""
    upload_files = backend.upload_files

    def safe(files):
        try:
            return upload_files(files)
        except Exception:  # noqa: BLE001 - reported back to the agent as permission_denied
            return [FileUploadResponse(path=path, error="permission_denied") for path, _ in files]
    backend.upload_files = safe


PREFIX = {"arxiv": "https://arxiv.org/abs/", "hf-daily": "https://huggingface.co/papers/",
          "hf-search": "https://huggingface.co/papers/"}


REQUIRED_HEADINGS = ("TL;DR", "Background", "Trends and open problems", "References")


def gate(backend):
    """Finalize + validate inside the sandbox. Return a problem description, or None when the report is good."""
    final = backend.execute(f"python3 {FINALIZER_PATH}")
    if final.exit_code != 0:
        return f"finalize_citations.py failed: {final.output[-1500:]}"
    check = backend.execute(f"python3 {VALIDATOR_PATH}")
    if check.exit_code != 0:
        return f"check_citations.py failed: {check.output[-1500:]}"
    try:
        sources = json.loads(download(backend, [SOURCES_PATH])[SOURCES_PATH])
    except (TypeError, ValueError):
        return f"{SOURCES_PATH} is missing or not valid JSON"
    try:
        report = download(backend, [REPORT_PATH])[REPORT_PATH].decode("utf-8", "replace")
    except AttributeError:
        return f"{REPORT_PATH} is missing"
    headings = {h.strip() for h in re.findall(r"^## (.+)$", report, re.M)}
    missing = [h for h in REQUIRED_HEADINGS if h not in headings]
    if missing:
        return f"report is missing required section heading(s) {missing}: use these exact '## ' titles"
    wrong = [s["n"] for s in sources if s.get("source") in PREFIX and not str(s.get("url")).startswith(PREFIX[s["source"]])]
    if wrong:
        return (f"sources {wrong} are labelled arxiv/hf-* but their URL is not {PREFIX['arxiv']}<id> or "
                f"{PREFIX['hf-search']}<id>. A page found with web_search/web_fetch is source \"web\"; "
                "an arxiv_search record uses https://arxiv.org/abs/<id> (no version, no /html/ or /pdf/).")
    families = {s.get("source") for s in sources}
    if len(families) < 3:
        return f"only {len(families)} source families are cited ({sorted(families)}); at least 3 are required"
    return None


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    if not topic.strip():
        print('usage: python research.py "<topic>"', file=sys.stderr)
        return 2
    model = make_model()
    if hasattr(model, "use_responses_api"):
        # Reasoning models reject function tools on /v1/chat/completions; the Responses API accepts them.
        model.use_responses_api = True
    model_name = getattr(model, "model_name", None) or getattr(model, "model", "unknown")
    start = time.monotonic()
    try:
        with open_sandbox() as backend:  # the sandbox is always stopped and removed, even on errors
            soft_upload_errors(backend)
            backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
            upload(backend, {VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
                             FINALIZER_PATH: FINALIZER_SOURCE.read_bytes()})
            agent = build_lead_agent(backend, model)
            messages = [{"role": "user", "content": build_prompt(topic)}]
            for _ in range(3):  # up to two repair rounds when the in-sandbox gate fails
                messages = agent.invoke({"messages": messages}, config={"recursion_limit": 1000})["messages"]
                problem = gate(backend)
                if problem is None:
                    break
                print(f"[gate] {problem}", file=sys.stderr)
                messages = [*messages, {"role": "user", "content": f"The final check failed: {problem}\n"
                            "Fix it (research more if a family is missing), then finalize and validate again."}]
            else:
                raise RuntimeError(problem)
            path = save_outputs(backend, topic, messages, time.monotonic() - start, model_name)
    except (RuntimeError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"Report saved: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
