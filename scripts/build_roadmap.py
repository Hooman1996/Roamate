"""Build docs/plan/roadmap.html from the plan and the step list.

The plan (docs/plan/implementation-plan.md) gives each milestone's size,
summary, test, gate and release; the step list
(docs/plan/implementation-steps.md) gives the phases, the steps and what is
done. The roadmap is never edited by hand.

Usage:
  python scripts/build_roadmap.py            write docs/plan/roadmap.html
  python scripts/build_roadmap.py --check    fail if the two sources disagree
                                             or roadmap.html is out of date
  python scripts/build_roadmap.py --fragment PATH
                                             also write the page without the
                                             <html> wrapper (for publishing)

Standard library only, so it runs in CI before any project setup.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs/plan/implementation-plan.md"
STEPS = ROOT / "docs/plan/implementation-steps.md"
TEMPLATE = ROOT / "docs/plan/roadmap.template.html"
OUT = ROOT / "docs/plan/roadmap.html"

PHASE_RE = re.compile(r"^#{2,3} (Phase \d+ — .+|Research track — .+)$")
MILESTONE_HEAD_RE = re.compile(r"^### ([MR]\d+)\. (.+)$")
STEP_RE = re.compile(r"^- \[( |x)\] \*\*([MR]\d+\.\d+)\*\* (.+)$")
PLAN_MILESTONE_RE = re.compile(
    r"^\*\*([MR]\d+)\. (.+?) \(([SML])\)\*\*\n"
    r"(.+)\n"
    r"\*You can test:\* (.+)\n"
    r"(?:\*Gate:\* (.+)\n)?"
    r"(?:\*Release:\* (.+)\n)?",
    re.MULTILINE,
)
VERSION_RE = re.compile(r"^\*\*Version:\*\* (.+)$", re.MULTILINE)


def phase_name(heading):
    """'Phase 2 — Foundation and accounts' -> ('Foundation and accounts', False)."""
    if heading.startswith("Research track"):
        return heading.split(" — ", 1)[1], True
    return heading.split(" — ", 1)[1], False


def parse_steps(text, errors):
    phases, milestones, seen = [], {}, set()
    current = None
    for n, line in enumerate(text.splitlines(), 1):
        if m := PHASE_RE.match(line):
            name, side = phase_name(m.group(1))
            phases.append({"name": name, "side": side, "ids": []})
        elif m := MILESTONE_HEAD_RE.match(line):
            current = m.group(1)
            if not phases:
                errors.append(f"steps line {n}: milestone {current} before any phase heading")
                continue
            milestones[current] = {"id": current, "title": m.group(2), "steps": [], "phase": phases[-1]["name"]}
            phases[-1]["ids"].append(current)
        elif m := STEP_RE.match(line):
            done, sid, title = m.group(1) == "x", m.group(2), m.group(3)
            if current is None:
                errors.append(f"steps line {n}: step {sid} outside a milestone")
                continue
            if sid in seen:
                errors.append(f"steps line {n}: duplicate step ID {sid}")
            seen.add(sid)
            if sid.split(".")[0] != current:
                errors.append(f"steps line {n}: step {sid} is listed under {current}")
            milestones[current]["steps"].append([sid, title, done])
    for m in milestones.values():
        if not m["steps"]:
            errors.append(f"steps: milestone {m['id']} has no steps")
    return phases, milestones


def parse_plan(text, errors):
    milestones, phase = {}, None
    section = text.split("\n## 12. Milestones", 1)
    if len(section) != 2:
        errors.append("plan: section '## 12. Milestones' not found")
        return {}, [], []
    body = section[1].split("\n---\n", 1)[0]
    for line in body.splitlines():
        if m := PHASE_RE.match(line):
            phase = phase_name(m.group(1))[0]
        elif line.startswith("**") and (m := PLAN_MILESTONE_RE.match(body[body.index(line):])):
            mid, title, size, summary, test, gate, release = m.groups()
            milestones[mid] = {
                "title": title, "size": size, "summary": summary, "test": test,
                "gate": gate or "", "release": release or "", "phase": phase,
            }
    simple = parse_simple_table(text, errors)
    later = parse_later(body, errors)
    return milestones, simple, later


def parse_simple_table(text, errors):
    """Rows of the 'Keeping it simple' table: [area, start with, add later]."""
    part = text.split("\n## 3. Keeping it simple", 1)
    if len(part) != 2:
        errors.append("plan: section '## 3. Keeping it simple' not found")
        return []
    rows = []
    for line in part[1].split("\n---\n", 1)[0].splitlines():
        if line.startswith("| ") and not line.startswith("| Area") and not line.startswith("| ---"):
            cells = [c.strip() for c in line.strip().strip("|").split(" | ")]
            if len(cells) == 3:
                rows.append(cells)
    return rows


def parse_later(body, errors):
    """Items of the 'Later' paragraph, split on commas outside parentheses."""
    part = body.split("### Later (not planned in detail yet)\n", 1)
    if len(part) != 2:
        errors.append("plan: '### Later (not planned in detail yet)' not found")
        return []
    para = part[1].strip().split("\n", 1)[0].rstrip(".")
    items, depth, cur = [], 0, ""
    for ch in para:
        depth += ch == "("
        depth -= ch == ")"
        if ch == "," and depth == 0:
            items.append(cur.strip())
            cur = ""
        else:
            cur += ch
    items.append(cur.strip())
    return [i[0].upper() + i[1:] for i in items if i]


def build():
    errors = []
    plan_text, steps_text = PLAN.read_text(), STEPS.read_text()
    phases, step_ms = parse_steps(steps_text, errors)
    plan_ms, simple, later = parse_plan(plan_text, errors)

    pv, sv = VERSION_RE.search(plan_text), VERSION_RE.search(steps_text)
    if not pv or not sv or pv.group(1) != sv.group(1):
        errors.append("the **Version:** lines of the plan and the step list differ")

    for mid in step_ms.keys() - plan_ms.keys():
        errors.append(f"{mid} is in the step list but not in plan §12")
    for mid in plan_ms.keys() - step_ms.keys():
        errors.append(f"{mid} is in plan §12 but not in the step list")
    for mid in step_ms.keys() & plan_ms.keys():
        s, p = step_ms[mid], plan_ms[mid]
        if s["title"] != p["title"]:
            errors.append(f"{mid} title differs: steps '{s['title']}' vs plan '{p['title']}'")
        if s["phase"] != p["phase"]:
            errors.append(f"{mid} phase differs: steps '{s['phase']}' vs plan '{p['phase']}'")

    if errors:
        return None, errors

    data = {
        "version": pv.group(1),
        "phases": [
            {
                "name": ph["name"],
                "side": ph["side"],
                "milestones": [
                    {"id": mid, "steps": step_ms[mid]["steps"],
                     **{k: plan_ms[mid][k] for k in ("title", "size", "summary", "test", "gate", "release")}}
                    for mid in ph["ids"]
                ],
            }
            for ph in phases
        ],
        "simple": simple,
        "later": later,
    }
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    fragment = TEMPLATE.read_text().replace("/*__DATA__*/null", payload)
    return fragment, data


def wrap(fragment):
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<!-- Generated by scripts/build_roadmap.py from implementation-plan.md and "
        "implementation-steps.md. Do not edit by hand. -->\n"
        f"</head>\n<body>\n{fragment}\n</body>\n</html>\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 on any problem")
    ap.add_argument("--fragment", type=Path, help="also write the unwrapped page here")
    args = ap.parse_args()

    fragment, result = build()
    if fragment is None:
        print("Roadmap sources disagree:", *result, sep="\n  ", file=sys.stderr)
        return 1
    page = wrap(fragment)
    ms = [m for ph in result["phases"] for m in ph["milestones"]]
    steps = [s for m in ms for s in m["steps"]]
    summary = f"{len(ms)} milestones, {len(steps)} steps, {sum(s[2] for s in steps)} done"

    if args.check:
        if not OUT.exists() or OUT.read_text() != page:
            print("docs/plan/roadmap.html is out of date: run python scripts/build_roadmap.py", file=sys.stderr)
            return 1
        print(f"Roadmap is up to date ({summary}).")
        return 0

    OUT.write_text(page)
    if args.fragment:
        args.fragment.write_text(fragment)
    print(f"Wrote {OUT.relative_to(ROOT)} ({summary}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
