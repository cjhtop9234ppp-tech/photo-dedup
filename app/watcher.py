"""
"파일자동읽기 폴더지정" 기능 - 지정한 폴더에 새 zip 파일이 들어오면 자동으로 감지한다.

외부 라이브러리(watchdog 등) 없이, 짧은 주기로 폴더를 다시 스캔하는 방식(폴링)으로 구현한다.
새로 나타난 zip 파일은 파일 크기가 잠깐 사이 변하지 않을 때(=다운로드가 끝났다고 볼 수 있을 때)만
콜백으로 전달한다 - 다운로드 도중인 파일을 성급하게 열어 실패하는 것을 막기 위함이다.

알집(ALZip)의 "폴더 감시 후 자동 압축풀기" 기능이 켜져 있으면 같은 폴더에 zip이 들어올 때
알집도 동시에 압축풀기 진행 창을 띄운다. `close_alzip_windows_soon()`은 제목에 "알집"이 포함된
최상위 창을 찾아 자동으로 닫아 준다(사용자가 매번 직접 닫지 않아도 되도록).
"""
from __future__ import annotations

import ctypes
import os
import threading
import time
from ctypes import wintypes

POLL_INTERVAL_SEC = 2.0
STABLE_CHECK_SEC = 1.5  # 이 시간 동안 파일 크기가 그대로면 다운로드가 끝난 것으로 판단
ALZIP_CLOSE_DURATION_SEC = 8.0  # 새 zip 감지 뒤 이 시간 동안 알집 창이 뜨는지 반복 확인
ALZIP_CLOSE_INTERVAL_SEC = 0.5

_WM_CLOSE = 0x0010
_ALZIP_TITLE_KEYWORDS = ("알집",)

_user32 = ctypes.windll.user32 if os.name == "nt" else None
_EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM) if os.name == "nt" else None


def _get_window_text(hwnd) -> str:
    length = _user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def close_alzip_windows() -> int:
    """제목에 '알집'이 포함된 최상위 창을 찾아 닫는다(WM_CLOSE 전송). 닫은 개수를 반환한다."""
    if _user32 is None:
        return 0
    closed = 0

    def _callback(hwnd, _lparam):
        nonlocal closed
        if not _user32.IsWindowVisible(hwnd):
            return True
        title = _get_window_text(hwnd)
        if title and any(k in title for k in _ALZIP_TITLE_KEYWORDS):
            _user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
            closed += 1
        return True

    _user32.EnumWindows(_EnumWindowsProc(_callback), 0)
    return closed


def close_alzip_windows_soon() -> None:
    """알집이 뒤늦게 압축풀기 창을 띄우는 경우까지 잡기 위해 잠깐 동안 반복해서 닫기를 시도한다."""
    if _user32 is None:
        return

    def _worker():
        end = time.time() + ALZIP_CLOSE_DURATION_SEC
        while time.time() < end:
            close_alzip_windows()
            time.sleep(ALZIP_CLOSE_INTERVAL_SEC)

    threading.Thread(target=_worker, daemon=True).start()


class FolderWatcher(threading.Thread):
    """지정된 폴더를 주기적으로 스캔해 새로 생긴 zip 파일을 콜백으로 전달하는 백그라운드 스레드."""

    def __init__(self, folder: str, on_new_zip):
        super().__init__(daemon=True)
        self.folder = folder
        self.on_new_zip = on_new_zip
        self._stop_event = threading.Event()
        self._seen: set[str] = set()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        # 감시 시작 시점에 이미 폴더에 있던 zip은 대상에서 제외한다(감시를 켜기 전부터 있던
        # 파일까지 전부 자동으로 처리되기 시작하면 안 되므로).
        self._seen = self._list_zip_names()
        while not self._stop_event.is_set():
            try:
                self._scan_once()
            except Exception:
                pass
            self._stop_event.wait(POLL_INTERVAL_SEC)

    def _list_zip_names(self) -> set[str]:
        try:
            return {f for f in os.listdir(self.folder) if f.lower().endswith(".zip")}
        except OSError:
            return set()

    def _scan_once(self) -> None:
        current = self._list_zip_names()
        for name in current - self._seen:
            path = os.path.join(self.folder, name)
            if self._is_stable(path):
                self._seen.add(name)
                close_alzip_windows_soon()
                self.on_new_zip(path)
            # 크기가 아직 안정되지 않았으면(다운로드 진행 중일 가능성) _seen에 넣지 않고
            # 다음 스캔 주기에 다시 확인한다.

    def _is_stable(self, path: str) -> bool:
        try:
            size1 = os.path.getsize(path)
        except OSError:
            return False
        time.sleep(STABLE_CHECK_SEC)
        try:
            size2 = os.path.getsize(path)
        except OSError:
            return False
        return size1 == size2 and size1 > 0
