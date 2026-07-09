from __future__ import annotations

import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

try:
    from tkcalendar import DateEntry
except Exception:  # pragma: no cover - optional dependency fallback
    DateEntry = None

from no_face_no_case.app.theme import ACCENT, BG, BLUE, DANGER, GREEN, INK, PANEL, TEXT, apply_theme
from no_face_no_case.app.widgets import pixel_title
from no_face_no_case.core.detection import FaceDetector
from no_face_no_case.core.effects import filter_detections_by_regions, intersects, privacy_preview
from no_face_no_case.core.identity import FaceMemory
from no_face_no_case.core.motion import estimate_translation, shift_regions
from no_face_no_case.core.models import ManualRegion, PlannerState, Rect
from no_face_no_case.core.processor import FaceTracker, MediaProcessor
from no_face_no_case.infrastructure.media_io import cv_to_rgb, first_frame, frame_at_index, inspect_media
from no_face_no_case.paths import bundled_or_old_asset


class PlannerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.state = PlannerState()
        self.detector = FaceDetector(bundled_or_old_asset("yolo26_face_fp32.onnx"))
        self.detector_model_options = {
            "YOLO26 face": (bundled_or_old_asset("yolo26_face_fp32.onnx"), None),
            "YOLO26n person (experimental)": (bundled_or_old_asset("yolo26n.pt"), {"person"}),
        }
        self.detector_model_name = "YOLO26 face"
        self.processor = MediaProcessor(self.detector)
        self.media_info = None
        self.base_preview_frame_bgr = None
        self.preview_frame_bgr = None
        self.preview_frame_index = 0
        self.preview_detections: list[tuple[int, int, int, int]] = []
        self.remembered_preview_detections: list[tuple[int, int, int, int]] = []
        self._raw_preview_detections: list[tuple[int, int, int, int]] = []
        self.preview_face_tracker = FaceTracker(0)
        self.preview_tracker_frame_index = -1
        self.face_memory = FaceMemory()
        self.ignored_detection_memory = FaceMemory()
        self.preview_protected_regions: list[Rect] = []
        self.preview_effect_regions: list[Rect] = []
        self.preview_manual_region_refs: list[tuple[int, ManualRegion]] = []
        self.detected_faces_rows_frame: ttk.Frame | None = None
        self.remembered_faces_rows_frame: ttk.Frame | None = None
        self.preview_photo = None
        self.canvas_image_box = (0, 0, 1, 1)
        self.selected_region_index: int | None = None
        self.region_drag_index: int | None = None
        self.drag_start: tuple[int, int] | None = None
        self.drag_start_region: Rect | None = None
        self.active_drag_id: int | None = None
        self.timeline_drag_region_index: int | None = None
        self.timeline_drag_edge: str | None = None
        self.timeline_drag_start_frame: int | None = None
        self.timeline_drag_original_frames: tuple[int, int, list[int]] | None = None
        self.detect_after_id: str | None = None
        self.seek_after_id: str | None = None
        self.playback_after_id: str | None = None
        self.is_preview_playing = False
        self._closing = False
        self.suppress_video_seek_callback = False
        self.processing_started_at = 0.0
        self.preview_detection_generation = 0

        self._vars()
        self._window()
        self.setup_gui()

    #region GUI
    def setup_gui(self) -> None:
        shell = ttk.Frame(self.root)
        shell.pack(fill="both", expand=True, padx=16, pady=12)

        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 2))
        pixel_title(
            header,
            "No Face, No Case",
            bundled_or_old_asset("PixelifySans-Regular.ttf"),
            size=60,
        ).pack(anchor="center")

        intro = ttk.Label(
            shell,
            text="Production workflow: review detections, adjust manual boxes, then export a privacy-safe copy.",
            style="Muted.TLabel",
        )
        intro.pack(anchor="center", pady=(0, 12))

        body = ttk.Frame(shell)
        body.pack(fill="both", expand=True)

        left_shell = tk.Frame(body, width=370, bg=PANEL, highlightbackground="#4a463c", highlightthickness=1)
        left_shell.pack(side="left", fill="y", padx=(0, 14))
        left_shell.pack_propagate(False)
        left = self._build_scrollable_panel(left_shell)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)

        self._build_file_panel(left)
        self._build_options_panel(left)
        self._build_metadata_panel(left)
        self._build_planner(right)
        self._build_footer(shell)

    def _build_file_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="File Setup", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        self.file_entry = self._browse_row(parent, "Media file", self.select_file)
        self.output_entry = self._browse_row(parent, "Output folder", self.select_output_folder)
        self.specs_label = ttk.Label(parent, text="No media selected", style="Muted.TLabel", wraplength=330)
        self.specs_label.pack(anchor="w", pady=(6, 14))
        self._section_break(parent)

    def _build_options_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Detection & Tracking", style="Section.TLabel").pack(anchor="w", pady=(4, 8))
        ttk.Label(parent, text="Detected area to affect").pack(anchor="w")
        ttk.Radiobutton(
            parent,
            text="Face area",
            variable=self.detection_area_var,
            value="face",
            command=self.select_detection_area,
        ).pack(anchor="w")
        ttk.Radiobutton(
            parent,
            text="Person",
            variable=self.detection_area_var,
            value="person",
            command=self.select_detection_area,
        ).pack(anchor="w")
        self.detection_detail_frame = ttk.Frame(parent)
        self.detection_detail_frame.pack(anchor="w", fill="x")
        self._sync_detection_area_controls()
        self._slider(parent, "Effect hold frames", self.extra_hold_var, 0, 30, self._reset_preview_tracker)
        self._slider(parent, "Confidence", self.confidence_var, 0.05, 1.0, self.schedule_detect_preview_faces)

        ttk.Label(parent, text="Effect Mode", style="Section.TLabel").pack(anchor="w", pady=(14, 8))
        ttk.Radiobutton(
            parent,
            text="Blur/pixelate detected faces",
            variable=self.target_var,
            value="faces",
            command=self.refresh_preview,
        ).pack(anchor="w")
        ttk.Radiobutton(
            parent,
            text="Keep faces clear, affect background",
            variable=self.target_var,
            value="background",
            command=self.refresh_preview,
        ).pack(anchor="w", pady=(0, 8))

        self._slider(parent, "Pixel size", self.face_pixel_var, 2, 100, self.refresh_preview)
        self._slider(parent, "Blur strength", self.blur_size_var, 3, 101, self.refresh_preview)

        ttk.Label(parent, text="Effects", style="Section.TLabel").pack(anchor="w", pady=(10, 8))
        ttk.Checkbutton(
            parent, text="Pixelate detected faces", variable=self.pixelate_var, command=self.refresh_preview
        ).pack(anchor="w")
        ttk.Checkbutton(parent, text="Blur selected target", variable=self.blur_var, command=self.refresh_preview).pack(
            anchor="w"
        )
        ttk.Checkbutton(parent, text="Use overlay on faces", variable=self.overlay_var, command=self.refresh_preview).pack(
            anchor="w"
        )
        ttk.Checkbutton(
            parent,
            text="Move protected boxes with camera",
            variable=self.follow_motion_var,
            command=self.refresh_preview,
        ).pack(anchor="w")
        ttk.Button(parent, text="Choose overlay", command=self.select_overlay).pack(anchor="w", pady=(6, 10))

        ttk.Label(parent, text="Review Tools", style="Section.TLabel").pack(anchor="w", pady=(14, 8))
        ttk.Label(
            parent,
            text=(
                "Controls: drag preview to add boxes. Drag a selected box to set a motion stop. "
                "Use the timeline handles for duration, drag the timeline bar to move it, "
                "right-click detections to ignore, double-click to remember."
            ),
            style="Muted.TLabel",
            wraplength=330,
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(parent, text="New manual box").pack(anchor="w")
        ttk.Radiobutton(
            parent,
            text="Keep clear / unblur",
            variable=self.manual_mode_var,
            value="clear",
        ).pack(anchor="w")
        ttk.Radiobutton(
            parent,
            text="Force blur/pixelate",
            variable=self.manual_mode_var,
            value="effect",
        ).pack(anchor="w", pady=(0, 6))
        self._slider(parent, "Manual box duration", self.manual_duration_var, 1, 300, None)
        ttk.Button(parent, text="Track selected box with camera", command=self.toggle_selected_region_tracking).pack(
            anchor="w", pady=(10, 0)
        )
        ttk.Button(parent, text="Detect faces again", command=self.detect_preview_faces).pack(anchor="w", pady=(8, 0))
        ttk.Button(parent, text="Clear remembered items", command=self.clear_remembered_faces).pack(
            anchor="w", pady=(8, 0)
        )
        ttk.Button(parent, text="Clear ignored detections", command=self.clear_ignored_detections).pack(
            anchor="w", pady=(8, 0)
        )
        ttk.Button(parent, text="Clear protected boxes", command=self.clear_regions).pack(anchor="w", pady=(8, 12))

        ttk.Label(parent, text="Detected Faces", style="Section.TLabel").pack(anchor="w", pady=(4, 8))
        self.detected_faces_rows_frame = ttk.Frame(parent)
        self.detected_faces_rows_frame.pack(anchor="w", fill="x")

        ttk.Label(parent, text="Remembered Faces", style="Section.TLabel").pack(anchor="w", pady=(12, 8))
        self.remembered_faces_rows_frame = ttk.Frame(parent)
        self.remembered_faces_rows_frame.pack(anchor="w", fill="x")
        self._section_break(parent)

    def _build_metadata_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Metadata", style="Section.TLabel").pack(anchor="w", pady=(4, 8))
        self.title_entry = self._labeled_entry(parent, "Filename")
        self.location_entry = self._labeled_entry(parent, "Location")
        ttk.Label(parent, text="Date").pack(anchor="w")
        if DateEntry:
            self.date_entry = DateEntry(parent, date_pattern="dd.MM.yyyy")
        else:
            self.date_entry = ttk.Entry(parent)
            self.date_entry.insert(0, datetime.now().strftime("%d.%m.%Y"))
        self.date_entry.pack(anchor="w", fill="x", pady=(2, 12))

    def _build_planner(self, parent: ttk.Frame) -> None:
        top = ttk.Frame(parent)
        top.pack(fill="x")
        ttk.Label(top, text="Preview", style="Section.TLabel").pack(side="left")
        self.region_count_label = ttk.Label(top, text="0 faces, 0 protected boxes", style="Muted.TLabel")
        self.region_count_label.pack(side="right")

        canvas_wrap = tk.Frame(parent, bg=PANEL, padx=8, pady=8, highlightbackground="#4a463c", highlightthickness=1)
        canvas_wrap.pack(fill="both", expand=True, pady=(8, 10))
        self.preview_canvas = tk.Canvas(
            canvas_wrap,
            bg=INK,
            highlightthickness=1,
            highlightbackground="#101010",
            highlightcolor=ACCENT,
            cursor="crosshair",
        )
        self.preview_canvas.pack(fill="both", expand=True)
        self.preview_canvas.bind("<Configure>", lambda _event: self.refresh_preview())
        self.preview_canvas.bind("<ButtonPress-1>", self.start_region)
        self.preview_canvas.bind("<B1-Motion>", self.drag_region)
        self.preview_canvas.bind("<ButtonRelease-1>", self.finish_region)
        self.preview_canvas.bind("<Button-3>", self.ignore_detection_at)
        self.preview_canvas.bind("<Control-Button-1>", self.ignore_detection_at)
        self.preview_canvas.bind("<Double-Button-1>", self.remember_detection_at)
        self.preview_canvas.bind("<Delete>", self.delete_selected_region)
        self.preview_canvas.bind("<BackSpace>", self.delete_selected_region)
        self.preview_canvas.bind("<MouseWheel>", self.step_video_with_wheel)
        self.preview_canvas.bind("<Button-4>", self.step_video_with_wheel)
        self.preview_canvas.bind("<Button-5>", self.step_video_with_wheel)

        controls = ttk.Frame(parent)
        controls.pack(fill="x")
        ttk.Button(controls, text="Process", style="Accent.TButton", command=self.process).pack(side="left")
        self.progress = ttk.Progressbar(controls, orient="horizontal", mode="determinate", length=360)
        self.progress.pack(side="left", fill="x", expand=True, padx=12)
        self.status_label = ttk.Label(controls, text="Ready", style="Muted.TLabel")
        self.status_label.pack(side="left")

        video_controls = ttk.Frame(parent)
        video_controls.pack(fill="x", pady=(8, 0))
        ttk.Label(video_controls, text="Video frame", style="Muted.TLabel").pack(side="left")
        self.play_button = ttk.Button(video_controls, text="Play", width=7, command=self.toggle_preview_playback)
        self.play_button.pack(side="left", padx=(8, 2))
        self.play_button.state(["disabled"])
        ttk.Button(video_controls, text="<", width=3, command=lambda: self.step_video_frame(-1)).pack(
            side="left", padx=(2, 2)
        )
        self.video_slider = ttk.Scale(
            video_controls,
            from_=0,
            to=100,
            orient="horizontal",
            variable=self.video_seek_var,
            command=lambda _value: self.schedule_video_seek(),
        )
        self.video_slider.pack(side="left", fill="x", expand=True, padx=4)
        ttk.Button(video_controls, text=">", width=3, command=lambda: self.step_video_frame(1)).pack(
            side="left", padx=(2, 8)
        )
        self.video_time_label = ttk.Label(video_controls, text="Frame 0/0  00:00", style="Muted.TLabel", width=18)
        self.video_time_label.pack(side="left")

        timeline_wrap = tk.Frame(parent, bg=PANEL, highlightbackground="#4a463c", highlightthickness=1)
        timeline_wrap.pack(fill="x", pady=(8, 0))
        self.timeline_canvas = tk.Canvas(timeline_wrap, height=132, bg=INK, highlightthickness=0)
        timeline_scrollbar = tk.Scrollbar(
            timeline_wrap,
            orient="vertical",
            command=self.timeline_canvas.yview,
            width=14,
            bg=ACCENT,
            activebackground="#ffd166",
            troughcolor="#191816",
            relief="flat",
            bd=0,
        )
        self.timeline_canvas.configure(yscrollcommand=timeline_scrollbar.set)
        self.timeline_canvas.pack(side="left", fill="x", expand=True)
        timeline_scrollbar.pack(side="right", fill="y")
        self.timeline_canvas.bind("<ButtonPress-1>", self.start_timeline_drag)
        self.timeline_canvas.bind("<B1-Motion>", self.drag_timeline_handle)
        self.timeline_canvas.bind("<ButtonRelease-1>", self.finish_timeline_drag)
        self.timeline_canvas.bind("<MouseWheel>", self.scroll_timeline)
        self.timeline_canvas.bind("<Button-4>", self.scroll_timeline)
        self.timeline_canvas.bind("<Button-5>", self.scroll_timeline)

    def _build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent)
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(footer, text="Developed by ACME Prototypes", style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Help", command=self.show_help).pack(side="right")
    #endregion GUI

    #region Planner
    def refresh_preview(self) -> None:
        self.preview_canvas.delete("all")
        if self.preview_frame_bgr is None:
            self.preview_canvas.create_text(
                self.preview_canvas.winfo_width() // 2,
                self.preview_canvas.winfo_height() // 2,
                text="Choose a file to start planning",
                fill=TEXT,
                font=("Segoe UI", 16, "bold"),
            )
            return

        canvas_width = self.preview_canvas.winfo_width()
        canvas_height = self.preview_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            self.root.after_idle(self.refresh_preview)
            return

        self._sync_effect_settings()
        self.preview_protected_regions = self._current_preview_protected_regions()
        self.preview_effect_regions = self._current_preview_effect_regions()
        self.preview_manual_region_refs = self._active_manual_region_refs()
        preview = privacy_preview(
            self.preview_frame_bgr,
            self.preview_detections,
            self.preview_protected_regions,
            self.state.settings,
            self.preview_effect_regions,
        )
        image = Image.fromarray(cv_to_rgb(preview))
        canvas_width = max(10, canvas_width)
        canvas_height = max(10, canvas_height)
        image.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
        x = (canvas_width - image.width) // 2
        y = (canvas_height - image.height) // 2
        self.canvas_image_box = (x, y, x + image.width, y + image.height)
        self.preview_photo = ImageTk.PhotoImage(image)
        self.preview_canvas.create_image(x, y, anchor="nw", image=self.preview_photo)
        self._draw_detection_boxes()
        self._draw_regions()
        self._draw_timeline()
        self._populate_detection_rows()

    def start_region(self, event: tk.Event) -> None:
        if self.preview_frame_bgr is None or not self._inside_image(event.x, event.y):
            return
        self.preview_canvas.focus_set()
        self.drag_start = (event.x, event.y)
        self.region_drag_index = self._manual_region_at_canvas_point(event.x, event.y)
        if self.region_drag_index is not None:
            self.selected_region_index = self.region_drag_index
            self.drag_start_region = self.state.manual_regions[self.region_drag_index].rect_at(
                self._current_region_frame_index()
            )
            self.active_drag_id = None
            if self.state.manual_regions[self.region_drag_index].locked:
                self.drag_start = None
                self.status_label.config(text="Selected box is locked")
            return
        self.selected_region_index = None
        self.drag_start_region = None
        self.active_drag_id = self.preview_canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline=ACCENT, width=3
        )

    def drag_region(self, event: tk.Event) -> None:
        if self.drag_start is None or self.active_drag_id is None:
            if self.drag_start is not None and self.region_drag_index is not None and self.drag_start_region is not None:
                self._move_selected_region(event.x, event.y)
            return
        x, y = self._clamp_to_image(event.x, event.y)
        self.preview_canvas.coords(self.active_drag_id, self.drag_start[0], self.drag_start[1], x, y)

    def finish_region(self, event: tk.Event) -> None:
        if self.drag_start is None:
            return
        x1, y1 = self.drag_start
        x2, y2 = self._clamp_to_image(event.x, event.y)
        self.drag_start = None
        self.drag_start_region = None
        moved_index = self.region_drag_index
        self.region_drag_index = None
        self.active_drag_id = None
        if moved_index is not None:
            self.selected_region_index = moved_index
            self.refresh_preview()
            return
        if abs(x2 - x1) < 8 or abs(y2 - y1) < 8:
            self.refresh_preview()
            return
        new_region = self._canvas_rect_to_normalized(x1, y1, x2, y2)
        start_frame = self._manual_region_start_frame()
        manual_region = ManualRegion(
            rect=new_region,
            mode=self.manual_mode_var.get(),
            start_frame=start_frame,
            end_frame=self._manual_region_end_frame(),
        )
        manual_region.set_keyframe(start_frame, new_region)
        self.state.manual_regions.append(manual_region)
        self.selected_region_index = len(self.state.manual_regions) - 1
        self._update_region_count()
        self.refresh_preview()

    def clear_regions(self) -> None:
        self.state.protected_regions.clear()
        self.state.manual_regions.clear()
        self.region_drag_index = None
        self.selected_region_index = None
        self._update_region_count()
        self.refresh_preview()

    def delete_selected_region(self, _event: tk.Event | None = None) -> None:
        if self.selected_region_index is None:
            return
        if self.selected_region_index < 0 or self.selected_region_index >= len(self.state.manual_regions):
            return
        if self.state.manual_regions[self.selected_region_index].locked:
            self.status_label.config(text="Unlock the selected box before deleting it")
            return
        del self.state.manual_regions[self.selected_region_index]
        self.region_drag_index = None
        self.selected_region_index = None
        self._update_region_count()
        self.refresh_preview()

    def toggle_selected_region_lock(self) -> None:
        region = self._selected_manual_region()
        if region is None:
            return
        region.locked = not region.locked
        self.status_label.config(text="Box locked" if region.locked else "Box unlocked")
        self.refresh_preview()

    def toggle_selected_region_tracking(self) -> None:
        region = self._selected_manual_region()
        if region is None:
            return
        if region.locked:
            self.status_label.config(text="Unlock the selected box before changing tracking")
            return
        region.follow_motion = not region.follow_motion
        self.status_label.config(
            text="Selected box will track camera motion" if region.follow_motion else "Selected box tracking disabled"
        )
        self.refresh_preview()

    def select_detection_area(self) -> None:
        self._sync_detection_area_controls()
        if self.detection_area_var.get() == "person":
            person_detector = "YOLO26n person (experimental)"
            if self.detector_model_name != person_detector:
                self.detector_model_name = person_detector
                model_path, allowed_class_names = self.detector_model_options[person_detector]
                self.detector.set_yolo_model(model_path, allowed_class_names)
                self.face_memory.clear()
                self.ignored_detection_memory.clear()
                self.detect_preview_faces()
                return
        elif self.detection_area_var.get() == "face":
            face_detector = "YOLO26 face"
            if self.detector_model_name != face_detector:
                self.detector_model_name = face_detector
                model_path, allowed_class_names = self.detector_model_options[face_detector]
                self.detector.set_yolo_model(model_path, allowed_class_names)
                self.face_memory.clear()
                self.ignored_detection_memory.clear()
                self.detect_preview_faces()
                return
        self._sync_effect_settings()
        self._sync_memory_mode()
        self._apply_ignored_detection_filter()
        self.refresh_preview()

    def detect_preview_faces(self) -> None:
        if self.preview_frame_bgr is None:
            return
        if self.detect_after_id is not None:
            self.root.after_cancel(self.detect_after_id)
            self.detect_after_id = None
        self._sync_effect_settings()
        self._sync_memory_mode()
        self.preview_detection_generation += 1
        generation = self.preview_detection_generation
        frame = self.preview_frame_bgr.copy()
        confidence = float(self.state.settings.confidence_threshold)
        self.status_label.config(text="Detecting faces...")
        threading.Thread(
            target=self._detect_preview_faces_worker,
            args=(frame, confidence, generation),
            daemon=True,
        ).start()

    def schedule_detect_preview_faces(self) -> None:
        if self.preview_frame_bgr is None:
            return
        if self.detect_after_id is not None:
            self.root.after_cancel(self.detect_after_id)
        self.status_label.config(text="Detection settings changed...")
        self.detect_after_id = self.root.after(250, self.detect_preview_faces)

    def _detect_preview_faces_worker(self, frame, confidence: float, generation: int) -> None:
        try:
            detections = self.detector.detect(frame, confidence)
        except Exception as exc:
            if not self._closing:
                try:
                    self.root.after(
                        0,
                        lambda message=str(exc), gen=generation: self._finish_preview_detection_error(message, gen),
                    )
                except tk.TclError:
                    pass
            return

        if self._closing:
            return

        try:
            self.root.after(0, lambda dets=detections, gen=generation: self._finish_preview_detection(dets, gen))
        except tk.TclError:
            pass

    def _finish_preview_detection(self, detections: list[tuple[int, int, int, int]], generation: int) -> None:
        if generation != self.preview_detection_generation or self.preview_frame_bgr is None:
            return
        self._raw_preview_detections = detections
        self._apply_ignored_detection_filter()
        self._apply_preview_hold_tracker()
        self._update_region_count()
        self.status_label.config(text=f"Detected {len(self.preview_detections)} face(s)")
        self.refresh_preview()

    def _finish_preview_detection_error(self, message: str, generation: int) -> None:
        if generation != self.preview_detection_generation or self.preview_frame_bgr is None:
            return
        self._raw_preview_detections = []
        self.preview_detections = []
        self.remembered_preview_detections = []
        self._update_region_count()
        self.status_label.config(text="Face detection failed")
        messagebox.showerror("Face detection failed", message)
        self.refresh_preview()

    def ignore_detection_at(self, event: tk.Event) -> None:
        detection = self._detection_at_canvas_point(event.x, event.y)
        if detection is None or self.preview_frame_bgr is None:
            return
        self.ignore_detection_box(detection)

    def remember_detection_at(self, event: tk.Event) -> None:
        detection = self._detection_at_canvas_point(event.x, event.y)
        if detection is None or self.preview_frame_bgr is None:
            return
        self._sync_memory_mode()
        if self.face_memory.remember(self.preview_frame_bgr, detection):
            self.drag_start = None
            self.active_drag_id = None
            self._apply_ignored_detection_filter()
            self._update_region_count()
            self.status_label.config(text=f"Remembered {len(self.face_memory)} {self._remembered_label()}(s)")
            self.refresh_preview()

    def ignore_detection_box(self, detection: tuple[int, int, int, int]) -> None:
        if self.preview_frame_bgr is None:
            return
        self._sync_memory_mode()
        self.ignored_detection_memory.remember(self.preview_frame_bgr, detection)
        self._apply_ignored_detection_filter()
        self._update_region_count()
        self.status_label.config(text="Ignored detected face")
        self.refresh_preview()

    def forget_remembered_detection(self, detection: tuple[int, int, int, int]) -> None:
        if self.preview_frame_bgr is None:
            return
        if self.face_memory.forget(self.preview_frame_bgr, detection):
            self._apply_ignored_detection_filter()
            self._update_region_count()
            self.status_label.config(text="Removed remembered face")
            self.refresh_preview()

    def clear_remembered_faces(self) -> None:
        self.face_memory.clear()
        self._apply_ignored_detection_filter()
        self._update_region_count()
        self.refresh_preview()

    def clear_ignored_detections(self) -> None:
        self.state.ignored_detection_regions.clear()
        self.ignored_detection_memory.clear()
        self._apply_ignored_detection_filter()
        self._update_region_count()
        self.refresh_preview()

    def schedule_video_seek(self) -> None:
        if not self.media_info or self.media_info.kind != "video" or not self.state.media_path:
            return
        if self.suppress_video_seek_callback:
            return
        self.stop_preview_playback()
        if self.seek_after_id is not None:
            self.root.after_cancel(self.seek_after_id)
        self.seek_after_id = self.root.after(120, self.load_video_preview_frame)

    def load_video_preview_frame(self) -> None:
        if not self.media_info or self.media_info.kind != "video" or not self.state.media_path:
            return
        if self.seek_after_id is not None:
            self.root.after_cancel(self.seek_after_id)
            self.seek_after_id = None
        frame_count = self.media_info.frame_count or 1
        frame_index = min(max(0, int(round(self.video_seek_var.get()))), max(0, frame_count - 1))
        try:
            self.preview_frame_index = frame_index
            self.preview_frame_bgr = frame_at_index(self.state.media_path, frame_index)
            duration = self.media_info.duration_seconds or 0
            fps = self.media_info.fps or 30.0
            current_seconds = frame_index / fps
            self.video_time_label.config(
                text=f"Frame {frame_index + 1}/{frame_count}  {time.strftime('%M:%S', time.gmtime(current_seconds))}"
            )
            self.detect_preview_faces()
        except Exception as exc:
            self.stop_preview_playback()
            self.status_label.config(text="Could not seek video")
            messagebox.showerror("Video preview failed", str(exc))

    def step_video_frame(self, delta: int) -> None:
        if not self.media_info or self.media_info.kind != "video":
            return
        self.stop_preview_playback()
        frame_count = self.media_info.frame_count or 1
        next_frame = min(max(0, self.preview_frame_index + delta), max(0, frame_count - 1))
        self.video_seek_var.set(next_frame)
        self.load_video_preview_frame()

    def step_video_with_wheel(self, event: tk.Event) -> None:
        if not self.media_info or self.media_info.kind != "video":
            return
        if getattr(event, "num", None) == 4 or getattr(event, "delta", 0) > 0:
            self.step_video_frame(-1)
        else:
            self.step_video_frame(1)

    def toggle_preview_playback(self) -> None:
        if not self.media_info or self.media_info.kind != "video" or not self.state.media_path:
            return
        if self.is_preview_playing:
            self.stop_preview_playback()
            return
        frame_count = self.media_info.frame_count or 1
        if self.preview_frame_index >= frame_count - 1:
            self.preview_frame_index = 0
            self.suppress_video_seek_callback = True
            self.video_seek_var.set(0)
            self.suppress_video_seek_callback = False
        self.is_preview_playing = True
        self.play_button.config(text="Pause")
        self.status_label.config(text="Preview playing...")
        self._schedule_preview_playback_tick()

    def stop_preview_playback(self) -> None:
        if self.playback_after_id is not None:
            self.root.after_cancel(self.playback_after_id)
            self.playback_after_id = None
        if self.is_preview_playing:
            self.is_preview_playing = False
            self.play_button.config(text="Play")

    def _schedule_preview_playback_tick(self) -> None:
        if self._closing or not self.is_preview_playing:
            return
        fps = self.media_info.fps if self.media_info and self.media_info.fps else 12.0
        interval_ms = max(50, int(1000 / min(max(fps, 1.0), 12.0)))
        self.playback_after_id = self.root.after(interval_ms, self._preview_playback_tick)

    def _preview_playback_tick(self) -> None:
        self.playback_after_id = None
        if self._closing or not self.is_preview_playing or not self.media_info or self.media_info.kind != "video":
            return
        frame_count = self.media_info.frame_count or 1
        next_frame = self.preview_frame_index + 1
        if next_frame >= frame_count:
            self.stop_preview_playback()
            self.status_label.config(text="Preview ended")
            return
        self.suppress_video_seek_callback = True
        self.video_seek_var.set(next_frame)
        self.suppress_video_seek_callback = False
        self.load_video_preview_frame()
        if self._closing or not self.is_preview_playing:
            return
        if self.is_preview_playing:
            self._schedule_preview_playback_tick()
    #endregion Planner

    def _populate_detection_rows(self) -> None:
        self._populate_detection_section(
            self.detected_faces_rows_frame,
            self.preview_detections,
            "No current detections",
            "Ignore",
            self.ignore_detection_box,
        )
        self._populate_detection_section(
            self.remembered_faces_rows_frame,
            self.remembered_preview_detections,
            "No remembered faces",
            "Forget",
            self.forget_remembered_detection,
        )

    def _populate_detection_section(
        self,
        container: ttk.Frame | None,
        detections: list[tuple[int, int, int, int]],
        empty_text: str,
        action_text: str,
        action,
    ) -> None:
        if container is None:
            return
        for child in container.winfo_children():
            child.destroy()
        if not detections:
            ttk.Label(container, text=empty_text, style="Muted.TLabel", wraplength=300).pack(anchor="w", pady=(0, 4))
            return
        for index, detection in enumerate(detections, start=1):
            row = ttk.Frame(container)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=f"{index}.", width=4).pack(side="left")
            ttk.Label(
                row,
                text=f"{detection[0]}:{detection[1]}  {detection[2] - detection[0]}x{detection[3] - detection[1]}",
                style="Muted.TLabel",
            ).pack(side="left", fill="x", expand=True)
            ttk.Button(row, text=action_text, width=7, command=lambda box=detection: action(box)).pack(side="right")

    #region File Actions
    def select_file(self) -> None:
        self.stop_preview_playback()
        path = filedialog.askopenfilename(
            filetypes=[("Media files", "*.mp4 *.mov *.avi *.mkv *.webm *.jpg *.jpeg *.png *.bmp *.webp")]
        )
        if not path:
            return
        self.load_media_file_async(Path(path))

    def load_media_file(self, media_path: Path) -> None:
        self.stop_preview_playback()
        try:
            info = inspect_media(media_path)
            self.preview_frame_bgr = first_frame(media_path)
            self.base_preview_frame_bgr = self.preview_frame_bgr.copy()
        except Exception as exc:
            self._handle_media_load_error(str(exc))
            return
        self._finish_media_load(media_path, info, self.preview_frame_bgr)

    def load_media_file_async(self, media_path: Path) -> None:
        self.stop_preview_playback()
        self.status_label.config(text="Loading media...")
        threading.Thread(target=self._load_media_file_worker, args=(media_path,), daemon=True).start()

    def _load_media_file_worker(self, media_path: Path) -> None:
        try:
            info = inspect_media(media_path)
            preview_frame = first_frame(media_path)
        except Exception as exc:
            if not self._closing:
                try:
                    self.root.after(0, lambda message=str(exc): self._handle_media_load_error(message))
                except tk.TclError:
                    pass
            return

        if self._closing:
            return

        try:
            self.root.after(0, lambda: self._finish_media_load(media_path, info, preview_frame))
        except tk.TclError:
            pass

    def _finish_media_load(self, media_path: Path, info, preview_frame_bgr) -> None:
        self.preview_frame_bgr = preview_frame_bgr
        self.base_preview_frame_bgr = preview_frame_bgr.copy()
        self.state.media_path = media_path
        self.media_info = info
        self.preview_frame_index = 0
        self._reset_preview_tracker()
        self.video_seek_var.set(0)
        if info.kind == "video":
            frame_count = max(1, info.frame_count or 1)
            self.video_slider.configure(to=max(0, frame_count - 1))
            self.video_time_label.config(text=f"Frame 1/{frame_count}  00:00")
            self.play_button.state(["!disabled"])
        else:
            self.video_slider.configure(to=100)
            self.video_time_label.config(text="Frame 0/0  00:00")
            self.play_button.state(["disabled"])
        self.face_memory.clear()
        self.ignored_detection_memory.clear()
        self.remembered_preview_detections.clear()
        self.state.ignored_detection_regions.clear()
        self.state.protected_regions.clear()
        self.state.manual_regions.clear()
        self.selected_region_index = None
        self.file_entry.delete(0, tk.END)
        self.file_entry.insert(0, str(media_path))
        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, media_path.stem)
        if not self.output_entry.get().strip():
            self.output_entry.insert(0, str(media_path.parent))
            self.state.output_dir = media_path.parent
        self.specs_label.config(text=self._format_specs(info))
        self.status_label.config(text=f"Loaded {media_path.name}")
        self.root.after_idle(self.refresh_preview)
        self.root.after_idle(self.detect_preview_faces)

    def _handle_media_load_error(self, message: str) -> None:
        self.preview_frame_bgr = None
        self.base_preview_frame_bgr = None
        self.media_info = None
        self.status_label.config(text="Could not load media")
        messagebox.showerror("Could not load media", message)

    def select_output_folder(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.state.output_dir = Path(path)
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, path)

    def select_overlay(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp")])
        if path:
            self.state.settings.overlay_path = Path(path)

    def process(self) -> None:
        self.stop_preview_playback()
        if not self.state.media_path:
            messagebox.showerror("Missing media", "Choose a media file first.")
            return
        output_dir = Path(self.output_entry.get().strip()) if self.output_entry.get().strip() else None
        if not output_dir:
            messagebox.showerror("Missing output folder", "Choose an output folder first.")
            return

        self._sync_settings()
        self.processing_started_at = time.time()
        self.progress["value"] = 0
        self.status_label.config(text="Processing...")
        threading.Thread(target=self._process_worker, args=(output_dir,), daemon=True).start()

    def _process_worker(self, output_dir: Path) -> None:
        try:
            output = self.processor.process(
                self.state.media_path,
                output_dir,
                self.state.metadata,
                self.state.settings,
                self.state.protected_regions,
                self.state.manual_regions,
                self.state.ignored_detection_regions,
                self.face_memory,
                self.ignored_detection_memory,
                self._threadsafe_progress,
            )
            elapsed = time.strftime("%M:%S", time.gmtime(time.time() - self.processing_started_at))
            if not self._closing:
                try:
                    self.root.after(0, lambda: self._processing_done(output, elapsed))
                except tk.TclError:
                    pass
        except Exception as exc:
            if not self._closing:
                try:
                    self.root.after(0, lambda: messagebox.showerror("Processing failed", str(exc)))
                    self.root.after(0, lambda: self.status_label.config(text="Failed"))
                except tk.TclError:
                    pass
    #endregion File Actions

    #region Helpers
    def _build_scrollable_panel(self, parent: ttk.Frame) -> ttk.Frame:
        canvas = tk.Canvas(parent, width=360, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(
            parent,
            orient="vertical",
            command=canvas.yview,
            width=16,
            bg=ACCENT,
            activebackground="#ffd166",
            troughcolor="#191816",
            relief="flat",
            bd=0,
        )
        content = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def sync_scroll_region(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def sync_content_width(event: tk.Event) -> None:
            canvas.itemconfigure(window_id, width=event.width)

        def scroll(event: tk.Event) -> None:
            if getattr(event, "num", None) == 4:
                canvas.yview_scroll(-3, "units")
            elif getattr(event, "num", None) == 5:
                canvas.yview_scroll(3, "units")
            else:
                delta = -1 if getattr(event, "delta", 0) > 0 else 1
                canvas.yview_scroll(delta * 3, "units")

        def bind_scroll(_event: tk.Event) -> None:
            canvas.bind_all("<MouseWheel>", scroll)
            canvas.bind_all("<Button-4>", scroll)
            canvas.bind_all("<Button-5>", scroll)

        def unbind_scroll(_event: tk.Event) -> None:
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        content.bind("<Configure>", sync_scroll_region)
        canvas.bind("<Configure>", sync_content_width)
        canvas.bind("<Enter>", bind_scroll)
        canvas.bind("<Leave>", unbind_scroll)
        content.bind("<Enter>", bind_scroll)
        content.bind("<Leave>", unbind_scroll)

        content.configure(padding=(0, 0, 8, 0))
        return content

    def _section_break(self, parent: ttk.Frame) -> None:
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(4, 12))

    def _vars(self) -> None:
        self.target_var = tk.StringVar(value="faces")
        self.pixelate_var = tk.BooleanVar(value=True)
        self.blur_var = tk.BooleanVar(value=False)
        self.overlay_var = tk.BooleanVar(value=False)
        self.follow_motion_var = tk.BooleanVar(value=True)
        self.manual_mode_var = tk.StringVar(value="clear")
        self.detection_area_var = tk.StringVar(value="face")
        self.person_effect_percent_var = tk.DoubleVar(value=33)
        self.face_pixel_var = tk.DoubleVar(value=20)
        self.blur_size_var = tk.DoubleVar(value=51)
        self.expand_var = tk.DoubleVar(value=1.2)
        self.extra_hold_var = tk.DoubleVar(value=0)
        self.confidence_var = tk.DoubleVar(value=0.25)
        self.manual_duration_var = tk.DoubleVar(value=30)
        self.video_seek_var = tk.DoubleVar(value=0)

    def _window(self) -> None:
        self.root.title("No Face No Case")
        self.root.geometry("1180x820")
        self.root.minsize(980, 680)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        apply_theme(self.root)
        icon = bundled_or_old_asset("icon.ico")
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except Exception:
                pass

    def _browse_row(self, parent: ttk.Frame, label: str, command) -> ttk.Entry:
        ttk.Label(parent, text=label).pack(anchor="w")
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=(2, 10))
        entry = ttk.Entry(row, width=42)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="Browse", command=command).pack(side="left", padx=(6, 0))
        return entry

    def _labeled_entry(self, parent: ttk.Frame, label: str) -> ttk.Entry:
        ttk.Label(parent, text=label).pack(anchor="w")
        entry = ttk.Entry(parent)
        entry.pack(anchor="w", fill="x", pady=(2, 10))
        return entry

    def _slider(self, parent: ttk.Frame, label: str, variable: tk.DoubleVar, start: float, end: float, command) -> None:
        self._slider_row(parent, label, variable, start, end, command).pack(anchor="w", fill="x")

    def _slider_row(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.DoubleVar,
        start: float,
        end: float,
        command,
    ) -> ttk.Frame:
        row = ttk.Frame(parent)
        row.columnconfigure(0, weight=1)
        header = ttk.Frame(row)
        header.grid(row=0, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(header, text=label).pack(side="left", anchor="w")
        value_label = ttk.Label(header, style="Muted.TLabel", width=8, anchor="e")
        value_label.pack(side="right", anchor="e")

        slider = ttk.Scale(
            row,
            from_=start,
            to=end,
            orient="horizontal",
            variable=variable,
            command=lambda _value: command() if command else None,
        )
        slider.grid(row=1, column=0, sticky="ew")

        def update_value_label(*_args) -> None:
            if not value_label.winfo_exists():
                return
            value_label.config(text=self._format_slider_value(variable, start, end, label))

        variable.trace_add("write", update_value_label)
        update_value_label()
        return row

    def _format_slider_value(self, variable: tk.DoubleVar, start: float, end: float, label: str) -> str:
        value = float(variable.get())
        if "percent" in label.lower():
            return f"{int(round(value))}%"
        if max(abs(start), abs(end), abs(value)) >= 10 and abs(value - round(value)) < 0.001:
            return f"{int(round(value))}"
        if abs(value - round(value)) < 0.001 and (float(start).is_integer() and float(end).is_integer()):
            return f"{int(round(value))}"
        return f"{value:.2f}".rstrip("0").rstrip(".")

    def _sync_detection_area_controls(self) -> None:
        if not hasattr(self, "detection_detail_frame"):
            return
        for child in self.detection_detail_frame.winfo_children():
            child.destroy()
        if self.detection_area_var.get() == "person":
            self._slider_row(
                self.detection_detail_frame,
                "Person percentage",
                self.person_effect_percent_var,
                5,
                100,
                self.refresh_preview,
            ).pack(anchor="w", fill="x")
        else:
            self._slider_row(
                self.detection_detail_frame,
                "Face expansion",
                self.expand_var,
                1.0,
                2.5,
                self.refresh_preview,
            ).pack(anchor="w", fill="x")
        self.root.update_idletasks()

    def _sync_settings(self) -> None:
        self.state.output_dir = Path(self.output_entry.get().strip())
        self._sync_effect_settings()
        self.state.metadata.title = self.title_entry.get().strip() or "output"
        self.state.metadata.location = self.location_entry.get().strip() or "unknown"
        if DateEntry and isinstance(self.date_entry, DateEntry):
            self.state.metadata.date = self.date_entry.get_date().strftime("%d_%m_%Y")
        else:
            self.state.metadata.date = self.date_entry.get().replace(".", "_")

    def _sync_effect_settings(self) -> None:
        self.state.settings.target = self.target_var.get()
        self.state.settings.detection_effect_area = self.detection_area_var.get()
        self.state.settings.person_effect_ratio = float(self.person_effect_percent_var.get()) / 100.0
        self.state.settings.pixelate_faces = self.pixelate_var.get()
        self.state.settings.blur_faces = self.blur_var.get()
        self.state.settings.overlay_faces = self.overlay_var.get()
        self.state.settings.follow_camera_motion = self.follow_motion_var.get()
        self.state.settings.pixel_size = int(self.face_pixel_var.get())
        self.state.settings.blur_size = int(self.blur_size_var.get())
        self.state.settings.face_expand_ratio = float(self.expand_var.get())
        self.state.settings.extra_hold_frames = int(self.extra_hold_var.get())
        self.state.settings.confidence_threshold = float(self.confidence_var.get())

    def _reset_preview_tracker(self) -> None:
        self.preview_face_tracker = FaceTracker(int(self.extra_hold_var.get()))
        self.preview_tracker_frame_index = -1
        if self.preview_frame_bgr is not None:
            self.refresh_preview()

    def _apply_preview_hold_tracker(self) -> None:
        if self.media_info is None or self.media_info.kind != "video":
            return
        if self.preview_tracker_frame_index != self.preview_frame_index - 1:
            self.preview_face_tracker = FaceTracker(int(self.extra_hold_var.get()))
        self.preview_detections = self.preview_face_tracker.update(self.preview_detections)
        self.preview_tracker_frame_index = self.preview_frame_index

    def _sync_memory_mode(self) -> None:
        target_kind = "person" if self.state.settings.detection_effect_area == "person" else "face"
        if self.face_memory.kind != target_kind:
            self.face_memory = FaceMemory(kind=target_kind)
            self.remembered_preview_detections.clear()
        if self.ignored_detection_memory.kind != target_kind:
            self.ignored_detection_memory = FaceMemory(kind=target_kind)

    def _remembered_label(self) -> str:
        return "person" if self.face_memory.kind == "person" else "face"

    def _draw_detection_boxes(self) -> None:
        x1, y1, x2, y2 = self.canvas_image_box
        image_width = x2 - x1
        image_height = y2 - y1
        if self.preview_frame_bgr is None:
            return
        frame_height, frame_width = self.preview_frame_bgr.shape[:2]
        for fx1, fy1, fx2, fy2 in self.remembered_preview_detections:
            badge_x = x1 + (fx1 / frame_width) * image_width
            badge_y = y1 + (fy1 / frame_height) * image_height
            self.preview_canvas.create_rectangle(
                badge_x,
                badge_y,
                x1 + (fx2 / frame_width) * image_width,
                y1 + (fy2 / frame_height) * image_height,
                outline=BLUE,
                width=4,
            )
            self.preview_canvas.create_oval(badge_x - 8, badge_y - 8, badge_x + 8, badge_y + 8, fill=BLUE, outline="")
            self.preview_canvas.create_text(badge_x, badge_y, text="R", fill="white", font=("Segoe UI", 8, "bold"))

        for index, (fx1, fy1, fx2, fy2) in enumerate(self.preview_detections, start=1):
            badge_x = x1 + (fx1 / frame_width) * image_width
            badge_y = y1 + (fy1 / frame_height) * image_height
            self.preview_canvas.create_rectangle(
                badge_x,
                badge_y,
                x1 + (fx2 / frame_width) * image_width,
                y1 + (fy2 / frame_height) * image_height,
                outline=GREEN,
                width=3,
            )
            self.preview_canvas.create_oval(badge_x - 8, badge_y - 8, badge_x + 8, badge_y + 8, fill=GREEN, outline="")
            self.preview_canvas.create_text(
                badge_x,
                badge_y,
                text=str(index),
                fill="white",
                font=("Segoe UI", 8, "bold"),
            )

        for region in self.state.ignored_detection_regions:
            rect = region.normalized()
            self.preview_canvas.create_rectangle(
                x1 + rect.x * image_width,
                y1 + rect.y * image_height,
                x1 + (rect.x + rect.width) * image_width,
                y1 + (rect.y + rect.height) * image_height,
                outline=DANGER,
                width=3,
                dash=(6, 3),
            )

    def _draw_regions(self) -> None:
        x1, y1, x2, y2 = self.canvas_image_box
        width = x2 - x1
        height = y2 - y1
        for index, region in enumerate(self.preview_protected_regions):
            rect = region.normalized()
            line_width = 3 if self._manual_region_selected(index, "clear") else 2
            self.preview_canvas.create_rectangle(
                x1 + rect.x * width,
                y1 + rect.y * height,
                x1 + (rect.x + rect.width) * width,
                y1 + (rect.y + rect.height) * height,
                outline=ACCENT,
                width=line_width + 1,
            )

        for index, region in enumerate(self.preview_effect_regions):
            rect = region.normalized()
            line_width = 3 if self._manual_region_selected(index, "effect") else 2
            self.preview_canvas.create_rectangle(
                x1 + rect.x * width,
                y1 + rect.y * height,
                x1 + (rect.x + rect.width) * width,
                y1 + (rect.y + rect.height) * height,
                outline=DANGER,
                width=line_width + 1,
                dash=(7, 4),
            )

    def _draw_timeline(self) -> None:
        if not hasattr(self, "timeline_canvas"):
            return
        self.timeline_canvas.delete("all")
        width = max(10, self.timeline_canvas.winfo_width())
        height = max(10, self.timeline_canvas.winfo_height())
        frame_count = self._timeline_frame_count()
        row_height = 28
        top = 8
        content_height = max(height, top * 2 + max(1, len(self.state.manual_regions)) * row_height)
        self.timeline_canvas.configure(scrollregion=(0, 0, width, content_height))
        self.timeline_canvas.create_rectangle(0, 0, width, content_height, fill=INK, outline="")

        for index, region in enumerate(self.state.manual_regions):
            row_top = top + index * row_height
            y = row_top + row_height // 2
            action_x = width - 24
            lock_x = width - 56
            self.timeline_canvas.create_line(
                0,
                row_top,
                width,
                row_top,
                fill="#2f2b24",
                width=1,
            )
            self.timeline_canvas.create_text(
                8,
                y,
                anchor="w",
                text=self._timeline_region_label(index, region),
                fill=TEXT if index == self.selected_region_index else "#c7bda4",
                font=("Segoe UI", 9, "bold" if index == self.selected_region_index else "normal"),
            )

            start_x = self._timeline_x_for_frame(region.start_frame, width)
            end_frame = region.end_frame if region.end_frame is not None else frame_count - 1
            end_x = self._timeline_x_for_frame(end_frame, width)
            color = DANGER if region.mode == "effect" else ACCENT
            self.timeline_canvas.create_line(self._timeline_left_margin(), y, width - 72, y, fill="#4a463c", width=2)
            self.timeline_canvas.create_rectangle(
                start_x,
                y - 6,
                end_x,
                y + 6,
                fill=color,
                outline=TEXT if index == self.selected_region_index else color,
                width=2 if index == self.selected_region_index else 1,
            )
            self.timeline_canvas.create_rectangle(
                start_x - 6,
                y - 10,
                start_x + 6,
                y + 10,
                fill="#f6f0df",
                outline=color,
                width=2,
                tags=(f"handle:{index}:start",),
            )
            self.timeline_canvas.create_rectangle(
                end_x - 6,
                y - 10,
                end_x + 6,
                y + 10,
                fill="#f6f0df",
                outline=color,
                width=2,
                tags=(f"handle:{index}:end",),
            )
            for keyframe in region.keyframes:
                key_x = self._timeline_x_for_frame(keyframe.frame, width)
                self.timeline_canvas.create_rectangle(key_x - 3, y - 7, key_x + 3, y + 7, fill=color, outline=TEXT)

            lock_symbol = "🔒" if region.locked else "🔓"
            lock_fill = DANGER if region.locked else TEXT
            self.timeline_canvas.create_text(
                lock_x,
                y,
                text=lock_symbol,
                fill=lock_fill,
                font=("Segoe UI Symbol", 13, "bold"),
                tags=(f"action:{index}:lock",),
            )
            self.timeline_canvas.create_text(
                action_x,
                y,
                text="✖",
                fill=DANGER,
                font=("Segoe UI Symbol", 13, "bold"),
                tags=(f"action:{index}:delete",),
            )

        current_x = self._timeline_x_for_frame(self.preview_frame_index, width)
        self.timeline_canvas.create_line(current_x, 0, current_x, content_height, fill=GREEN, width=2)

    def start_timeline_drag(self, event: tk.Event) -> None:
        canvas_y = self.timeline_canvas.canvasy(event.y)
        action_hit = self._timeline_action_at(event.x, canvas_y)
        if action_hit is not None:
            row_index, action = action_hit
            self.selected_region_index = row_index
            if action == "lock":
                self.toggle_selected_region_lock()
            elif action == "delete":
                self.delete_selected_region()
            self.refresh_preview()
            return
        hit = self._timeline_handle_at(event.x, canvas_y)
        if hit is not None and self.media_info and self.media_info.kind == "video":
            self.timeline_drag_region_index, self.timeline_drag_edge = hit
            self.selected_region_index = self.timeline_drag_region_index
            if self.state.manual_regions[self.timeline_drag_region_index].locked:
                self.status_label.config(text="Selected box is locked")
                self.refresh_preview()
                return
            self.timeline_drag_start_frame = self._timeline_frame_for_x(
                event.x, max(10, self.timeline_canvas.winfo_width())
            )
            self.timeline_drag_original_frames = self._timeline_original_frames(self.timeline_drag_region_index)
            self.refresh_preview()
            return

        row_index = self._timeline_row_at(canvas_y)
        if row_index is not None:
            self.selected_region_index = row_index
            span_hit = self._timeline_span_at(event.x, row_index)
            if span_hit and self.media_info and self.media_info.kind == "video":
                if self.state.manual_regions[row_index].locked:
                    self.status_label.config(text="Selected box is locked")
                    self.refresh_preview()
                    return
                self.timeline_drag_region_index = row_index
                self.timeline_drag_edge = "span"
                self.timeline_drag_start_frame = self._timeline_frame_for_x(
                    event.x, max(10, self.timeline_canvas.winfo_width())
                )
                self.timeline_drag_original_frames = self._timeline_original_frames(row_index)
                self.refresh_preview()
                return
        if self.media_info and self.media_info.kind == "video":
            self._seek_timeline_x(event.x)

    def drag_timeline_handle(self, event: tk.Event) -> None:
        if self.timeline_drag_region_index is None or self.timeline_drag_edge is None:
            return
        region = self._selected_manual_region()
        if region is None:
            return
        frame = self._timeline_frame_for_x(event.x, max(10, self.timeline_canvas.winfo_width()))
        if self.timeline_drag_edge == "span":
            self._move_timeline_span(region, frame)
        elif self.timeline_drag_edge == "start":
            end_frame = region.end_frame if region.end_frame is not None else self._timeline_frame_count() - 1
            region.start_frame = min(max(0, frame), end_frame)
            if not region.keyframes:
                region.set_keyframe(region.start_frame, region.rect)
            else:
                first = min(region.keyframes, key=lambda keyframe: keyframe.frame)
                first.frame = region.start_frame
                region.keyframes.sort(key=lambda keyframe: keyframe.frame)
        else:
            region.end_frame = max(region.start_frame, frame)
        self._draw_timeline()

    def finish_timeline_drag(self, _event: tk.Event) -> None:
        if self.timeline_drag_region_index is None:
            return
        self.timeline_drag_region_index = None
        self.timeline_drag_edge = None
        self.timeline_drag_start_frame = None
        self.timeline_drag_original_frames = None
        self.refresh_preview()

    def scroll_timeline(self, event: tk.Event) -> None:
        if getattr(event, "num", None) == 4:
            self.timeline_canvas.yview_scroll(-3, "units")
        elif getattr(event, "num", None) == 5:
            self.timeline_canvas.yview_scroll(3, "units")
        else:
            delta = -1 if getattr(event, "delta", 0) > 0 else 1
            self.timeline_canvas.yview_scroll(delta * 3, "units")

    def _seek_timeline_x(self, x: int) -> None:
        frame_index = self._timeline_frame_for_x(x, max(10, self.timeline_canvas.winfo_width()))
        self.stop_preview_playback()
        self.video_seek_var.set(frame_index)
        self.load_video_preview_frame()

    def _timeline_left_margin(self) -> int:
        return 76

    def _timeline_frame_count(self) -> int:
        return max(1, self.media_info.frame_count or 1) if self.media_info and self.media_info.kind == "video" else 1

    def _timeline_x_for_frame(self, frame: int, width: int) -> int:
        frame_count = self._timeline_frame_count()
        left = self._timeline_left_margin()
        right = max(left + 1, width - 14)
        if frame_count <= 1:
            return left
        ratio = min(max(frame, 0), frame_count - 1) / (frame_count - 1)
        return int(left + ratio * (right - left))

    def _timeline_frame_for_x(self, x: int, width: int) -> int:
        frame_count = self._timeline_frame_count()
        left = self._timeline_left_margin()
        right = max(left + 1, width - 14)
        ratio = (min(max(x, left), right) - left) / max(1, right - left)
        return int(round(ratio * (frame_count - 1)))

    def _timeline_row_at(self, canvas_y: float) -> int | None:
        row = int((canvas_y - 8) // 28)
        if 0 <= row < len(self.state.manual_regions):
            return row
        return None

    def _timeline_handle_at(self, x: int, canvas_y: float) -> tuple[int, str] | None:
        width = max(10, self.timeline_canvas.winfo_width())
        row = self._timeline_row_at(canvas_y)
        if row is None:
            return None
        region = self.state.manual_regions[row]
        start_x = self._timeline_x_for_frame(region.start_frame, width)
        end_frame = region.end_frame if region.end_frame is not None else self._timeline_frame_count() - 1
        end_x = self._timeline_x_for_frame(end_frame, width)
        if abs(x - start_x) <= 8:
            return row, "start"
        if abs(x - end_x) <= 8:
            return row, "end"
        return None

    def _timeline_action_at(self, x: int, canvas_y: float) -> tuple[int, str] | None:
        row = self._timeline_row_at(canvas_y)
        if row is None:
            return None
        width = max(10, self.timeline_canvas.winfo_width())
        lock_x = width - 56
        delete_x = width - 24
        if abs(x - lock_x) <= 14:
            return row, "lock"
        if abs(x - delete_x) <= 14:
            return row, "delete"
        return None

    def _timeline_span_at(self, x: int, row: int) -> bool:
        width = max(10, self.timeline_canvas.winfo_width())
        region = self.state.manual_regions[row]
        start_x = self._timeline_x_for_frame(region.start_frame, width)
        end_frame = region.end_frame if region.end_frame is not None else self._timeline_frame_count() - 1
        end_x = self._timeline_x_for_frame(end_frame, width)
        return start_x + 8 <= x <= end_x - 8

    def _timeline_original_frames(self, region_index: int) -> tuple[int, int, list[int]]:
        region = self.state.manual_regions[region_index]
        end_frame = region.end_frame if region.end_frame is not None else self._timeline_frame_count() - 1
        return region.start_frame, end_frame, [keyframe.frame for keyframe in region.keyframes]

    def _move_timeline_span(self, region: ManualRegion, frame: int) -> None:
        if self.timeline_drag_start_frame is None or self.timeline_drag_original_frames is None:
            return
        start_frame, end_frame, keyframe_frames = self.timeline_drag_original_frames
        span = end_frame - start_frame
        delta = frame - self.timeline_drag_start_frame
        min_delta = -start_frame
        max_delta = (self._timeline_frame_count() - 1) - end_frame
        delta = min(max(delta, min_delta), max_delta)
        region.start_frame = start_frame + delta
        region.end_frame = region.start_frame + span
        for keyframe, original_frame in zip(region.keyframes, keyframe_frames):
            keyframe.frame = original_frame + delta
        region.keyframes.sort(key=lambda keyframe: keyframe.frame)

    def _timeline_region_label(self, index: int, region: ManualRegion) -> str:
        flags = ""
        if region.locked:
            flags += " L"
        if region.follow_motion:
            flags += " T"
        return f"Box {index + 1}{flags}"

    def _inside_image(self, x: int, y: int) -> bool:
        x1, y1, x2, y2 = self.canvas_image_box
        return x1 <= x <= x2 and y1 <= y <= y2

    def _clamp_to_image(self, x: int, y: int) -> tuple[int, int]:
        x1, y1, x2, y2 = self.canvas_image_box
        return min(max(x, x1), x2), min(max(y, y1), y2)

    def _canvas_rect_to_normalized(self, x1: int, y1: int, x2: int, y2: int) -> Rect:
        ix1, iy1, ix2, iy2 = self.canvas_image_box
        width = ix2 - ix1
        height = iy2 - iy1
        left = (min(x1, x2) - ix1) / width
        top = (min(y1, y2) - iy1) / height
        right = (max(x1, x2) - ix1) / width
        bottom = (max(y1, y2) - iy1) / height
        return Rect(left, top, right - left, bottom - top).normalized()

    def _canvas_delta_to_normalized(self, dx: int, dy: int) -> tuple[float, float]:
        ix1, iy1, ix2, iy2 = self.canvas_image_box
        return dx / max(1, ix2 - ix1), dy / max(1, iy2 - iy1)

    def _move_selected_region(self, x: int, y: int) -> None:
        if self.drag_start is None or self.region_drag_index is None or self.drag_start_region is None:
            return
        clamped_x, clamped_y = self._clamp_to_image(x, y)
        dx, dy = self._canvas_delta_to_normalized(clamped_x - self.drag_start[0], clamped_y - self.drag_start[1])
        moved_region = Rect(
            self.drag_start_region.x + dx,
            self.drag_start_region.y + dy,
            self.drag_start_region.width,
            self.drag_start_region.height,
        ).normalized()
        region = self.state.manual_regions[self.region_drag_index]
        state_region = self._preview_rect_to_state_rect(moved_region) if region.follow_motion else moved_region
        if self.media_info and self.media_info.kind == "video":
            region.set_keyframe(self.preview_frame_index, state_region)
            region.end_frame = max(region.end_frame or self.preview_frame_index, self.preview_frame_index)
        else:
            region.rect = state_region
            region.set_keyframe(0, state_region)
        self.refresh_preview()

    def _manual_region_at_canvas_point(self, x: int, y: int) -> int | None:
        if self.preview_frame_bgr is None or not self._inside_image(x, y):
            return None
        ix1, iy1, ix2, iy2 = self.canvas_image_box
        image_width = ix2 - ix1
        image_height = iy2 - iy1
        px = (x - ix1) / image_width
        py = (y - iy1) / image_height
        frame_index = self._current_region_frame_index()
        frame_height, frame_width = self.preview_frame_bgr.shape[:2]
        motion_dx, motion_dy = self._current_motion_delta()
        for index, manual_region in reversed(self.preview_manual_region_refs):
            rect = self._manual_region_preview_rect(
                manual_region,
                frame_index,
                frame_width,
                frame_height,
                motion_dx,
                motion_dy,
            ).normalized()
            if rect.x <= px <= rect.x + rect.width and rect.y <= py <= rect.y + rect.height:
                return index
        return None

    def _current_preview_protected_regions(self) -> list[Rect]:
        frame_index = self._current_region_frame_index()
        frame_height, frame_width = self.preview_frame_bgr.shape[:2] if self.preview_frame_bgr is not None else (1, 1)
        motion_dx, motion_dy = self._current_motion_delta()
        active_clear_regions = [
            self._manual_region_preview_rect(region, frame_index, frame_width, frame_height, motion_dx, motion_dy)
            for _index, region in self._active_manual_region_refs()
            if region.mode == "clear"
        ]
        if (
            not self.follow_motion_var.get()
            or self.preview_frame_bgr is None
            or self.base_preview_frame_bgr is None
            or self.media_info is None
            or self.media_info.kind != "video"
            or not self.state.protected_regions
        ):
            return list(self.state.protected_regions) + active_clear_regions

        dx, dy = estimate_translation(self.base_preview_frame_bgr, self.preview_frame_bgr)
        return shift_regions(self.state.protected_regions, dx, dy, frame_width, frame_height) + active_clear_regions

    def _current_preview_effect_regions(self) -> list[Rect]:
        frame_index = self._current_region_frame_index()
        frame_height, frame_width = self.preview_frame_bgr.shape[:2] if self.preview_frame_bgr is not None else (1, 1)
        motion_dx, motion_dy = self._current_motion_delta()
        return [
            self._manual_region_preview_rect(region, frame_index, frame_width, frame_height, motion_dx, motion_dy)
            for _index, region in self._active_manual_region_refs()
            if region.mode == "effect"
        ]

    def _manual_region_preview_rect(
        self,
        region: ManualRegion,
        frame_index: int | None,
        frame_width: int,
        frame_height: int,
        motion_dx: float,
        motion_dy: float,
    ) -> Rect:
        rect = region.rect_at(frame_index)
        if not region.follow_motion:
            return rect
        return shift_regions([rect], motion_dx, motion_dy, frame_width, frame_height)[0]

    def _active_manual_region_refs(self) -> list[tuple[int, ManualRegion]]:
        frame_index = self.preview_frame_index if self.media_info and self.media_info.kind == "video" else None
        return [
            (index, region)
            for index, region in enumerate(self.state.manual_regions)
            if region.active_at(frame_index)
        ]

    def _current_region_frame_index(self) -> int | None:
        return self.preview_frame_index if self.media_info and self.media_info.kind == "video" else None

    def _selected_manual_region(self) -> ManualRegion | None:
        if self.selected_region_index is None:
            return None
        if self.selected_region_index < 0 or self.selected_region_index >= len(self.state.manual_regions):
            return None
        return self.state.manual_regions[self.selected_region_index]

    def _manual_region_start_frame(self) -> int:
        if self.media_info and self.media_info.kind == "video":
            return self.preview_frame_index
        return 0

    def _manual_region_end_frame(self) -> int | None:
        if not self.media_info or self.media_info.kind != "video":
            return None
        frame_count = max(1, self.media_info.frame_count or 1)
        duration = max(1, int(round(self.manual_duration_var.get())))
        return min(frame_count - 1, self.preview_frame_index + duration - 1)

    def _manual_region_selected(self, mode_index: int, mode: str) -> bool:
        matching_indexes = [
            index for index, region in self.preview_manual_region_refs if region.mode == mode
        ]
        return mode_index < len(matching_indexes) and matching_indexes[mode_index] == self.selected_region_index

    def _current_motion_delta(self) -> tuple[float, float]:
        if (
            self.preview_frame_bgr is None
            or self.base_preview_frame_bgr is None
            or self.media_info is None
            or self.media_info.kind != "video"
        ):
            return 0.0, 0.0
        return estimate_translation(self.base_preview_frame_bgr, self.preview_frame_bgr)

    def _preview_rect_to_state_rect(self, region: Rect) -> Rect:
        if self.preview_frame_bgr is None:
            return region.normalized()
        frame_height, frame_width = self.preview_frame_bgr.shape[:2]
        dx, dy = self._current_motion_delta()
        return Rect(
            region.x - dx / frame_width,
            region.y - dy / frame_height,
            region.width,
            region.height,
        ).normalized()

    def _pixel_rect_to_normalized(self, box: tuple[int, int, int, int]) -> Rect:
        if self.preview_frame_bgr is None:
            return Rect(0, 0, 0, 0)
        frame_height, frame_width = self.preview_frame_bgr.shape[:2]
        x1, y1, x2, y2 = box
        return Rect(
            x1 / frame_width,
            y1 / frame_height,
            (x2 - x1) / frame_width,
            (y2 - y1) / frame_height,
        ).normalized()

    def _detection_at_canvas_point(self, x: int, y: int) -> tuple[int, int, int, int] | None:
        if self.preview_frame_bgr is None or not self._inside_image(x, y):
            return None
        ix1, iy1, ix2, iy2 = self.canvas_image_box
        image_width = ix2 - ix1
        image_height = iy2 - iy1
        frame_height, frame_width = self.preview_frame_bgr.shape[:2]
        px = int(((x - ix1) / image_width) * frame_width)
        py = int(((y - iy1) / image_height) * frame_height)
        point = (px, py, px + 1, py + 1)
        for detection in reversed(self.preview_detections + self.remembered_preview_detections):
            if intersects(detection, point):
                return detection
        return None

    def _format_specs(self, info) -> str:
        mb = info.size_bytes / (1024 * 1024)
        if info.kind == "video":
            duration = info.duration_seconds or 0
            return f"{info.width}x{info.height}, {mb:.2f} MB, {info.fps:.2f} FPS, {duration:.1f}s"
        return f"{info.width}x{info.height}, {mb:.2f} MB"

    def _threadsafe_progress(self, value: float, message: str) -> None:
        if self._closing:
            return
        try:
            self.root.after(0, lambda: self.progress.configure(value=value))
            self.root.after(0, lambda: self.status_label.config(text=message))
        except tk.TclError:
            pass

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.stop_preview_playback()
        for after_id in (self.detect_after_id, self.seek_after_id, self.playback_after_id):
            if after_id is None:
                continue
            try:
                self.root.after_cancel(after_id)
            except Exception:
                pass
        self.detect_after_id = None
        self.seek_after_id = None
        self.playback_after_id = None
        self.root.destroy()

    def _update_region_count(self) -> None:
        self.region_count_label.config(
            text=(
                f"{len(self.preview_detections)} faces, "
                f"{len(self.face_memory)} remembered, "
                f"{len(self.state.manual_regions)} manual boxes, "
                f"{len(self.ignored_detection_memory) + len(self.state.ignored_detection_regions)} ignored"
            )
        )

    def _apply_ignored_detection_filter(self) -> None:
        if self.preview_frame_bgr is None:
            self.preview_detections = []
            self.remembered_preview_detections = []
            return
        self._sync_memory_mode()
        frame_height, frame_width = self.preview_frame_bgr.shape[:2]
        filtered = filter_detections_by_regions(
            self._raw_preview_detections,
            self.state.ignored_detection_regions,
            frame_width,
            frame_height,
        )
        filtered, _ignored = self.ignored_detection_memory.split_detections(self.preview_frame_bgr, filtered)
        self.preview_detections, self.remembered_preview_detections = self.face_memory.split_detections(
            self.preview_frame_bgr, filtered
        )

    def _processing_done(self, output: Path, elapsed: str) -> None:
        self.status_label.config(text=f"Done in {elapsed}")
        self.progress["value"] = 100
        messagebox.showinfo("Processing complete", f"Output saved to:\n{output}")

    def show_help(self) -> None:
        messagebox.showinfo(
            "Planner Help",
            "1. Choose an image or video.\n"
            "2. Choose whether to affect faces or keep faces clear and affect the background.\n"
            "3. Drag boxes on the preview over manual clear/effect areas.\n"
            "4. Drag a selected box later in the video to set a motion stop.\n"
            "5. Drag timeline handles to shorten/prolong a box; drag the timeline bar to move it.\n"
                "6. Lock boxes to prevent accidental edits; enable tracking to follow camera motion.\n"
                "7. Use the Detected Faces lists to ignore or forget a specific detection.\n"
                "8. Right-click a green detection to ignore matching detections while they are detected.\n"
                "9. Double-click a green detection to remember a face/person that should stay clear.\n"
                "10. Process the file.\n\n"
                "Green boxes are unknown detections. Blue boxes are remembered detections. "
                "Orange boxes are manual protected areas. Red dashed boxes are legacy ignored regions.",
        )
    #endregion Helpers
