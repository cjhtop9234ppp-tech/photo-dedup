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
