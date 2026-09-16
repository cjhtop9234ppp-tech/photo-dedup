# PhotoDedup (중복 사진 정리 도구) — 프로젝트 재현 가이드

이 문서 하나만 보고 새 Windows PC에서 프로젝트를 처음부터 끝까지 그대로 재현할 수 있도록,
목적/구조/의존성/설정/실행 순서/전체 소스코드/검증 방법/트러블슈팅을 빠짐없이 기록합니다.
아래 소스코드는 요약이 아니라 실제 완성본 파일의 전체 내용입니다.

---

## 1. 프로젝트 개요

### 목적
zip으로 압축된 사진 묶음에서 **내용이 동일하거나 사실상 같은 중복 사진**을 자동으로 찾아,
각 중복 그룹에서 **압축파일 내 순서상 가장 먼저 등장한 사진 1장만** 남기고 **바탕화면(Desktop)에
결과 폴더 하나만** 만들어주는 Windows 데스크톱 프로그램입니다. 파일명이 아니라 사진 "내용"으로
판별하며, 결과 폴더에 모인 고유 사진들은 그리드 화면에서 사람이 직접 순서를 정리한 뒤 확정할 수
있습니다.

### 사용 기술 스택
| 구분 | 사용 기술 | 비고 |
|---|---|---|
| 언어 | Python 3.11 | 개발/테스트에 사용한 정확한 버전: **3.11.15** |
| GUI | tkinter (표준 라이브러리) + `tkinterdnd2` | 드래그앤드롭 지원을 위해 tkinterdnd2 사용 |
| 이미지 처리 | `Pillow` | 이미지 열기/썸네일/EXIF 처리 |
| 중복 판별 | `hashlib`(표준 라이브러리, SHA-256) + `imagehash`(pHash) | 정확 일치 + 유사 일치 이중 판별 |
| 휴지통 이동 | `Send2Trash` | 원본 zip을 완전삭제 대신 복구 가능하게 삭제 |
| 폴더 자동 감시 | `ctypes`(표준 라이브러리, 폴링) | 외부 라이브러리 없이 감시 폴더의 새 zip을 주기적으로 스캔 |
| 시스템 트레이 | `pystray` | 감시가 켜져 있는 동안 창을 닫아도 계속 감시하도록 트레이 아이콘 상주 |
| 패키징 | `PyInstaller` (onefile) | 단일 실행파일(.exe) 생성 |
| 설치 프로그램 | Inno Setup 6 (ISCC.exe) | Program Files 설치 + 시작메뉴/바탕화면 바로가기 + 제거 프로그램 + zip 우클릭 컨텍스트 메뉴 |
| 외부 연동(선택) | FastStone Image Viewer | 설치돼 있으면 결과 폴더를 이 뷰어로 자동 오픈, 없으면 탐색기로 대체 |

### 주요 기능 요약
1. **입력**: zip 파일을 창에 드래그앤드롭하거나 "파일 선택" 버튼(기본 경로: `다운로드` 폴더)으로 추가. 여러 zip 동시 지원.
2. **중복 판별** (2단계):
   - 1단계: 파일 전체의 SHA-256 해시가 같으면 완전 동일한 사진으로 판정
   - 2단계: `imagehash.phash`의 해밍거리가 임계값(기본 5, 슬라이더로 0~20 조절) 이하이면 유사 사진으로 판정 (재압축/화질변경 등 흡수)
   - 옵션: 회전(90/180/270도)·좌우반전된 사진도 같은 사진으로 판정할지 체크박스로 선택 (기본 켜짐)
   - 성능: BK-tree로 해밍거리 근사 최근접 탐색을 사용해 사진이 많아도 비교적 빠르게 처리
3. **그룹핑**: Union-Find로 중복 그룹을 묶고, 그룹 내에서 zip 등장 순서가 가장 빠른 사진 1장만 최종 결과에 남김
4. **출력**: 바탕화면에 `결과_유니크사진_YYYYMMDD_HHMMSS` 폴더 **하나만** 생성 (리포트 파일, zip 재압축 등 그 외 파일 생성 안 함). 처리 요약(전체/고유/제거/읽기실패 수)은 화면(UI)에만 표시.
5. **제외된 중복 사진 미리보기**: 그룹별로 "유지"/"제외" 사진 썸네일을 대조해서 보여주는 팝업 (그랩 스크롤 지원)
6. **사진 순서 정리 화면** ("결과 폴더 열기" 클릭 시 열림): 큰 화면(기본 최대화)에 사진을 그리드로 배치하고,
   - 클릭/Shift+클릭으로 선택, 마우스 드래그 또는 "선택 위로/아래로" 버튼으로 순서 변경
   - Delete 키로 사진 제외 표시(즉시 삭제 아님), Ctrl+Z로 실행 취소 (최대 50단계)
   - 창 크기에 맞춰 한 줄에 보이는 사진 수(열 개수)가 자동으로 늘고 줆
   - "최종 결과폴더로 보내기" 확정 시에만: 화면 순서대로 파일명에 순번(`001_`, `002_`…) 부여, 제외 표시한 사진 완전 삭제, **원본 zip을 휴지통으로 이동**, 결과 폴더를 **FastStone Image Viewer로 자동 오픈**(없으면 탐색기)
7. **자동 실행**: 탐색기에서 zip 파일을 우클릭 → "중복 사진 정리 도구로 열기"를 선택하면 파일 목록 채우기 → 처리 시작 → 결과 폴더 열기(순서 정리 화면)까지 자동으로 진행됨. 다만 "최종 결과폴더로 보내기"만은 사람이 직접 눌러야 함(파일명 변경 + zip 삭제가 일어나는 단계라 의도적으로 자동화하지 않음).
8. **예외 처리**: 이미지가 아닌 파일 무시, 손상된 이미지는 "읽기 실패" 목록으로 안내, 암호 걸린/손상된 zip은 오류 메시지로 안내.
9. **파일자동읽기 폴더지정** (v1.1.0부터): GUI에서 감시할 폴더(기본값: 다운로드 폴더)를 지정하고
   저장하면, 그 폴더에 새 zip 파일이 들어올 때마다 자동으로 7번 자동 실행 흐름이 시작된다
   (`app/watcher.py`의 `FolderWatcher`가 폴링 방식으로 감지, 파일 크기가 잠깐 변하지 않을 때만
   "다운로드 완료"로 판단). 저장 시 Windows 로그인 시 자동 실행(`app/startup.py`, `HKCU\...\Run`)도
   함께 등록되고, 트레이 아이콘(`app/tray.py`, pystray)이 떠서 창을 닫아도 감시가 계속된다.
   알집(ALZip)의 "폴더 감시 후 자동 압축풀기" 기능이 함께 켜져 있으면 알집이 띄우는 압축풀기
   진행 창을 자동으로 찾아 닫아준다(`close_alzip_windows_soon`, 창 제목에 "알집"이 포함된 창만).
   **감시 폴더에서 자동 감지된 처리는 v1.1.2부터 창을 띄우지 않고 조용히(silent) 처리된다** —
   결과는 `self.result`에 남아있고, 나중에 바탕화면 아이콘이나 트레이 아이콘을 더블클릭해서 창을
   열면 "결과 폴더 열기"로 확인/확정할 수 있다(트레이 아이콘은 더블클릭이 기본 동작이 되도록
   `pystray.MenuItem(..., default=True)`로 지정됨). 반면 사람이 탐색기에서 zip을 직접
   "열기"한 경우(우클릭 등)는 여전히 창이 즉시 나타난다 - 이 둘의 구분은
   `app/gui.py`의 `run_auto(..., silent=...)` 파라미터로 이루어진다.

---

## 2. 폴더/파일 구조

```
PhotoDedup/
├── app/
│   ├── __init__.py          # 빈 파일 (app을 패키지로 만들기 위함)
│   ├── core.py               # 핵심 로직: 압축해제, sha256+pHash 이중 판별, 그룹핑, 바탕화면 결과폴더 생성
│   ├── cli.py                 # 콘솔(CLI) 버전 진입점
│   ├── singleinstance.py       # 중복 실행 방지(명명된 뮤텍스) + 이미 떠 있는 인스턴스로 zip 열기 요청 전달
│   ├── settings.py             # "파일자동읽기 폴더지정" 설정 저장/불러오기 (%APPDATA%\PhotoDedup\config.json)
│   ├── watcher.py               # 감시 폴더 폴링(FolderWatcher) + 알집 창 자동 닫기
│   ├── startup.py                 # Windows 로그인 시 자동 실행 등록/해제 (HKCU\...\Run)
│   ├── tray.py                     # 시스템 트레이 아이콘 (pystray)
│   └── gui.py                       # GUI 버전 (tkinter + tkinterdnd2), 사진 순서 편집 창(OrderEditor) 포함
├── main.py                     # 프로그램 진입점 (인자 없으면 GUI, zip 경로면 자동실행 GUI, --tray는 트레이 감시, 그 외 옵션은 CLI)
├── requirements.txt             # Python 의존성 목록
├── build.bat                     # PyInstaller exe 빌드 + (있으면) Inno Setup 설치 프로그램 빌드 스크립트
├── installer.iss                  # Inno Setup 설치 프로그램 스크립트
├── README.md                       # 사용 설명서
├── PhotoDedup_사용설명서.png         # 한 장짜리 인포그래픽 사용 설명서 (별도 생성물)
├── .gitignore                       # venv/build/dist/installer_output 등 제외
├── 옵시디언_노트/                     # 개발 과정을 정리한 Obsidian 노트 모음 (별도 생성물, 프로그램 동작과 무관)
├── venv/                             # (재현 시 새로 생성) Python 가상환경
├── build/                            # (빌드 시 생성) PyInstaller 중간 산출물
├── dist/
│   └── PhotoDedup.exe                # (빌드 시 생성) 배포용 단일 실행파일
└── installer_output/
    └── PhotoDedup_Setup_1.1.4.exe     # (빌드 시 생성) Inno Setup 설치 프로그램
```

