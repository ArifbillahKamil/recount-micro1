"""Load credentials from a ``.env`` file at the project root.

Reading only from the shell environment is the safer default, but it is not what
people expect, and an ignored ``.env`` that silently does nothing is worse than
no support at all. So ``.env`` is read, with two rules:

* **The real environment always wins.** A variable already exported in the shell
  is never overwritten by the file, so a one-off ``OPENAI_API_KEY=... python ...``
  behaves the way you would expect.
* **Values are never printed.** Only the path of the file that was loaded and the
  names of the keys it set.

No third-party dependency; this is a deliberately small parser covering the
subset of ``.env`` syntax that matters here.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

FILENAME = ".env"
MARKERS = ("recount", "run_all.py")


def project_root(start: Optional[Path] = None) -> Path:
    """Walk upward looking for the project root, falling back to ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if all((candidate / marker).exists() for marker in MARKERS):
            return candidate
    return here


def find(start: Optional[Path] = None) -> Optional[Path]:
    """Locate a ``.env`` in the working directory, its parents, or the root."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        path = candidate / FILENAME
        if path.is_file():
            return path
    fallback = project_root(start) / FILENAME
    return fallback if fallback.is_file() else None


def parse(text: str) -> dict:
    """Parse ``KEY=VALUE`` lines, tolerating comments, blanks and ``export``."""
    values: dict = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.lower().startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        # Strip one matching pair of surrounding quotes.
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        else:
            # Only an unquoted value can carry a trailing inline comment.
            hash_at = value.find(" #")
            if hash_at != -1:
                value = value[:hash_at].rstrip()
        values[key] = value
    return values


def load(start: Optional[Path] = None, verbose: bool = True) -> Optional[Path]:
    """Populate ``os.environ`` from ``.env``. Returns the file used, if any."""
    path = find(start)
    if path is None:
        return None
    try:
        values = parse(path.read_text(encoding="utf-8"))
    except OSError:
        return None

    applied = []
    for key, value in values.items():
        if os.environ.get(key):
            continue  # the shell wins
        os.environ[key] = value
        applied.append(key)

    if verbose and applied:
        # Names only. Never the values.
        print(f"loaded {', '.join(sorted(applied))} from {path}")
    return path
