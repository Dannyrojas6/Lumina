from __future__ import annotations

import ctypes
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
VENV_CFG_PATH = REPO_ROOT / ".venv" / "pyvenv.cfg"
SITE_PACKAGES_PATH = REPO_ROOT / ".venv" / "Lib" / "site-packages"
TARGET_PYTHON_VERSION: Final[tuple[int, int]] = (3, 12)
BOOTSTRAP_ENV: Final[str] = "LUMINA_COORDINATE_PICKER_BOOTSTRAPPED"


def _read_pyvenv_home() -> Path:
    if not VENV_CFG_PATH.exists():
        raise RuntimeError(f"missing virtual environment config: {VENV_CFG_PATH}")

    for raw_line in VENV_CFG_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "home":
            return Path(value.strip())

    raise RuntimeError(f"missing 'home' entry in {VENV_CFG_PATH}")


def _build_python_path(existing: str | None) -> str:
    parts = [str(SITE_PACKAGES_PATH)]
    if existing:
        parts.append(existing)
    return os.pathsep.join(parts)


def ensure_runtime() -> None:
    if not SITE_PACKAGES_PATH.exists():
        raise RuntimeError(f"missing site-packages directory: {SITE_PACKAGES_PATH}")

    if sys.version_info[:2] != TARGET_PYTHON_VERSION:
        if os.environ.get(BOOTSTRAP_ENV) == "1":
            raise RuntimeError(
                "failed to switch to Python 3.12 for coordinate_picker.py"
            )

        python_home = _read_pyvenv_home()
        python_executable = python_home / "python.exe"
        if not python_executable.exists():
            raise RuntimeError(f"missing Python executable: {python_executable}")

        env = os.environ.copy()
        env[BOOTSTRAP_ENV] = "1"
        env["PYTHONPATH"] = _build_python_path(env.get("PYTHONPATH"))
        os.execve(
            str(python_executable),
            [str(python_executable), str(SCRIPT_PATH), *sys.argv[1:]],
            env,
        )

    site_packages = str(SITE_PACKAGES_PATH)
    if site_packages not in sys.path:
        sys.path.insert(0, site_packages)


ensure_runtime()

import tkinter as tk
from tkinter import filedialog

from PIL import Image, ImageTk


WINDOW_WIDTH: Final[int] = 1920
WINDOW_HEIGHT: Final[int] = 1080
SIDEBAR_WIDTH: Final[int] = 280
TOGGLE_STRIP_WIDTH: Final[int] = 40
MAX_SCALE: Final[float] = 8.0
ZOOM_STEP: Final[float] = 1.1
POINT_RADIUS: Final[int] = 6
TEST_IMAGE_DIR = REPO_ROOT / "test_image"

BG_ROOT: Final[str] = "#11161c"
BG_CANVAS: Final[str] = "#0b1015"
BG_SIDEBAR: Final[str] = "#1a2129"
BG_TOGGLE: Final[str] = "#232d38"
FG_TEXT: Final[str] = "#ecf0f3"
FG_MUTED: Final[str] = "#8d98a5"
ACCENT: Final[str] = "#50c4d3"
POINT_COLOR: Final[str] = "#f7d24b"
RECT_COLOR: Final[str] = "#59d38b"
PREVIEW_COLOR: Final[str] = "#f59f58"


@dataclass(frozen=True)
class PixelPoint:
    x: int
    y: int


@dataclass(frozen=True)
class PixelRect:
    x1: int
    y1: int
    x2: int
    y2: int


