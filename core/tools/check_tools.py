"""Static and import checks for the repo's Python tools (no game files are changed).

  python core/tools/check_tools.py          every check
  python core/tools/check_tools.py --quick  skip the import check

1. Every tool parses.
2. Every hodpaths.tool('...') / hodpaths.setting('...') with a constant name
   resolves to a file in the repo.
3. Every tool with a main guard (and the shared libraries) imports cleanly in a
   fresh interpreter. Scripts that act when imported are only parsed.
"""
import ast
import subprocess
import sys
from pathlib import Path

import hodpaths

LIBRARIES = {"hodsprite", "nathan_paths", "txrc", "hodpaths"}
# Read their command line at import (not a layout problem): parse only.
CLI_AT_IMPORT = {"overlap", "render_tpf"}


def tools():
    for d in hodpaths.TOOL_DIRS:
        yield from sorted(d.glob("*.py"))


def guarded(tree):
    for node in tree.body:
        if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test):
            return True
    return False


def main():
    problems, importable = [], []
    for p in tools():
        rel = p.relative_to(hodpaths.REPO).as_posix()
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError as e:
            problems.append(f"{rel}: {e}")
            continue
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                    isinstance(node.func.value, ast.Name) and node.func.value.id == "hodpaths" and
                    node.func.attr in ("tool", "setting") and node.args and isinstance(node.args[0], ast.Constant)):
                try:
                    getattr(hodpaths, node.func.attr)(node.args[0].value)
                except FileNotFoundError as e:
                    problems.append(f"{rel}:{node.lineno}: {e}")
        if (guarded(tree) or p.stem in LIBRARIES) and p.stem not in CLI_AT_IMPORT:
            importable.append(p)
    print(f"parsed {sum(1 for _ in tools())} tools; {len(problems)} path problems")
    if "--quick" not in sys.argv:
        for p in importable:
            code = f"import sys; sys.argv=[{p.name!r}]; sys.path.insert(0, {str(p.parent)!r}); import {p.stem}"
            r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120,
                               cwd=str(hodpaths.WORK if hodpaths.WORK.is_dir() else hodpaths.REPO))
            if r.returncode:
                last = (r.stderr.strip().splitlines() or ["?"])[-1]
                problems.append(f"{p.relative_to(hodpaths.REPO).as_posix()}: import failed: {last}")
        print(f"imported {len(importable)} tools")
    for line in problems:
        print("  " + line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
