"""Engine version and deterministic fingerprint (SPEC-40 / SPEC-41)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Union

ENGINE_VERSION = "0.40.0"

_FINGERPRINT_CACHE: dict[str, str] = {}


def engine_fingerprint(root_dir: Union[str, Path, None] = None) -> str:
    """sha256 hex of the bytes, in sorted path order, of:
    dora/engine.py, dora/scenario.py, dora/tools.py, dora/plan_check.py
    and every file under dora/data/.
    Normalises \\r\\n -> \\n so Windows and Linux produce the exact same hash.
    Caches the result per root_dir.
    """
    if root_dir is None:
        base = Path(__file__).resolve().parent.parent
    else:
        base = Path(root_dir).resolve()

    cache_key = str(base)
    if cache_key in _FINGERPRINT_CACHE:
        return _FINGERPRINT_CACHE[cache_key]

    fixed_files = [
        Path("dora") / "engine.py",
        Path("dora") / "scenario.py",
        Path("dora") / "tools.py",
        Path("dora") / "plan_check.py",
    ]

    data_dir = base / "dora" / "data"
    data_files = []
    if data_dir.exists():
        for p in data_dir.rglob("*"):
            if p.is_file():
                rel = p.relative_to(base)
                data_files.append(rel)

    all_rel_paths = sorted(fixed_files + data_files, key=lambda p: p.as_posix())

    hasher = hashlib.sha256()
    for rel in all_rel_paths:
        full_path = base / rel
        if full_path.exists() and full_path.is_file():
            raw = full_path.read_bytes()
            norm = raw.replace(b"\r\n", b"\n")
            hasher.update(norm)

    digest = hasher.hexdigest()
    _FINGERPRINT_CACHE[cache_key] = digest
    return digest
