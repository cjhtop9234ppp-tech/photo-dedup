"""
프로그램이 이미 실행 중일 때, 창을 하나 더 띄우는 대신 이미 떠 있는 창에 요청만 넘겨준다.

배경: "파일자동읽기 폴더지정"으로 감시를 켜두면 트레이에 프로그램이 계속 떠 있는 상태가 되는데,
이 상태에서 사람이 zip 파일을 탐색기에서 다시 열거나(우클릭 "열기"), 프로그램을 한 번 더
실행하면 완전히 별개인 두 번째 프로세스가 새로 생겨서 - 창이 2개 뜨고, 각자 독립적으로 같은
zip을 처리하려다 서로 부딪히는(같은 결과 폴더에 동시에 쓰기 등) 문제가 있었다. Windows 명명된
뮤텍스(Mutex)로 "이미 실행 중인 인스턴스가 있는지"를 확인해서 이 문제를 막는다.
"""
from __future__ import annotations

import ctypes
import json
import os
import threading
from ctypes import wintypes

from . import settings as app_settings

POLL_INTERVAL_SEC = 1.5

_MUTEX_NAME = "PhotoDedup_SingleInstance_Mutex"
_ERROR_ALREADY_EXISTS = 183
_PENDING_FILE = app_settings.CONFIG_DIR / "pending_zips.json"

_mutex_handle = None  # 뮤텍스를 계속 들고 있어야(참조 유지) 프로세스가 끝날 때까지 살아있다


def try_acquire() -> bool:
    """이 프로세스가 유일한 실행 중 인스턴스가 될 수 있으면 True, 이미 다른 인스턴스가 있으면 False."""
    global _mutex_handle
    if os.name != "nt":
        return True

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.GetLastError.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    handle = kernel32.CreateMutexW(None, False, _MUTEX_NAME)
    already_running = kernel32.GetLastError() == _ERROR_ALREADY_EXISTS
    if already_running:
        if handle:
            kernel32.CloseHandle(handle)
        return False

    _mutex_handle = handle  # GC/해제 방지용으로 계속 들고 있는다
    return True


def request_open_in_running_instance(zip_paths: list[str]) -> None:
    """이미 다른 인스턴스가 실행 중일 때, 그 인스턴스에게 이 zip들을 대신 열어달라고(또는 창만
    앞으로 가져와 달라고) 요청한다. zip_paths가 비어 있어도(단순 재실행) 창을 띄워달라는 뜻이다."""
    app_settings.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    existing: list[str] = []
    if _PENDING_FILE.is_file():
        try:
            existing = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except Exception:
            existing = []
    existing.extend(zip_paths)
    _PENDING_FILE.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")


def take_pending_requests() -> list[str]:
    """대기 중인 요청(zip 경로 목록, 비어 있을 수도 있음)을 읽고 파일을 지운다.

    실행 중인 인스턴스가 주기적으로 호출해서 새로 들어온 요청이 있는지 확인하는 용도.
    반환값이 빈 리스트여도 파일 자체가 있었다면 "창을 열어달라"는 요청으로 취급해야 한다.
    이 함수는 파일이 있었는지 여부를 (had_request, zip_paths) 형태로 알려준다.
    """
    if not _PENDING_FILE.is_file():
        return None
    try:
        data = json.loads(_PENDING_FILE.read_text(encoding="utf-8"))
        paths = [p for p in data if isinstance(p, str)] if isinstance(data, list) else []
    except Exception:
        paths = []
    try:
        _PENDING_FILE.unlink()
    except OSError:
        pass
    return paths


class PendingRequestWatcher(threading.Thread):
    """실행 중인(유일한) 인스턴스에서, 나중에 또 실행하려다 넘겨받은 요청이 있는지 주기적으로 확인한다."""

    def __init__(self, on_request):
        super().__init__(daemon=True)
        self.on_request = on_request  # on_request(zip_paths: list[str]) - 빈 리스트면 "창만 보여줘" 요청
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.is_set():
            paths = take_pending_requests()
            if paths is not None:
                self.on_request(paths)
            self._stop_event.wait(POLL_INTERVAL_SEC)
