"""
Windows 로그인 시 자동 실행 등록/해제.

HKCU(현재 사용자)의 Run 키에만 값을 쓴다 - 관리자 권한이 필요 없고, 시스템 전체(HKLM)가
아닌 이 계정에만 영향을 준다. "파일자동읽기 폴더지정"을 저장/해제할 때만 호출된다.
"""
from __future__ import annotations

import sys

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE_NAME = "PhotoDedup"


def _startup_command() -> str:
    if getattr(sys, "frozen", False):
        # PyInstaller로 빌드된 exe: 그 exe 자신을 --tray로 실행
        return f'"{sys.executable}" --tray'
    # 개발 환경(python main.py)에서 테스트할 때
    from pathlib import Path
    main_py = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{sys.executable}" "{main_py}" --tray'


def enable_startup() -> None:
    if sys.platform != "win32":
        return
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
        winreg.SetValueEx(key, _RUN_VALUE_NAME, 0, winreg.REG_SZ, _startup_command())


def disable_startup() -> None:
    if sys.platform != "win32":
        return
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, _RUN_VALUE_NAME)
    except FileNotFoundError:
        pass
