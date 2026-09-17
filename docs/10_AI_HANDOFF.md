# 10. AI HANDOFF

> Codex / Claude Code / ChatGPT 등 다른 AI가 이 프로젝트를 처음 넘겨받았을 때 **가장 먼저 읽어야
> 할 문서**입니다. 모든 내용은 실제 코드/저장소 상태 확인 기준입니다.

## 프로그램 목적

zip으로 압축된 사진 묶음에서 **내용이 같거나 사실상 같은 중복 사진**을 자동으로 찾아, 각 중복
그룹에서 zip 내부 최초 등장 사진 1장만 남기고 바탕화면에 결과 폴더를 만드는 Windows 데스크톱
프로그램. 정리 후에는 사람이 큰 화면에서 사진 순서를 직접 재배치하고 확정할 수 있습니다.

## 현재 상태

| 항목 | 상태 |
|---|---|
| 기능 개발 | 완료, 실사용 중 |
| exe / 설치 프로그램 | 완료, 정상 빌드/설치 확인됨 |
| GitHub 저장소 | **완료** — `https://github.com/cjhtop9234ppp-tech/photo-dedup` (Private, branch: `master`) |
| GitHub Release | **완료** — `v1.0.0`, 설치 파일 Asset 등록됨 |
| README / LICENSE | 완료 (MIT) |
| 자동화 테스트(CI) | 없음 |
| 알려진 미완성 항목 | [[09_향후개발_TODO]] A항목 참고 |

## 절대 변경하면 안 되는 부분 (`DO_NOT_BREAK`)

