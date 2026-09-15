# 07. 버전 변경이력 (CHANGELOG)

## 실제 git 커밋 로그 (`git log`, 직접 확인)

| 커밋 | 날짜 | 내용 |
|---|---|---|
| `96cbae3` | 2026-09-15 | Initial public release: PhotoDedup v1.0.0 |
| `73fb964` | 2026-09-15 | Fill in actual repository clone URL in README |

저장소가 2026-09-15에 처음 생성되었기 때문에 git 커밋은 2개뿐이며, **그 이전의 실제 기능
개발 과정은 커밋으로 남아있지 않습니다.** 아래는 git 커밋이 아니라, 개발 세션 기록과 코드에
남은 근거를 기준으로 정리한 **기능 단계별 이력**입니다.

## 버전/단계별 정리 (git 이전 개발 과정, 기능 단계 기준)

### 1단계 — 기본 중복 제거 기능
```text
├─ 추가: zip 드래그앤드롭/파일선택 입력, sha256(계산만)+pHash 이중 계산, Union-Find+BK-tree
│        중복 그룹화, zip 등장 순서 기준 대표 사진 선정, 바탕화면 결과 폴더 생성
├─ 추가: CLI(app/cli.py), GUI(app/gui.py) 두 가지 실행 방식
└─ 검증: 테스트 zip으로 CLI 실행, 기대 개수 일치 확인
```

### 2단계 — UI/출력 정책 개선
```text
├─ 변경: 출력물을 "바탕화면 폴더 1개"로 단순화 (리포트/zip재압축 제거)
├─ 추가: "제외된 중복 사진 미리보기" 팝업 + 그랩 스크롤
├─ 변경: "결과 폴더 열기"가 탐색기 대신 사진 순서 정리 창(OrderEditor)을 열도록 변경
├─ 추가: OrderEditor — 선택/드래그재정렬/열개수자동조절/Delete/Ctrl+Z
├─ 성능 개선: 위젯 destroy/재생성 → 최초 1회 생성 후 재사용
└─ 추가: Inno Setup 설치 프로그램(installer.iss), 빌드 스크립트(build.bat)
```

### 3단계 — 자동화 및 외부 연동
```text
├─ 추가: zip 우클릭 자동실행 (컨텍스트 메뉴, main.py 분기, DedupApp.run_auto)
├─ 추가: 확정 시 원본 zip 휴지통 이동(send2trash), FastStone Image Viewer 자동 실행
└─ 버그 수정: zip이 아닌 파일을 넣으면 빈 결과 폴더가 생성되던 문제 수정
```

### 4단계 — GitHub 공개 준비 (v1.0.0)
```text
├─ 수정: 하드코딩된 Windows 계정명 경로 일반화 (Path.home() 기반으로 변경)
├─ 추가: README.md 재작성(설치/사용법/Workflow/오류해결 등 GitHub 방문자 기준)
├─ 추가: LICENSE(MIT)
├─ 변경: .gitignore에 개발 메모 폴더 추가 제외
├─ 완료: GitHub 저장소 생성(Private) 및 최초 Push
└─ 완료: GitHub Release v1.0.0 발행, 설치 파일 Asset 등록
```

## `확인 필요`

- 4단계 이전(1~3단계) 각각의 정확한 날짜는 git 커밋이 없어 확인할 수 없습니다.
- 향후 버전은 `installer.iss`의 `MyAppVersion`과 GitHub Release 태그를 함께 올려서 관리하는 것을
  권장합니다(현재는 v1.0.0 하나만 존재).

## 관련 문서
- [[05_오류_및_해결이력]]
- [[08_백업_복구_GitHub]]
