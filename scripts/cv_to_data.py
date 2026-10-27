#!/usr/bin/env python3
"""Generate data/cv.json for the website from the LaTeX CV.

The CV (English and Chinese, in the grants repository) is the single source for positions, education,
publications, books, grants, teaching, awards, service and talks. This script reads both .tex files,
converts the few LaTeX macros they use to HTML, merges the hand-written additions in data/extra.yaml
(DOIs, abstracts, glosses, course descriptions) and writes data/cv.json.

Working papers and work in progress are deliberately left out: they are not published on the site, and
the repository is public.

Usage:
    python3 scripts/cv_to_data.py [--en PATH] [--zh PATH]

Defaults: ~/projects/grants/cv/cv_simple.tex and cv_simple_zh.tex. Exits with status 1 if the CV has a
section this script does not know, or if an entry in data/extra.yaml no longer matches the CV.
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CV_DIR = Path.home() / "projects" / "grants" / "cv"

# (section, subsection or subsubsection) -> key in the output. None means "skip on purpose".
SECTIONS = {
    "en": {
        ("Academic Positions", None): "positions",
        ("Other Positions", None): "other_positions",
        ("Education", None): "education",
        ("Research Interests", None): "interests",
        ("Research Output", "Publications"): "publications",
        ("Research Output", "Working Papers"): None,
        ("Research Output", "Work in Progress"): None,
        ("Research Output", "Books, Reports, and Other Publications"): "books",
        ("Grants", None): "grants",
        ("Teaching Experience", "Current Teaching"): "teaching_current",
        ("Teaching Experience", "Past Teaching"): "teaching_past",
        ("Awards & Achievements", None): "awards",
        ("Professional Activities", "Referee Services"): "referee",
        ("Professional Activities", "Media Exposure & Consultancy"): "media",
        ("Professional Activities", "Conference Organisation"): "conference_org",
        ("Professional Activities", "Special Invitations & Public Lectures"): "invited",
        ("Professional Activities", "Summer Schools & External Lectures"): "summer",
        ("Professional Activities", "Seminar Talks & Conferences"): "talks",
    },
    "zh": {
        ("学术职位", None): "positions",
        ("其他职务", None): "other_positions",
        ("教育背景", None): "education",
        ("研究方向", None): "interests",
        ("研究成果", "已发表论文"): "publications",
        ("研究成果", "工作论文"): None,
        ("研究成果", "进展中研究"): None,
        ("研究成果", "专著、报告与其他出版物"): "books",
        ("科研项目", None): "grants",
        ("教学经历", "当前授课"): "teaching_current",
        ("教学经历", "过往授课"): "teaching_past",
        ("获奖与荣誉", None): "awards",
        ("学术服务", "审稿服务"): "referee",
        ("学术服务", "媒体曝光与咨询"): "media",
        ("学术服务", "会议组织"): "conference_org",
        ("学术服务", "特邀报告与公开讲座"): "invited",
        ("学术服务", "暑期学校与外部授课"): "summer",
        ("学术服务", "学术报告与会议"): "talks",
    },
}

# Commands that take brace arguments, with their argument count.
ENTRY_ARGS = {"position": 3, "grant": 5, "teaching": 5, "dateitem": 2, "talkyear": 2}
HEADINGS = ("cvsection", "cvsubsection", "cvsubsubsection")
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
MONTH_NAMES = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()

problems = []


# ---------------------------------------------------------------- LaTeX reading

def strip_comments(text):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def read_arg(text, i):
    """Return (argument, index after it) for the brace group starting at or after i."""
    while text[i].isspace():
        i += 1
    if text[i] != "{":
        raise ValueError(f"expected '{{' at {text[i:i + 40]!r}")
    depth, j = 0, i
    while True:
        c = text[j]
        if c == "\\":
            j += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1


def to_html(tex):
    """Convert the LaTeX used in the CV to an HTML fragment."""
    s = html.escape(tex, quote=False)
    s = s.replace("\\&amp;", "&amp;")

    def command(name, n, fmt):
        nonlocal s
        pat = re.compile(r"\\" + name + r"(?![A-Za-z])")
        out, i = [], 0
        while (m := pat.search(s, i)):
            out.append(s[i:m.start()])
            j, args = m.end(), []
            for _ in range(n):
                a, j = read_arg(s, j)
                args.append(a)
            out.append(fmt(*args))
            i = j
        out.append(s[i:])
        s = "".join(out)

    for _ in range(3):  # nested macros
        command("emph", 1, lambda a: f"<em>{a}</em>")
        command("textbf", 1, lambda a: f"<strong>{a}</strong>")
        command("zh", 1, lambda a: a)
        command("href", 2, lambda u, t: f'<a href="{u}">{t}</a>')
    s = s.replace("\\newline", "<br>").replace("\\ ", " ").replace("\\,", " ")
    s = s.replace("``", "“").replace("''", "”").replace("---", "—").replace("--", "–")
    s = s.replace("~", " ").replace("\\$", "$").replace("\\%", "%")
    s = re.sub(r"\s+", " ", s).strip()
    if "\\" in s:
        problems.append(f"unconverted LaTeX: {s[:80]}")
    return s


def plain(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment))


def parse(path, lang):
    text = strip_comments(Path(path).read_text(encoding="utf-8"))
    body = text.split("\\begin{document}", 1)[1].split("\\end{document}", 1)[0]
    body = body[body.index("\\cvsection"):]
    blocks, cur = [], None  # each block: {"head": (section, sub), "entries": [...], "items": [...], "text": [...]}
    section = sub = None
    i, n, in_outputs = 0, len(body), False
    while i < n:
        if body.startswith("\\", i):
            m = re.match(r"\\([A-Za-z]+)", body[i:])
            name = m.group(1) if m else ""
            j = i + 1 + len(name)
            if name in HEADINGS:
                title, j = read_arg(body, j)
                title = plain(to_html(title))
                if name == "cvsection":
                    section, sub = title, None
                else:
                    sub = title
                cur = {"head": (section, sub), "entries": [], "items": [], "text": []}
                blocks.append(cur)
                i = j
                continue
            if name in ENTRY_ARGS:
                args = []
                for _ in range(ENTRY_ARGS[name]):
                    a, j = read_arg(body, j)
                    args.append(a)
                cur["entries"].append((name, args))
                i = j
                continue
            if name == "begin" or name == "end":
                env, j = read_arg(body, j)
                if env == "outputs":
                    in_outputs = name == "begin"
                i = j
                continue
            if name == "item" and in_outputs:
                end = body.find("\\item", j)
                stop = body.find("\\end{outputs}", j)
                end = stop if end < 0 or (0 <= stop < end) else end
                cur["items"].append(body[j:end].strip())
                i = end
                continue
        # free text up to the next command we handle
        nxt = re.search(r"\\(?:" + "|".join(HEADINGS + tuple(ENTRY_ARGS) + ("begin", "end", "item")) + r")\b", body[i + 1:])
        end = i + 1 + nxt.start() if nxt else n
        chunk = body[i:end].strip()
        if chunk and cur is not None:
            cur["text"].append(chunk)
        i = end
    out = {}
    for b in blocks:
        head = b["head"]
        if head not in SECTIONS[lang]:
            if b["entries"] or b["items"] or b["text"]:
                problems.append(f"{lang}: unknown CV section {head}")
            continue
        key = SECTIONS[lang][head]
        if key is not None:
            out[key] = b
    return out


# ---------------------------------------------------------------- dates

def month_year(s):
    """'May 2026', 'Jun. 2026', '2026 年 5 月' -> (2026, 5); None if it is not one."""
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", s)
    if m and m.group(1).lower() in MONTHS:
        return int(m.group(2)), MONTHS[m.group(1).lower()]
    m = re.match(r"(\d{4})\s*年\s*(\d{1,2})\s*月", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None


def grant_dates(s):
    """'08/01/2026 -- 30/03/2026' (en, day first) or '2026/01/08 -- 2026/03/30' (zh) -> two (year, month)."""
    parts = re.findall(r"\d+/\d+/\d+", s)
    res = []
    for p in parts:
        a, b, c = p.split("/")
        res.append((int(c), int(b)) if len(c) == 4 else (int(a), int(b)))
    return res


def ym_label(ym):
    return f"{MONTH_NAMES[ym[1] - 1]} {ym[0]}"


# ---------------------------------------------------------------- building

def split_list(s, sep):
    return [x.strip() for x in re.split(sep, s) if x.strip()]


def build(lang, blocks, extra):
    sep = "；" if lang == "zh" else ";"
    d = {}
    for key in ("positions", "other_positions", "education"):
        d[key] = [{"title": to_html(a), "org": to_html(b), "dates": to_html(c)}
                  for _, (a, b, c) in blocks[key]["entries"]]
    d["interests"] = to_html(" ".join(blocks["interests"]["text"]))

    pubs = []
    for raw in blocks["publications"]["items"]:
        m = re.match(r"(?s)(?P<authors>.*?)\.\s*``(?P<title>.*?)''\s*\\emph\{(?P<venue>[^}]*)\}\s*(?P<details>.*)", raw)
        if not m:
            problems.append(f"{lang}: cannot parse publication: {raw[:80]}")
            continue
        authors = split_list(plain(to_html(m["authors"])), r",\s*(?:and\s+)?|\s+and\s+")
        title = to_html(m["title"]).rstrip(".")
        year = re.search(r"\((\d{4})\)", m["details"])
        pubs.append({"authors": authors, "title": title, "venue": to_html(m["venue"]),
                     "details": to_html(m["details"]), "year": int(year.group(1)) if year else None})
    d["publications"] = pubs

    books = []
    for raw in blocks["books"]["items"]:
        zh_title = re.search(r"《[^》]+》[^,，}]*", raw)
        yr = re.search(r"(\d{4})\s*$", raw)
        books.append({"html": to_html(raw), "title_zh": zh_title.group(0).strip() if zh_title else "",
                      "year": int(yr.group(1)) if yr else None})
    d["books"] = books

    grants = []
    for _, (title, role, amount, funder, dates) in blocks["grants"]["entries"]:
        ds = grant_dates(dates)
        grants.append({"title": to_html(title), "role": to_html(role), "amount": to_html(amount),
                       "funder": to_html(funder), "dates": to_html(dates),
                       "start": "%04d-%02d" % ds[0] if ds else "", "end": "%04d-%02d" % ds[-1] if ds else "",
                       "period": " – ".join(ym_label(x) for x in ds) if ds and lang == "en" else to_html(dates)})
    d["grants"] = grants
    d["grants_total"] = to_html(" ".join(blocks["grants"]["text"]))

    for key in ("teaching_current", "teaching_past"):
        d[key] = [{"course": to_html(a), "role": to_html(b), "dates": to_html(c), "programme": to_html(p),
                   "awards": to_html(w)} for _, (a, b, c, p, w) in blocks[key]["entries"]]

    for key in ("awards", "media", "conference_org", "invited", "summer"):
        d[key] = [{"date": to_html(a), "text": to_html(b)} for _, (a, b) in blocks[key]["entries"]]
    d["referee"] = split_list(plain(to_html(" ".join(blocks["referee"]["text"]))), sep)
    d["talks"] = [{"year": a.strip(), "venues": split_list(to_html(b), sep)}
                  for _, (a, b) in blocks["talks"]["entries"]]

    # The latest dated activities, for the "Recent" list on the home page.
    recent = []
    for key, kind in (("invited", "talk"), ("summer", "teaching"), ("conference_org", "service"), ("media", "media")):
        for it in d[key]:
            ym = month_year(plain(it["date"]))
            if ym:
                recent.append({"ym": "%04d-%02d" % ym, "date": it["date"], "kind": kind, "html": it["text"]})
    for g in grants:
        if g["start"]:
            y, mo = map(int, g["start"].split("-"))
            label = ym_label((y, mo)) if lang == "en" else f"{y} 年 {mo} 月"
            text = (f"New grant: {g['title']} ({g['funder']}, {g['role']})" if lang == "en"
                    else f"新项目：{g['title']}（{g['funder']}，{g['role']}）")
            recent.append({"ym": g["start"], "date": label, "kind": "grant", "html": text})
    recent.sort(key=lambda r: r["ym"], reverse=True)
    d["recent"] = recent[:6]
    return d


def merge_extra(en, extra):
    used = set()
    for p in en["publications"]:
        for pid, meta in (extra.get("publications") or {}).items():
            if plain(p["title"]).lower().startswith(meta["match"].lower()):
                p["id"] = pid
                p["doi"] = meta.get("doi", "")
                p["abstract"] = (meta.get("abstract") or "").strip()
                used.add(pid)
                break
        else:
            p["id"] = re.sub(r"[^a-z0-9]+", "-", plain(p["title"]).lower())[:40].strip("-")
    for pid in set(extra.get("publications") or {}) - used:
        problems.append(f"extra.yaml: publication '{pid}' matches no publication in the CV")
    ids = {p["id"] for p in en["publications"]}
    for pid in extra.get("selected") or []:
        if pid not in ids:
            problems.append(f"extra.yaml: selected '{pid}' is not a publication id")

    glosses = extra.get("book_glosses") or {}
    for b in en["books"]:
        b["gloss"] = glosses.get(b["title_zh"], "")
    for k in set(glosses) - {b["title_zh"] for b in en["books"]}:
        problems.append(f"extra.yaml: book gloss '{k}' matches no book in the CV")

    courses = extra.get("courses") or {}
    for t in en["teaching_current"] + en["teaching_past"]:
        t["desc"] = (courses.get(plain(t["course"])) or "").strip()
    for k in set(courses) - {plain(t["course"]) for t in en["teaching_current"] + en["teaching_past"]}:
        problems.append(f"extra.yaml: course '{k}' matches no course in the CV")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--en", default=CV_DIR / "cv_simple.tex")
    ap.add_argument("--zh", default=CV_DIR / "cv_simple_zh.tex")
    ap.add_argument("--out", default=ROOT / "data" / "cv.json")
    a = ap.parse_args()
    extra = yaml.safe_load((ROOT / "data" / "extra.yaml").read_text(encoding="utf-8"))
    data = {}
    for lang, path in (("en", a.en), ("zh", a.zh)):
        data[lang] = build(lang, parse(path, lang), extra)
    merge_extra(data["en"], extra)
    for p in problems:
        print("problem:", p, file=sys.stderr)
    if problems:
        return 1
    Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    en = data["en"]
    print(f"wrote {a.out}: {len(en['publications'])} publications, {len(en['books'])} books, "
          f"{len(en['grants'])} grants, {len(en['teaching_current']) + len(en['teaching_past'])} courses, "
          f"{len(en['talks'])} years of talks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