```text
1. app/core.py의 process_zips() 안 `if groups:` 가드
   — 없으면 zip이 아닌 파일을 넣었을 때 빈 결과 폴더가 다시 생성되는 버그가 재발함

2. app/gui.py의 OrderEditor._confirm() 2단계 임시이름 리네임
   — 한 번에 바로 최종이름으로 바꾸면 순서가 꼬일 때 파일명 충돌 가능

3. send2trash() 사용 유지
   — os.remove()/shutil.rmtree()로 바꾸면 복구 불가능한 완전삭제가 됨

4. app/core.py의 PhotoItem을 @dataclass(eq=False)로 유지
   — eq=True로 바꾸면 GUI의 set() 기반 선택 로직이 TypeError(unhashable type)로 깨짐

5. installer.iss의 AppId({8F1E9C2E-7B3A-4C5D-9E1F-2A6B8C4D7E10}) 변경 금지
   — 바꾸면 기존 설치본 위에 업데이트되지 않고 별도 프로그램으로 인식됨

6. installer.iss [Registry] 섹션이 HKCR\.zip(zip 기본 연결 프로그램) 자체는
   건드리지 않는 구조를 유지할 것 — 사용자의 기존 zip 프로그램 기본 설정을 침해하면 안 됨

7. "최종 결과폴더로 보내기" 확정 단계는 사람이 직접 눌러야 하는 구조를 유지할 것
   — 자동 실행 모드도 이 단계만큼은 자동화하지 않는 것이 이 프로젝트의 핵심 설계 원칙

8. (v1.1.0부터) "파일자동읽기 폴더지정"(감시 폴더 자동 처리) 기능도 위 7번 원칙을 그대로
   따른다 — app/watcher.py가 감시 폴더에서 새 zip을 감지해 app/gui.py의 run_auto()를
   자동 호출하지만, run_auto()는 항상 OrderEditor를 띄운 채로 멈추고 "최종 결과폴더로
   보내기"는 여전히 사람이 직접 눌러야 한다. 이 흐름을 자동화하는 방향으로 바꾸지 말 것

9. app/watcher.py의 close_alzip_windows()는 창 제목에 "알집"이 포함된 창만 닫는다 —
   이 키워드 매칭 범위를 넓히면(예: 아무 zip 관련 창이나 닫기) 사용자가 보고 있던 다른
   무관한 창을 실수로 닫을 위험이 있으므로, 반드시 특정 프로그램 이름으로 좁게 유지할 것

10. app/startup.py는 HKCU(현재 사용자)의 Run 키에만 값을 쓴다 — HKLM(시스템 전체)로
    바꾸면 관리자 권한이 필요해지고 다른 계정에도 영향을 주게 되므로 바꾸지 말 것

11. (v1.1.1부터) main.py의 `_launch_gui()`는 GUI를 띄우기 전에 반드시
    `app/singleinstance.py`의 `try_acquire()`로 "이미 실행 중인 인스턴스가 있는지"를 먼저
    확인한다 — 이 확인을 건너뛰면, 감시가 켜진 채로 트레이에 프로그램이 떠 있는 상태에서
    zip을 또 열었을 때 창이 2개 뜨고 두 프로세스가 같은 결과 폴더에 동시에 쓰려다 부딪히는
    버그(v1.1.0에서 실제 발생)가 재발한다

12. (v1.1.2부터) app/gui.py의 `_handle_watched_zip()`(감시 폴더에서 자동 감지한 경우)는
    `run_auto(..., silent=True)`를 호출해서 창을 띄우지 않고 조용히 처리해야 한다 —
    반대로 `_handle_external_request()`(사람이 바탕화면 아이콘/트레이 아이콘을 더블클릭했거나
    탐색기에서 zip을 직접 열려고 한 경우)는 `silent=False`로 창을 보여줘야 한다. 이 둘을
    바꾸면 "다운로드할 때마다 창이 튀어나온다"는 문제가 재발하거나, 반대로 사람이 직접 연
    zip인데도 아무 반응이 없는 것처럼 보이는 문제가 생긴다

13. (v1.1.3부터) app/watcher.py의 `FolderWatcher`는 파일명이 아니라 **수정시각(mtime)**으로
    "새 파일인지"를 판단한다 — 파일명만 보고 판단하면(v1.1.2까지의 방식) 브라우저가 같은
    파일명으로 재다운로드(덮어쓰기)했을 때 "이미 본 파일"로 착각해 영원히 무시해버리는 버그가
    재발한다. 다시 파일명 기준(`set[str]`)으로 되돌리지 말 것

14. (v1.1.4부터) OrderEditor._confirm()이 성공적으로 끝나면 "완료했습니다" 안내 팝업을
    띄우지 않는다 — 사용자가 명시적으로 요청한 사항으로, 확정 이후에는 FastStone(사진편집기)
    창만 화면에 남기고 메인 창은 트레이 아이콘이 있으면 다시 숨긴다(`_hide_to_tray_if_active`).
    단, 사진/zip 삭제가 일부 실패한 경우의 경고 팝업(`messagebox.showwarning`)은 그대로 유지할
    것 - 이건 사람이 반드시 알아야 하는 예외 상황이다. "확정 전 계속할까요?" 확인 팝업
    (`messagebox.askyesno`)도 그대로 유지할 것 - 파일명 변경/zip 삭제 전 마지막 안전장치다

15. (v1.1.5부터) `run_auto(..., silent=True)`(감시 폴더 자동 감지)여도 `_auto_open_order_editor`는
    항상 True로 유지해서 순서 정리 창(OrderEditor)은 자동으로 연다 — silent가 숨기는 대상은
    "중복 사진 정리 도구" 메인 창(`root.deiconify()`를 건너뜀)뿐이다. 이 둘을 다시 하나로
    묶어서(silent=True일 때 OrderEditor까지 숨기는 방향으로) 되돌리지 말 것

16. (v1.1.5부터) `_on_edit_order()`에서 OrderEditor를 생성하기 직전/직후로
    `root.deiconify()` / `root.withdraw()`를 감싸는 코드(`was_hidden` 처리)를 지우지 말 것 —
    메인 창이 완전히 숨겨진(withdrawn) 상태에서 곧바로 최대화 Toplevel(OrderEditor)을 열면
    Windows가 그 창을 (owner가 숨겨져 있다는 이유로) **최소화된 상태로** 띄워버려서 화면에
    전혀 안 보이는 실제 버그가 있었다(`GetWindowRect`가 `-32000,-32000` 같은 최소화 전용
    좌표를 반환하는 것으로 확인됨). 메인 창을 아주 잠깐 보통 상태로 되돌렸다가 바로 다시
    숨기는 이 우회책이 그 문제를 해결한다 - 화면에는 메인 창이 보일 틈 없이 순서 정리
    창만 나타난다

17. (v1.1.6부터) `app/gui.py`의 `_add_zip_paths()`(모든 zip 경로가 `self.zip_paths`에
    들어가는 유일한 통로), `_on_save_watch_settings()`/`_maybe_resume_watch()`(감시 폴더
    경로), `OrderEditor._confirm()`의 `send2trash()` 호출 직전, `app/watcher.py`의
    `FolderWatcher.__init__` — 이 네 곳 모두 경로에 `os.path.normpath()`를 적용해야 한다.
    `filedialog.askdirectory()`(감시 폴더 "찾아보기...")는 Windows에서도 슬래시(`/`)가 섞인
    경로를 돌려줄 때가 있는데, 이 경로를 그대로 `os.path.join()`에 쓰면 `"C:/Users/..\\file.zip"`
    처럼 슬래시가 섞인 경로가 만들어지고, `send2trash()`의 Windows 레거시 백엔드가 이런
    경로에서는 파일이 실제로 있어도 `[Errno 3] 지정된 경로를 찾을 수 없습니다` 오류를 내며
    zip 삭제에 실패한다(실사용 중 실제 발생 확인). 이 정규화를 하나라도 제거하면 재발한다

18. (v1.1.7부터) `app/watcher.py`의 `FolderWatcher`, `app/singleinstance.py`의
    `PendingRequestWatcher`는 백그라운드 스레드에서 실행되는데, 이 스레드들의 콜백
    (`_on_watcher_new_zip`, `_on_external_request`)은 절대 `root.after()`나 다른 tkinter
    위젯을 직접 호출하면 안 되고, `self._watcher_events` 큐(`queue.Queue`)에 이벤트를
    넣기만 해야 한다 - 실제 위젯 조작은 메인 루프에서 주기적으로 도는
    `_poll_watcher_events()`가 큐를 비우면서 처리한다. tkinter는 스레드 안전하지 않아서
    백그라운드 스레드가 `root.after()`를 직접 반복 호출하면 오래 켜둘수록(며칠 단위 감시)
    이벤트가 조용히 씹히거나 감시가 멈춘 것처럼 보이는 문제가 있었다(실사용 중 발견 -
    18시간 이상 켜둔 뒤 새 zip을 감지하지 못함). 처리 스레드(`worker_thread`)가 이미 쓰고
    있던 `self.progress_queue` + `_poll_queue()` 패턴과 반드시 동일하게 유지할 것

19. (v1.1.7부터) `_start_watch_internal()`이 예약하는 `_check_watcher_alive()`(60초마다
    `FolderWatcher.is_alive()` 확인 후 죽어 있으면 같은 폴더로 재시작)를 지우지 말 것 -
    18번 항목의 근본 원인을 완전히 배제할 수 없으므로, 감시 스레드가 어떤 이유로든 멈추더라도
    최대 60초 안에 스스로 복구되게 하는 마지막 안전장치다
```

