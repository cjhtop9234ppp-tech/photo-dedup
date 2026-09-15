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
