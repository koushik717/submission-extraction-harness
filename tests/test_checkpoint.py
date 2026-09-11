"""Checkpoint resume behavior."""

from __future__ import annotations

from pathlib import Path

from submission_harness.checkpoint import CheckpointStore


def test_checkpoint_skips_completed(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    assert not store.is_done("a|0")
    store.save_result("a|0", {"doc_id": "a", "value": 1})
    assert store.is_done("a|0")

    store2 = CheckpointStore(tmp_path)
    assert store2.is_done("a|0")
    rows = store2.load_results()
    assert len(rows) == 1
    assert rows[0]["value"] == 1