### 핵심 파일 역할 한 줄 설명
| 파일 | 역할 |
|---|---|
| `main.py` | 실행 진입점. 인자 형태를 보고 GUI/자동실행 GUI/트레이 감시(`--tray`)/CLI 중 무엇을 실행할지 결정 |
| `app/__init__.py` | `app` 디렉터리를 파이썬 패키지로 인식시키는 빈 파일 |
| `app/core.py` | zip 압축 해제, SHA-256+pHash 이중 판별, Union-Find/BK-tree 그룹핑, 바탕화면 결과 폴더 생성 등 GUI/CLI 공용 핵심 로직 |
| `app/cli.py` | 콘솔에서 `python -m app.cli photos.zip` 형태로 실행하는 CLI. 개발 중 핵심 로직을 빠르게 검증하는 용도 |
| `app/singleinstance.py` | Windows 명명된 뮤텍스로 중복 실행을 막고, 이미 실행 중이면 zip 경로를 그 인스턴스에 파일로 전달 |
| `app/settings.py` | "파일자동읽기 폴더지정" 설정(감시 폴더 경로/켜짐 여부)을 `%APPDATA%\PhotoDedup\config.json`에 저장/불러오기 |
| `app/watcher.py` | 지정 폴더를 폴링해 새 zip을 감지하는 `FolderWatcher`, 알집 창을 자동으로 닫는 `close_alzip_windows_soon` |
| `app/startup.py` | Windows 로그인 시 자동 실행 등록/해제 (`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) |
| `app/tray.py` | 감시가 켜져 있을 때 창을 닫아도 계속 감시하도록 떠 있는 시스템 트레이 아이콘 (pystray) |
| `app/gui.py` | tkinter 기반 GUI 전체. `DedupApp`(메인 창), `OrderEditor`(사진 순서 정리 창), FastStone 탐지 함수 등 포함 |
| `requirements.txt` | pip으로 설치할 의존성 목록 |
| `build.bat` | venv 활성화 후 실행하면 exe와 설치 프로그램을 한 번에 빌드하는 배치 스크립트 |
| `installer.iss` | Inno Setup 설치 프로그램 정의 (설치 경로, 바로가기, 레지스트리 컨텍스트 메뉴 등) |
| `README.md` | 사용자용 사용 설명서 (실행법, 빌드법, 판별 로직 요약 등) |

---

## 3. 의존성 및 버전

### 언어/런타임 버전 (개발 환경 기준, 그대로 맞추는 것을 권장)
```
$ python --version
Python 3.11.15

$ 시스템: Windows 10 Pro (10.0.19045.6466)
```

> Python 3.9~3.12에서도 대체로 동작하지만, exe 빌드 검증은 3.11 기준으로 했습니다.
> 새 PC에 Python 3.11이 없다면 `winget install Python.Python.3.11` 등으로 설치하세요.

### requirements.txt (전체 원문)
```text
Pillow>=10.0.0
imagehash>=4.3.1
tkinterdnd2>=0.3.0
send2trash>=1.8.0
pystray>=0.19.0
pyinstaller>=6.0.0
```

### 실제 개발 환경에서 설치된 정확한 버전 (`pip freeze` 결과, 100% 동일 재현이 필요하면 이 버전으로 고정 설치)
```text
altgraph==0.17.5
ImageHash==4.3.2
numpy==2.4.6
packaging==26.3
pefile==2024.8.26
pillow==12.3.0
pyinstaller==6.22.2
pyinstaller-hooks-contrib==2026.7
pystray==0.19.5
PyWavelets==1.9.0
pywin32-ctypes==0.2.3
scipy==1.17.1
Send2Trash==2.1.0
six==1.17.0
tkinterdnd2==0.6.3
```
(`numpy`, `scipy`, `PyWavelets`, `packaging`, `pefile`, `altgraph`, `pyinstaller-hooks-contrib`, `pywin32-ctypes`, `six`는
`imagehash`/`pyinstaller`/`pystray`가 내부적으로 요구하는 간접 의존성이며 직접 설치할 필요는 없습니다 - `requirements.txt`만
설치하면 pip이 알아서 함께 설치합니다.)

### 설치 프로그램(Setup.exe) 빌드에 필요한 외부 도구
```
Inno Setup 6 Command-Line Compiler
Copyright (C) 1997-2026 Jordan Russell.
https://www.innosetup.com
```
- 설치: `winget install JRSoftware.InnoSetup` (또는 https://jrsoftware.org/isinfo.php 에서 직접 다운로드)
- 개발 시 사용한 경로: `C:\Users\<사용자명>\AppData\Local\Programs\Inno Setup 6\ISCC.exe`
- exe 빌드 자체에는 필요 없고, "정식 설치 프로그램(Setup.exe)"까지 만들 때만 필요합니다.

### 선택적 외부 프로그램 (없어도 전체 기능은 정상 동작, 없으면 자동으로 대체 동작함)
- **FastStone Image Viewer** (버전 8.4.0.0으로 개발/테스트함): 결과 폴더 확정 후 자동으로 열어주는 뷰어. 설치돼 있지 않으면 코드가 자동으로 Windows 탐색기로 대체합니다. 필요하면 https://www.faststone.org/ 에서 무료로 설치할 수 있습니다.

---

## 4. 환경 설정

이 프로젝트는 **외부 API나 데이터베이스에 연결하지 않는 순수 로컬 데스크톱 프로그램**이라
`.env` 파일이나 API 키, 비밀값이 전혀 필요 없습니다. 코드 안의 설정값은 모두 아래 표가 전부이며,
특정 계정에 종속된 하드코딩 경로는 없습니다(`.env.example` 대신, 실제로 코드 안에 있는 값 목록과
위치를 그대로 정리했습니다).

| 위치 | 현재 값 | 설명 | 다른 PC에서 필요한 조치 |
|---|---|---|---|
| `app/gui.py` → `_on_pick_files()` | `str(Path.home() / "Downloads")` | "파일 선택" 버튼을 눌렀을 때 기본으로 열리는 폴더 | 수정 불필요 - 실행하는 계정의 실제 다운로드 폴더를 자동으로 찾으며, 없으면 `Path.home()`(홈 폴더)로 대체됩니다. |
| `app/gui.py` → `_FASTSTONE_COMMON_PATHS` | `C:\Program Files (x86)\FastStone Image Viewer\FSViewer.exe` 등 2개 경로 | FastStone Image Viewer 설치 경로 후보 | 코드가 이 경로들 + 레지스트리(App Paths)까지 자동으로 확인하므로 **보통 수정 불필요**. FastStone을 다른 경로에 설치했다면 이 리스트에 경로를 추가하세요. |
| `installer.iss` → `AppId` | `{8F1E9C2E-7B3A-4C5D-9E1F-2A6B8C4D7E10}` | Inno Setup이 설치 프로그램을 식별하는 고유 GUID | 그대로 재현할 목적이면 **바꾸지 마세요**(바꾸면 "다른 프로그램"으로 인식되어 기존 설치본 위에 업데이트되지 않고 별도 설치됨). 완전히 새로운 별개 배포판을 만드는 경우에만 새 GUID로 교체하세요. |
| `app/core.py` → `get_desktop_path()` | (하드코딩 값 없음, 레지스트리로 자동 탐지) | 바탕화면 실제 경로(OneDrive 리다이렉트 포함)를 `HKCU\...\Shell Folders`에서 읽어옴 | 수정 불필요 - 어떤 PC/계정에서도 자동으로 맞는 경로를 찾습니다. |
| `app/settings.py` → `CONFIG_FILE` | `%APPDATA%\PhotoDedup\config.json` | "파일자동읽기 폴더지정"에서 저장한 감시 폴더 경로/켜짐 여부 (v1.1.0부터, 사용자별 저장) | 수정 불필요 - 계정마다 자동으로 알맞은 `%APPDATA%` 경로를 사용합니다. 파일이 없으면 감시 꺼짐 상태로 시작합니다. |

**환경변수는 사용하지 않습니다.** v1.1.0부터 "파일자동읽기 폴더지정" 설정 하나만 `app/settings.py`를
통해 `%APPDATA%\PhotoDedup\config.json`에 저장됩니다(위 표 참고). 그 외 값들은 여전히 소스코드
(`app/gui.py`, `installer.iss`) 안에 상수로 들어 있습니다.

---

## 5. 설치 및 실행 순서

새 Windows PC에서 아래 순서를 그대로 따라 하면 됩니다. (PowerShell 또는 Git Bash 어느 쪽이든 가능;
아래는 PowerShell 기준입니다.)

```powershell
# 0) 사전 준비: Python 3.11 설치 확인
python --version
# Python 3.11.x 가 아니면: winget install Python.Python.3.11

# 1) 프로젝트 폴더 준비
#    (git 저장소로 관리 중이라면 git clone, 아니라면 PhotoDedup 폴더를 그대로 복사)
cd "C:\원하는 경로"
# git clone <레포주소> PhotoDedup   # git으로 관리하는 경우
cd PhotoDedup

# 2) 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate

# 3) 의존성 설치
pip install -r requirements.txt

# 4) (선택) 핵심 로직 빠르게 검증 - CLI로 테스트 zip 처리
#    검증 방법은 8번 섹션 참고. 테스트 zip이 있다면:
python main.py photos.zip

# 5) GUI 실행 (개발/테스트용 - 콘솔 창이 함께 뜸)
python main.py

# 6) 배포용 실행파일(exe) 빌드
pyinstaller --noconfirm --onefile --windowed --name PhotoDedup ^
    --collect-all tkinterdnd2 ^
    --collect-all imagehash ^
    --collect-all pystray ^
    main.py
#    결과: dist\PhotoDedup.exe (약 60MB, 콘솔 창 없이 GUI만 뜸)

# 7) (선택) 정식 설치 프로그램(Setup.exe)까지 빌드
winget install JRSoftware.InnoSetup
"%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" installer.iss
#    결과: installer_output\PhotoDedup_Setup_1.1.4.exe

# 6~7번은 build.bat 하나로 한 번에 실행 가능:
build.bat
```

실행 방식별 정리:
- **개발 중 GUI 확인**: `python main.py` (인자 없음)
- **개발 중 CLI로 빠르게 검증**: `python main.py photos.zip --threshold 8 --rotate-flip`
- **배포용 실행**: `dist\PhotoDedup.exe` 더블클릭 (또는 `installer_output\PhotoDedup_Setup_1.1.4.exe`로 정식 설치 후 시작메뉴/바탕화면 아이콘 실행)
- **zip 우클릭 자동실행**: 설치 프로그램으로 설치하면서 "탐색기에서 zip 파일 우클릭 시 ... 메뉴 추가" 옵션을 체크하면, 이후 아무 zip이나 우클릭 → "중복 사진 정리 도구로 열기"로 자동실행 가능

---

## 6. 핵심 소스코드 전체

아래는 최종 완성본 기준, 각 파일의 **전체 원문**입니다.

### `main.py`
```python
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

GUI를 띄우는 모든 경우(인자 없음 / zip 경로 / --tray)는 먼저 "이미 실행 중인 인스턴스가 있는지"를
확인한다. 이미 떠 있다면 새 창을 또 띄우지 않고, 넘겨받은 zip이 있으면 그 인스턴스에 처리를
요청만 하고 조용히 끝난다 - 감시가 켜진 채로 프로그램이 트레이에 떠 있는 상태에서 zip을 또 열었을
때 창이 2개 뜨고 서로 같은 결과 폴더에 동시에 쓰려다 부딪히는 문제를 막기 위함이다.
"""
import sys


def main():
    args = sys.argv[1:]

    if args and not args[0].startswith("-"):
        zip_paths = [a for a in args if a.lower().endswith(".zip")]
        if zip_paths:
            _launch_gui(zip_paths=zip_paths)
            return

    if args and args[0] == "--tray":
        _launch_gui(start_hidden=True)
        return

    if args:
        from app.cli import main as cli_main
        sys.exit(cli_main(args))
    else:
        _launch_gui()


def _launch_gui(zip_paths=None, start_hidden=False):
    from app import singleinstance
    if not singleinstance.try_acquire():
        # 이미 다른 인스턴스가 실행 중이다 - 새 창을 띄우지 않고 그 인스턴스에 요청만 넘긴다.
        singleinstance.request_open_in_running_instance(zip_paths or [])
        return
    from app.gui import main as gui_main
    gui_main(auto_zip_paths=zip_paths, start_hidden=start_hidden)


if __name__ == "__main__":
    main()
```

### `app/__init__.py`
```python
```
(빈 파일입니다 - `app` 폴더를 파이썬 패키지로 인식시키는 용도 외 내용 없음)

### `app/core.py`
```python
"""
중복 사진 탐지 핵심 로직
- zip 압축 해제(순서 보존)
- sha256(완전 동일) + phash(내용 유사) 이중 판별
- 중복 그룹화 및 바탕화면 결과 폴더 생성

CLI(cli.py)와 GUI(gui.py)가 공용으로 이 모듈을 사용한다.
결과는 항상 바탕화면(Desktop)에 `결과_유니크사진_YYYYMMDD_HHMMSS` 폴더 하나만 생성하며,
리포트 파일이나 zip 재압축 등 그 외의 파일은 생성하지 않는다. 처리 요약은 호출자가
반환된 ProcessResult를 이용해 화면(UI)에 직접 표시한다.
"""
from __future__ import annotations

import hashlib
import io
import os
import shutil
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageOps
import imagehash

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}

ProgressCallback = Optional[Callable[..., None]]


# --------------------------------------------------------------------------
# 데이터 구조
# --------------------------------------------------------------------------

@dataclass(eq=False)
class PhotoItem:
    """eq=False: 기본 객체 동일성(identity) 비교/해시를 사용한다.

    GUI의 순서 편집 화면에서 선택된 사진들을 set()에 담아 다루므로 해시 가능해야 하고,
    같은 사진의 서로 다른 인스턴스를 값 비교로 같다고 취급할 이유가 없다(항상 동일 객체를 참조해 다룬다).
    """

    order_index: int
    source_zip: str
    archive_name: str
    extracted_path: str
    display_name: str
    size: int = 0
    sha256: Optional[str] = None
    phash: Optional["imagehash.ImageHash"] = None
    phash_variants: dict = field(default_factory=dict)
    read_error: Optional[str] = None
    output_name: Optional[str] = None


@dataclass
class DupGroup:
    kept: PhotoItem
    excluded: list


@dataclass
class ProcessResult:
    all_items: list
    ok_items: list
    failed_items: list
    groups: list
    unique_count: int
    removed_count: int
    output_dir: str
    extract_errors: list


# --------------------------------------------------------------------------
# 바탕화면 경로 확인
# --------------------------------------------------------------------------

def get_desktop_path() -> Path:
    """OneDrive 등으로 리다이렉트된 경우까지 고려해 실제 바탕화면 경로를 구한다."""
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            )
            value, _ = winreg.QueryValueEx(key, "Desktop")
            path = Path(os.path.expandvars(value))
            if path.is_dir():
                return path
        except Exception:
            pass
    fallback = Path.home() / "Desktop"
    return fallback


# --------------------------------------------------------------------------
# 1단계: zip 압축 해제 (원본 순서 보존)
# --------------------------------------------------------------------------

def extract_zips(zip_paths, extract_root: Path, progress_cb: ProgressCallback = None):
    """zip 목록에서 사진 파일만 원본 순서 그대로 추출한다.

    반환값: (items: list[PhotoItem], errors: list[str])
    """
    items: list[PhotoItem] = []
    errors: list[str] = []
    idx = 0

    for zi, zip_path in enumerate(zip_paths):
        zip_path = Path(zip_path)
        try:
            zf = zipfile.ZipFile(zip_path)
        except zipfile.BadZipFile as e:
            errors.append(f"[{zip_path.name}] 압축파일을 열 수 없습니다(손상됨): {e}")
            continue
        except FileNotFoundError:
            errors.append(f"[{zip_path.name}] 파일을 찾을 수 없습니다.")
            continue

        try:
            out_dir = extract_root / f"zip{zi}_{zip_path.stem}"
            out_dir.mkdir(parents=True, exist_ok=True)
            for info in zf.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                ext = Path(name).suffix.lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue
                try:
                    data = zf.read(info)
                except RuntimeError as e:
                    # 암호 걸린 zip 항목 등
                    errors.append(f"[{zip_path.name}] '{name}' 압축 해제 실패(암호 걸림 가능): {e}")
                    continue
                except Exception as e:
                    errors.append(f"[{zip_path.name}] '{name}' 압축 해제 실패: {e}")
                    continue

                safe_name = f"{idx:06d}_{Path(name).name}"
                dest_path = out_dir / safe_name
                dest_path.write_bytes(data)

                items.append(PhotoItem(
                    order_index=idx,
                    source_zip=zip_path.name,
                    archive_name=name,
                    extracted_path=str(dest_path),
                    display_name=Path(name).name,
                    size=len(data),
                ))
                idx += 1
                if progress_cb:
                    progress_cb("extract", idx)
        finally:
            zf.close()

    return items, errors


# --------------------------------------------------------------------------
# 2단계: 해시 계산 (sha256 + phash [+ 회전/반전 변형])
# --------------------------------------------------------------------------

def compute_hashes(items: list, include_variants: bool = False, progress_cb: ProgressCallback = None):
    total = len(items)
    for i, item in enumerate(items):
        try:
            with open(item.extracted_path, "rb") as f:
                data = f.read()
            item.sha256 = hashlib.sha256(data).hexdigest()

            with Image.open(io.BytesIO(data)) as img:
                img.load()
                img = ImageOps.exif_transpose(img)  # EXIF 회전 정보 정규화
                img_rgb = img.convert("RGB")
                item.phash = imagehash.phash(img_rgb)
                if include_variants:
                    item.phash_variants["rot90"] = imagehash.phash(img_rgb.rotate(90, expand=True))
                    item.phash_variants["rot180"] = imagehash.phash(img_rgb.rotate(180, expand=True))
                    item.phash_variants["rot270"] = imagehash.phash(img_rgb.rotate(270, expand=True))
                    item.phash_variants["flip"] = imagehash.phash(ImageOps.mirror(img_rgb))
        except Exception as e:
            item.read_error = f"{type(e).__name__}: {e}"

        if progress_cb:
            progress_cb("hash", i + 1, total)

    return items


# --------------------------------------------------------------------------
# 3단계: 중복 그룹화 (Union-Find + BK-tree 기반 pHash 근접 탐색)
# --------------------------------------------------------------------------

class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


class BKTree:
    """해밍 거리 기반 근사 최근접 탐색 트리 (pHash 비교 O(n log n) 근사)."""

    def __init__(self):
        self.root = None  # (key, {distance: node})
        self.items_by_key: dict[str, list[int]] = {}

    @staticmethod
    def _key_str(h) -> str:
        return str(h)

    def add(self, hash_key, index: int):
        ks = self._key_str(hash_key)
        self.items_by_key.setdefault(ks, []).append(index)

        if self.root is None:
            self.root = (hash_key, {})
            return

        node = self.root
        while True:
            node_key, children = node
            d = hash_key - node_key
            if d == 0:
                return
            if d in children:
                node = children[d]
            else:
                children[d] = (hash_key, {})
                return

    def query(self, hash_key, threshold: int) -> list[int]:
        if self.root is None:
            return []
        result: list[int] = []
        stack = [self.root]
        while stack:
            node_key, children = stack.pop()
            d = hash_key - node_key
            if d <= threshold:
                result.extend(self.items_by_key[self._key_str(node_key)])
            lo, hi = d - threshold, d + threshold
            for cd, child in children.items():
                if lo <= cd <= hi:
                    stack.append(child)
        return result


def cluster_photos(ok_items: list, threshold: int, allow_rotate_flip: bool) -> UnionFind:
    n = len(ok_items)
    uf = UnionFind(n)

    base_tree = BKTree()
    for i in range(n):
        matches = base_tree.query(ok_items[i].phash, threshold)
        for j in matches:
            uf.union(i, j)
        base_tree.add(ok_items[i].phash, i)

    if allow_rotate_flip:
        for variant_name in ("rot90", "rot180", "rot270", "flip"):
            for i in range(n):
                vh = ok_items[i].phash_variants.get(variant_name)
                if vh is None:
                    continue
                for j in base_tree.query(vh, threshold):
                    if j != i:
                        uf.union(i, j)

    return uf


def build_groups(ok_items: list, uf: UnionFind) -> list:
    clusters: dict[int, list[int]] = {}
    for i in range(len(ok_items)):
        root = uf.find(i)
        clusters.setdefault(root, []).append(i)

    groups = []
    for idxs in clusters.values():
        idxs.sort(key=lambda i: ok_items[i].order_index)
        kept = ok_items[idxs[0]]
        excluded = [ok_items[i] for i in idxs[1:]]
        groups.append(DupGroup(kept=kept, excluded=excluded))

    groups.sort(key=lambda g: g.kept.order_index)
    return groups


# --------------------------------------------------------------------------
# 4단계: 바탕화면에 결과 폴더 생성
# --------------------------------------------------------------------------

def write_output(groups: list, output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    used_names: dict[str, int] = {}
    kept_items = sorted([g.kept for g in groups], key=lambda it: it.order_index)

    for item in kept_items:
        name = item.display_name
        if name in used_names:
            used_names[name] += 1
            stem, ext = Path(name).stem, Path(name).suffix
            name = f"{stem}_{used_names[name]}{ext}"
        else:
            used_names[name] = 0
        shutil.copy2(item.extracted_path, output_dir / name)
        item.output_name = name

    return output_dir


# --------------------------------------------------------------------------
# 전체 파이프라인
# --------------------------------------------------------------------------

def process_zips(
    zip_paths: list,
    work_dir: Path,
    phash_threshold: int = 5,
    allow_rotate_flip: bool = False,
    progress_cb: ProgressCallback = None,
) -> ProcessResult:
    work_dir = Path(work_dir)
    extract_dir = work_dir / "extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)

    if progress_cb:
        progress_cb("stage", "압축 해제 중...")
    all_items, extract_errors = extract_zips(zip_paths, extract_dir, progress_cb)

    if progress_cb:
        progress_cb("stage", "이미지 해시 계산 중...")
    compute_hashes(all_items, include_variants=allow_rotate_flip, progress_cb=progress_cb)

    ok_items = [it for it in all_items if it.read_error is None]
    failed_items = [it for it in all_items if it.read_error is not None]

    if progress_cb:
        progress_cb("stage", "중복 그룹 분석 중...")
    uf = cluster_photos(ok_items, phash_threshold, allow_rotate_flip)
    groups = build_groups(ok_items, uf)

    # 결과로 남길 사진이 하나도 없으면(zip이 아닌 파일을 잘못 넣은 경우 등) 바탕화면에
    # 아무것도 만들지 않는다 - 빈 폴더조차 생성하지 않음.
    output_dir_str = ""
    if groups:
        if progress_cb:
            progress_cb("stage", "바탕화면에 결과 폴더 생성 중...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = get_desktop_path() / f"결과_유니크사진_{timestamp}"
        write_output(groups, output_dir)
        output_dir_str = str(output_dir)
    else:
        if progress_cb:
            progress_cb("stage", "처리 가능한 사진이 없어 결과 폴더를 생성하지 않았습니다.")

    removed_count = sum(len(g.excluded) for g in groups)

    if progress_cb:
        progress_cb("stage", "완료")

    return ProcessResult(
        all_items=all_items,
        ok_items=ok_items,
        failed_items=failed_items,
        groups=groups,
        unique_count=len(groups),
        removed_count=removed_count,
        output_dir=output_dir_str,
        extract_errors=extract_errors,
    )
```

### `app/cli.py`
```python
"""
중복 사진 탐지 - 콘솔(CLI) 버전

처리 결과는 항상 바탕화면(Desktop)에 `결과_유니크사진_YYYYMMDD_HHMMSS` 폴더 하나로만
저장되며, 그 외의 리포트 파일이나 zip은 생성하지 않는다. 요약은 콘솔 화면에만 출력한다.

사용 예:
    python -m app.cli photos.zip
    python -m app.cli a.zip b.zip --threshold 8 --rotate-flip
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import core


def main(argv=None):
    parser = argparse.ArgumentParser(description="zip 안의 중복 사진을 찾아 바탕화면에 고유 사진 폴더를 만듭니다.")
    parser.add_argument("zips", nargs="+", help="처리할 zip 파일 경로 (여러 개 가능)")
    parser.add_argument("--threshold", type=int, default=5, help="pHash 해밍거리 임계값 (기본 5, 낮을수록 엄격)")
    parser.add_argument("--rotate-flip", action="store_true", help="회전/좌우반전된 사진도 같은 사진으로 판정")
    args = parser.parse_args(argv)

    for z in args.zips:
        if not Path(z).exists():
            print(f"[오류] 파일을 찾을 수 없습니다: {z}", file=sys.stderr)
            return 1

    def progress(kind, *rest):
        if kind == "stage":
            print(f">> {rest[0]}")
        elif kind == "hash":
            done, total = rest
            if total and (done % 50 == 0 or done == total):
                print(f"   해시 계산 {done}/{total}")
        elif kind == "extract":
            if rest[0] % 100 == 0:
                print(f"   추출 {rest[0]}개...")

    with tempfile.TemporaryDirectory(prefix="photodedup_") as tmp:
        result = core.process_zips(
            zip_paths=args.zips,
            work_dir=Path(tmp),
            phash_threshold=args.threshold,
            allow_rotate_flip=args.rotate_flip,
            progress_cb=progress,
        )

    print()
    print(f"전체 사진 수     : {len(result.all_items)}")
    print(f"고유 사진 수     : {result.unique_count}")
    print(f"제거된 중복 수   : {result.removed_count}")
    print(f"읽기 실패 수     : {len(result.failed_items)}")
    if result.failed_items:
        print("읽기 실패 목록:")
        for it in result.failed_items:
            print(f"   - {it.display_name} ({it.source_zip}/{it.archive_name}): {it.read_error}")
    if result.extract_errors:
        print("압축 해제 오류:")
        for e in result.extract_errors:
            print(f"   - {e}")
    print()
    if result.output_dir:
        print(f"결과 폴더(바탕화면): {result.output_dir}")
    else:
        print("처리 가능한 사진이 없어 결과 폴더를 생성하지 않았습니다.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### `app/singleinstance.py`
```python
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
```

### `app/settings.py`
```python
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
```

### `app/watcher.py`
```python
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
    """지정된 폴더를 주기적으로 스캔해 새로 생기거나 다시 바뀐 zip 파일을 콜백으로 전달하는
    백그라운드 스레드.

    파일명이 아니라 "수정시각(mtime)"으로 변화를 판단한다 - 브라우저가 같은 파일명으로 다시
    다운로드하면(같은 이름으로 덮어쓰기) 파일명만 보고 판단할 경우 "이미 본 파일"로 취급해
    영원히 무시해버리는 문제가 있었다. mtime 기준으로 보면 덮어써진 시점에 mtime이 갱신되므로
    "그 이름은 봤지만 그 이후로 내용이 바뀌었다"를 정확히 구분할 수 있다.
    """

    def __init__(self, folder: str, on_new_zip):
        super().__init__(daemon=True)
        self.folder = folder
        self.on_new_zip = on_new_zip
        self._stop_event = threading.Event()
        self._known_mtimes: dict[str, float] = {}  # 파일명 -> 마지막으로 처리(또는 무시 확정)한 수정시각

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        # 감시 시작 시점에 이미 폴더에 있던 zip은 "그 상태 그대로"인 한 대상에서 제외한다
        # (감시를 켜기 전부터 있던 파일까지 전부 자동으로 처리되기 시작하면 안 되므로).
        # 이후 같은 이름의 파일이 다시 다운로드되어 mtime이 바뀌면 그때는 새로 처리한다.
        self._known_mtimes = self._snapshot_mtimes()
        while not self._stop_event.is_set():
            try:
                self._scan_once()
            except Exception:
                pass
            self._stop_event.wait(POLL_INTERVAL_SEC)

    def _snapshot_mtimes(self) -> dict[str, float]:
        result: dict[str, float] = {}
        try:
            for f in os.listdir(self.folder):
                if not f.lower().endswith(".zip"):
                    continue
                try:
                    result[f] = os.path.getmtime(os.path.join(self.folder, f))
                except OSError:
                    pass
        except OSError:
            pass
        return result

    def _scan_once(self) -> None:
        current = self._snapshot_mtimes()
        for name, mtime in current.items():
            known_mtime = self._known_mtimes.get(name)
            if known_mtime is not None and mtime <= known_mtime:
                continue  # 이미 처리(또는 무시 확정)한 뒤로 바뀌지 않은 파일
            path = os.path.join(self.folder, name)
            if self._is_stable(path):
                self._known_mtimes[name] = mtime
                close_alzip_windows_soon()
                self.on_new_zip(path)
            # 크기가 아직 안정되지 않았으면(다운로드 진행 중일 가능성) 기록을 갱신하지 않고
            # 다음 스캔 주기에 다시 확인한다.
        # 폴더에서 사라진 파일의 기록은 정리한다(메모리 누수 방지).
        for name in set(self._known_mtimes) - set(current):
            self._known_mtimes.pop(name, None)

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
```

### `app/startup.py`
```python
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
```

### `app/tray.py`
```python
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
            pystray.MenuItem("창 열기", lambda: on_show(), default=True),
            pystray.MenuItem("완전히 종료", lambda: on_quit()),
        ),
    )
```

### `app/gui.py`
```python
"""
중복 사진 탐지 - GUI (tkinter + tkinterdnd2)
"""
from __future__ import annotations

import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except Exception:
    _HAS_DND = False

from PIL import Image, ImageTk
from send2trash import send2trash

from . import core
from . import settings as app_settings
from . import singleinstance as app_singleinstance
from . import startup as app_startup
from . import tray as app_tray
from . import watcher as app_watcher

APP_TITLE = "중복 사진 정리 도구"
THUMB_SIZE = (110, 110)

# FastStone Image Viewer를 찾을 때 시도해보는 흔한 설치 경로 (없으면 레지스트리 App Paths도 확인한다)
_FASTSTONE_COMMON_PATHS = [
    r"C:\Program Files (x86)\FastStone Image Viewer\FSViewer.exe",
    r"C:\Program Files\FastStone Image Viewer\FSViewer.exe",
]


def find_faststone_exe() -> str | None:
    """설치된 FastStone Image Viewer 실행파일 경로를 찾는다. 못 찾으면 None."""
    for p in _FASTSTONE_COMMON_PATHS:
        if os.path.isfile(p):
            return p

    if sys.platform == "win32":
        try:
            import winreg
            for hive, subkey in (
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\FSViewer.exe"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\FSViewer.exe"),
            ):
                try:
                    key = winreg.OpenKey(hive, subkey)
                    path, _ = winreg.QueryValueEx(key, "")
                    if path and os.path.isfile(path):
                        return path
                except FileNotFoundError:
                    continue
        except Exception:
            pass

    return None

_ORDER_PREFIX_RE = re.compile(r"^\d{2,}_(.+)$")


def _strip_order_prefix(name: str) -> str:
    """이미 순번이 붙어있는 파일명(예: 001_photo.jpg)이면 순번을 떼고 원래 이름만 돌려준다.

    순서 편집을 다시 실행해도 001_002_photo.jpg 처럼 순번이 계속 누적되지 않게 하기 위함.
    """
    m = _ORDER_PREFIX_RE.match(name)
    return m.group(1) if m else name


class DedupApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("760x920")
        self.root.minsize(700, 860)

        self.zip_paths: list[str] = []
        self.last_zip_paths: list[str] = []  # 처리에 실제로 사용된 zip 경로(목록이 나중에 바뀌어도 유지)
        self.work_dir: str | None = None
        self.result: core.ProcessResult | None = None
        self.progress_queue: "queue.Queue" = queue.Queue()
        self.worker_thread: threading.Thread | None = None
        self.thumb_cache: list = []  # PhotoImage 참조 유지용
        self._auto_open_order_editor = False  # 자동 실행 모드에서 처리 끝나면 순서 정리 창까지 자동으로 열지 여부

        # "파일자동읽기 폴더지정" (감시 폴더 자동 처리) 관련 상태
        self.folder_watcher: app_watcher.FolderWatcher | None = None
        self.tray_icon = None
        self._watch_pending: list[tuple[str, bool]] = []  # (zip 경로, silent 여부) 대기열
        self._order_editor_open = False

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._maybe_resume_watch()

        # 이 프로세스가 유일한 인스턴스이므로(main.py에서 이미 확인됨), 나중에 또 실행하려다
        # 넘겨받는 요청(zip 열기/창 보여주기)이 있는지 계속 확인한다.
        self.pending_request_watcher = app_singleinstance.PendingRequestWatcher(self._on_external_request)
        self.pending_request_watcher.start()

    # ------------------------------------------------------------------
    # UI 구성
    # ------------------------------------------------------------------
    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # 드롭 영역
        self.drop_frame = tk.LabelFrame(self.root, text="1. zip 파일 추가", padx=8, pady=8)
        self.drop_frame.pack(fill="x", **pad)

        drop_text = "여기로 zip 파일을 드래그 앤 드롭하세요"
        if not _HAS_DND:
            drop_text += "\n(드래그앤드롭 라이브러리 없음 - 아래 버튼으로 파일을 선택하세요)"
        self.drop_label = tk.Label(
            self.drop_frame, text=drop_text, height=4,
            relief="ridge", bd=2, bg="#f5f5f5", fg="#555555", justify="center",
        )
        self.drop_label.pack(fill="x", expand=True)

        if _HAS_DND:
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self._on_drop)

        btn_row = tk.Frame(self.drop_frame)
        btn_row.pack(fill="x", pady=(6, 0))
        tk.Button(btn_row, text="파일 선택...", command=self._on_pick_files).pack(side="left")
        tk.Button(btn_row, text="목록 지우기", command=self._on_clear_files).pack(side="left", padx=6)

        self.file_listbox = tk.Listbox(self.drop_frame, height=4)
        self.file_listbox.pack(fill="x", pady=(6, 0))

        # 옵션
        opt_frame = tk.LabelFrame(self.root, text="2. 옵션", padx=8, pady=8)
        opt_frame.pack(fill="x", **pad)

        thresh_row = tk.Frame(opt_frame)
        thresh_row.pack(fill="x")
        tk.Label(thresh_row, text="유사 판정 민감도 (pHash 임계값):").pack(side="left")
        self.threshold_var = tk.IntVar(value=5)
        self.threshold_label = tk.Label(thresh_row, text="5  (엄격)", width=14)
        self.threshold_label.pack(side="right")
        self.threshold_scale = tk.Scale(
            opt_frame, from_=0, to=20, orient="horizontal",
            variable=self.threshold_var, showvalue=False, command=self._on_threshold_change,
        )
        self.threshold_scale.pack(fill="x")
        tk.Label(
            opt_frame, text="0(완전히 같은 사진만) ~ 20(약간만 비슷해도 중복 처리, 느슨)",
            fg="#777777",
        ).pack(anchor="w")

        self.rotate_flip_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            opt_frame, text="회전 / 좌우반전된 사진도 같은 사진으로 판정",
            variable=self.rotate_flip_var,
        ).pack(anchor="w", pady=(4, 0))

        # 실행
        run_frame = tk.Frame(self.root)
        run_frame.pack(fill="x", **pad)
        self.start_btn = tk.Button(
            run_frame, text="처리 시작", command=self._on_start, bg="#2f7dd1", fg="white",
            font=("", 11, "bold"), height=1,
        )
        self.start_btn.pack(side="left")

        self.status_label = tk.Label(run_frame, text="대기 중", anchor="w")
        self.status_label.pack(side="left", padx=10, fill="x", expand=True)

        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.progress.pack(fill="x", padx=10, pady=(0, 6))

        # 결과
        self.result_frame = tk.LabelFrame(self.root, text="3. 결과", padx=8, pady=8)
        self.result_frame.pack(fill="both", expand=True, **pad)

        self.summary_label = tk.Label(self.result_frame, text="아직 처리하지 않았습니다.", justify="left", anchor="w")
        self.summary_label.pack(fill="x")

        result_btn_row = tk.Frame(self.result_frame)
        result_btn_row.pack(fill="x", pady=(8, 0))
        self.open_folder_btn = tk.Button(result_btn_row, text="결과 폴더 열기", command=self._on_edit_order, state="disabled")
        self.open_folder_btn.pack(side="left")
        self.preview_btn = tk.Button(result_btn_row, text="제외된 중복 사진 미리보기", command=self._on_preview, state="disabled")
        self.preview_btn.pack(side="left", padx=6)

        self.log_text = tk.Text(self.result_frame, height=8, state="disabled", wrap="word")
        self.log_text.pack(fill="both", expand=True, pady=(8, 0))

        # 파일자동읽기 폴더지정 (지정 폴더에 zip이 들어오면 자동으로 처리 시작)
        watch_frame = tk.LabelFrame(self.root, text="파일자동읽기 폴더지정", padx=8, pady=8)
        watch_frame.pack(fill="x", **pad)

        tk.Label(
            watch_frame,
            text="지정한 폴더에 사진 zip 파일이 들어오면 자동으로 이 프로그램이 실행되어 처리합니다.\n"
                 "(\"최종 결과폴더로 보내기\" 확정만은 항상 사람이 직접 눌러야 합니다)",
            fg="#555555", justify="left",
        ).pack(anchor="w")

        watch_row = tk.Frame(watch_frame)
        watch_row.pack(fill="x", pady=(6, 0))
        saved = app_settings.load_settings()
        default_folder = saved["watch_folder"] or str(Path.home() / "Downloads")
        self.watch_folder_var = tk.StringVar(value=default_folder)
        tk.Entry(watch_row, textvariable=self.watch_folder_var).pack(side="left", fill="x", expand=True)
        tk.Button(watch_row, text="찾아보기...", command=self._on_browse_watch_folder).pack(side="left", padx=(6, 0))

        watch_btn_row = tk.Frame(watch_frame)
        watch_btn_row.pack(fill="x", pady=(6, 0))
        self.watch_status_label = tk.Label(watch_btn_row, text="", fg="#555555", anchor="w")
        self.watch_status_label.pack(side="left", fill="x", expand=True)
        tk.Button(watch_btn_row, text="감시 끄기", command=self._on_disable_watch).pack(side="right")
        tk.Button(
            watch_btn_row, text="저장", command=self._on_save_watch_settings,
            bg="#2f7dd1", fg="white",
        ).pack(side="right", padx=(0, 6))

        self._update_watch_status_label(saved["watch_enabled"], saved["watch_folder"])

    # ------------------------------------------------------------------
    # 파일 입력
    # ------------------------------------------------------------------
    def _on_drop(self, event):
        paths = self.root.tk.splitlist(event.data)
        added = [p for p in paths if p.lower().endswith(".zip")]
        skipped = len(paths) - len(added)
        self._add_zip_paths(added)
        if skipped:
            messagebox.showwarning(APP_TITLE, f"zip 파일이 아닌 {skipped}개 항목은 제외되었습니다.")

    def _on_pick_files(self):
        initial_dir = str(Path.home() / "Downloads")
        if not os.path.isdir(initial_dir):
            initial_dir = str(Path.home())
        paths = filedialog.askopenfilenames(
            title="zip 파일 선택", initialdir=initial_dir, filetypes=[("ZIP 파일", "*.zip")],
        )
        self._add_zip_paths(paths)

    def _add_zip_paths(self, paths):
        for p in paths:
            if p not in self.zip_paths:
                self.zip_paths.append(p)
                self.file_listbox.insert("end", p)

    def _on_clear_files(self):
        self.zip_paths.clear()
        self.file_listbox.delete(0, "end")

    def _on_threshold_change(self, _value=None):
        v = self.threshold_var.get()
        label = "엄격" if v <= 5 else ("보통" if v <= 12 else "느슨")
        self.threshold_label.config(text=f"{v}  ({label})")

    # ------------------------------------------------------------------
    # 파일자동읽기 폴더지정 (감시 폴더에 새 zip이 들어오면 자동으로 처리)
    # ------------------------------------------------------------------
    def _update_watch_status_label(self, enabled: bool, folder: str):
        if enabled and folder:
            text = f"감시 중: {folder}  (Windows 시작 시 자동 실행 + 트레이 상주)"
        else:
            text = "감시 꺼짐"
        self.watch_status_label.config(text=text)

    def _on_browse_watch_folder(self):
        initial = self.watch_folder_var.get().strip() or str(Path.home() / "Downloads")
        if not os.path.isdir(initial):
            initial = str(Path.home())
        folder = filedialog.askdirectory(title="감시할 폴더 선택", initialdir=initial)
        if folder:
            self.watch_folder_var.set(folder)

    def _on_save_watch_settings(self):
        folder = self.watch_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning(APP_TITLE, "존재하는 폴더 경로를 입력해주세요.")
            return

        app_settings.save_settings({"watch_folder": folder, "watch_enabled": True})
        self._start_watch_internal(folder)
        self._ensure_tray()
        try:
            app_startup.enable_startup()
        except Exception as e:
            messagebox.showwarning(APP_TITLE, f"Windows 시작 프로그램 등록에 실패했습니다:\n{e}")
        self._update_watch_status_label(True, folder)
        messagebox.showinfo(
            APP_TITLE,
            f"'{folder}' 폴더 감시를 시작합니다.\n"
            "이제부터 이 폴더에 사진 zip 파일이 들어오면 자동으로 처리를 시작합니다.\n"
            "창을 닫아도 트레이 아이콘에 상주하며 계속 감시합니다.",
        )

    def _on_disable_watch(self):
        folder = self.watch_folder_var.get().strip()
        app_settings.save_settings({"watch_folder": folder, "watch_enabled": False})
        self._stop_watch_internal()
        try:
            app_startup.disable_startup()
        except Exception:
            pass
        self._update_watch_status_label(False, folder)

    def _start_watch_internal(self, folder: str):
        self._stop_watch_internal()
        self.folder_watcher = app_watcher.FolderWatcher(folder, self._on_watcher_new_zip)
        self.folder_watcher.start()

    def _stop_watch_internal(self):
        if self.folder_watcher is not None:
            self.folder_watcher.stop()
            self.folder_watcher = None

    def _maybe_resume_watch(self):
        """이전에 저장해 둔 감시 설정이 켜져 있으면(예: Windows 시작 시 자동 실행) 다시 감시를 시작한다."""
        saved = app_settings.load_settings()
        if saved["watch_enabled"] and saved["watch_folder"] and os.path.isdir(saved["watch_folder"]):
            self._start_watch_internal(saved["watch_folder"])
            self._ensure_tray()

    def _on_watcher_new_zip(self, zip_path: str):
        # 이 콜백은 감시 스레드에서 호출되므로, tkinter 위젯 조작은 반드시 메인 스레드로 넘긴다.
        self.root.after(0, lambda: self._handle_watched_zip(zip_path))

    def _handle_watched_zip(self, zip_path: str):
        # 감시 폴더에서 자동으로 감지한 zip은 창을 띄우지 않고 조용히 처리한다(v1.1.2부터).
        # 결과는 나중에 바탕화면 아이콘이나 트레이 아이콘을 더블클릭해서 창을 열면 확인할 수 있다.
        self._watch_pending.append((zip_path, True))
        self._drain_watch_queue()

    def _drain_watch_queue(self):
        if not self._watch_pending:
            return
        if self.worker_thread and self.worker_thread.is_alive():
            return
        if self._order_editor_open:
            return
        next_zip, silent = self._watch_pending.pop(0)
        self.run_auto([next_zip], silent=silent)

    # ------------------------------------------------------------------
    # 단일 인스턴스: 이미 실행 중일 때 또 실행하려던 요청(zip 열기/창 보여주기) 처리
    # ------------------------------------------------------------------
    def _on_external_request(self, zip_paths: list[str]):
        # 이 콜백은 감시 스레드에서 호출되므로, tkinter 위젯 조작은 반드시 메인 스레드로 넘긴다.
        self.root.after(0, lambda: self._handle_external_request(zip_paths))

    def _handle_external_request(self, zip_paths: list[str]):
        # 사람이 직접 바탕화면 아이콘/트레이 아이콘을 더블클릭했거나 탐색기에서 zip을 열려고 한
        # 경우이므로, 감시 폴더 자동 감지와 달리 창을 보여준다.
        self.root.deiconify()
        self.root.lift()
        if not zip_paths:
            return
        self._watch_pending.extend((p, False) for p in zip_paths)
        self._drain_watch_queue()

    # ------------------------------------------------------------------
    # 트레이 아이콘 / 종료 (감시가 켜져 있는 동안 창을 닫아도 계속 감시하기 위함)
    # ------------------------------------------------------------------
    def _ensure_tray(self):
        if self.tray_icon is not None or not app_tray.is_available():
            return
        self.tray_icon = app_tray.create_tray_icon(on_show=self._show_from_tray, on_quit=self._quit_from_tray)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _show_from_tray(self):
        self.root.after(0, lambda: (self.root.deiconify(), self.root.lift()))

    def _hide_to_tray_if_active(self):
        """트레이 아이콘이 떠 있으면(감시를 한 번이라도 켠 적이 있으면) 메인 창을 다시 숨긴다.

        "최종 결과폴더로 보내기" 확정 뒤에는 FastStone(사진편집기)만 화면에 남기고, 방금까지
        쓰던 메인 창/순서 정리 창은 다시 트레이로 내려간다. 트레이 아이콘이 없으면(감시를
        켠 적이 없으면) 숨길 경우 다시 열 방법이 없으므로 그대로 둔다.
        """
        if self.tray_icon is not None:
            self.root.withdraw()

    def _quit_from_tray(self):
        self.root.after(0, self._shutdown)

    # ------------------------------------------------------------------
    # 자동 실행 (탐색기 우클릭 "중복 사진 정리 도구로 열기" / zip을 exe로 드래그 / 감시 폴더 감지)
    # ------------------------------------------------------------------
    def run_auto(self, zip_paths: list, silent: bool = False):
        """전달받은 zip으로 파일 선택 → 처리 시작 → 결과 폴더 열기까지 자동으로 진행한다.

        "최종 결과폴더로 보내기" 확정만은 사람이 직접 눌러야 하며, 그 전에 사람이 직접
        검수/수정할 수 있도록 순서 정리 창을 열어둔 상태로 자동 진행을 멈춘다.

        silent=True(감시 폴더에서 자동 감지한 경우)면 창/팝업을 전혀 띄우지 않고 조용히
        처리만 한다 - 순서 정리 창(OrderEditor)도 자동으로 열지 않는다. 처리 결과는
        `self.result`에 남아있으므로, 나중에 사람이 창을 열어 "결과 폴더 열기"를 누르면
        그때 순서를 확인하고 확정할 수 있다.
        """
        valid = [p for p in zip_paths if os.path.isfile(p)]
        missing = [p for p in zip_paths if p not in valid]
        if missing and not silent:
            messagebox.showwarning(APP_TITLE, "다음 zip 파일을 찾을 수 없습니다:\n" + "\n".join(missing))
        if not valid:
            return
        # 감시 폴더에서 반복적으로 자동 실행될 수 있으므로, 이전 자동 실행에서 남아있을 수 있는
        # 목록을 지우고 이번에 전달받은 zip만으로 새로 시작한다(누적되어 옛 zip까지 다시 처리되는 것을 방지).
        self._on_clear_files()
        self._add_zip_paths(valid)
        self._auto_open_order_editor = not silent
        if not silent:
            self.root.deiconify()
            self.root.lift()
        self._on_start()

    # ------------------------------------------------------------------
    # 처리 실행
    # ------------------------------------------------------------------
    def _on_start(self):
        if not self.zip_paths:
            messagebox.showwarning(APP_TITLE, "먼저 zip 파일을 추가해주세요.")
            return
        if self.worker_thread and self.worker_thread.is_alive():
            return

        self.start_btn.config(state="disabled")
        self.open_folder_btn.config(state="disabled")
        self.preview_btn.config(state="disabled")
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self._log_clear()
        self.summary_label.config(text="처리 중입니다...")

        self.work_dir = tempfile.mkdtemp(prefix="photodedup_")
        zip_paths = list(self.zip_paths)
        self.last_zip_paths = zip_paths  # 이번 처리에 실제로 쓰인 zip 목록을 기억해둔다(나중에 순서 정리 확정 시 삭제 대상)
        threshold = self.threshold_var.get()
        rotate_flip = self.rotate_flip_var.get()

        def worker():
            try:
                result = core.process_zips(
                    zip_paths=zip_paths,
                    work_dir=Path(self.work_dir),
                    phash_threshold=threshold,
                    allow_rotate_flip=rotate_flip,
                    progress_cb=lambda *a: self.progress_queue.put(a),
                )
                self.progress_queue.put(("done", result))
            except Exception as e:
                self.progress_queue.put(("error", str(e)))

        self.worker_thread = threading.Thread(target=worker, daemon=True)
        self.worker_thread.start()
        self.root.after(100, self._poll_queue)

    def _poll_queue(self):
        try:
            while True:
                msg = self.progress_queue.get_nowait()
                kind = msg[0]

                if kind == "stage":
                    self.status_label.config(text=msg[1])
                    self._log(msg[1])
                    if msg[1] in ("바탕화면에 결과 폴더 생성 중...", "완료"):
                        self.progress.stop()
                        self.progress.config(mode="determinate")
                        self.progress["value"] = 100 if msg[1] == "완료" else 95

                elif kind == "extract":
                    self.status_label.config(text=f"압축 해제 중... ({msg[1]}개)")

                elif kind == "hash":
                    done, total = msg[1], msg[2]
                    self.progress.stop()
                    self.progress.config(mode="determinate")
                    pct = (done / total * 100) if total else 0
                    self.progress["value"] = pct
                    self.status_label.config(text=f"이미지 해시 계산 중... ({done}/{total})")

                elif kind == "done":
                    self._on_process_done(msg[1])
                    return

                elif kind == "error":
                    self._on_process_error(msg[1])
                    return
        except queue.Empty:
            pass

        self.root.after(100, self._poll_queue)

    def _on_process_done(self, result: core.ProcessResult):
        self.result = result
        self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 100
        self.start_btn.config(state="normal")
        self.open_folder_btn.config(state="normal" if result.output_dir else "disabled")
        self.preview_btn.config(state="normal" if any(g.excluded for g in result.groups) else "disabled")

        folder_line = (
            f"결과 폴더(바탕화면): {result.output_dir}" if result.output_dir
            else "처리 가능한 사진이 없어 결과 폴더를 생성하지 않았습니다."
        )
        summary = (
            f"전체 사진 수: {len(result.all_items)}   "
            f"고유 사진 수: {result.unique_count}   "
            f"제거된 중복 수: {result.removed_count}   "
            f"읽기 실패: {len(result.failed_items)}\n"
            f"{folder_line}"
        )
        self.summary_label.config(text=summary)
        self.status_label.config(text="완료")
        self._log(f"완료. {folder_line}")
        if result.failed_items:
            self._log("읽기 실패 목록:")
            for it in result.failed_items:
                self._log(f"  - {it.display_name} ({it.source_zip}/{it.archive_name}): {it.read_error}")
        if result.extract_errors:
            for e in result.extract_errors:
                self._log(f"[경고] {e}")

        if self._auto_open_order_editor:
            self._auto_open_order_editor = False
            self._on_edit_order()
        else:
            # silent(감시 폴더 자동 감지) 처리가 끝났거나 사람이 직접 "처리 시작"을 눌러 끝난
            # 경우 - 대기 중인 다음 감시 대상 zip이 있으면 이어서 처리한다.
            self._drain_watch_queue()

    def _on_process_error(self, message: str):
        self._auto_open_order_editor = False
        self.progress.stop()
        self.progress.config(mode="determinate", value=0)
        self.start_btn.config(state="normal")
        self.status_label.config(text="오류 발생")
        self.summary_label.config(text="처리 중 오류가 발생했습니다.")
        self._log(f"[오류] {message}")
        messagebox.showerror(APP_TITLE, f"처리 중 오류가 발생했습니다:\n{message}")
        self._drain_watch_queue()

    # ------------------------------------------------------------------
    # 결과 액션
    # ------------------------------------------------------------------
    def _open_in_explorer(self, path: str):
        if os.path.isdir(path):
            if sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])

    def _open_result_viewer(self, path: str):
        """결과 폴더를 FastStone Image Viewer로 열어본다. 설치돼 있지 않으면 탐색기로 대신 연다."""
        if not os.path.isdir(path):
            return
        faststone = find_faststone_exe()
        if faststone:
            try:
                subprocess.Popen([faststone, path])
                return
            except Exception:
                pass
        self._open_in_explorer(path)

    def _on_edit_order(self):
        if not self.result or not os.path.isdir(self.result.output_dir):
            self._drain_watch_queue()
            return
        items = sorted([g.kept for g in self.result.groups], key=lambda it: it.order_index)
        if not items:
            messagebox.showinfo(APP_TITLE, "정리된 사진이 없습니다.")
            self._drain_watch_queue()
            return
        self._order_editor_open = True
        OrderEditor(self, items, source_zip_paths=self.last_zip_paths)

    def _on_order_editor_closed(self):
        self._order_editor_open = False
        self._drain_watch_queue()

    def _on_preview(self):
        if not self.result:
            return
        dup_groups = [g for g in self.result.groups if g.excluded]
        if not dup_groups:
            messagebox.showinfo(APP_TITLE, "제외된 중복 사진이 없습니다.")
            return

        win = tk.Toplevel(self.root)
        win.title("제외된 중복 사진 미리보기")
        win.geometry("700x600")

        canvas = tk.Canvas(win)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        local_thumb_cache = []

        for gi, g in enumerate(dup_groups, 1):
            group_frame = tk.LabelFrame(inner, text=f"그룹 {gi}", padx=6, pady=6)
            group_frame.pack(fill="x", padx=8, pady=6)

            row = tk.Frame(group_frame)
            row.pack(fill="x")
            self._add_thumb(row, g.kept, "유지", "#2e7d32", local_thumb_cache)
            for e in g.excluded:
                self._add_thumb(row, e, "제외", "#c62828", local_thumb_cache)

        win.thumb_cache = local_thumb_cache  # 창이 열려있는 동안 참조 유지
        self._enable_drag_scroll(canvas, inner)

    def _enable_drag_scroll(self, canvas: tk.Canvas, inner: tk.Frame):
        """캔버스 안 어디를 클릭/드래그해도(자식 위젯 포함) 위아래로 스크롤되도록 한다.

        자식 위젯에서 발생한 마우스 이벤트는 캔버스로 자동 전파되지 않으므로
        모든 하위 위젯에 동일한 핸들러를 재귀적으로 바인딩한다. 좌표는 위젯마다
        원점이 달라지므로 화면 절대좌표(x_root/y_root)를 기준으로 delta를 계산한다.
        """

        def start_drag(event):
            canvas.scan_mark(event.x_root, event.y_root)
            canvas.config(cursor="fleur")

        def do_drag(event):
            canvas.scan_dragto(event.x_root, event.y_root, gain=1)

        def end_drag(_event):
            canvas.config(cursor="hand2")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def bind_widget(widget):
            widget.config(cursor="hand2")
            widget.bind("<ButtonPress-1>", start_drag)
            widget.bind("<B1-Motion>", do_drag)
            widget.bind("<ButtonRelease-1>", end_drag)
            widget.bind("<MouseWheel>", on_mousewheel)
            for child in widget.winfo_children():
                bind_widget(child)

        canvas.config(cursor="hand2")
        canvas.bind("<ButtonPress-1>", start_drag)
        canvas.bind("<B1-Motion>", do_drag)
        canvas.bind("<ButtonRelease-1>", end_drag)
        canvas.bind("<MouseWheel>", on_mousewheel)
        bind_widget(inner)

    def _add_thumb(self, parent, item: core.PhotoItem, tag: str, color: str, cache: list):
        cell = tk.Frame(parent, padx=4)
        cell.pack(side="left")
        try:
            img = Image.open(item.extracted_path)
            img.thumbnail(THUMB_SIZE)
            photo = ImageTk.PhotoImage(img)
            cache.append(photo)
            tk.Label(cell, image=photo).pack()
        except Exception:
            tk.Label(cell, text="(미리보기 실패)", width=14, height=6).pack()
        tk.Label(cell, text=tag, fg=color, font=("", 9, "bold")).pack()
        tk.Label(cell, text=item.display_name, wraplength=110, justify="center").pack()

    # ------------------------------------------------------------------
    # 로그 / 종료
    # ------------------------------------------------------------------
    def _log(self, text: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _log_clear(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _on_close(self):
        # 감시가 켜져 있고 트레이 아이콘이 떠 있으면, 창만 숨기고 감시는 계속한다.
        if self.folder_watcher is not None and self.tray_icon is not None:
            self.root.withdraw()
            return
        self._shutdown()

    def _shutdown(self):
        self._stop_watch_internal()
        if self.pending_request_watcher is not None:
            self.pending_request_watcher.stop()
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
            self.tray_icon = None
        if self.work_dir and os.path.isdir(self.work_dir):
            shutil.rmtree(self.work_dir, ignore_errors=True)
        self.root.destroy()


class OrderEditor:
    """'결과 폴더 열기'를 누르면 뜨는 사진 순서 편집 창.

    바로 탐색기를 열지 않고, 큰 화면(기본 최대화)에 정리된 사진을 순서대로 늘어놓아
    사용자가 여러 장을 선택해 위/아래로 옮기거나 마우스로 드래그해 순서를 바꿀 수 있게 한다.
    "최종 결과폴더로 보내기"를 눌러야만 실제로 파일명이 그 순서(순번_원본파일명)로 바뀌고,
    원본 zip 파일이 휴지통으로 이동하며, 그 뒤에 결과 폴더가 FastStone Image Viewer(설치돼
    있으면)로 열린다(없으면 탐색기로 대신 연다).

    성능/깜빡임 대책: 사진 목록의 구성(멤버십)은 편집 중 절대 바뀌지 않고 순서만 바뀌므로,
    각 사진의 썸네일과 셀(Frame) 위젯을 처음 한 번만 만들어 재사용한다. 선택 상태 변경은
    테두리 색만 바꾸고, 순서 변경은 기존 위젯을 새 grid 위치로 재배치(regrid)할 뿐 위젯을
    파괴/재생성하지 않는다 - 매번 위젯을 지웠다 다시 그리던 예전 방식이 클릭할 때마다
    화면이 깜빡이고 느리게 느껴지던 원인이었다.
    """

    COLUMNS_MIN = 3
    THUMB_SIZE = (150, 150)
    CELL_PAD = 6
    CELL_EXTRA_W = 30  # 셀 테두리/여백을 대략 감안한 여유폭 (썸네일 크기 자체는 고정)
    NORMAL_BORDER = "#cccccc"
    SELECTED_BORDER = "#2f7dd1"
    DROP_TARGET_BORDER = "#ff9800"

    def __init__(self, app: DedupApp, items: list, source_zip_paths: list | None = None):
        self.app = app
        self.output_dir = Path(app.result.output_dir)
        self.source_zip_paths = list(source_zip_paths or [])  # 확정 시 휴지통으로 보낼 원본 zip 경로
        self.items = list(items)  # 현재 화면상의 순서
        self.selected: set = set()
        self.anchor_item = None  # shift-클릭 범위 선택의 기준점
        self.hover_item = None  # 드래그 중 마우스 아래 있는 삽입 대상(미리보기 표시용)
        self.thumb_cache: list = []  # PhotoImage 참조 유지용(가비지 컬렉션 방지)
        self.thumb_images: dict = {}  # id(item) -> PhotoImage (한 번만 생성, 재사용)
        self.cells: dict = {}  # id(item) -> 셀 Frame (한 번만 생성, 재사용)
        self.badges: dict = {}  # id(item) -> 순번 배지 Label
        self.deleted_items: list = []  # Delete 키로 제외 표시된 사진(확정 시 실제로 삭제됨)
        self.history: list = []  # 실행 취소(Ctrl+Z)용 스냅샷 스택: (items, deleted_items) 튜플들
        self.drag_item = None
        self.drag_start = None
        self.dragging = False
        self._shift_held = False
        self.columns = self.COLUMNS_MIN

        self.win = tk.Toplevel(app.root)
        self.win.title("사진 순서 정리")
        self._size_window()
        self._build_ui()
        self.win.update_idletasks()
        self._preload_thumbnails()
        self._build_cells()
        self._recompute_columns(force=True)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.win.bind("<Delete>", self._on_delete_key)
        self.win.bind("<Control-z>", self._on_undo)
        self.win.bind("<Control-Z>", self._on_undo)
        self.win.focus_set()

    def _size_window(self):
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        w, h = int(sw * 0.9), int(sh * 0.9)
        x, y = (sw - w) // 2, (sh - h) // 2
        self.win.geometry(f"{w}x{h}+{x}+{y}")
        self.win.minsize(1000, 700)
        try:
            self.win.state("zoomed")  # 큰 화면(최대화 상태)으로 열어 편집하기 편하게
        except tk.TclError:
            pass

    def _build_ui(self):
        top = tk.Frame(self.win, padx=10, pady=8)
        top.pack(fill="x")

        tk.Label(
            top,
            text="사진을 클릭해 선택(Shift+클릭으로 범위 선택)한 뒤 '선택 위로/아래로' 버튼이나 "
                 "마우스 드래그로 순서를 바꾸세요.\nDelete 키: 선택한 사진 제외 표시  |  Ctrl+Z: 실행 취소",
            fg="#555555", justify="left",
        ).pack(side="left")

        btn_frame = tk.Frame(top)
        btn_frame.pack(side="right")
        tk.Button(btn_frame, text="선택 위로", command=lambda: self._move_selected(-1)).pack(side="left", padx=3)
        tk.Button(btn_frame, text="선택 아래로", command=lambda: self._move_selected(1)).pack(side="left", padx=3)
        tk.Button(btn_frame, text="선택 해제", command=self._clear_selection).pack(side="left", padx=3)
        tk.Button(btn_frame, text="닫기 (변경 취소)", command=self._on_cancel).pack(side="left", padx=3)
        tk.Button(
            btn_frame, text="최종 결과폴더로 보내기", command=self._confirm,
            bg="#2f7dd1", fg="white", font=("", 10, "bold"),
        ).pack(side="left", padx=(12, 0))

        self.status_label = tk.Label(self.win, text="", anchor="w", padx=10)
        self.status_label.pack(fill="x")

        body = tk.Frame(self.win)
        body.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(body)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

    # ------------------------------------------------------------------
    # 위젯/썸네일 준비 (한 번만 생성 후 재사용)
    # ------------------------------------------------------------------
    def _preload_thumbnails(self):
        for item in self.items:
            try:
                img = Image.open(item.extracted_path)
                img.thumbnail(self.THUMB_SIZE)
                photo = ImageTk.PhotoImage(img)
                self.thumb_cache.append(photo)
                self.thumb_images[id(item)] = photo
            except Exception:
                self.thumb_images[id(item)] = None

    def _build_cells(self):
        for item in self.items:
            cell, badge = self._make_cell(item)
            self.cells[id(item)] = cell
            self.badges[id(item)] = badge

    def _make_cell(self, item: core.PhotoItem):
        cell = tk.Frame(
            self.inner, highlightthickness=3,
            highlightbackground=self.NORMAL_BORDER, highlightcolor=self.NORMAL_BORDER, bg="white",
        )

        badge = tk.Label(cell, text="", bg=self.SELECTED_BORDER, fg="white", font=("", 9, "bold"), width=3)
        badge.pack(anchor="w")

        photo = self.thumb_images.get(id(item))
        if photo is not None:
            thumb_label = tk.Label(cell, image=photo, bg="white")
        else:
            thumb_label = tk.Label(cell, text="(미리보기 실패)", width=18, height=8, bg="white")
        thumb_label.pack()

        name_label = tk.Label(
            cell, text=item.output_name or item.display_name, wraplength=self.THUMB_SIZE[0], bg="white",
        )
        name_label.pack()

        for w in (cell, badge, thumb_label, name_label):
            w.item_ref = item
            w.bind("<ButtonPress-1>", self._on_press)
            w.bind("<B1-Motion>", self._on_motion)
            w.bind("<ButtonRelease-1>", self._on_release)

        return cell, badge

    # ------------------------------------------------------------------
    # 배치 (창 크기에 맞춘 열 수 계산 + 재배치, 위젯은 그대로 재사용)
    # ------------------------------------------------------------------
    def _on_canvas_resize(self, event):
        self._recompute_columns()

    def _recompute_columns(self, force: bool = False):
        width = self.canvas.winfo_width()
        if width <= 1:
            width = int(self.win.winfo_screenwidth() * 0.85)
        cell_w = self.THUMB_SIZE[0] + self.CELL_EXTRA_W
        cols = max(self.COLUMNS_MIN, width // cell_w)
        if force or cols != self.columns:
            self.columns = cols
            self._relayout()

    def _relayout(self):
        for i, item in enumerate(self.items):
            r, c = divmod(i, self.columns)
            self.cells[id(item)].grid(row=r, column=c, padx=self.CELL_PAD, pady=self.CELL_PAD)
            self.badges[id(item)].config(text=str(i + 1))
        self.canvas.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._update_status()

    def _update_status(self):
        text = f"전체 {len(self.items)}장  |  선택 {len(self.selected)}장"
        if self.deleted_items:
            text += f"  |  제외 표시 {len(self.deleted_items)}장(확정 시 삭제됨)"
        self.status_label.config(text=text)

    # ------------------------------------------------------------------
    # 실행 취소 (Ctrl+Z)
    # ------------------------------------------------------------------
    def _push_history(self):
        self.history.append((list(self.items), list(self.deleted_items)))
        if len(self.history) > 50:
            self.history.pop(0)

    def _on_undo(self, event=None):
        if not self.history:
            return
        self.items, self.deleted_items = self.history.pop()
        self.selected.clear()
        self.anchor_item = None
        self._relayout()
        self._update_selection_visual()

    # ------------------------------------------------------------------
    # Delete 키: 선택한 사진을 목록에서 빼고 삭제 예정으로 표시 (실제 파일 삭제는 확정 시점)
    # ------------------------------------------------------------------
    def _on_delete_key(self, event=None):
        if not self.selected:
            return
        self._push_history()
        to_remove = [it for it in self.items if it in self.selected]
        for item in to_remove:
            self.cells[id(item)].grid_forget()
        self.items = [it for it in self.items if it not in self.selected]
        self.deleted_items.extend(to_remove)
        self.selected.clear()
        self.anchor_item = None
        self._relayout()

    # ------------------------------------------------------------------
    # 선택 (클릭 토글 / Shift+클릭 범위 선택) - 위젯을 다시 만들지 않고 테두리 색만 갱신
    # ------------------------------------------------------------------
    def _border_color(self, item) -> str:
        return self.SELECTED_BORDER if item in self.selected else self.NORMAL_BORDER

    def _set_cell_border(self, item, color: str):
        cell = self.cells.get(id(item))
        if cell:
            cell.configure(highlightbackground=color, highlightcolor=color)

    def _update_selection_visual(self):
        for item in self.items:
            self._set_cell_border(item, self._border_color(item))
        self._update_status()

    def _clear_selection(self):
        self.selected.clear()
        self.anchor_item = None
        self._update_selection_visual()

    def _handle_click_selection(self, item, shift_held: bool):
        if shift_held and self.anchor_item is not None and self.anchor_item in self.items:
            i1 = self.items.index(self.anchor_item)
            i2 = self.items.index(item)
            lo, hi = min(i1, i2), max(i1, i2)
            self.selected = set(self.items[lo:hi + 1])
        else:
            if item in self.selected:
                self.selected.discard(item)
            else:
                self.selected.add(item)
            self.anchor_item = item
        self._update_selection_visual()

    def _move_selected(self, direction: int):
        if not self.selected:
            return
        idxs = sorted(i for i, it in enumerate(self.items) if it in self.selected)
        if direction < 0 and idxs[0] == 0:
            return
        if direction > 0 and idxs[-1] == len(self.items) - 1:
            return
        self._push_history()
        if direction < 0:
            for i in idxs:
                self.items[i - 1], self.items[i] = self.items[i], self.items[i - 1]
        else:
            for i in reversed(idxs):
                self.items[i + 1], self.items[i] = self.items[i], self.items[i + 1]
        self._relayout()

    # ------------------------------------------------------------------
    # 드래그 (선택된 사진 함께 이동 + 놓일 위치 실시간 표시)
    # ------------------------------------------------------------------
    def _widget_item(self, widget):
        w = widget
        while w is not None:
            item = getattr(w, "item_ref", None)
            if item is not None:
                return item
            if w is self.inner or w is self.win:
                return None
            w = w.master
        return None

    def _on_press(self, event):
        self.drag_item = self._widget_item(event.widget)
        self.drag_start = (event.x_root, event.y_root)
        self.dragging = False
        self._shift_held = bool(event.state & 0x0001)

    def _on_motion(self, event):
        if self.drag_item is None or self.drag_start is None:
            return
        dx = event.x_root - self.drag_start[0]
        dy = event.y_root - self.drag_start[1]
        if not self.dragging and (abs(dx) > 6 or abs(dy) > 6):
            self.dragging = True
            self.win.config(cursor="fleur")
        if self.dragging:
            self._update_drop_target(event)

    def _update_drop_target(self, event):
        target_widget = self.win.winfo_containing(event.x_root, event.y_root)
        target_item = self._widget_item(target_widget) if target_widget else None
        if target_item is self.hover_item:
            return
        if self.hover_item is not None:
            self._set_cell_border(self.hover_item, self._border_color(self.hover_item))
        self.hover_item = target_item
        if target_item is not None and target_item is not self.drag_item:
            self._set_cell_border(target_item, self.DROP_TARGET_BORDER)

    def _on_release(self, event):
        if self.drag_item is None:
            return
        if not self.dragging:
            self._handle_click_selection(self.drag_item, self._shift_held)
        else:
            self.win.config(cursor="")
            if self.hover_item is not None:
                self._set_cell_border(self.hover_item, self._border_color(self.hover_item))
            self._reorder_to(self.drag_item, self.hover_item)
            self.hover_item = None

        self.drag_item = None
        self.drag_start = None
        self.dragging = False

    def _on_cancel(self):
        self.win.destroy()
        self.app._on_order_editor_closed()

    def _reorder_to(self, dragged_item, target_item):
        if target_item is None or target_item is dragged_item:
            return
        # 끌기 시작한 사진이 현재 선택 목록에 포함돼 있으면, 선택된 사진 전체를 함께 옮긴다.
        moving = set(self.selected) if dragged_item in self.selected and self.selected else {dragged_item}
        if target_item in moving:
            return
        self._push_history()
        moving_ordered = [it for it in self.items if it in moving]
        remaining = [it for it in self.items if it not in moving]
        target_pos = remaining.index(target_item)
        self.items = remaining[:target_pos] + moving_ordered + remaining[target_pos:]
        self._relayout()

    def _confirm(self):
        total_kept = len(self.items)
        total_deleted = len(self.deleted_items)
        zip_paths = [p for p in self.source_zip_paths if os.path.isfile(p)]

        msg = f"현재 화면에 보이는 순서대로 {total_kept}장의 파일명을 변경합니다."
        if total_deleted:
            msg += f"\nDelete로 제외 표시한 {total_deleted}장은 결과 폴더에서 완전히 삭제됩니다."
        if zip_paths:
            names = ", ".join(Path(p).name for p in zip_paths)
            msg += f"\n원본 zip 파일({names})은 휴지통으로 보내집니다."
        msg += "\n계속할까요?"
        if not messagebox.askyesno(APP_TITLE, msg):
            return

        width = max(3, len(str(total_kept))) if total_kept else 3
        try:
            # 1단계: 이름 충돌을 피하기 위해 남길 사진들을 전부 임시 이름으로 바꾼다.
            temp_names = []
            for item in self.items:
                src = self.output_dir / item.output_name
                tmp_name = f"__order_tmp_{uuid.uuid4().hex}{Path(item.output_name).suffix}"
                src.rename(self.output_dir / tmp_name)
                temp_names.append(tmp_name)

            # 2단계: 순번_원본파일명 형태의 최종 이름으로 바꾼다.
            for idx, (item, tmp_name) in enumerate(zip(self.items, temp_names), start=1):
                base = _strip_order_prefix(item.output_name)
                final_name = f"{idx:0{width}d}_{base}"
                (self.output_dir / tmp_name).rename(self.output_dir / final_name)
                item.output_name = final_name

            # 3단계: Delete로 제외 표시한 사진들은 이 시점에 실제로 삭제한다.
            delete_errors = []
            for item in self.deleted_items:
                try:
                    (self.output_dir / item.output_name).unlink(missing_ok=True)
                except Exception as e:
                    delete_errors.append(f"{item.output_name}: {e}")

            # 4단계: 원본 zip 파일을 휴지통으로 보낸다 (완전 삭제가 아니라 복구 가능하게).
            zip_errors = []
            for zp in zip_paths:
                try:
                    send2trash(zp)
                except Exception as e:
                    zip_errors.append(f"{Path(zp).name}: {e}")
        except Exception as e:
            messagebox.showerror(APP_TITLE, f"파일명 변경 중 오류가 발생했습니다:\n{e}")
            return

        # 문제가 없었으면 완료 팝업 없이 곧바로 FastStone(사진편집기)만 뜨게 한다.
        # 삭제 실패 등 사람이 알아야 할 문제가 있을 때만 경고 팝업을 보여준다.
        if delete_errors or zip_errors:
            warning = "일부 작업이 실패했습니다."
            if delete_errors:
                warning += "\n\n일부 사진 삭제 실패:\n" + "\n".join(delete_errors)
            if zip_errors:
                warning += "\n\n일부 zip 삭제 실패:\n" + "\n".join(zip_errors)
            messagebox.showwarning(APP_TITLE, warning)
        self.app._open_result_viewer(str(self.output_dir))
        self.win.destroy()
        self.app._on_order_editor_closed()
        self.app._hide_to_tray_if_active()


def main(auto_zip_paths: list | None = None, start_hidden: bool = False):
    if _HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = DedupApp(root)
    if start_hidden:
        # Windows 시작 시 "--tray"로 자동 실행되는 경우: 창을 띄우지 않고 트레이 감시만 시작한다.
        # (DedupApp.__init__의 _maybe_resume_watch()가 이미 감시/트레이를 켜 둔 상태다)
        root.withdraw()
    if auto_zip_paths:
        root.after(200, lambda: app.run_auto(auto_zip_paths))
    root.mainloop()


if __name__ == "__main__":
    main()
```

### `requirements.txt`
```text
Pillow>=10.0.0
imagehash>=4.3.1
tkinterdnd2>=0.3.0
send2trash>=1.8.0
pystray>=0.19.0
pyinstaller>=6.0.0
```

### `build.bat`
```bat
@echo off
REM 중복 사진 정리 도구 - exe 빌드 + 설치 프로그램(installer) 빌드 스크립트
REM 사용법: venv 안에서 이 배치파일을 실행하세요.
REM   PhotoDedup> venv\Scripts\activate
REM   PhotoDedup> build.bat

pyinstaller --noconfirm --onefile --windowed --name PhotoDedup ^
    --collect-all tkinterdnd2 ^
    --collect-all imagehash ^
    --collect-all pystray ^
    main.py

echo.
echo exe 빌드 완료: dist\PhotoDedup.exe

REM Inno Setup(ISCC.exe)이 설치되어 있으면 설치 프로그램(Setup.exe)도 함께 빌드합니다.
REM 설치: winget install JRSoftware.InnoSetup  (https://jrsoftware.org/isinfo.php)
set ISCC="%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% installer.iss
    echo 설치 프로그램 빌드 완료: installer_output\PhotoDedup_Setup_1.1.4.exe
) else (
    echo [안내] Inno Setup(ISCC.exe)을 찾지 못해 설치 프로그램은 건너뛰었습니다.
    echo         "winget install JRSoftware.InnoSetup" 설치 후 다시 실행하면 설치 프로그램까지 만들어집니다.
)

pause
```

### `installer.iss`
```ini
; 중복 사진 정리 도구 (PhotoDedup) - Inno Setup 설치 스크립트
; 빌드: "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" installer.iss

#define MyAppName "중복 사진 정리 도구 (PhotoDedup)"
#define MyAppVersion "1.1.4"
#define MyAppExeName "PhotoDedup.exe"

[Setup]
AppId={{8F1E9C2E-7B3A-4C5D-9E1F-2A6B8C4D7E10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\PhotoDedup
DefaultGroupName=PhotoDedup
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=PhotoDedup_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "contextmenu"; Description: "탐색기에서 zip 파일 우클릭 시 ""중복 사진 정리 도구로 열기"" 메뉴 추가 (zip의 기본 열기 동작은 바뀌지 않습니다)"; GroupDescription: "탐색기 통합"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; zip의 기본(더블클릭) 연결 프로그램은 그대로 두고, 우클릭 메뉴에 항목만 추가한다.
Root: HKCR; Subkey: "SystemFileAssociations\.zip\shell\PhotoDedup"; ValueType: string; ValueName: ""; ValueData: "중복 사진 정리 도구로 열기"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKCR; Subkey: "SystemFileAssociations\.zip\shell\PhotoDedup"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: contextmenu
Root: HKCR; Subkey: "SystemFileAssociations\.zip\shell\PhotoDedup\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
```

---

## 7. 데이터베이스/스키마

**해당 없음.** 이 프로그램은 데이터베이스를 전혀 사용하지 않습니다. 모든 상태는 프로그램 실행 중
메모리 안에서만 유지되며(파이썬 `dataclass` 객체들), 영구 저장되는 것은 아래 두 가지뿐입니다.

1. 처리 결과 사진 파일들 — 바탕화면의 `결과_유니크사진_YYYYMMDD_HHMMSS` 폴더
2. (선택) Inno Setup 설치 시 등록되는 레지스트리 값 몇 개 — 위 `installer.iss`의 `[Registry]` 섹션 참고 (제거 시 자동 삭제됨)

마이그레이션 파일, 시드 데이터도 없습니다.

---

## 8. 검증 방법

### 8-1. 테스트용 zip 만들기
아래 스크립트를 `make_test_zip.py`로 저장하고 실행하면, 다음이 섞인 검증용 zip이 만들어집니다:
- 완전히 같은 사진이 2번 들어있는 경우 (`001_first.jpg`, `003_exact_copy.jpg`)
- 같은 사진을 재압축(화질만 다르게)한 경우 (`002_recompressed.jpg`)
- 서로 다른 고유 사진 2장 (`004_green.png`, `006_blue.jpg`)
- 이미지가 아닌 파일 (`readme.txt` - 무시되어야 함)
- 손상된 이미지 파일 (`005_broken.jpg` - "읽기 실패"로 처리되어야 함)

```python
import io
import random
import zipfile
from PIL import Image, ImageDraw

def make_img(seed, size=(200, 200)):
    rnd = random.Random(seed)
    img = Image.new("RGB", size, (20, 20, 20))
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x0, y0 = rnd.randint(0, 180), rnd.randint(0, 180)
        x1, y1 = x0 + rnd.randint(5, 40), y0 + rnd.randint(5, 40)
        color = (rnd.randint(0, 255), rnd.randint(0, 255), rnd.randint(0, 255))
        d.rectangle([x0, y0, x1, y1], fill=color)
    return img

buf_a = io.BytesIO()
img_a = make_img("A")
img_a.save(buf_a, format="JPEG", quality=95)
bytes_a = buf_a.getvalue()

buf_a2 = io.BytesIO()
img_a.save(buf_a2, format="JPEG", quality=70)
bytes_a2 = buf_a2.getvalue()

buf_b = io.BytesIO()
img_b = make_img("B")
img_b.save(buf_b, format="PNG")
bytes_b = buf_b.getvalue()

buf_c = io.BytesIO()
img_c = make_img("C")
img_c.save(buf_c, format="JPEG", quality=95)
bytes_c = buf_c.getvalue()

corrupted = b"not a real image"

import sys
out = sys.argv[1] if len(sys.argv) > 1 else "test_photos.zip"
with zipfile.ZipFile(out, "w") as zf:
    zf.writestr("001_first.jpg", bytes_a)
    zf.writestr("002_recompressed.jpg", bytes_a2)
    zf.writestr("003_exact_copy.jpg", bytes_a)
    zf.writestr("readme.txt", b"not an image, should be ignored")
    zf.writestr("004_green.png", bytes_b)
    zf.writestr("005_broken.jpg", corrupted)
    zf.writestr("006_blue.jpg", bytes_c)

print("done:", out)
```

### 8-2. CLI로 핵심 로직 검증
```bash
venv\Scripts\activate
python make_test_zip.py test_photos.zip
python main.py test_photos.zip --threshold 5
```

**기대되는 출력 (핵심 부분)**:
```
>> 압축 해제 중...
>> 이미지 해시 계산 중...
   해시 계산 6/6
>> 중복 그룹 분석 중...
>> 바탕화면에 결과 폴더 생성 중...
>> 완료

전체 사진 수     : 6
고유 사진 수     : 3
제거된 중복 수   : 2
읽기 실패 수     : 1
읽기 실패 목록:
   - 005_broken.jpg (test_photos.zip/005_broken.jpg): UnidentifiedImageError: cannot identify image file ...

결과 폴더(바탕화면): C:\Users\<사용자명>\Desktop\결과_유니크사진_YYYYMMDD_HHMMSS
```
이 결과 폴더 안에는 `001_first.jpg`, `004_green.png`, `006_blue.jpg` 3개 파일만 있어야 합니다
(재압축본과 완전동일 복사본은 제외되고, 손상 파일은 아예 안 들어가고, `readme.txt`는 무시됩니다).
**이 숫자(전체 6 / 고유 3 / 제거 2 / 읽기실패 1)와 정확히 일치해야 core.py 로직이 올바르게
재현된 것입니다.**

### 8-3. GUI 동작 확인
```bash
python main.py
```
1. "파일 선택..."을 눌러 `test_photos.zip`을 선택 (기본 경로가 다운로드 폴더로 열리는지 확인)
2. "처리 시작" 클릭 → 진행률 표시줄이 움직이고 잠시 후 요약이 표시되는지 확인
3. "제외된 중복 사진 미리보기" 클릭 → 그룹 1개(유지 1장 + 제외 2장)가 보이는지, 마우스로 드래그해서 스크롤되는지 확인
4. "결과 폴더 열기" 클릭 → 사진 순서 정리 창이 (최대화 상태로) 뜨는지 확인
5. 사진 1장을 클릭 → 파란 테두리로 선택되는지, Shift+클릭으로 범위 선택되는지 확인
6. 사진을 마우스로 드래그 → 놓일 위치가 주황 테두리로 표시되는지 확인
7. 사진 선택 후 Delete → 화면에서 사라지고 상태표시줄에 "제외 표시 1장"이 뜨는지 확인
8. Ctrl+Z → 방금 지운 사진이 되돌아오는지 확인
9. "최종 결과폴더로 보내기" 클릭 → 확인 팝업(zip 삭제 안내 포함)이 뜨고, 확인하면 결과 폴더의 파일명이
   `001_...`, `002_...` 형태로 바뀌고, FastStone Image Viewer(설치돼 있으면) 또는 탐색기가 열리는지 확인

### 8-4. exe 빌드 검증
```bash
pyinstaller --noconfirm --onefile --windowed --name PhotoDedup ^
    --collect-all tkinterdnd2 --collect-all imagehash --collect-all pystray main.py
dist\PhotoDedup.exe
```
- 콘솔 창 없이 GUI 창만 뜨는지 확인
- `dist\PhotoDedup.exe test_photos.zip` 처럼 zip 경로를 인자로 주고 실행하면, 파일 선택 → 처리 시작 →
  결과 폴더 열기까지 **자동으로** 진행되고 "최종 결과폴더로 보내기"에서 멈추는지 확인 (자동실행 기능 검증)

### 8-5. 설치 프로그램 빌드/설치/제거 검증
```powershell
"%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" installer.iss
installer_output\PhotoDedup_Setup_1.1.4.exe
```
- 설치 마법사에서 "탐색기에서 zip 파일 우클릭 시... 메뉴 추가" 체크박스가 보이는지 확인
- 설치 후 임의의 zip 파일을 우클릭했을 때 "중복 사진 정리 도구로 열기" 메뉴가 보이는지, 클릭 시 자동실행되는지 확인
- zip의 **기본(더블클릭) 프로그램은 바뀌지 않았는지** 확인 (설치 전/후 동일해야 함)
- "프로그램 추가/제거"에서 제거했을 때 설치 폴더, 시작메뉴/바탕화면 바로가기, 위 컨텍스트 메뉴
  레지스트리가 모두 깨끗이 삭제되는지 확인 (`HKCU\...\Run`에 자동 감시를 등록한 적이 있다면 그 값도
  프로그램 제거와 별개로 GUI의 "감시 끄기"로 미리 해제해두는 것을 권장)

### 8-6. "파일자동읽기 폴더지정" (감시 폴더 자동 처리) 검증
1. GUI 하단 "파일자동읽기 폴더지정"에서 빈 테스트 폴더를 지정하고 "저장" 클릭 →
   "감시 중: ..." 상태로 바뀌고 안내 팝업이 뜨는지 확인
2. 그 폴더에 사진이 든 zip 파일을 복사해 넣기 → 몇 초 안에 자동으로 파일 선택 → 처리 시작 →
   결과 폴더 열기(순서 정리 화면)까지 자동 진행되는지 확인 ("최종 결과폴더로 보내기"는 여전히
   사람이 눌러야 함)
3. 메인 창을 닫기(X버튼) → 프로그램이 완전히 종료되지 않고 트레이 아이콘에 남아있는지 확인,
   트레이 아이콘 우클릭 → "창 열기"로 다시 창이 뜨는지, "완전히 종료"로 트레이까지 종료되는지 확인
4. `HKCU:\Software\Microsoft\Windows\CurrentVersion\Run`에 `PhotoDedup` 값이 등록되었는지 확인
   (`Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run`)
5. GUI에서 "감시 끄기" 클릭 → 위 Run 값이 삭제되고, 폴더에 새 zip을 넣어도 더는 자동 실행되지
   않는지 확인
6. (v1.1.1부터, 중복 실행 방지 검증) 감시가 켜진 채로 프로그램이 떠 있는 상태에서, 같은 zip을
   `PhotoDedup.exe "경로.zip"` 형태로 다시 한 번 실행 → 새 창이 뜨지 않고(프로세스는 곧바로
   종료됨), 기존에 떠 있던 창 하나가 그 zip을 처리하는지 확인 (9-10번 트러블슈팅 참고)
7. (v1.1.2부터, 조용한 처리 검증) `PhotoDedup.exe --tray`로 감시만 켠 채(창 없음) 감시 폴더에
   zip을 넣기 → 몇 초 안에 결과 폴더가 바탕화면에 생기지만(`Get-ChildItem`으로 확인) **창은 전혀
   뜨지 않아야** 한다(`Get-Process PhotoDedup | Select MainWindowTitle`이 비어 있어야 함).
   이 상태에서 `PhotoDedup.exe`를 인자 없이 다시 실행(바탕화면 아이콘 더블클릭과 동일) →
   그제서야 창이 나타나고, 방금 조용히 처리된 결과가 "3. 결과"에 그대로 표시되는지 확인.
   트레이 아이콘을 더블클릭해도 같은 방식으로 창이 열리는지 확인(9-10, 9-11번 참고)

> Git Bash(MSYS)에서 설치 프로그램을 커맨드라인 옵션과 함께 직접 실행해 무음 설치를 테스트하려면
> `/VERYSILENT` 대신 `//VERYSILENT`(슬래시 두 개)를 써야 합니다. 자세한 이유는 9번 트러블슈팅 참고.

---

## 9. 알려진 이슈 및 트러블슈팅

### 9-1. Git Bash에서 설치 프로그램에 `/VERYSILENT` 같은 옵션을 주면 무시됨
- **증상**: `PhotoDedup_Setup_1.0.0.exe /VERYSILENT /DIR=...`를 Git Bash에서 실행하면 무음 설치가 안 되고
  일반 설치 마법사가 뜨거나, 예상치 못한 동작(자동으로 앱이 실행되는 등)이 발생함.
- **원인**: Git Bash(MSYS)가 `/`로 시작하는 인자를 유닉스 경로로 착각해서, 예를 들어 `/VERYSILENT`를
  `C:/Program Files/Git/VERYSILENT` 같은 엉뚱한 경로 문자열로 자동 치환해버림. `/DIR=C:\...`처럼 `=` 뒤에
  이미 `C:\`로 시작하는 값이 오는 경우는 치환되지 않아 정상 동작하는 것과 대조적으로, `/VERYSILENT`처럼
  `=`이 없는 단독 스위치만 이 문제가 생김.
- **해결**: Inno Setup이 이 문제를 위해 지원하는 `//VERYSILENT`, `//SUPPRESSMSGBOXES` 처럼 **슬래시
  두 개**로 시작하는 대체 표기를 사용하면 정상적으로 인식됨. (PowerShell이나 cmd.exe, 또는 탐색기에서
  더블클릭 실행할 때는 이 문제가 아예 없음 - 순수 개발/테스트 편의를 위한 이슈였음.)

### 9-2. PyInstaller `--windowed` 빌드는 콘솔 출력이 안 보임
- **증상**: `dist\PhotoDedup.exe`를 실행했을 때 CLI 옵션(`--threshold` 등)을 줘도 콘솔 창이 없어서
  결과를 볼 수 없음.
- **원인**: `--windowed` 플래그로 빌드하면 콘솔이 완전히 분리되어(GUI 전용 서브시스템) `print()` 출력이
  어디에도 보이지 않음.
- **해결**: CLI 동작을 확인하고 싶을 때는 배포용 exe 대신 `python main.py ...`로 직접 실행할 것. exe는
  항상 GUI 전용으로 쓰는 것을 전제로 설계함.

### 9-3. tkinter `dataclass`가 기본값으로는 `set()`에 못 들어감
- **증상**: `OrderEditor`에서 선택된 사진들을 `set()`에 담으려는데 `TypeError: unhashable type: 'PhotoItem'`
  발생.
- **원인**: `@dataclass`는 기본적으로 `eq=True`를 생성하는데, `eq=True`이면서 `frozen=False`인 경우
  파이썬이 자동으로 `__hash__ = None`으로 만들어버려서 해시 불가능한 객체가 됨.
- **해결**: `app/core.py`의 `PhotoItem`을 `@dataclass(eq=False)`로 선언해서 기본 객체 동일성(identity)
  비교/해시를 쓰도록 함. 같은 사진의 서로 다른 인스턴스를 값으로 비교할 이유가 없으므로 이 방식이 적절함.

### 9-4. tkinter 자식 위젯의 마우스 이벤트가 부모(Canvas)로 자동 전파되지 않음
- **증상**: Canvas 위에 마우스 드래그로 스크롤(그랩 스크롤)을 구현했는데, Canvas의 빈 여백에서는
  동작하지만 그 위에 올려둔 Label/Frame 위에서 드래그하면 스크롤이 안 됨.
- **원인**: tkinter의 마우스 버튼 이벤트(`<ButtonPress-1>` 등)는 이벤트가 발생한 그 위젯에만 전달되고,
  키보드 이벤트와 달리 상위 위젯으로 자동 버블링되지 않음.
- **해결**: `_enable_drag_scroll()`에서 Canvas뿐 아니라 그 안의 모든 자식 위젯에 재귀적으로 동일한
  이벤트 핸들러를 바인딩함. 좌표는 위젯마다 원점(0,0)이 다르므로, 상대좌표(`event.x`/`event.y`) 대신
  화면 전체 기준 절대좌표(`event.x_root`/`event.y_root`)로 델타를 계산해서 어느 위젯에서 이벤트가
  발생하든 일관되게 동작하도록 함. `OrderEditor`의 드래그-재정렬 기능도 같은 원리로 구현.

### 9-5. `send2trash`가 PyInstaller로 빌드했을 때도 정상 동작하는지
- **배경**: `send2trash.win`은 내부적으로 `try: pywin32 사용 / except ImportError: SHFileOperation(ctypes) 사용`
  구조라, `pywin32`를 따로 설치하지 않아도 정상 동작함(레거시 경로 사용). 이 프로젝트의 `requirements.txt`에는
  `pywin32`가 없고, 실제로 pywin32 없이 테스트해서 정상적으로 휴지통 이동이 되는 것을 확인함.
- **주의**: PyInstaller 빌드 로그에 `win32com` 관련 "module not found" 경고가 나올 수 있는데, 이는
  `try/except`로 이미 처리되는 정상적인 폴백 경로라 무시해도 됨 (실제로 빌드/실행 모두 문제없음).

### 9-6. FastStone Image Viewer 경로를 못 찾는 경우
- **증상**: 결과 폴더 확정 후 FastStone이 아니라 탐색기가 열림.
- **원인**: `find_faststone_exe()`가 흔한 설치 경로 2곳과 레지스트리 `App Paths`를 확인하는데, 이례적인
  경로에 설치했거나 아예 설치돼 있지 않으면 못 찾음.
- **해결**: 이건 버그가 아니라 의도된 폴백 동작임 (FastStone은 필수 의존성이 아님). 특정 PC에서 항상
  FastStone을 쓰고 싶다면 `app/gui.py`의 `_FASTSTONE_COMMON_PATHS` 리스트에 실제 설치 경로를 추가하면 됨.

### 9-7. Windows 기본 zip 프로그램(ALZip/Bandizip 등)과 충돌하지 않는지
- **확인 사항**: 이 프로젝트의 zip 우클릭 컨텍스트 메뉴는 `HKCR\SystemFileAssociations\.zip\shell\PhotoDedup`
  에만 항목을 추가하고, `HKCR\.zip`(더블클릭 시 실행될 기본 프로그램)은 절대 수정하지 않음. 개발 중
  실제로 ALZip이 기본 프로그램으로 설정된 PC에서 설치/제거를 테스트했고, 설치 전후로 기본 프로그램이
  전혀 바뀌지 않는 것을 확인함.

### 9-8. (개발 중 발생했던 사고, 재현 시 참고) 휴지통 관련 스크립트 실행 시 주의
- 개발 과정에서 테스트 파일을 정리하던 중 `Clear-RecycleBin -Force`(PowerShell)를 실행해 시스템 휴지통
  **전체**를 비운 적이 있음. 이 프로젝트 코드 자체에는 이런 명령이 전혀 없지만(코드는 `send2trash`로
  개별 파일만 정확히 이동시킴), **재현/테스트 과정에서 휴지통을 다루는 스크립트를 직접 짤 때는
  특정 파일만 지정해서 지우고, 절대 휴지통 전체를 비우는 명령을 쓰지 않도록 주의할 것.**

### 9-9. (수정된 버그) zip이 아닌 파일을 넣었을 때 빈 결과 폴더가 생성되던 문제
- **증상**: zip이 아닌 파일(예: PDF)을 "파일 선택"으로 직접 골랐거나 인자로 넘겼을 때, 처리할 사진이
  하나도 없는데도 바탕화면에 `결과_유니크사진_YYYYMMDD_HHMMSS` 라는 **빈 폴더가 생성**됨.
- **원인**: `core.process_zips()`가 `groups`(중복 그룹 결과)가 비어 있는지 확인하지 않고 항상
  `write_output()`을 호출해 `output_dir.mkdir(...)`부터 실행했기 때문. zip이 아닌 파일은
  `extract_zips()` 안의 `zipfile.ZipFile()`에서 `BadZipFile` 예외로 걸러지긴 하지만, 그 뒤 파이프라인은
  빈 리스트로 계속 진행되어 결국 "결과 없음"인데도 폴더만 만들어버림. (`app/cli.py`의 `argparse`도
  `zips` 인자의 확장자를 검사하지 않아서, 파일만 존재하면 zip이 아니어도 일단 파이프라인에 넘어감.)
- **해결**: `process_zips()`에서 `if groups:` 로 감싸서, 남길 사진이 하나도 없으면 `write_output()`을
  아예 호출하지 않고 `output_dir_str = ""`로 둠. GUI(`_on_process_done`)와 CLI(`main.py` 끝부분)는
  `result.output_dir`이 빈 문자열이면 "처리 가능한 사진이 없어 결과 폴더를 생성하지 않았습니다."라고만
  안내하고, "결과 폴더 열기" 버튼도 비활성화되도록 수정함. 이제 zip이 아닌 파일을 넣으면 바탕화면에
  **아무 흔적도 남지 않음** (폴더도, 파일도 생성 안 됨).

### 9-10. (v1.1.0에서 발생, v1.1.1에서 수정된 버그) "파일자동읽기 폴더지정" 감시 중에 zip을 또 열면 창이 2개 뜨고 처리가 꼬임
- **증상**: 감시를 켜서(트레이 상주) 프로그램이 백그라운드에서 이미 떠 있는 상태에서, 감시 폴더 안의
  zip 파일을 사람이 다시 열면(탐색기 우클릭 "중복 사진 정리 도구로 열기" 등) 완전히 똑같은 창이
  2개 뜨고, 실제로는 둘 다 제대로 처리되지 않는 것처럼 보임(실사용 중 실제로 발생 확인).
- **원인**: 프로그램에 "이미 실행 중인지" 확인하는 장치가 전혀 없었음. `app/gui.py`의
  `DedupApp.__init__()`은 실행될 때마다 무조건 `_maybe_resume_watch()`로 저장된 감시 설정을 다시
  불러와 **자기 자신의 독립적인 `FolderWatcher`를 새로 시작**했음. 그 결과 감시 중인 프로세스가 이미
  떠 있는데 사람이 zip을 또 열면, 그 zip을 처리하려는 새 프로세스가 하나 더 생기고 그 프로세스도
  똑같이 감시를 재개해서 - 두 프로세스가 각자 독립적으로 같은 대상을 처리하려다 같은 결과 폴더에
  동시에 쓰기 작업을 하며 부딪힘.
- **해결**: `app/singleinstance.py`를 새로 추가. Windows 명명된 뮤텍스(`CreateMutexW`)로 "이미 이
  이름의 뮤텍스를 가진 프로세스가 있는지"를 확인해서, 이미 있으면(`GetLastError() ==
  ERROR_ALREADY_EXISTS`) 새 프로세스는 GUI를 아예 띄우지 않고 넘겨받은 zip 경로들을
  `%APPDATA%\PhotoDedup\pending_zips.json`에 적어두기만 하고 즉시 종료함(`main.py`의
  `_launch_gui()`). 이미 떠 있던(유일한) 인스턴스는 `PendingRequestWatcher`로 이 파일을 1.5초
  주기로 확인하다가 새 요청을 발견하면 기존 감시 폴더 처리와 동일한 대기열(`_watch_pending`)에
  넣어 순서대로 처리함. 이제 감시가 켜진 상태에서 zip을 몇 번을 다시 열어도 창은 항상 1개만 뜨고,
  그 하나의 창이 요청을 순서대로 처리한다.

### 9-11. (v1.1.2 개선) 다운로드할 때마다 프로그램 창이 튀어나오는 것을 막고, 더블클릭으로만 열리게 함
- **요청 배경**: 감시 폴더에 zip이 들어올 때마다 창이 자동으로 튀어나오는 게(v1.1.0/v1.1.1 동작)
  다른 작업 중에 방해가 된다는 실사용 피드백.
- **변경**: `app/gui.py`의 `run_auto()`에 `silent` 매개변수를 추가. 감시 폴더에서 자동 감지한
  경우(`_handle_watched_zip`)는 `silent=True`로 호출되어 창을 띄우지 않고(`root.deiconify()`
  호출 안 함) 순서 정리 창(OrderEditor)도 자동으로 열지 않는다. 처리 결과(`self.result`)는
  메모리에 남아있으므로, 나중에 창을 열면 "결과 폴더 열기"로 확인/확정할 수 있다. 반대로
  사람이 직접 zip을 열려고 한 경우(`_handle_external_request`에 zip 경로가 있는 경우, 또는
  탐색기 우클릭으로 바로 실행된 경우)는 `silent=False`로 창이 즉시 나타난다.
- **창을 다시 여는 방법 2가지**: (1) 바탕화면/시작메뉴 아이콘을 더블클릭 - 이미 실행 중인
  인스턴스에 "창만 보여달라"는 요청이 전달됨(`app/singleinstance.py`). (2) 트레이 아이콘을
  더블클릭 - `app/tray.py`에서 "창 열기" 메뉴 항목을 `default=True`로 지정해서, 트레이 아이콘의
  기본 동작(더블클릭)이 곧바로 창 열기가 되도록 함.
- **(v1.1.4 추가)** "최종 결과폴더로 보내기" 확정이 성공하면 안내 팝업 없이 곧바로
  FastStone(사진편집기)만 화면에 남고, 메인 창은 트레이 아이콘이 떠 있으면 다시 숨겨진다
  (`OrderEditor._confirm()` 끝에서 `self.app._hide_to_tray_if_active()` 호출). 삭제 실패 등
  예외적인 문제가 있을 때만 경고 팝업이 뜬다. "계속할까요?" 확인 팝업은 그대로 유지된다.

### 9-12b. (개발 환경 참고사항) GUI 버튼을 PowerShell로 자동 클릭해서 검증하려 하면 신뢰할 수 없음
- **증상**: `SetCursorPos`/`mouse_event`/`SendInput`으로 화면 좌표를 클릭하거나 심지어
  `SendMessage`로 `BM_CLICK`을 보내도, tkinter 버튼의 `command` 콜백이 실행되지 않는 경우가
  있었음. `SetForegroundWindow`를 호출해도 실제로 포그라운드가 그 창으로 안 바뀔 때도 있었음
  (Windows가 "포그라운드를 뺏는 것"을 다른 프로세스가 함부로 못 하게 막는 보안 동작).
- **결론**: 이 환경에서 실제 OS 레벨 클릭 자동화로 tkinter GUI를 검증하는 것은 신뢰할 수 없다.
  버튼 동작(콜백 로직)을 검증할 때는 `unittest.mock`으로 위젯의 `command`가 호출하는 메서드를
  **직접 호출**해서(예: `editor._confirm()`), `messagebox`/서브프로세스 호출 등을
  `mock.patch`로 가로채 확인하는 방식이 훨씬 안정적이다. 화면에 실제로 보이는지 자체를
  확인해야 할 때만(버튼 클릭이 아니라 레이아웃/텍스트 확인 목적) 스크린샷 방식을 쓰고,
  버튼을 "누르는" 동작 자체는 자동화하지 말 것.

### 9-12. (v1.1.0~v1.1.2에서 발생, v1.1.3에서 수정된 버그) 같은 파일명으로 zip을 다시 다운로드해도 감시가 반응하지 않음
- **증상**: 감시 폴더에 이미 같은 이름의 zip이 있던 상태에서, 그 이름 그대로 다시
  다운로드(덮어쓰기)해도 감시가 전혀 반응하지 않음 - 실사용 중 같은 원본 파일을 반복
  테스트/재다운로드하다가 발견.
- **원인**: `app/watcher.py`의 `FolderWatcher`가 "이미 본 파일"을 파일명만으로
  기억(`_seen: set[str]`)했음. 감시가 시작되기 전부터 폴더에 있던 파일은 처음부터
  `_seen`에 들어가 있으므로, 그 파일이 나중에 같은 이름으로 통째로 덮어써져도(내용은
  완전히 다른 새 zip인데도) 이름이 같다는 이유만으로 계속 무시됨.
- **해결**: 파일명 대신 **수정시각(mtime)**을 기억하도록 변경(`_known_mtimes: dict[str, float]`).
  매 스캔마다 현재 mtime과 마지막으로 기억해 둔 mtime을 비교해서, 마지막에 처리(또는 무시 확정)한
  이후로 mtime이 갱신됐으면 "바뀐 파일"로 보고 다시 처리한다. 감시 시작 시점에 있던 파일은
  그 시점의 mtime이 baseline으로 기록되므로 "그 상태 그대로 있는 동안"은 여전히 무시되고,
  같은 이름으로 다시 다운로드되어 mtime이 갱신되는 순간부터는 정상적으로 감지된다.
