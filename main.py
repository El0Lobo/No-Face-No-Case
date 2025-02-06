import cv2
import threading
from ultralytics import YOLO
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, PhotoImage
from PIL import Image, ImageTk
from tkcalendar import DateEntry
import concurrent.futures
from datetime import datetime
import time
import os
import sys
from ttkthemes import ThemedTk
import webbrowser


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


model = YOLO(resource_path('yolov8n-face.pt'))


class VideoProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("No Face No Case")
        self.root.geometry("500x750")

        # Load the icon using the resource path
        icon = PhotoImage(file=resource_path("Ⓐ.png"))
        self.root.iconphoto(True, icon)
        self.root.set_theme("equilux")

        # Adjustable defaults
        self.blur_size = 51
        self.face_expand_ratio = 1.2
        self.confidence_threshold = 0.5
        self.original_fps = 0

        self.setup_gui()

    def setup_gui(self):
        frame = ttk.Frame(self.root, padding=10)
        frame.pack(expand=True, fill='both')

        ttk.Label(frame, text="Select a media file (video or image):").pack(anchor="w")
        self.file_path_entry = ttk.Entry(frame, width=50)
        self.file_path_entry.pack(anchor="w")

        ttk.Button(frame, text="Browse", command=self.select_file).pack(anchor="w", pady=5)
        self.specs_label = ttk.Label(frame, text="File specs will be displayed here.")
        self.specs_label.pack(anchor="w")

        ttk.Label(frame, text="Filename:").pack(anchor="w")
        self.clip_name_entry = ttk.Entry(frame)
        self.clip_name_entry.pack(anchor="w")

        ttk.Label(frame, text="Date:").pack(anchor="w")
        self.date_picker = DateEntry(frame, locale='de_DE', date_pattern='dd.MM.yyyy')
        self.date_picker.pack(anchor="w")

        ttk.Label(frame, text="Location:").pack(anchor="w")
        self.location_entry = ttk.Entry(frame)
        self.location_entry.pack(anchor="w", pady=5)

        # FPS Options
        ttk.Label(frame, text="Output FPS:").pack(anchor="w")
        self.fps_var = tk.IntVar(value=0)
        self.fps_60_checkbox = ttk.Checkbutton(frame, text="60 FPS", variable=self.fps_var, onvalue=60, command=self.update_fps_selection)
        self.fps_60_checkbox.pack(anchor="w")
        self.fps_30_checkbox = ttk.Checkbutton(frame, text="30 FPS", variable=self.fps_var, onvalue=30, command=self.update_fps_selection)
        self.fps_30_checkbox.pack(anchor="w", pady=5)

        # Face Size Expansion Slider
        ttk.Label(frame, text="Face Size Expansion:").pack(anchor="w")
        self.size_value_label = ttk.Label(frame, text=f"{self.face_expand_ratio:.2f}")
        self.size_value_label.pack(anchor="w")
        self.size_slider = ttk.Scale(frame, from_=0.1, to=2.0, orient='horizontal', length=300, command=self.update_size_label)
        self.size_slider.set(self.face_expand_ratio)
        self.size_slider.pack(anchor="w", pady=5)

        # Confidence Threshold Slider
        ttk.Label(frame, text="Confidence Threshold:").pack(anchor="w")
        self.confidence_value_label = ttk.Label(frame, text=f"{self.confidence_threshold:.2f}")
        self.confidence_value_label.pack(anchor="w")
        self.confidence_slider = ttk.Scale(frame, from_=0.1, to=1.0, orient='horizontal', length=300, command=self.update_confidence_label)
        self.confidence_slider.set(self.confidence_threshold)
        self.confidence_slider.pack(anchor="w", pady=5)

        # Blur Strength Slider
        ttk.Label(frame, text="Blur Strength:").pack(anchor="w")
        self.blur_value_label = ttk.Label(frame, text=str(self.blur_size))
        self.blur_value_label.pack(anchor="w")
        self.blur_slider = ttk.Scale(frame, from_=3, to=101, orient='horizontal', length=300, command=self.update_blur_label)
        self.blur_slider.set(self.blur_size)
        self.blur_slider.pack(anchor="w", pady=5)

        # Pixelation Toggle
        self.pixelate_var = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Enable Pixelation", variable=self.pixelate_var).pack(anchor="w", pady=5)

        ttk.Button(frame, text="Process", command=self.process).pack(anchor="w", pady=10)

        self.progress_bar = ttk.Progressbar(frame, orient='horizontal', length=500, mode='determinate')
        self.progress_bar.pack(anchor="w", pady=5)
        self.time_label = ttk.Label(frame, text="")
        self.time_label.pack(anchor="w", pady=5)

        footer_frame = ttk.Frame(frame)
        footer_frame.pack(side="bottom", pady=10)
        developed_by_label = ttk.Label(footer_frame, text="Developed by")
        developed_by_label.pack(side="left")

        try:
            acme_image = Image.open(resource_path("ⒶCME.png")).resize((50, 20), Image.Resampling.LANCZOS)
            self.acme_logo = ImageTk.PhotoImage(acme_image)
            acme_image_label = ttk.Label(footer_frame, image=self.acme_logo, cursor="hand2")
            acme_image_label.pack(side="left", padx=5)
            acme_image_label.bind("<Button-1>", lambda e: webbrowser.open("https://acme-prototypes.com/"))
        except Exception as e:
            print(f"Error loading footer image: {e}")


    def update_size_label(self, event):
        self.size_value_label.config(text=f"{self.size_slider.get():.2f}")

    def update_confidence_label(self, event):
        self.confidence_value_label.config(text=f"{self.confidence_slider.get():.2f}")

    def update_blur_label(self, event):
        self.blur_size = int(self.blur_slider.get())
        self.blur_value_label.config(text=str(self.blur_size))

    def update_fps_selection(self):
        if self.original_fps < 30:
            self.fps_30_checkbox.state(["disabled"])
            self.fps_60_checkbox.state(["disabled"])
        elif self.original_fps < 60:
            self.fps_60_checkbox.state(["disabled"])
        else:
            self.fps_30_checkbox.state(["!disabled"])
            self.fps_60_checkbox.state(["!disabled"])

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media files", "*.mp4;*.avi;*.jpg;*.png")])
        if file_path:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, file_path)
            self.display_specs(file_path)
            self.autofill_metadata(file_path)

    def display_specs(self, file_path):
        if file_path.endswith(('.mp4', '.avi')):
            cap = cv2.VideoCapture(file_path)
            self.original_fps = cap.get(cv2.CAP_PROP_FPS)
            resolution = f"{cap.get(cv2.CAP_PROP_FRAME_WIDTH):.2f}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT):.2f}"
            size_kb = os.path.getsize(file_path) / 1024
            specs = f"Resolution: {resolution}, FPS: {self.original_fps:.2f}, Size: {size_kb:.2f} KB"
            cap.release()
            self.update_fps_selection()
        elif file_path.endswith(('.jpg', '.png')):
            image = cv2.imread(file_path)
            resolution = f"{image.shape[1]:.2f}x{image.shape[0]:.2f}"
            size_kb = os.path.getsize(file_path) / 1024
            specs = f"Resolution: {resolution}, Size: {size_kb:.2f} KB"
        self.specs_label.config(text=specs)

    def autofill_metadata(self, file_path):
        file_name = os.path.basename(file_path).split('.')[0]
        self.clip_name_entry.delete(0, tk.END)
        self.clip_name_entry.insert(0, file_name)

        # Autofill date using the file's modification timestamp
        try:
            stats = os.stat(file_path)
            creation_date = datetime.fromtimestamp(stats.st_mtime).strftime("%d.%m.%Y")
            self.date_picker.set_date(datetime.fromtimestamp(stats.st_mtime))
        except Exception as e:
            print(f"Failed to extract date: {e}")

        # Manually enter a default location (since actual location metadata is unavailable)
        self.location_entry.delete(0, tk.END)
        self.location_entry.insert(0, "Unknown Location")  # Replace with user-defined location if available


    def process(self):
        file_path = self.file_path_entry.get()
        if not file_path:
            messagebox.showerror("Error", "Please select a file first.")
            return

        output_path = filedialog.asksaveasfilename(defaultextension=".mp4")
        if not output_path:
            return

        self.face_expand_ratio = self.size_slider.get()
        self.confidence_threshold = self.confidence_slider.get()

        self.process_in_background(file_path, output_path)

    def process_in_background(self, video_path, output_path):
        def run_processing():
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            output_fps = self.fps_var.get() or self.original_fps
            frame_skip = int(self.original_fps / output_fps) if output_fps < self.original_fps else 1

            frame_count, output_count = 0, 0
            cap.release()

            def progress_callback():
                nonlocal output_count
                output_count += 1
                progress = (output_count / (total_frames / frame_skip)) * 100
                self.update_progress_bar(progress)

            self.blur_faces(video_path, output_path, frame_skip, progress_callback)

        threading.Thread(target=run_processing).start()

    def blur_faces(self, video_path, output_path, frame_skip, progress_callback):
        cap = cv2.VideoCapture(video_path)
        out = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*'mp4v'), self.fps_var.get() or cap.get(cv2.CAP_PROP_FPS), (int(cap.get(3)), int(cap.get(4))))

        frame_number = 0
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break

            if frame_number % frame_skip == 0:
                processed_frame = self.process_frame(frame)
                out.write(processed_frame)
                progress_callback()

            frame_number += 1

        cap.release()
        out.release()

    def process_frame(self, frame):
        faces = self.detect_faces_yolo(frame)
        for (x, y, w, h) in faces:
            x_start, y_start, x_end, y_end = max(0, x), max(0, y), min(frame.shape[1], x + w), min(frame.shape[0], y + h)
            face_area = frame[y_start:y_end, x_start:x_end]

            if self.pixelate_var.get():
                small = cv2.resize(face_area, (10, 10), interpolation=cv2.INTER_LINEAR)
                face_area = cv2.resize(small, (face_area.shape[1], face_area.shape[0]), interpolation=cv2.INTER_NEAREST)
            else:
                blur_strength = max(3, self.blur_size // 2 * 2 + 1)
                face_area = cv2.GaussianBlur(face_area, (blur_strength, blur_strength), 30)

            frame[y_start:y_end, x_start:x_end] = face_area

        return frame

    def detect_faces_yolo(self, frame):
        results = model(frame, conf=self.confidence_threshold)
        return [(int(x1), int(y1), int(x2 - x1), int(y2 - y1)) for x1, y1, x2, y2 in results[0].boxes.xyxy.tolist()]

    def update_progress_bar(self, progress):
        self.progress_bar['value'] = progress
        self.root.update_idletasks()


if __name__ == "__main__":
    root = ThemedTk(theme="arc")
    app = VideoProcessorApp(root)
    root.mainloop()