## 주요 파일

| 파일 | 역할 |
|---|---|
| `main.py` | 진입점, 실행모드 분기 |
| `app/core.py` | 핵심 로직 (`process_zips()`가 전체 진입점) |
| `app/gui.py` | GUI 전체 (`DedupApp`, `OrderEditor`) |
| `app/cli.py` | CLI |
| `app/singleinstance.py` | 중복 실행 방지 (Windows 명명된 뮤텍스) + 이미 실행 중인 인스턴스로 zip 열기 요청 전달 |
| `app/settings.py` | "파일자동읽기 폴더지정" 설정 저장/불러오기 (`%APPDATA%\PhotoDedup\config.json`) |
| `app/watcher.py` | 감시 폴더 폴링(`FolderWatcher`) + 알집 창 자동 닫기(`close_alzip_windows`) |
| `app/startup.py` | Windows 로그인 시 자동 실행 등록/해제 (`HKCU\...\Run`) |
| `app/tray.py` | 시스템 트레이 아이콘(pystray) |
| `installer.iss` | 설치 프로그램 정의 |
| `README.md` | 사용자용 설명서(GitHub 저장소 첫 화면) |
| `REPRODUCTION_GUIDE.md` | 전체 소스 원문 포함 재현 가이드 |

## 실행 방법

```bash
git clone https://github.com/cjhtop9234ppp-tech/photo-dedup.git
cd photo-dedup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py              # GUI
python main.py photos.zip --threshold 8 --rotate-flip   # CLI
```

## 테스트 방법

`REPRODUCTION_GUIDE.md`(저장소 루트) 8번 섹션에 실제 테스트 zip 생성 스크립트와 기대 출력값이
있습니다. 핵심 확인 포인트:

1. 완전동일 2장 + 재압축 1장 + 고유 2장 + 비이미지 1개 + 손상이미지 1개가 섞인 zip 처리 시
   "전체 6 / 고유 3 / 제거 2 / 읽기실패 1"이 정확히 나오는지
2. zip이 아닌 파일을 넣었을 때 바탕화면에 아무 폴더도 생성되지 않는지
3. GUI에서 순서 편집 → 확정 시 파일명 순번이 부여되고 원본 zip이 휴지통으로 가는지

## 수정 후 반드시 검증할 사항

```text
□ 위 DO_NOT_BREAK 7가지가 여전히 지켜지는지
□ 테스트 zip으로 CLI 실행 시 기대 개수가 그대로 나오는지 (회귀 테스트)
□ GUI가 오류 없이 뜨고, 처리~순서편집~확정까지 한 번은 실제로 눌러서 확인
□ exe 빌드가 정상적으로 되는지 (pyinstaller 명령 실행, 콘솔 없이 GUI만 뜨는지)
□ 설치 프로그램을 만들었다면, 격리된 폴더에 //VERYSILENT로 설치 → 제거까지 재확인
□ 소스코드에 특정 PC 사용자명/절대경로가 새로 하드코딩되지 않았는지 (grep으로 확인)
□ requirements.txt에 새 의존성을 추가했다면 README/REPRODUCTION_GUIDE.md도 함께 갱신
□ 변경사항을 git commit 하기 전, 민감정보(API키/비밀번호/개인정보) 포함 여부 재확인
```

## 관련 문서
- [[05_오류_및_해결이력]]
- [[06_유지보수_가이드]]
- [[11_SKILL_역분석_MASTER]]
