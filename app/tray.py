"""
시스템 트레이 아이콘.

"파일자동읽기 폴더지정" 감시가 켜져 있는 동안, 메인 창을 닫아도(X 버튼) 프로그램이 완전히
종료되지 않고 트레이로 내려가 계속 폴더를 감시할 수 있게 해준다. pystray가 설치되어 있지
않으면(예: 개발 환경에 아직 pip install을 안 한 경우) 트레이 없이도 감시 기능 자체는
동작하되, 창을 닫으면 프로그램이 종료된다(watcher도 함께 멈춤).
"""
from __future__ import annotations

try:
    import pystray
    from PIL import Image, ImageDraw
    _HAS_TRAY = True
except Exception:
    _HAS_TRAY = False

APP_TITLE = "중복 사진 정리 도구"


def is_available() -> bool:
    return _HAS_TRAY


def _make_icon_image():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, 61, 61], fill=(47, 125, 209, 255))
    d.rectangle([16, 18, 48, 24], fill=(255, 255, 255, 255))
    d.rectangle([16, 30, 48, 36], fill=(255, 255, 255, 255))
    d.rectangle([16, 42, 40, 48], fill=(255, 255, 255, 255))
    return img


def create_tray_icon(on_show, on_quit):
    """트레이 아이콘 객체를 만들어 반환한다(아직 실행하지 않은 상태). pystray가 없으면 None."""
    if not _HAS_TRAY:
        return None
    return pystray.Icon(
        "PhotoDedup",
        _make_icon_image(),
        f"{APP_TITLE} (자동감시 중)",
        menu=pystray.Menu(
            pystray.MenuItem("창 열기", lambda: on_show()),
            pystray.MenuItem("완전히 종료", lambda: on_quit()),
        ),
    )
