"""
사용자 설정 저장/불러오기.

현재는 "파일자동읽기 폴더지정"(다운로드 폴더 자동 감시) 설정 하나만 저장한다.
%APPDATA%\\PhotoDedup\\config.json 에 저장하며, 프로그램 자체 설치 위치(Program Files 등)에는
쓰기 권한이 없을 수 있어 반드시 사용자별 쓰기 가능 폴더(APPDATA)를 사용한다.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "PhotoDedup"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "watch_folder": "",
    "watch_enabled": False,
}


def load_settings() -> dict:
    if CONFIG_FILE.is_file():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {**DEFAULTS, **data}
        except Exception:
            pass
    return dict(DEFAULTS)


def save_settings(settings: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = {**DEFAULTS, **settings}
    CONFIG_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
