from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ctypes
import os
import tkinter as tk
from tkinter import filedialog

import numpy as np
from PIL import Image, ImageTk


REPO_ROOT = Path(__file__).resolve().parents[1]
TEST_IMAGE_DIR = REPO_ROOT / "test_image"
DEFAULT_WINDOW_WIDTH = 2400
DEFAULT_WINDOW_HEIGHT = 1360
SIDEBAR_WIDTH = 620
BG = "#11161c"
PANEL = "#1a2129"
BLOCK = "#121920"
TEXT = "#ecf0f3"
MUTED = "#8d98a5"
CROP_COLOR = "#59d38b"
MASK_COLOR = "#f59f58"
PREVIEW_COLOR = "#f7d24b"

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


@dataclass(frozen=True)
class CropRect:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class MaskRect:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class PixelPoint:
    x: int
    y: int


def normalize_rect(x1: int, y1: int, x2: int, y2: int) -> tuple[int, int, int, int]:
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def clamp_rect(rect: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = rect
    x1 = min(max(x1, 0), width)
    y1 = min(max(y1, 0), height)
    x2 = min(max(x2, 0), width)
    y2 = min(max(y2, 0), height)
    return normalize_rect(x1, y1, x2, y2)


def crop_image(image_rgb: np.ndarray, crop_rect: CropRect) -> np.ndarray:
    x1, y1, x2, y2 = clamp_rect(
        (crop_rect.x1, crop_rect.y1, crop_rect.x2, crop_rect.y2),
        image_rgb.shape[1],
        image_rgb.shape[0],
    )
    if x2 <= x1 or y2 <= y1:
        return image_rgb[:0, :0].copy()
    return image_rgb[y1:y2, x1:x2].copy()


def apply_masks(image_rgb: np.ndarray, masks: list[MaskRect]) -> np.ndarray:
    if image_rgb.size == 0 or not masks:
        return image_rgb.copy()

    height, width = image_rgb.shape[:2]
    mask_map = np.zeros((height, width), dtype=bool)
    for rect in masks:
        x1, y1, x2, y2 = clamp_rect((rect.x1, rect.y1, rect.x2, rect.y2), width, height)
        if x2 > x1 and y2 > y1:
            mask_map[y1:y2, x1:x2] = True

    masked = image_rgb.copy()
    if not np.any(mask_map):
        return masked
    keep_mask = ~mask_map
    if np.any(keep_mask):
        fill = np.round(masked[keep_mask].reshape(-1, 3).mean(axis=0)).astype(np.uint8)
    else:
        fill = np.zeros(3, dtype=np.uint8)
    masked[mask_map] = fill
    return masked


def relative_mask_from_absolute(crop_rect: CropRect, absolute_rect: CropRect) -> MaskRect | None:
    left = max(crop_rect.x1, absolute_rect.x1)
    top = max(crop_rect.y1, absolute_rect.y1)
    right = min(crop_rect.x2, absolute_rect.x2)
    bottom = min(crop_rect.y2, absolute_rect.y2)
    if right <= left or bottom <= top:
        return None
    return MaskRect(left - crop_rect.x1, top - crop_rect.y1, right - crop_rect.x1, bottom - crop_rect.y1)


def absolute_mask_from_relative(crop_rect: CropRect, mask_rect: MaskRect) -> CropRect:
    return CropRect(
        crop_rect.x1 + mask_rect.x1,
        crop_rect.y1 + mask_rect.y1,
        crop_rect.x1 + mask_rect.x2,
        crop_rect.y1 + mask_rect.y2,
    )


def format_rect(rect: tuple[int, int, int, int]) -> str:
    return f"({rect[0]}, {rect[1]}, {rect[2]}, {rect[3]})"


def build_default_export(image_name: str, crop_region: tuple[int, int, int, int], mask_regions: list[tuple[int, int, int, int]]) -> str:
    lines = [
        f"# {image_name}",
        "# MASK_RECTS uses crop-local coordinates",
        f"CROP_REGION = {format_rect(crop_region)}",
        "MASK_RECTS = [",
    ]
    for rect in mask_regions:
        lines.append(f"    {format_rect(rect)},")
    lines.append("]")
    return "\n".join(lines)


def format_export_block(image_name: str, crop_rect: CropRect, masks: list[MaskRect]) -> str:
    relative_masks = [(mask.x1, mask.y1, mask.x2, mask.y2) for mask in masks]
    absolute_masks = [
        (crop_rect.x1 + mask.x1, crop_rect.y1 + mask.y1, crop_rect.x1 + mask.x2, crop_rect.y1 + mask.y2)
        for mask in masks
    ]
    lines = [
        build_default_export(image_name, (crop_rect.x1, crop_rect.y1, crop_rect.x2, crop_rect.y2), relative_masks),
        "",
        "MASK_RECTS_ABS = [",
    ]
    for rect in absolute_masks:
        lines.append(f"    {format_rect(rect)},")
    lines.append("]")
    return "\n".join(lines)


class MaskRegionPickerApp:
    def __init__(self, root: tk.Tk, open_dialog_on_start: bool = True) -> None:
        self.root = root
        self.open_dialog_on_start = open_dialog_on_start
        self.root.title("Lumina Mask Region Picker")
        self.root.configure(bg=BG)
        self._configure_window()

        self.image_path: Path | None = None
        self.image_rgb: np.ndarray | None = None
        self.image_pil: Image.Image | None = None
        self.source_photo: ImageTk.PhotoImage | None = None
        self.crop_photo: ImageTk.PhotoImage | None = None
        self.masked_photo: ImageTk.PhotoImage | None = None

        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0

        self.crop_rect: CropRect | None = None
        self.mask_rects: list[MaskRect] = []
        self.drag_origin: PixelPoint | None = None
        self.drag_preview: CropRect | None = None
        self.drag_kind: str | None = None

        self.file_var = tk.StringVar(value="\u672a\u9009\u62e9")
        self.crop_var = tk.StringVar(value="-")
        self.mask_var = tk.StringVar(value="0")
        self.cursor_var = tk.StringVar(value="-")
        self.status_var = tk.StringVar(value="\u5de6\u952e\u62d6\u62fd\u8bbe\u7f6e\u88c1\u526a\u533a\uff0c\u53f3\u952e\u62d6\u62fd\u8ffd\u52a0\u906e\u6321\u533a")

        self._build_ui()
        self._bind_events()
        if self.open_dialog_on_start:
            self.root.after(50, self.choose_image)

    def _configure_window(self) -> None:
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = min(DEFAULT_WINDOW_WIDTH, max(screen_width - 120, 1200))
        window_height = min(DEFAULT_WINDOW_HEIGHT, max(screen_height - 120, 900))
        pos_x = max((screen_width - window_width) // 2, 0)
        pos_y = max((screen_height - window_height) // 2, 0)
        self.root.geometry(f"{window_width}x{window_height}+{pos_x}+{pos_y}")
        self.root.minsize(1400, 900)

    def _build_ui(self) -> None:
        left = tk.Frame(self.root, bg=BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.source_canvas = tk.Canvas(left, bg="#0b1015", highlightthickness=0, cursor="crosshair")
        self.source_canvas.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(self.root, width=SIDEBAR_WIDTH, bg=PANEL)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        for title, variable in (("\u6587\u4ef6", self.file_var), ("\u88c1\u526a\u533a", self.crop_var), ("\u906e\u6321\u5757\u6570\u91cf", self.mask_var), ("\u5f53\u524d\u5750\u6807", self.cursor_var)):
            frame = tk.Frame(right, bg=PANEL)
            frame.pack(fill=tk.X, padx=16, pady=(12 if title == "\u6587\u4ef6" else 0, 10))
            tk.Label(frame, text=title, bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 10)).pack(fill=tk.X)
            tk.Label(frame, textvariable=variable, bg=PANEL, fg=TEXT, anchor="w", justify="left", wraplength=SIDEBAR_WIDTH - 40, font=("Consolas", 11)).pack(fill=tk.X, pady=(2, 0))

        buttons = tk.Frame(right, bg=PANEL)
        buttons.pack(fill=tk.X, padx=16, pady=(4, 8))
        for text, command in (("\u91cd\u65b0\u9009\u62e9\u56fe\u7247", self.choose_image), ("\u590d\u5236\u5bfc\u51fa\u6587\u672c", self.copy_export), ("\u590d\u5236\u88c1\u526a\u533a", self.copy_crop), ("\u5220\u9664\u6700\u540e\u906e\u6321", self.remove_last_mask), ("\u6e05\u7a7a\u906e\u6321\u533a", self.clear_masks), ("\u6e05\u7a7a\u5168\u90e8", self.clear_all)):
            tk.Button(buttons, text=text, command=command, bg="#2b3642", fg=TEXT, activebackground="#324151", activeforeground=TEXT, relief=tk.FLAT, bd=0, highlightthickness=0, font=("Segoe UI", 10), pady=8).pack(fill=tk.X, pady=(0, 8))

        tk.Label(right, text="\u88c1\u526a\u9884\u89c8", bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 10)).pack(fill=tk.X, padx=16, pady=(0, 6))
        self.crop_canvas = tk.Canvas(right, bg=BLOCK, height=150, highlightthickness=1, highlightbackground="#2d3946")
        self.crop_canvas.pack(fill=tk.X, padx=16, pady=(0, 10))

        tk.Label(right, text="\u906e\u6321\u9884\u89c8", bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 10)).pack(fill=tk.X, padx=16, pady=(0, 6))
        self.masked_canvas = tk.Canvas(right, bg=BLOCK, height=150, highlightthickness=1, highlightbackground="#2d3946")
        self.masked_canvas.pack(fill=tk.X, padx=16, pady=(0, 10))

        tk.Label(right, text="\u5bfc\u51fa\u6587\u672c", bg=PANEL, fg=MUTED, anchor="w", font=("Segoe UI", 10)).pack(fill=tk.X, padx=16, pady=(0, 6))
        self.export_text = tk.Text(right, height=12, bg=BLOCK, fg=TEXT, insertbackground=TEXT, relief=tk.FLAT, bd=0, font=("Consolas", 10), wrap=tk.NONE)
        self.export_text.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        tk.Label(right, text="\u4f7f\u7528\u65b9\u6cd5\n1. \u70b9\u2018\u91cd\u65b0\u9009\u62e9\u56fe\u7247\u2019\u8f7d\u5165\u622a\u56fe\n2. \u5de6\u952e\u62d6\u4e00\u5757\uff0c\u4f5c\u4e3a\u88c1\u526a\u533a\n3. \u53f3\u952e\u7ee7\u7eed\u62d6\uff0c\u8ffd\u52a0\u8981\u906e\u6389\u7684\u533a\u57df\n4. \u770b\u53f3\u4fa7\u2018\u906e\u6321\u9884\u89c8\u2019\u662f\u5426\u6b63\u786e\n5. \u70b9\u2018\u590d\u5236\u5bfc\u51fa\u6587\u672c\u2019\u76f4\u63a5\u62ff\u7ed3\u679c\n\n\u5feb\u6377\u952e\nO \u91cd\u65b0\u9009\u56fe\nBackspace \u5220\u9664\u6700\u540e\u906e\u6321\nDelete \u6e05\u7a7a\u906e\u6321\nEsc \u6e05\u7a7a\u5168\u90e8", bg=PANEL, fg=MUTED, anchor="w", justify="left", font=("Segoe UI", 10)).pack(fill=tk.X, padx=16, pady=(0, 6))
        tk.Label(right, textvariable=self.status_var, bg=PANEL, fg="#50c4d3", anchor="w", justify="left", wraplength=SIDEBAR_WIDTH - 32, font=("Segoe UI", 10)).pack(fill=tk.X, padx=16, pady=(0, 16))

    def _bind_events(self) -> None:
        self.source_canvas.bind("<Configure>", lambda _event: self.render())
        self.crop_canvas.bind("<Configure>", lambda _event: self.render_previews())
        self.masked_canvas.bind("<Configure>", lambda _event: self.render_previews())
        self.source_canvas.bind("<Motion>", self.on_mouse_move)
        self.source_canvas.bind("<Leave>", lambda _event: self._set_cursor(None))
        self.source_canvas.bind("<ButtonPress-1>", lambda event: self.start_drag(event, "crop"))
        self.source_canvas.bind("<B1-Motion>", self.update_drag)
        self.source_canvas.bind("<ButtonRelease-1>", self.finish_drag)
        self.source_canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.source_canvas.bind("<B3-Motion>", self.update_drag)
        self.source_canvas.bind("<ButtonRelease-3>", self.finish_drag)
        self.root.bind("o", lambda _event: self.choose_image())
        self.root.bind("O", lambda _event: self.choose_image())
        self.root.bind("<BackSpace>", lambda _event: self.remove_last_mask())
        self.root.bind("<Delete>", lambda _event: self.clear_masks())
        self.root.bind("<Escape>", lambda _event: self.clear_all())

    def choose_image(self) -> None:
        image_path = filedialog.askopenfilename(parent=self.root, title="\u9009\u62e9\u56fe\u7247", initialdir=str(TEST_IMAGE_DIR), filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp *.webp"), ("All Files", "*.*")])
        if image_path:
            self.load_image(Path(image_path))

    def load_image(self, image_path: Path) -> None:
        with Image.open(image_path) as loaded:
            self.image_pil = loaded.convert("RGB")
        self.image_rgb = np.array(self.image_pil)
        self.image_path = image_path
        self.crop_rect = None
        self.mask_rects = []
        self.file_var.set(image_path.name)
        self.status_var.set("\u5de6\u952e\u62d6\u62fd\u8bbe\u7f6e\u88c1\u526a\u533a\uff0c\u53f3\u952e\u62d6\u62fd\u8ffd\u52a0\u906e\u6321\u533a")
        self.update_export()
        self.render()

    def copy_export(self) -> None:
        content = self.export_text.get("1.0", tk.END).strip()
        if content:
            self.root.clipboard_clear()
            self.root.clipboard_append(content)
            self.root.update_idletasks()
            self.status_var.set("\u5bfc\u51fa\u6587\u672c\u5df2\u590d\u5236")

    def copy_crop(self) -> None:
        if self.crop_rect is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(format_rect((self.crop_rect.x1, self.crop_rect.y1, self.crop_rect.x2, self.crop_rect.y2)))
        self.root.update_idletasks()
        self.status_var.set("\u88c1\u526a\u533a\u5df2\u590d\u5236")

    def clear_masks(self) -> None:
        self.mask_rects = []
        self.status_var.set("\u5df2\u6e05\u7a7a\u906e\u6321\u533a")
        self.update_export()
        self.render()

    def remove_last_mask(self) -> None:
        if self.mask_rects:
            self.mask_rects.pop()
            self.status_var.set("\u5df2\u5220\u9664\u6700\u540e\u4e00\u4e2a\u906e\u6321\u533a")
            self.update_export()
            self.render()

    def clear_all(self) -> None:
        self.crop_rect = None
        self.mask_rects = []
        self.drag_origin = None
        self.drag_preview = None
        self.drag_kind = None
        self.status_var.set("\u5df2\u6e05\u7a7a\u88c1\u526a\u533a\u548c\u906e\u6321\u533a")
        self.update_export()
        self.render()

    def on_right_press(self, event: tk.Event) -> None:
        if self.crop_rect is None:
            self.status_var.set("\u8bf7\u5148\u753b\u88c1\u526a\u533a\uff0c\u518d\u6dfb\u52a0\u906e\u6321\u533a")
            return
        self.start_drag(event, "mask")

    def start_drag(self, event: tk.Event, drag_kind: str) -> None:
        point = self.canvas_to_image(event.x, event.y)
        if point is None:
            return
        self.drag_origin = point
        self.drag_preview = CropRect(point.x, point.y, point.x, point.y)
        self.drag_kind = drag_kind

    def update_drag(self, event: tk.Event) -> None:
        if self.drag_origin is None:
            return
        point = self.canvas_to_image(event.x, event.y)
        if point is None:
            return
        x1, y1, x2, y2 = normalize_rect(self.drag_origin.x, self.drag_origin.y, point.x, point.y)
        self.drag_preview = CropRect(x1, y1, x2, y2)
        self.render()

    def finish_drag(self, event: tk.Event) -> None:
        if self.drag_origin is None or self.drag_kind is None:
            return
        point = self.canvas_to_image(event.x, event.y) or self.drag_origin
        x1, y1, x2, y2 = normalize_rect(self.drag_origin.x, self.drag_origin.y, point.x, point.y)
        rect = CropRect(x1, y1, x2, y2)
        if rect.x2 > rect.x1 and rect.y2 > rect.y1:
            if self.drag_kind == "crop":
                self.crop_rect = rect
                self.mask_rects = []
                self.status_var.set("\u5df2\u66f4\u65b0\u88c1\u526a\u533a")
            elif self.crop_rect is not None:
                mask = relative_mask_from_absolute(self.crop_rect, rect)
                if mask is not None:
                    self.mask_rects.append(mask)
                    self.status_var.set("\u5df2\u8ffd\u52a0\u906e\u6321\u533a")
        self.drag_origin = None
        self.drag_preview = None
        self.drag_kind = None
        self.update_export()
        self.render()

    def on_mouse_move(self, event: tk.Event) -> None:
        self._set_cursor(self.canvas_to_image(event.x, event.y))
        self.render()

    def _set_cursor(self, point: PixelPoint | None) -> None:
        self.cursor_var.set("-" if point is None else f"({point.x}, {point.y})")

    def canvas_to_image(self, x: float, y: float) -> PixelPoint | None:
        if self.image_pil is None:
            return None
        image_x = round((x - self.offset_x) / self.scale)
        image_y = round((y - self.offset_y) / self.scale)
        if image_x < 0 or image_y < 0 or image_x >= self.image_pil.size[0] or image_y >= self.image_pil.size[1]:
            return None
        return PixelPoint(image_x, image_y)

    def image_to_canvas(self, x: int, y: int) -> tuple[float, float]:
        return self.offset_x + (x * self.scale), self.offset_y + (y * self.scale)

    def render(self) -> None:
        self.source_canvas.delete("all")
        if self.image_pil is None:
            self.source_canvas.create_text(400, 300, text="\u8bf7\u9009\u62e9\u4e00\u5f20\u56fe\u7247", fill=TEXT, font=("Segoe UI", 20, "bold"))
            self.render_previews()
            return

        canvas_width = max(self.source_canvas.winfo_width(), 1)
        canvas_height = max(self.source_canvas.winfo_height(), 1)
        self.scale = min(canvas_width / self.image_pil.size[0], canvas_height / self.image_pil.size[1])
        self.offset_x = (canvas_width - (self.image_pil.size[0] * self.scale)) / 2
        self.offset_y = (canvas_height - (self.image_pil.size[1] * self.scale)) / 2

        display = self.image_pil.resize((max(int(self.image_pil.size[0] * self.scale), 1), max(int(self.image_pil.size[1] * self.scale), 1)), Image.Resampling.LANCZOS)
        self.source_photo = ImageTk.PhotoImage(display)
        self.source_canvas.create_image(self.offset_x, self.offset_y, image=self.source_photo, anchor=tk.NW)

        if self.crop_rect is not None:
            self.draw_rect(self.crop_rect, CROP_COLOR)
            for mask in self.mask_rects:
                self.draw_rect(absolute_mask_from_relative(self.crop_rect, mask), MASK_COLOR)
        if self.drag_preview is not None:
            self.draw_rect(self.drag_preview, PREVIEW_COLOR, dash=(6, 4))
        self.render_previews()

    def draw_rect(self, rect: CropRect, color: str, dash: tuple[int, int] | None = None) -> None:
        x1, y1 = self.image_to_canvas(rect.x1, rect.y1)
        x2, y2 = self.image_to_canvas(rect.x2, rect.y2)
        self.source_canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, dash=dash)

    def render_previews(self) -> None:
        if self.image_rgb is None or self.crop_rect is None:
            self.draw_preview(self.crop_canvas, None, "\u6682\u65e0\u88c1\u526a\u533a")
            self.draw_preview(self.masked_canvas, None, "\u6682\u65e0\u906e\u6321\u7ed3\u679c")
            return
        crop = crop_image(self.image_rgb, self.crop_rect)
        masked = apply_masks(crop, self.mask_rects)
        self.draw_preview(self.crop_canvas, crop, "\u6682\u65e0\u88c1\u526a\u533a")
        self.draw_preview(self.masked_canvas, masked, "\u6682\u65e0\u906e\u6321\u7ed3\u679c")

    def draw_preview(self, canvas: tk.Canvas, image_rgb: np.ndarray | None, empty_text: str) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        if image_rgb is None or image_rgb.size == 0:
            canvas.create_text(width / 2, height / 2, text=empty_text, fill=MUTED, font=("Segoe UI", 11))
            return
        pil = Image.fromarray(image_rgb)
        scale = min(width / pil.size[0], height / pil.size[1], 1.0)
        display = pil.resize((max(int(pil.size[0] * scale), 1), max(int(pil.size[1] * scale), 1)), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(display)
        canvas.create_image(width / 2, height / 2, image=photo, anchor=tk.CENTER)
        if canvas is self.crop_canvas:
            self.crop_photo = photo
        else:
            self.masked_photo = photo

    def update_export(self) -> None:
        self.crop_var.set("-" if self.crop_rect is None else format_rect((self.crop_rect.x1, self.crop_rect.y1, self.crop_rect.x2, self.crop_rect.y2)))
        self.mask_var.set(str(len(self.mask_rects)))
        self.export_text.delete("1.0", tk.END)
        if self.crop_rect is not None:
            text = format_export_block(self.image_path.name if self.image_path else "unknown", self.crop_rect, self.mask_rects)
            self.export_text.insert("1.0", text)


def main() -> int:
    enable_dpi_awareness()
    root = tk.Tk()
    open_dialog_on_start = os.environ.get("LUMINA_MASK_PICKER_SKIP_START_DIALOG") != "1"
    app = MaskRegionPickerApp(root, open_dialog_on_start=open_dialog_on_start)

    image_path_raw = os.environ.get("LUMINA_MASK_PICKER_IMAGE")
    if image_path_raw:
        image_path = Path(image_path_raw)
        if image_path.exists():
            root.after(50, lambda: app.load_image(image_path))

    auto_close_raw = os.environ.get("LUMINA_MASK_PICKER_AUTO_CLOSE_MS")
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

