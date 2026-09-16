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

        summary = f"완료했습니다. (유지 {total_kept}장"
        summary += f", 삭제 {total_deleted}장)" if total_deleted else ")"
        if zip_paths:
            summary += f"\n원본 zip {len(zip_paths) - len(zip_errors)}개를 휴지통으로 보냈습니다."
        if delete_errors:
            summary += "\n\n일부 사진 삭제 실패:\n" + "\n".join(delete_errors)
        if zip_errors:
            summary += "\n\n일부 zip 삭제 실패:\n" + "\n".join(zip_errors)
        messagebox.showinfo(APP_TITLE, summary)
        self.app._open_result_viewer(str(self.output_dir))
        self.win.destroy()
        self.app._on_order_editor_closed()


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
