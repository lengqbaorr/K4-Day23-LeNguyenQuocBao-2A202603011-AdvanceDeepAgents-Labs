"""Citation consistency validator.   Runs INSIDE the sandbox (standard library only).

research.py uploads this file to the sandbox and the lead agent runs it with the `execute` tool:
    python3 /tmp/work/research/check_citations.py [report.md] [sources.json]
It must exit 0 and print "OK: ..." when the report is consistent, else print each problem and exit 1.
"""
import json
import re
import sys

REPORT = "/tmp/work/report/report.md"
SOURCES = "/tmp/work/research/sources.json"


def check(report_text, sources):
    """Return a list of problem strings (empty list = OK).

    """
    problems = []
    if not isinstance(sources, list) or not sources:
        return ["no sources in sources.json (expected a nonempty array)"]
    by_number, urls = {}, set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            problems.append(f"source {index + 1} is not an object")
            continue
        n, url = source.get("n"), source.get("url")
        if type(n) is not int or n < 1:
            problems.append(f"source {index + 1} has invalid n")
        elif n in by_number:
            problems.append(f"duplicate source number [{n}]")
        else:
            by_number[n] = source
        if not isinstance(url, str) or not re.match(r"https?://\S+$", url):
            problems.append(f"source {index + 1} has invalid URL")
        elif url in urls:
            problems.append(f"duplicate source URL: {url}")
        else:
            urls.add(url)

    # Remove fenced code before detecting headings and citations.
    clean, fence = [], None
    for line in report_text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker[1]
            continue
        clean.append(line)
    text = "\n".join(clean)
    headings = list(re.finditer(r"^## References\s*$", text, re.M))
    if not headings:
        problems.append("missing ## References")
        body, references = text, ""
    else:
        if len(headings) != 1:
            problems.append("expected exactly one ## References heading")
        body, references = text[:headings[0].start()], text[headings[0].end():]
    body = re.sub(r"`+[^`\n]*`+", "", body)
    cited = set()
    for match in re.finditer(r"\[(\d+(?:\s*(?:,|[-–])\s*\d+)*)\](?!\s*\()", body):
        for part in match[1].split(","):
            bounds = [int(x) for x in re.split(r"[-–]", part)]
            if len(bounds) == 1:
                cited.add(bounds[0])
            elif bounds[1] < bounds[0] or bounds[1] - bounds[0] > 10000:
                problems.append(f"invalid citation range [{part}]")
            else:
                cited.update(range(bounds[0], bounds[1] + 1))
    for n in sorted(cited - by_number.keys()):
        problems.append(f"[{n}] cited but missing from sources.json")
    for n in sorted(by_number.keys() - cited):
        problems.append(f"source [{n}] never cited")
    counts = {}
    for line in references.splitlines():
        match = re.match(r"^\[(\d+)\]\s*", line)
        if not match:
            if line.strip():
                problems.append(f"invalid reference line: {line[:100]}")
            continue
        n = int(match[1])
        counts[n] = counts.get(n, 0) + 1
        found = re.findall(r"https?://[^\s<>]+", line)
        if len(found) != 1:
            problems.append(f"reference [{n}] must contain exactly one URL")
        elif n in by_number and found[0] != by_number[n].get("url"):
            problems.append(f"reference [{n}] URL differs from sources.json")
        if n not in by_number:
            problems.append(f"reference [{n}] is not a source")
    for n in by_number:
        if counts.get(n, 0) != 1:
            problems.append(f"source [{n}] needs exactly one reference line")
    return problems


def main(argv):
    report_path = argv[1] if len(argv) > 1 else REPORT
    sources_path = argv[2] if len(argv) > 2 else SOURCES
    try:
        with open(report_path, encoding="utf-8") as f:
            report = f.read()
        with open(sources_path, encoding="utf-8") as f:
            sources = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"cannot read inputs: {exc}")
        return 1
    problems = check(report, sources)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"OK: {len(sources)} sources, all citations resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
