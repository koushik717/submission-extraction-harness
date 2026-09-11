"""Crash-safe experiment checkpointing."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


class CheckpointStore:
    """JSONL + state.json checkpoint under a run directory."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.results_path = self.run_dir / "results.jsonl"
        self._done: set[str] = set()
        self._state: dict[str, Any] = {"completed_keys": [], "meta": {}}
        if self.state_path.exists():
            self._state = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._done = set(self._state.get("completed_keys", []))

    def is_done(self, key: str) -> bool:
        return key in self._done

    def save_result(self, key: str, payload: dict[str, Any]) -> None:
        record = {"key": key, **payload}
        with self.results_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=_json_default) + "\n")
        self._done.add(key)
        self._state["completed_keys"] = sorted(self._done)
        self.state_path.write_text(
            json.dumps(self._state, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )

    def update_meta(self, **kwargs: Any) -> None:
        self._state.setdefault("meta", {}).update(kwargs)
        self.state_path.write_text(
            json.dumps(self._state, indent=2, default=_json_default) + "\n",
            encoding="utf-8",
        )

    def load_results(self) -> list[dict[str, Any]]:
        if not self.results_path.exists():
            return []
        rows = []
        for line in self.results_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)
