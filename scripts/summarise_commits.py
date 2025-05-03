#!/usr/bin/env python3
"""
summarise_commits.py – Generate a high-level summary of the last N days of git
activity (default 14).

Usage examples
--------------
# Analyse current repository for the last 2 weeks
python scripts/summarise_commits.py

# Analyse another repo for the last 30 days
python scripts/summarise_commits.py /path/to/repo 30
"""
from __future__ import annotations

import collections
import datetime as _dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Tuple


class GitError(RuntimeError):
    """Raised when an underlying git command fails."""


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside *repo* and return stdout (stripped)."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(repo), *args],
            stderr=subprocess.STDOUT,
            text=True,
        )
        return out.rstrip("\n")
    except subprocess.CalledProcessError as exc:
        raise GitError(f"git {' '.join(args)} failed:\n{exc.output}") from exc


def _collect_commits(repo: Path, since: _dt.datetime) -> List[Dict]:
    """Return basic metadata for commits newer than *since*."""
    fmt = "%H|%ad|%an|%s"
    raw = _git(
        repo,
        "log",
        f"--since={since.isoformat()}",
        f"--pretty=format:{fmt}",
        "--date=short",
    )
    commits: List[Dict] = []
    for line in raw.splitlines():
        sha, date, author, subject = line.split("|", 3)
        commits.append(
            {"sha": sha, "date": date, "author": author, "subject": subject}
        )
    return commits


def _commit_stats(repo: Path, sha: str) -> Dict:
    """Return insertions, deletions and per-file stats for a commit."""
    numstat = _git(repo, "show", "--numstat", "--format=", sha)
    ins = dels = 0
    files: Dict[str, Tuple[int, int]] = {}
    for ln in numstat.splitlines():
        a, d, f = ln.split("\t")
        add = int(a) if a != "-" else 0
        rem = int(d) if d != "-" else 0
        ins += add
        dels += rem
        files[f] = (add, rem)
    return {"insertions": ins, "deletions": dels, "files": files}


def _aggregate(repo: Path, commits: List[Dict]) -> Dict:
    authors, dirs, files = (collections.Counter() for _ in range(3))
    totals = {"insertions": 0, "deletions": 0}
    new_files, deleted_files = set(), set()

    for c in commits:
        authors[c["author"]] += 1
        stats = _commit_stats(repo, c["sha"])
        totals["insertions"] += stats["insertions"]
        totals["deletions"] += stats["deletions"]

        for path, (add, rem) in stats["files"].items():
            files[path] += add + rem
            topdir = path.split("/", 1)[0] if "/" in path else path
            dirs[topdir] += add + rem

        for ln in _git(repo, "show", "--pretty=format:", "--name-status", c["sha"]).splitlines():
            status, path = ln.split("\t", 1)
            if status == "A":
                new_files.add(path)
            elif status == "D":
                deleted_files.add(path)

    return {
        "commit_count": len(commits),
        "authors": authors.most_common(5),
        "top_dirs": dirs.most_common(8),
        "top_files": files.most_common(10),
        "totals": totals,
        "new_files": sorted(new_files)[:10],
        "deleted_files": sorted(deleted_files)[:10],
    }


def _format_markdown(summary: Dict, commits: List[Dict], days: int) -> str:
    md: List[str] = []
    md.append(f"### 📝 Commit activity (last {days} days)")
    md.append("")
    md.append(f"- {summary['commit_count']} commits "
              f"({summary['totals']['insertions']} ++ / {summary['totals']['deletions']} --)")
    md.append("")
    md.append("**Top authors**")
    md += [f"- {a} ({n})" for a, n in summary["authors"]]
    md.append("")
    md.append("**Most-touched directories**")
    md += [f"- {d:<20} {n}" for d, n in summary["top_dirs"]]
    md.append("")
    md.append("**Most-touched files**")
    md += [f"- {f:<40} {n}" for f, n in summary["top_files"]]
    if summary["new_files"]:
        md.append("\n**New files (sample)**")
        md += [f"- {p}" for p in summary["new_files"]]
    if summary["deleted_files"]:
        md.append("\n**Deleted files (sample)**")
        md += [f"- {p}" for p in summary["deleted_files"]]
    md.append("\n**Recent commit subjects**")
    md += [f"- {c['date']} {c['subject']} ({c['sha'][:7]})" for c in commits[:10]]
    return "\n".join(md)


def main() -> None:
    repo_path = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 14
    since = _dt.datetime.now() - _dt.timedelta(days=days)

    commits = _collect_commits(repo_path, since)
    summary = _aggregate(repo_path, commits)

    print(_format_markdown(summary, commits, days))
    print("\n---\nRaw JSON (for scripting):\n")
    print(json.dumps({"summary": summary, "commits": commits}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except GitError as err:
        sys.stderr.write(str(err) + "\n")
        sys.exit(1)
