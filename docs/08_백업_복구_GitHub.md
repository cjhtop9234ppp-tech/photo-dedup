# 08. 백업 · 복구 · GitHub

## 현재 GitHub 저장소 상태 (실제 확인, `git remote -v` / `git log` / `git status`)

| 항목 | 값 |
|---|---|
| Repository | `cjhtop9234ppp-tech/photo-dedup` — https://github.com/cjhtop9234ppp-tech/photo-dedup |
| Visibility | **Private** |
| Branch | `master` (origin/master와 동기화됨) |
| Remote | `origin` → `https://github.com/cjhtop9234ppp-tech/photo-dedup.git` |
| 최근 커밋 | `73fb964` "Fill in actual repository clone URL in README" |
| Working Tree | Clean (커밋 안 된 변경사항 없음) |
| Release | `v1.0.0` (Asset: `PhotoDedup_Setup_1.0.0.exe`) |

## `.gitignore`로 GitHub에 올라가지 않는 것 (실제 내용)

```gitignore
venv/
build/
dist/
installer_output/
__pycache__/
*.pyc
PhotoDedup.spec
결과_유니크사진_*/
결과_유니크사진_*_리포트.*
옵시디언_노트/
PhotoDedup_SKILL_역분석_MASTER/
```

`옵시디언_노트/`, `PhotoDedup_SKILL_역분석_MASTER/`는 실제 업무 맥락이 언급될 수 있는 개발
메모라 의도적으로 제외했습니다. 이 문서가 들어있는 `docs/` 폴더는 **아직 `.gitignore`에
없으므로, 별도로 커밋하지 않는 한 GitHub에 올라가지 않은 상태**입니다(작성 시점 기준. 커밋
여부는 사용자가 직접 결정해야 함) → `확인 필요`(이후 실제로 커밋했는지는 그때그때 `git log`로 확인).

## Clone (새 PC에서 처음 받을 때)

```bash
git clone https://github.com/cjhtop9234ppp-tech/photo-dedup.git
cd photo-dedup
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Private 저장소이므로 GitHub 인증(로그인 또는 `gh auth login` / SSH 키)이 되어 있어야 clone이
됩니다.

## Pull (최신 변경사항 받기)

```bash
git pull origin master
```

## Push (변경사항 올리기)

```bash
git add <바뀐 파일>
git commit -m "설명"
git push origin master
```

> **주의**: `git push --force`(강제 push)는 사용하지 마세요. 여러 사람/여러 PC에서 동시에
> 작업할 경우 다른 작업 내용을 덮어쓸 수 있습니다.

## 새 Release 만들기 (버전 올릴 때)

```bash
# 1) installer.iss의 MyAppVersion을 새 버전으로 수정
# 2) 빌드
build.bat
# 3) 태그 + Release 생성 (GitHub CLI 사용)
gh release create v1.1.0 "installer_output/PhotoDedup_Setup_1.1.0.exe" \
  --title "v1.1.0" --notes "변경사항..."
```

## 새 PC에서 완전히 복구하는 과정

```text
GitHub (https://github.com/cjhtop9234ppp-tech/photo-dedup)
↓
git clone (또는 Releases에서 설치 파일만 받아 바로 설치도 가능)
↓
python -m venv venv && venv\Scripts\activate
↓
pip install -r requirements.txt
↓
설정 복구: 해당 없음 (환경변수/설정파일 없음 — [[04_설정값_환경변수]])
↓
python main.py 실행
↓
테스트 zip으로 검증 (REPRODUCTION_GUIDE.md 8번 섹션)
```

## 관련 문서
- [[03_설치_및_실행방법]]
- [[07_버전_변경이력_CHANGELOG]]
