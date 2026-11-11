"""On-disk content-addressed cache for expensive model requests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


class DiskCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    @staticmethod
    def key(payload: Any) -> str:
        packed = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(packed.encode("utf-8")).hexdigest()

    def get(self, payload: Any) -> Any | None:
        path = self.root / f"{self.key(payload)}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return None

    def get_or_create(self, payload: Any, create: Callable[[], Any]) -> tuple[Any, bool]:
        key = self.key(payload)
        path = self.root / f"{key}.json"
        cached = self.get(payload)
        if cached is not None:
            return cached, True
        value = create()
        self.root.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return value, False
