from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def db_path(self) -> Path:
        return self.resolve(self.raw["output"]["database_path"])

    @property
    def draft_dir(self) -> Path:
        return self.resolve(self.raw["output"]["draft_dir"])

    def resolve(self, value: str) -> Path:
        path = Path(value)
        if path.is_absolute():
            return path
        return (self.path.parent / path).resolve()


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as f:
        return AppConfig(raw=json.load(f), path=config_path)


def save_config(config: AppConfig) -> None:
    with config.path.open("w", encoding="utf-8") as f:
        json.dump(config.raw, f, ensure_ascii=False, indent=2)
        f.write("\n")
