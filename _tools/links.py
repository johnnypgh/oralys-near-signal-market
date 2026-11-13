#!/usr/bin/env python3
"""Walk test helper: every markdown link and every backticked path in AGENTS.md, CLAUDE.md and
every CONTEXT.md must resolve. Paths are relative to the workspace root (or to the file for ./ and ../).
Paths under an output/ folder only need their parent folder to exist, since a run creates them.

Usage: python3 -I _tools/links.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "node_modules", "target", ".keys"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)")
TICK = re.compile(r"`([^`\s]+)`")
PATHY = re.compile(r"^(\.{0,2}/)?[\w.-]+(/[\w.*-]*)*(\.(md|json|py|ts|sh|rs|toml|wasm|txt|log)|/)$")


def targets(md_path):
    text = open(md_path, encoding="utf-8").read()
    for m in LINK.finditer(text):
        t = m.group(1)
        if not re.match(r"^[a-z]+://", t) and not t.startswith("mailto:"):
            yield t
    for m in TICK.finditer(text):
        t = m.group(1)
        if "://" in t or t.startswith("~") or t.startswith("$") or "<" in t or "*" in t:
            continue
        if PATHY.match(t) and ("/" in t or t.endswith(".md")):
            yield t


def resolves(md_path, t):
    base = os.path.dirname(md_path) if t.startswith(("./", "../")) else ROOT
    p = os.path.normpath(os.path.join(base, t))
    if os.path.exists(p):
        return True
    if "/output/" in p.replace(os.sep, "/") + "/":
        parent = p
        while not os.path.basename(parent) == "output" and parent != ROOT:
            parent = os.path.dirname(parent)
        return os.path.isdir(parent)
    return False


def main():
    files = [os.path.join(ROOT, f) for f in ("AGENTS.md", "CLAUDE.md", "CONTEXT.md") if os.path.exists(os.path.join(ROOT, f))]
    for d, dirs, fs in os.walk(ROOT):
        dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
        if d != ROOT and "CONTEXT.md" in fs:
            files.append(os.path.join(d, "CONTEXT.md"))
    bad, checked = [], 0
    for f in files:
        for t in targets(f):
            checked += 1
            if not resolves(f, t):
                bad.append(f"{os.path.relpath(f, ROOT)}: {t}")
    for f in files:
        print(f"scanned {os.path.relpath(f, ROOT)}")
    if bad:
        print(f"FAIL: {len(bad)} of {checked} paths do not resolve")
        for b in bad:
            print(f"  {b}")
        sys.exit(1)
    print(f"OK: {checked} paths in {len(files)} files resolve")


if __name__ == "__main__":
    main()
