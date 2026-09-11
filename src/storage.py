"""Locked, atomic daily persistence with a replayable local transaction."""

from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def colony_lock(data_dir: Path):
    """Use a process lock that the OS releases on crash, without stale lockouts."""
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / ".run_day.lock").open("a+b") as stream:
        stream.seek(0)
        if os.fstat(stream.fileno()).st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another colony run is active") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise RuntimeError("Another colony run is active") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def recover_day(data_dir: Path, output_dir: Path) -> None:
    pending = data_dir / ".pending-day.json"
    if not pending.exists():
        return
    payload = json.loads(pending.read_text(encoding="utf-8"))
    targets = {"history": data_dir / "history.md", "people": data_dir / "people_history.md",
               "html": output_dir / "index.html", "map": output_dir / "colony.svg",
               "state": data_dir / "state.json"}
    if set(payload) != set(targets) or not all(isinstance(v, str) for v in payload.values()):
        raise ValueError("Invalid pending colony transaction")
    state = json.loads(payload["state"])
    if not isinstance(state, dict) or "day" not in state or "last_run_date" not in state:
        raise ValueError("Invalid pending colony state")
    # State is installed last. Replaying replaces full files, never appends twice.
    for key, path in targets.items():
        atomic_write(path, payload[key])
    pending.unlink()


def commit_day(payload: dict[str, str], data_dir: Path, output_dir: Path) -> None:
    atomic_write(data_dir / ".pending-day.json", json.dumps(payload))
    recover_day(data_dir, output_dir)