def enable_dpi_awareness() -> None:
    if os.name != "nt":
        return

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        return
    except Exception:
        pass

    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class CoordinatePickerApp:
    def __init__(self, root: tk.Tk, open_dialog_on_start: bool = True) -> None:
        self.root = root
        self.open_dialog_on_start = open_dialog_on_start

        self.image_path: Path | None = None
        self.source_image: Image.Image | None = None
        self.display_photo: ImageTk.PhotoImage | None = None
        self.cached_view_key: tuple[int, int, int, int, int] | None = None

        self.canvas_width = 1
        self.canvas_height = 1
        self.scale = 1.0
        self.fit_scale = 1.0
        self.max_scale = MAX_SCALE
        self.pan_x = 0.0
        self.pan_y = 0.0

        self.latest_point: PixelPoint | None = None
        self.latest_rect: PixelRect | None = None
        self.drag_origin: PixelPoint | None = None
        self.drag_preview: PixelRect | None = None

        self.cursor_canvas_x: float | None = None
        self.cursor_canvas_y: float | None = None
        self.cursor_point: PixelPoint | None = None

        self.middle_drag_anchor: tuple[int, int] | None = None
        self.middle_drag_pan: tuple[float, float] | None = None

        self.sidebar_expanded = True

        self.file_var = tk.StringVar(value="未选择")
        self.scale_var = tk.StringVar(value="-")
        self.cursor_var = tk.StringVar(value="-")
        self.point_var = tk.StringVar(value="-")
        self.rect_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(
            value="左键取点，右键框选，中键拖动，滚轮缩放"
        )

        self._build_window()
        self._build_layout()
        self._bind_events()
        self._update_output_fields()
        self._render()

        if self.open_dialog_on_start:
            self.root.after(50, self.choose_image)

    def _build_window(self) -> None:
        self.root.title("Lumina Coordinate Picker")
        self.root.configure(bg=BG_ROOT)
        self.root.resizable(False, False)
        self.root.geometry(self._build_geometry())
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def _build_geometry(self) -> str:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        pos_x = max((screen_width - WINDOW_WIDTH) // 2, 0)
        pos_y = max((screen_height - WINDOW_HEIGHT) // 2, 0)
        return f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{pos_x}+{pos_y}"

    def _build_layout(self) -> None:
        self.main_frame = tk.Frame(self.root, bg=BG_ROOT)
        self.main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            self.main_frame,
            bg=BG_CANVAS,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.sidebar_frame = tk.Frame(self.root, width=SIDEBAR_WIDTH, bg=BG_SIDEBAR)
        self.sidebar_frame.pack(side=tk.RIGHT, fill=tk.Y)
        self.sidebar_frame.pack_propagate(False)

        self.toggle_strip = tk.Frame(
            self.sidebar_frame,
            width=TOGGLE_STRIP_WIDTH,
            bg=BG_TOGGLE,
        )
        self.toggle_strip.pack(side=tk.LEFT, fill=tk.Y)
        self.toggle_strip.pack_propagate(False)

        self.toggle_button = tk.Button(
            self.toggle_strip,
            text="<",
            command=self.toggle_sidebar,
            bg=BG_TOGGLE,
            fg=FG_TEXT,
            activebackground=BG_TOGGLE,
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 12, "bold"),
        )
        self.toggle_button.pack(fill=tk.X, pady=(12, 0), padx=6)

        self.sidebar_content = tk.Frame(self.sidebar_frame, bg=BG_SIDEBAR)
        self.sidebar_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        title = tk.Label(
            self.sidebar_content,
            text="坐标结果",
            bg=BG_SIDEBAR,
            fg=FG_TEXT,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        )
        title.pack(fill=tk.X, padx=16, pady=(16, 12))

        self._create_info_block("文件", self.file_var, wraplength=210)
        self._create_info_block("倍率", self.scale_var)
        self._create_info_block("当前坐标", self.cursor_var)
        self._create_info_block("最新点", self.point_var)
        self._create_info_block("最新矩形", self.rect_var)

        button_frame = tk.Frame(self.sidebar_content, bg=BG_SIDEBAR)
        button_frame.pack(fill=tk.X, padx=16, pady=(8, 10))

        self.copy_point_button = self._create_action_button(
            button_frame,
            "复制点坐标",
            self.copy_point,
        )
        self.copy_rect_button = self._create_action_button(
            button_frame,
            "复制矩形坐标",
            self.copy_rect,
        )
        self.open_button = self._create_action_button(
            button_frame,
            "重新选择图片",
            self.choose_image,
        )
        self.reset_button = self._create_action_button(
            button_frame,
            "重置视图",
            self.reset_view,
        )

        hint = tk.Label(
            self.sidebar_content,
            text="快捷键\nO 重新选图\nR 重置视图\nEsc 清除当前点和矩形",
            justify="left",
            bg=BG_SIDEBAR,
            fg=FG_MUTED,
            font=("Segoe UI", 10),
            anchor="nw",
        )
        hint.pack(fill=tk.X, padx=16, pady=(0, 12))

        status_label = tk.Label(
            self.sidebar_content,
            textvariable=self.status_var,
            justify="left",
            bg=BG_SIDEBAR,
            fg=ACCENT,
            wraplength=210,
            font=("Segoe UI", 10),
            anchor="nw",
        )
        status_label.pack(fill=tk.X, padx=16, pady=(0, 16))

    def _create_info_block(
        self,
        title: str,
        variable: tk.StringVar,
        wraplength: int = 210,
    ) -> None:
        container = tk.Frame(self.sidebar_content, bg=BG_SIDEBAR)
        container.pack(fill=tk.X, padx=16, pady=(0, 12))

        label = tk.Label(
            container,
            text=title,
            bg=BG_SIDEBAR,
            fg=FG_MUTED,
            font=("Segoe UI", 10),
            anchor="w",
        )
        label.pack(fill=tk.X)

        value = tk.Label(
            container,
            textvariable=variable,
            justify="left",
            bg=BG_SIDEBAR,
            fg=FG_TEXT,
            font=("Consolas", 11),
            wraplength=wraplength,
            anchor="w",
        )
        value.pack(fill=tk.X, pady=(3, 0))

    def _create_action_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
    ) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg="#2b3642",
            fg=FG_TEXT,
            activebackground="#324151",
            activeforeground=FG_TEXT,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            font=("Segoe UI", 10),
            pady=8,
        )
        button.pack(fill=tk.X, pady=(0, 8))
        return button

    def _bind_events(self) -> None:
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.canvas.bind("<Button-1>", self._on_left_click)
        self.canvas.bind("<ButtonPress-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_release)
        self.canvas.bind("<ButtonPress-2>", self._on_middle_press)
        self.canvas.bind("<B2-Motion>", self._on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_release)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)

        self.root.bind("o", self._open_from_key)
        self.root.bind("O", self._open_from_key)
        self.root.bind("r", self._reset_from_key)
        self.root.bind("R", self._reset_from_key)
        self.root.bind("<Escape>", self._clear_from_key)

    def _open_from_key(self, _event: tk.Event) -> None:
        self.choose_image()

    def _reset_from_key(self, _event: tk.Event) -> None:
        self.reset_view()

    def _clear_from_key(self, _event: tk.Event) -> None:
        self.clear_annotations()

    def choose_image(self) -> None:
        image_path = filedialog.askopenfilename(
            parent=self.root,
            title="选择图片",
            initialdir=str(TEST_IMAGE_DIR),
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp"),
                ("PNG Files", "*.png"),
                ("All Files", "*.*"),
            ],
        )
        if not image_path:
            self.status_var.set("未选择图片，可点击按钮或按 O 重新打开")
            self.canvas.focus_set()
            self._render()
            return

        self.load_image(Path(image_path))
        self.canvas.focus_set()

    def load_image(self, image_path: Path) -> None:
        with Image.open(image_path) as loaded:
            self.source_image = loaded.convert("RGB")

        self.image_path = image_path
        self.latest_point = None
        self.latest_rect = None
        self.drag_origin = None
        self.drag_preview = None
        self.cursor_point = None
        self.file_var.set(image_path.name)
        self.cached_view_key = None
        self.status_var.set("左键取点，右键框选，中键拖动，滚轮缩放")

        self.root.update_idletasks()
        self.fit_scale = self._calculate_fit_scale()
        self.scale = self.fit_scale
        self.max_scale = max(MAX_SCALE, self.fit_scale)
        self._recenter_image()
        self._update_output_fields()
        self._render()

    def toggle_sidebar(self) -> None:
        self.sidebar_expanded = not self.sidebar_expanded
        if self.sidebar_expanded:
            self.sidebar_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            self.sidebar_frame.configure(width=SIDEBAR_WIDTH)
            self.toggle_button.configure(text="<")
        else:
            self.sidebar_content.pack_forget()
            self.sidebar_frame.configure(width=TOGGLE_STRIP_WIDTH)
            self.toggle_button.configure(text=">")

        self.root.update_idletasks()
        self._render()

    def reset_view(self) -> None:
        if self.source_image is None:
            self.status_var.set("当前没有图片可重置")
            return

        self.fit_scale = self._calculate_fit_scale()
        self.scale = self.fit_scale
        self.max_scale = max(MAX_SCALE, self.fit_scale)
        self._recenter_image()
        self.status_var.set("视图已重置")
        self._update_output_fields()
        self._render()

    def clear_annotations(self) -> None:
        self.latest_point = None
        self.latest_rect = None
        self.drag_origin = None
        self.drag_preview = None
        self.status_var.set("已清除当前点和矩形")
        self._update_output_fields()
        self._render()

    def copy_point(self) -> None:
        if self.latest_point is None:
            return
        self._copy_to_clipboard(self._format_point(self.latest_point))
        self.status_var.set("点坐标已复制")

    def copy_rect(self) -> None:
        if self.latest_rect is None:
            return
        self._copy_to_clipboard(self._format_rect(self.latest_rect))
        self.status_var.set("矩形坐标已复制")

    def _copy_to_clipboard(self, value: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(value)
        self.root.update_idletasks()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        new_width = max(int(event.width), 1)
        new_height = max(int(event.height), 1)
        if new_width == self.canvas_width and new_height == self.canvas_height:
            return

        image_center: tuple[float, float] | None = None
        if self.source_image is not None and self.scale > 0:
            image_center = self._canvas_to_image_float(
                self.canvas_width / 2,
                self.canvas_height / 2,
            )

        previous_fit = self.fit_scale
        self.canvas_width = new_width
        self.canvas_height = new_height

        if self.source_image is None:
            self._render()
            return

        self.fit_scale = self._calculate_fit_scale()
        self.max_scale = max(MAX_SCALE, self.fit_scale)

        if self.scale <= previous_fit + 1e-6:
            self.scale = self.fit_scale
            self._recenter_image()
        else:
            self.scale = max(self.scale, self.fit_scale)
            if image_center is not None:
                self.pan_x = (self.canvas_width / 2) - (image_center[0] * self.scale)
                self.pan_y = (self.canvas_height / 2) - (image_center[1] * self.scale)
            self._clamp_pan()

        self._update_output_fields()
        self._render()

    def _on_mouse_move(self, event: tk.Event) -> None:
        self.cursor_canvas_x = float(event.x)
        self.cursor_canvas_y = float(event.y)
        self.cursor_point = self._canvas_to_image_point(event.x, event.y)

        if self.drag_origin is not None:
            current = self._canvas_to_image_point(event.x, event.y)
            if current is not None:
                self.drag_preview = self._normalize_rect(self.drag_origin, current)

        self._update_output_fields()
        self._render()

    def _on_mouse_leave(self, _event: tk.Event) -> None:
        self.cursor_canvas_x = None
        self.cursor_canvas_y = None
        self.cursor_point = None
        self._update_output_fields()
        self._render()

    def _on_left_click(self, event: tk.Event) -> None:
        point = self._canvas_to_image_point(event.x, event.y)
        if point is None:
            return

        self.latest_point = point
        self.status_var.set("已记录点坐标")
        self._update_output_fields()
        self._render()

    def _on_right_press(self, event: tk.Event) -> None:
        point = self._canvas_to_image_point(event.x, event.y)
        if point is None:
            return

        self.drag_origin = point
        self.drag_preview = self._normalize_rect(point, point)
        self.status_var.set("正在框选矩形")
        self._update_output_fields()
        self._render()

    def _on_right_drag(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return

        point = self._canvas_to_image_point(event.x, event.y)
        if point is None:
            return

        self.drag_preview = self._normalize_rect(self.drag_origin, point)
        self._update_output_fields()
        self._render()

    def _on_right_release(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return

        point = self._canvas_to_image_point(event.x, event.y)
        if point is None:
            point = self.drag_origin

        self.latest_rect = self._normalize_rect(self.drag_origin, point)
        self.drag_origin = None
        self.drag_preview = None
        self.status_var.set("已记录矩形坐标")
        self._update_output_fields()
        self._render()

    def _on_middle_press(self, event: tk.Event) -> None:
        if self.source_image is None:
            return
        self.middle_drag_anchor = (int(event.x), int(event.y))
        self.middle_drag_pan = (self.pan_x, self.pan_y)
        self.status_var.set("正在拖动画面")

    def _on_middle_drag(self, event: tk.Event) -> None:
        if self.middle_drag_anchor is None or self.middle_drag_pan is None:
            return

        delta_x = int(event.x) - self.middle_drag_anchor[0]
        delta_y = int(event.y) - self.middle_drag_anchor[1]
        self.pan_x = self.middle_drag_pan[0] + delta_x
        self.pan_y = self.middle_drag_pan[1] + delta_y
        self._clamp_pan()
        self._render()

    def _on_middle_release(self, _event: tk.Event) -> None:
        if self.middle_drag_anchor is None:
            return

        self.middle_drag_anchor = None
        self.middle_drag_pan = None
        self.status_var.set("画面拖动结束")

    def _on_mousewheel(self, event: tk.Event) -> None:
        if self.source_image is None or event.delta == 0:
            return

        image_point = self._canvas_to_image_float(event.x, event.y)
        if image_point is None:
            return

        image_width, image_height = self.source_image.size
        if image_point[0] < 0 or image_point[0] > image_width:
            return
        if image_point[1] < 0 or image_point[1] > image_height:
            return

        factor = ZOOM_STEP if event.delta > 0 else 1 / ZOOM_STEP
        self.zoom_at(event.x, event.y, factor)

    def zoom_at(self, canvas_x: int, canvas_y: int, factor: float) -> None:
        if self.source_image is None:
            return

        image_point = self._canvas_to_image_float(canvas_x, canvas_y)
        if image_point is None:
            return

        next_scale = self.scale * factor
        next_scale = min(max(next_scale, self.fit_scale), self.max_scale)
        if abs(next_scale - self.scale) < 1e-9:
            return

        self.scale = next_scale
        self.pan_x = canvas_x - (image_point[0] * self.scale)
        self.pan_y = canvas_y - (image_point[1] * self.scale)
        self._clamp_pan()
        self.status_var.set(f"当前倍率 {self.scale:.2f}x")
        self._update_output_fields()
        self._render()

    def _calculate_fit_scale(self) -> float:
        if self.source_image is None:
            return 1.0

        image_width, image_height = self.source_image.size
        available_width = max(self.canvas.winfo_width(), 1)
        available_height = max(self.canvas.winfo_height(), 1)
        return min(available_width / image_width, available_height / image_height)

    def _recenter_image(self) -> None:
        if self.source_image is None:
            return

        scaled_width = self.source_image.size[0] * self.scale
        scaled_height = self.source_image.size[1] * self.scale
        self.pan_x = (self.canvas_width - scaled_width) / 2
        self.pan_y = (self.canvas_height - scaled_height) / 2
        self._clamp_pan()

    def _clamp_pan(self) -> None:
        if self.source_image is None:
            return

        scaled_width = self.source_image.size[0] * self.scale
        scaled_height = self.source_image.size[1] * self.scale

        if scaled_width <= self.canvas_width:
            self.pan_x = (self.canvas_width - scaled_width) / 2
        else:
            min_x = self.canvas_width - scaled_width
            self.pan_x = min(0.0, max(min_x, self.pan_x))

        if scaled_height <= self.canvas_height:
            self.pan_y = (self.canvas_height - scaled_height) / 2
        else:
            min_y = self.canvas_height - scaled_height
            self.pan_y = min(0.0, max(min_y, self.pan_y))

    def _canvas_to_image_float(
        self,
        canvas_x: float,
        canvas_y: float,
    ) -> tuple[float, float] | None:
        if self.source_image is None or self.scale <= 0:
            return None

        image_x = (canvas_x - self.pan_x) / self.scale
        image_y = (canvas_y - self.pan_y) / self.scale
        return image_x, image_y

    def _canvas_to_image_point(
        self,
        canvas_x: float,
        canvas_y: float,
    ) -> PixelPoint | None:
        if self.source_image is None:
            return None

        image_point = self._canvas_to_image_float(canvas_x, canvas_y)
        if image_point is None:
            return None

        image_x = self._clamp_coordinate(round(image_point[0]), self.source_image.size[0])
        image_y = self._clamp_coordinate(round(image_point[1]), self.source_image.size[1])
        return PixelPoint(image_x, image_y)

    def _image_to_canvas(self, point: PixelPoint) -> tuple[float, float]:
        return (
            self.pan_x + (point.x * self.scale),
            self.pan_y + (point.y * self.scale),
        )

    def _clamp_coordinate(self, value: int, size: int) -> int:
        if size <= 0:
            return 0
        return min(max(value, 0), size - 1)

    def _normalize_rect(self, first: PixelPoint, second: PixelPoint) -> PixelRect:
        return PixelRect(
            x1=min(first.x, second.x),
            y1=min(first.y, second.y),
            x2=max(first.x, second.x),
            y2=max(first.y, second.y),
        )

    def _visible_image_bounds(self) -> tuple[int, int, int, int] | None:
        if self.source_image is None:
            return None

        image_width, image_height = self.source_image.size
        left = max(0, int((0 - self.pan_x) / self.scale))
        top = max(0, int((0 - self.pan_y) / self.scale))
        right = min(image_width, int((self.canvas_width - self.pan_x) / self.scale) + 2)
        bottom = min(
            image_height,
            int((self.canvas_height - self.pan_y) / self.scale) + 2,
        )
        if right <= left or bottom <= top:
            return None
        return left, top, right, bottom

    def _render(self) -> None:
        self.canvas.delete("all")
        if self.source_image is None:
            self._render_empty_state()
            return

        bounds = self._visible_image_bounds()
        if bounds is None:
            self._render_empty_state()
            return

        left, top, right, bottom = bounds
        scale_key = int(round(self.scale * 10000))
        view_key = (left, top, right, bottom, scale_key)
        if self.cached_view_key != view_key or self.display_photo is None:
            crop = self.source_image.crop((left, top, right, bottom))
            render_width = max(int(round((right - left) * self.scale)), 1)
            render_height = max(int(round((bottom - top) * self.scale)), 1)
            display_image = crop.resize(
                (render_width, render_height),
                Image.Resampling.LANCZOS,
            )
            self.display_photo = ImageTk.PhotoImage(display_image)
            self.cached_view_key = view_key

        draw_x = self.pan_x + (left * self.scale)
        draw_y = self.pan_y + (top * self.scale)
        self.canvas.create_image(draw_x, draw_y, image=self.display_photo, anchor=tk.NW)

        self._draw_latest_rect()
        self._draw_drag_preview()
        self._draw_latest_point()
        self._draw_cursor_overlay()

    def _render_empty_state(self) -> None:
        self.canvas.create_text(
            self.canvas_width / 2,
            (self.canvas_height / 2) - 24,
            text="请选择一张图片",
            fill=FG_TEXT,
            font=("Segoe UI", 20, "bold"),
        )
        self.canvas.create_text(
            self.canvas_width / 2,
            (self.canvas_height / 2) + 14,
            text="默认打开 test_image，取消后可点右侧按钮或按 O 重新打开",
            fill=FG_MUTED,
            font=("Segoe UI", 11),
        )

    def _draw_latest_point(self) -> None:
        if self.latest_point is None:
            return

        center_x, center_y = self._image_to_canvas(self.latest_point)
        radius = POINT_RADIUS
        self.canvas.create_oval(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            outline=POINT_COLOR,
            width=2,
        )
        self.canvas.create_line(
            center_x - 12,
            center_y,
            center_x + 12,
            center_y,
            fill=POINT_COLOR,
            width=2,
        )
        self.canvas.create_line(
            center_x,
            center_y - 12,
            center_x,
            center_y + 12,
            fill=POINT_COLOR,
            width=2,
        )

    def _draw_latest_rect(self) -> None:
        if self.latest_rect is None:
            return

        self._draw_rect(self.latest_rect, RECT_COLOR, dash=None, width=2)

    def _draw_drag_preview(self) -> None:
        if self.drag_preview is None:
            return

        self._draw_rect(self.drag_preview, PREVIEW_COLOR, dash=(6, 4), width=2)

    def _draw_rect(
        self,
        rect: PixelRect,
        color: str,
        dash: tuple[int, int] | None,
        width: int,
    ) -> None:
        x1, y1 = self._image_to_canvas(PixelPoint(rect.x1, rect.y1))
        x2, y2 = self._image_to_canvas(PixelPoint(rect.x2, rect.y2))
        self.canvas.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            outline=color,
            width=width,
            dash=dash,
        )

    def _draw_cursor_overlay(self) -> None:
        if self.cursor_canvas_x is None or self.cursor_canvas_y is None:
            return

        self.canvas.create_line(
            self.cursor_canvas_x,
            0,
            self.cursor_canvas_x,
            self.canvas_height,
            fill="#4d5966",
            width=1,
        )
        self.canvas.create_line(
            0,
            self.cursor_canvas_y,
            self.canvas_width,
            self.cursor_canvas_y,
            fill="#4d5966",
            width=1,
        )

        if self.cursor_point is None:
            return

        text_id = self.canvas.create_text(
            min(self.cursor_canvas_x + 14, self.canvas_width - 14),
            min(self.cursor_canvas_y + 14, self.canvas_height - 14),
            text=self._format_point(self.cursor_point),
            anchor=tk.NW,
            fill=FG_TEXT,
            font=("Consolas", 10),
        )
        bbox = self.canvas.bbox(text_id)
        if bbox is None:
            return
        x1, y1, x2, y2 = bbox
        background = self.canvas.create_rectangle(
            x1 - 6,
            y1 - 4,
            x2 + 6,
            y2 + 4,
            fill="#10161d",
            outline="#3a4653",
        )
        self.canvas.tag_raise(text_id, background)

    def _update_output_fields(self) -> None:
        self.file_var.set(self.image_path.name if self.image_path else "未选择")
        self.scale_var.set("-" if self.source_image is None else f"{self.scale:.2f}x")
        self.cursor_var.set(
            self._format_point(self.cursor_point) if self.cursor_point else "-"
        )
        self.point_var.set(
            self._format_point(self.latest_point) if self.latest_point else "-"
        )
        self.rect_var.set(
            self._format_rect(self.latest_rect) if self.latest_rect else "-"
        )

        self.copy_point_button.configure(
            state=tk.NORMAL if self.latest_point is not None else tk.DISABLED
        )
        self.copy_rect_button.configure(
            state=tk.NORMAL if self.latest_rect is not None else tk.DISABLED
        )
        self.reset_button.configure(
            state=tk.NORMAL if self.source_image is not None else tk.DISABLED
        )

    def _format_point(self, point: PixelPoint) -> str:
        return f"({point.x}, {point.y})"

    def _format_rect(self, rect: PixelRect) -> str:
        return f"({rect.x1}, {rect.y1}, {rect.x2}, {rect.y2})"


def main() -> int:
    enable_dpi_awareness()
    root = tk.Tk()
    open_dialog_on_start = os.environ.get("LUMINA_COORD_PICKER_SKIP_START_DIALOG") != "1"
    app = CoordinatePickerApp(root, open_dialog_on_start=open_dialog_on_start)

    image_path_raw = os.environ.get("LUMINA_COORD_PICKER_IMAGE")
    if image_path_raw:
        image_path = Path(image_path_raw)
        if image_path.exists():
            root.after(50, lambda: app.load_image(image_path))

    auto_close_raw = os.environ.get("LUMINA_COORD_PICKER_AUTO_CLOSE_MS")
    if auto_close_raw:
        try:
            auto_close_ms = max(int(auto_close_raw), 0)
        except ValueError:
            auto_close_ms = 0
        if auto_close_ms > 0:
            root.after(auto_close_ms, root.destroy)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


