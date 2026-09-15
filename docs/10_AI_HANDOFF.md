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
```

## 주요 파일

| 파일 | 역할 |
|---|---|
| `main.py` | 진입점, 실행모드 분기 |
| `app/core.py` | 핵심 로직 (`process_zips()`가 전체 진입점) |
| `app/gui.py` | GUI 전체 (`DedupApp`, `OrderEditor`) |
| `app/cli.py` | CLI |
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
