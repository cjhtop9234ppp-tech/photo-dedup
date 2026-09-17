"""
"이미지 도구 선택" - 결과 폴더를 열 때 쓸 이미지 뷰어 프로그램을 찾아 목록으로 보여준다.

Windows에는 "설치된 모든 뷰어 프로그램" 목록을 한 번에 안전하게 가져오는 API가 없다.
대신 실제 이 PC에서 확인되는 두 가지 근거를 사용한다:

1. 사진 확장자(.jpg/.jpeg/.png)의 기본 연결 프로그램과, 탐색기 "다른 앱으로 열기"에
   등록된 적 있는 프로그램들(`HKCR\\.jpg\\OpenWithProgids` 등)을 레지스트리에서 찾아
   실행 경로까지 확인한다.
2. FastStone Image Viewer는 `app/gui.py`의 `find_faststone_exe()`가 이미 흔한 설치
   경로 + App Paths 레지스트리로 찾고 있으므로 그 결과도 항상 후보에 포함한다.

이 방식으로도 못 찾는 프로그램(예: 설치 프로그램 없이 폴더에 풀어서 쓰는 프로그램)은
목록에 자동으로 뜨지 않을 수 있다 - 이런 경우를 위해 GUI 쪽에 "찾아보기..."로 직접
실행파일(.exe)을 고르는 방법을 항상 함께 제공한다.
"""
from __future__ import annotations

import os
import sys

_IMAGE_EXTS = (".jpg", ".jpeg", ".png")


def _parse_command_exe(command: str) -> str | None:
    """`"C:\\Program Files\\App\\app.exe" "%1"` 형태의 레지스트리 명령 문자열에서
    실행파일 경로만 뽑아낸다."""
    command = command.strip()
    if not command:
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        exe = command[1:end] if end != -1 else command[1:]
    else:
        exe = command.split(" ", 1)[0]
    return exe if exe else None


def _resolve_progid_exe(progid: str) -> str | None:
    if sys.platform != "win32":
        return None
    import winreg
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{progid}\\shell\\open\\command")
        command, _ = winreg.QueryValueEx(key, "")
    except OSError:
        return None
    exe = _parse_command_exe(command)
    if exe and os.path.isfile(exe):
        return exe
    return None


def _candidate_progids_for_ext(ext: str) -> list[str]:
    """이 확장자의 기본 연결 프로그램 + "다른 앱으로 열기" 후보 ProgId 목록."""
    if sys.platform != "win32":
        return []
    import winreg
    progids: list[str] = []
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext)
        default_progid, _ = winreg.QueryValueEx(key, "")
        if default_progid:
            progids.append(default_progid)
    except OSError:
        pass
    try:
        key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{ext}\\OpenWithProgids")
        i = 0
        while True:
            try:
                name, _, _ = winreg.EnumValue(key, i)
            except OSError:
                break
            i += 1
            # AppX(스토어 앱)는 exe 경로로 바로 실행할 수 없어 대상에서 제외한다.
            if name and not name.startswith("AppX"):
                progids.append(name)
    except OSError:
        pass
    return progids


def _friendly_label(progid: str, exe_path: str) -> str:
    name = progid
    for suffix in (".jpg", ".jpeg", ".png"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    name = name.strip(". ")
    # "Hocr.Document.jpg.120"처럼 점이 남아있는 ProgId는 사람이 보기 불편하므로,
    # 실행파일 이름을 대신 표시 이름으로 쓴다.
    if not name or "." in name:
        name = os.path.splitext(os.path.basename(exe_path))[0]
    return name


def detect_viewers() -> list[tuple[str, str]]:
    """(표시 이름, 실행파일 경로) 목록을 돌려준다. 같은 실행파일은 한 번만 포함한다."""
    if sys.platform != "win32":
        return []

    seen_paths: set[str] = set()
    results: list[tuple[str, str]] = []

    for ext in _IMAGE_EXTS:
        for progid in _candidate_progids_for_ext(ext):
            exe = _resolve_progid_exe(progid)
            if not exe:
                continue
            key = os.path.normcase(exe)
            if key in seen_paths:
                continue
            seen_paths.add(key)
            results.append((_friendly_label(progid, exe), exe))

    return results
