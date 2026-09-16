"""
중복 사진 정리 도구 - 진입점

- 인자 없이 실행: GUI 실행 (exe 더블클릭 시 기본 동작)
- zip 파일 경로를 인자로 실행: GUI를 "자동 실행" 모드로 띄움
  (탐색기에서 zip을 우클릭 → "중복 사진 정리 도구로 열기"를 선택했을 때, 또는 zip을
   exe/바로가기 위로 드래그했을 때 Windows가 이 방식으로 프로그램을 실행한다)
  → 파일 목록에 그 zip이 자동으로 채워지고, "처리 시작"과 "결과 폴더 열기"까지 자동으로 진행된다.
  (최종 "최종 결과폴더로 보내기" 확정만은 사람이 직접 눌러야 한다 - 순서 확인 없이 파일명이
  바뀌거나 원본 zip이 휴지통으로 가는 일을 막기 위함)
- "--tray": "파일자동읽기 폴더지정"에서 저장한 감시를 Windows 시작 시 자동으로 재개하기 위한
  모드. 창을 띄우지 않고 트레이 아이콘 + 폴더 감시만 시작한다(GUI에서 감시를 켤 때 이 옵션과
  함께 자기 자신을 Windows 시작프로그램으로 등록한다).
- "-"로 시작하는 다른 옵션과 함께 실행: 콘솔(CLI) 모드 (예: main.exe photos.zip --threshold 8)
"""
import sys


def main():
    args = sys.argv[1:]

    if args and not args[0].startswith("-"):
        zip_paths = [a for a in args if a.lower().endswith(".zip")]
        if zip_paths:
            from app.gui import main as gui_main
            gui_main(auto_zip_paths=zip_paths)
            return

    if args and args[0] == "--tray":
        from app.gui import main as gui_main
        gui_main(start_hidden=True)
        return

    if args:
        from app.cli import main as cli_main
        sys.exit(cli_main(args))
    else:
        from app.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
