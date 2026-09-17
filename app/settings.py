"""
사용자 설정 저장/불러오기.

"파일자동읽기 폴더지정"(다운로드 폴더 자동 감시)과 "이미지 도구 선택"(결과 폴더를 열 때 쓸
프로그램) 설정을 저장한다. %APPDATA%\\PhotoDedup\\config.json 에 저장하며, 프로그램 자체
설치 위치(Program Files 등)에는 쓰기 권한이 없을 수 있어 반드시 사용자별 쓰기 가능
폴더(APPDATA)를 사용한다.
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
    "viewer_path": "",  # 비어있으면 기존 동작(FastStone 자동 감지 → 없으면 탐색기) 그대로
    "viewer_label": "",
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
    """넘겨받은 키만 갱신하고 나머지 기존 설정은 그대로 유지한다.

    예전에는 DEFAULTS 위에만 덮어써서, 예를 들어 뷰어 설정만 저장해도 감시 설정이
    기본값으로 초기화돼버리는 문제가 있었다 - 반드시 "지금 저장된 값" 위에 덮어써야 한다.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    merged = {**load_settings(), **settings}
    CONFIG_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
