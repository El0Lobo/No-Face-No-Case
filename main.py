import cv2
import threading
from ultralytics import YOLO
import tkinter as tk
from tkinter import filedialog, ttk, messagebox, PhotoImage
import time
from tkcalendar import DateEntry
from datetime import datetime
import os
import sys
from ttkthemes import ThemedTk
import webbrowser
from PIL import PngImagePlugin
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageOps
import subprocess
import ffmpeg as ffmpeg_python_lib



def resource_path(relative_path):
    """Get absolute path to resource, works for dev and PyInstaller."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    resolved_path = os.path.join(base_path, relative_path)

    # Debug output
    print(f"Checking path: {resolved_path}")

    if not os.path.exists(resolved_path):
        print(f"Path not found: {resolved_path}")

        # Special check for ffmpeg binary
        if relative_path == 'ffmpeg.exe':
            alt_path = os.path.join(base_path, 'ffmpeg.exe')
            if os.path.exists(alt_path):
                print(f"FFmpeg found at alternate path: {alt_path}")
                return alt_path

    return resolved_path

def get_ffmpeg_path():
    """Get the path to FFmpeg binary."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    possible_paths = [
        os.path.join(base_path, 'ffmpeg.exe'),
        os.path.join(base_path, 'ffmpeg', 'ffmpeg.exe'),
        os.path.join(base_path, 'ffmpeg', 'bin', 'ffmpeg.exe'),
        'ffmpeg'  # Fallback to system path
    ]

    for path in possible_paths:
        print(f"Checking for FFmpeg at: {path}")
        if os.path.exists(path):
            print(f"FFmpeg found at: {path}")
            return path

    print("FFmpeg not found, falling back to system path.")
    return 'ffmpeg'

model = YOLO(resource_path('yolov11n-face.pt'))

def render_text_on_canvas(frame, text, font_path, font_size, text_color):
    """Render text using a custom font with a transparent background on a Canvas."""
    if not os.path.exists(font_path):
        print("Font file not found:", font_path)
        return None

    try:
        # Set up image size
        width, height = 600, 60  # You can adjust these dimensions if needed
        image = Image.new("RGBA", (width, height), (70, 70, 70))  # Transparent background
        draw = ImageDraw.Draw(image)

        # Load the custom font with PIL
        custom_font = ImageFont.truetype(font_path, font_size)

        # Calculate text position to center it
        text_bbox = draw.textbbox((0, 0), text, font=custom_font)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2

        # Draw the text
        draw.text((text_x, text_y), text, font=custom_font, fill=text_color)

        # Convert to PhotoImage for tkinter
        text_image = ImageTk.PhotoImage(image)

        # Create and pack a Canvas to display the rendered image
        canvas = tk.Canvas(frame, width=width, height=height, bg="#464646", highlightthickness=0)
        canvas.create_image(0, 0, anchor="nw", image=text_image)
        canvas.image = text_image  # Keep a reference to prevent garbage collection
        canvas.pack(expand=True, fill="both")

        return canvas
    except Exception as e:
        print("Failed to render text with custom font:", e)
        return None

def render_text_link(frame, text, font_path, font_size, text_color, link_url):
    """Render text using a custom font with a clickable link."""
    if not os.path.exists(font_path):
        print("Font file not found:", font_path)
        return None

    try:
        # Set up image size and render text
        width, height = 600, 50
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # Transparent text image
        draw = ImageDraw.Draw(image)

        # Load the custom font
        custom_font = ImageFont.truetype(font_path, font_size)

        # Calculate text position to center it
        text_bbox = draw.textbbox((0, 0), text, font=custom_font)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2

        # Draw the text
        draw.text((text_x, text_y), text, font=custom_font, fill=text_color)

        # Convert to PhotoImage
        text_image = ImageTk.PhotoImage(image)

        # Create a label to display the text and make it clickable
        label = tk.Label(frame, image=text_image, bg="#464646", cursor="hand2")
        label.image = text_image  # Keep a reference to avoid garbage collection

        # Add click event to open the link
        def open_link(event):
            webbrowser.open(link_url)

        label.bind("<Button-1>", open_link)
        label.pack(expand=True, fill="both")

        return label
    except Exception as e:
        print("Failed to render text link with custom font:", e)
        return None

class SplashScreen:
    def __init__(self, root):
        self.root = root
        self.running = True  # Flag to control message updates
        self.root.overrideredirect(True)
        self.root.geometry("600x600+600+200")

        # Load and set icon
        icon_path = resource_path("Ⓐ.png")
        if os.path.exists(icon_path):
            try:
                self.icon_ref = PhotoImage(file=icon_path)
                self.root.iconphoto(True, self.icon_ref)
            except Exception as e:
                print("Failed to set icon:", e)

        # Canvas setup
        self.canvas = tk.Canvas(self.root, width=600, height=600, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # Load and resize the splash image dynamically to fit the canvas
        splash_image_path = resource_path('splash.png')
        original_image = Image.open(splash_image_path)
        self.splash_image = ImageTk.PhotoImage(original_image.resize((600, 600), Image.Resampling.LANCZOS))

        # Draw the splash image centered on the canvas
        self.canvas.create_image(300, 300, anchor="center", image=self.splash_image)

        # Load custom font for the message text
        self.custom_font = ImageFont.truetype(resource_path('PixelifySans-Regular.ttf'), 20)

        # Messages to display
        self.messages = [
            "Adjusting focus for a jaded perspective...",
            "My glasses! I can't see without my glasses!",
            "Scanning for something important... probably lost again...",
            "Optimizing vision for cyclopean clarity...",
            "Fine-tuning ghost-trap containment protocols...",
            "Loading infinite witty comebacks...",
            "Thinking about Rodents...",
            "Optimizing pixels for cuteness...",
            "Still looking for those missing glasses...",
            "Finalizing installation of 'No Face No Case'..."
        ]

        self.message_index = 0
        self.update_message()

    def update_message(self):
        if not self.running or self.message_index >= len(self.messages):
            return

        # Clear the canvas and redraw the splash image
        self.canvas.delete("all")
        self.canvas.create_image(300, 300, anchor="center", image=self.splash_image)

        # Get the current message and calculate text position
        text = self.messages[self.message_index]
        text_position = (300, 580)  # Position near the bottom of the splash screen

        # Create a transparent overlay for the text
        overlay = Image.new("RGBA", (600, 600), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Draw the text with a shadow effect for better visibility
        shadow_offsets = [(1, 1), (-1, -1), (1, -1), (-1, 1)]
        for offset in shadow_offsets:
            draw.text((text_position[0] + offset[0], text_position[1] + offset[1]),
                      text, font=self.custom_font, fill="black", anchor="mm")

        # Draw the main white text
        draw.text(text_position, text, font=self.custom_font, fill="white", anchor="mm")

        # Convert the overlay to a Tk-compatible image and display it
        overlay_tk = ImageTk.PhotoImage(overlay)
        self.canvas.create_image(0, 0, anchor="nw", image=overlay_tk)
        self.overlay_image = overlay_tk  # Keep a reference to prevent garbage collection

        self.message_index += 1
        self.root.after(300, self.update_message)

    def show(self):
        """Show the splash screen for 4 seconds and then destroy it."""
        self.root.after(4000, self.close)

    def close(self):
        """Stop the update loop and close the splash window."""
        self.running = False
        self.root.destroy()

class VideoProcessorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("No Face No Case")
        self.root.geometry("850x950")
        
        # Center the window on the screen
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        window_width = 850
        window_height = 950
        x_pos = (screen_width // 2) - (window_width // 2)
        y_pos = (screen_height // 2) - (window_height // 2) - 50  
        self.root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")

        self.cap = None
        self.slider_active = False  # Initialize slider activity flag
        self.face_positions = []  # Stores active face positions and remaining frame counts

        # Load and set icon
        icon_path = resource_path("Ⓐ.png")
        if os.path.exists(icon_path):
            try:
                self.icon_ref = PhotoImage(file=icon_path)  
                self.root.iconphoto(True, self.icon_ref)
            except Exception as e:
                print("Failed to set icon:", e)
        self.root.set_theme("equilux")

        # Adjustable defaults
        self.blur_size = 51
        self.pixel_size = 10
        self.face_expand_ratio = 1.2
        self.confidence_threshold = 0.5
        self.original_fps = 0
        self.overlay_image_path = resource_path('default.png')

        self.extra_fps_var = tk.BooleanVar()
        self.extra_fps_value = 2  # Default FPS value

        # Initialize control variables
        self.blur_var = tk.BooleanVar()
        self.pixelate_var = tk.BooleanVar(value=True) 
        self.overlay_var = tk.BooleanVar()

        # Placeholder labels to avoid attribute errors
        self.expand_value_label = None
        self.confidence_value_label = None
        self.blur_value_label = None
        self.pixel_value_label = None

        self.playing_video = False
        self.volume_level = 0.5
        self.muted = False

        self.setup_gui()

#region GUI
    def setup_gui(self):
        # --- Main Layout ---
        main_frame = ttk.Frame(self.root)
        main_frame.pack(expand=True, fill='both', padx=0, pady=0)

        # --- Headline ---
        headline_frame = ttk.Frame(self.root, height=60)
        headline_frame.place(relx=0.5, y=20, anchor="center")

        render_text_on_canvas(
            headline_frame,
            text="No Face, No Case",
            font_path=resource_path("PixelifySans-Regular.ttf"),
            font_size=54,
            text_color="orange"
        )

        # --- Panels ---
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Left Panel: Settings ---
        settings_frame = ttk.Frame(content_frame, padding=(10, 50))
        settings_frame.pack(side="left", fill="y", expand=True)

        # --- Right Panel: Preview ---
        preview_frame = ttk.Frame(content_frame, padding=(10, 70))
        preview_frame.pack(side="right", fill="both", expand=True)

    #region Left

        # --- Left Panel Content ---
        # File Setup
        ttk.Label(settings_frame, text="File Setup:", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5))
        # --- Select media file section ---
        ttk.Label(settings_frame, text="Select a media file (video or image):").pack(anchor="w", pady=(10, 2))

        # Frame for the input file path and Browse button
        input_frame = ttk.Frame(settings_frame)
        input_frame.pack(anchor="w", fill="x", pady=(5, 10))

        # Entry and button in the same row
        self.file_path_entry = ttk.Entry(input_frame)
        self.file_path_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(input_frame, text="Browse", command=self.select_file).pack(side="left")

        # --- Select output folder section ---
        ttk.Label(settings_frame, text="Select Output Folder:").pack(anchor="w", pady=(10, 2))

        # Frame for the output folder path entry and Browse button
        output_folder_frame = ttk.Frame(settings_frame)
        output_folder_frame.pack(anchor="w", fill="x", pady=(5, 10))

        # Entry and button in the same row
        self.output_folder_entry = ttk.Entry(output_folder_frame)
        self.output_folder_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(output_folder_frame, text="Browse", command=self.select_output_folder).pack(side="left")


        # Metadata
        ttk.Label(settings_frame, text="Metadata:", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5))
        ttk.Label(settings_frame, text="Filename:").pack(anchor="w")
        self.clip_name_entry = ttk.Entry(settings_frame, width=40)
        self.clip_name_entry.pack(anchor="w", pady=(5, 10))

        ttk.Label(settings_frame, text="Date:").pack(anchor="w")
        self.date_picker = DateEntry(settings_frame, locale='de_DE', date_pattern='dd.MM.yyyy')
        self.date_picker.pack(anchor="w", pady=(5, 10))

        ttk.Label(settings_frame, text="Location:").pack(anchor="w")
        self.location_entry = ttk.Entry(settings_frame, width=40)
        self.location_entry.pack(anchor="w", pady=(5, 10))

        # Options
        ttk.Label(settings_frame, text="Options:", font=("Arial", 14, "bold")).pack(anchor="w", pady=(20, 5))

        # Frame to hold the checkbox and size label side by side
        pixelation_checkbox_frame = ttk.Frame(settings_frame)
        pixelation_checkbox_frame.pack(anchor="w", pady=(5, 5))

        # Enable Pixelation checkbox with pre-checked state
        ttk.Checkbutton(pixelation_checkbox_frame, text="Enable Pixelation", variable=self.pixelate_var).pack(side="left")

        # Pixelation Size label and value next to the checkbox
        ttk.Label(pixelation_checkbox_frame, text="Pixelation Size:").pack(side="left", padx=(10, 5))
        self.pixel_value_label = ttk.Label(pixelation_checkbox_frame, text=f"{self.pixel_size}")
        self.pixel_value_label.pack(side="left")

        # Pixelation slider placed below the checkbox and label-value frame
        self.pixel_slider = ttk.Scale(
            settings_frame, from_=0.5, to=10, orient='horizontal', length=300, command=self.update_pixel_label
        )
        self.pixel_slider.set(6.0)  # Set default value to 5.0
        self.pixel_slider.pack(anchor="w", pady=(5, 10))

        # Frame to hold the checkbox and strength label side by side
        blur_checkbox_frame = ttk.Frame(settings_frame)
        blur_checkbox_frame.pack(anchor="w", pady=(5, 5))

        # Enable Blur checkbox
        ttk.Checkbutton(blur_checkbox_frame, text="Enable Blur", variable=self.blur_var).pack(side="left")

        # Strength label and value next to the checkbox
        ttk.Label(blur_checkbox_frame, text="Blur Strength:").pack(side="left", padx=(10, 5))
        self.blur_value_label = ttk.Label(blur_checkbox_frame, text=f"{self.blur_size}")
        self.blur_value_label.pack(side="left")

        # Blur strength slider below the checkbox
        self.blur_slider = ttk.Scale(settings_frame, from_=3, to=101, orient='horizontal', length=300, command=self.update_blur_label)
        self.blur_slider.set(self.blur_size)
        self.blur_slider.pack(anchor="w", pady=(0, 10))

        # Frame to hold the checkbox and button side by side
        overlay_frame = ttk.Frame(settings_frame)
        overlay_frame.pack(anchor="w", pady=(5, 10))

        # Enable Overlay checkbox
        ttk.Checkbutton(overlay_frame, text="Enable Overlay", variable=self.overlay_var).pack(side="left", padx=(0, 10))

        # Select Overlay Image button
        ttk.Button(overlay_frame, text="Select Overlay Image", command=self.select_overlay_image).pack(side="left")

        # Frame to hold the checkbox and number selector side by side
        overlay_frame = ttk.Frame(settings_frame)
        overlay_frame.pack(anchor="w", pady=(5, 10))

        # Frame to hold the checkbox, number selector, and label
        overlay_frame = ttk.Frame(settings_frame)
        overlay_frame.pack(anchor="w", pady=(5, 10))

        # Checkbox for enabling extra FPS
        ttk.Checkbutton(overlay_frame, text="Enable Extra Frames", variable=self.extra_fps_var).pack(side="left", padx=(0, 10))

        # Number selector (Spinbox) for selecting FPS value 
        self.extra_fps_spinbox = ttk.Spinbox(overlay_frame, from_=1, to=15, width=5)
        self.extra_fps_spinbox.set(self.extra_fps_value)  
        self.extra_fps_spinbox.pack(side="left")

        # Static FPS label displayed next to the Spinbox
        ttk.Label(overlay_frame, text="FPS").pack(side="left", padx=(10, 0))

    #endregion Left
    #region Right
        # --- Right Panel Content ---
        # Enable Preview checkbox
        self.preview_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(preview_frame, text="Enable Preview", variable=self.preview_enabled, command=self.update_preview).pack(anchor="n", pady=(0, 10))

        # Preview canvas
        self.preview_canvas = tk.Canvas(preview_frame, width=500, height=500, bg="black")
        self.preview_canvas.pack(anchor="n", pady=(10, 10))
        
        # Add controls to the preview frame (play/pause, volume, mute)
        self.setup_gui_controls(preview_frame)

        # Add a label to display file specifications in the preview frame
        self.specs_label = ttk.Label(preview_frame, text="Resolution: N/A, Size: N/A, FPS: N/A")
        self.specs_label.pack(anchor="n", pady=(10, 5))

        # --- Effect Expansion Size Section ---
        # Frame to hold label and value side by side
        expand_frame = ttk.Frame(preview_frame)
        expand_frame.pack(anchor="n", pady=(10, 2))

        # Effect Expansion Size label and value side by side
        ttk.Label(expand_frame, text="Effect Expansion Size (Face radius):").pack(side="left", padx=(0, 5))
        self.expand_value_label = ttk.Label(expand_frame, text=f"{self.face_expand_ratio:.2f}")
        self.expand_value_label.pack(side="left")

        # Slider placed below the label frame
        self.expand_slider = ttk.Scale(preview_frame, from_=0.5, to=2.0, orient='horizontal', length=300, command=self.update_expand_size_label)
        self.expand_slider.set(self.face_expand_ratio)
        self.expand_slider.pack(anchor="n", pady=(5, 10))

        # Confidence Threshold slider
        # Frame to hold label and value side by side
        confidence_frame = ttk.Frame(preview_frame)
        confidence_frame.pack(anchor="n", pady=(10, 2))

        # Confidence Threshold label and value side by side
        ttk.Label(confidence_frame, text="Confidence Threshold:").pack(side="left", padx=(0, 5))
        self.confidence_value_label = ttk.Label(confidence_frame, text=f"{self.confidence_threshold:.2f}")
        self.confidence_value_label.pack(side="left")

        # Slider placed below the label frame
        self.confidence_slider = ttk.Scale(preview_frame, from_=0.1, to=1.0, orient='horizontal', length=300, command=self.update_confidence_label)
        self.confidence_slider.set(self.confidence_threshold)
        self.confidence_slider.pack(anchor="n", pady=(5, 10))
        self.initialize_preview()
    #endregion Right
    #region Full widht and Footer
        # --- Full-width Controls ---
        control_frame = ttk.Frame(self.root)
        control_frame.place(relx=0.5, rely=0.89, anchor="center")  # Adjust `rely` as needed

        # Button Frame for centered alignment
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(anchor="center", pady=(0, 5))

        # Process
        button_font = tkfont.Font(family="Arial", size=14, weight="bold")  # Define font without bg

        # Set background color in the button, not the font
        process_button = ttk.Button(
            button_frame,
            text="Process",
            command=self.process
        )

        # Apply styles to change button appearance, including background color
        style = ttk.Style(self.root)
        style.configure("Custom.TButton", font=button_font, background="orange", foreground="white")

        # Use the custom style
        process_button.configure(style="Custom.TButton")
        process_button.pack(side="left", padx=(10, 5))

        # Create a custom style for the button (if you want to use consistent styling for other buttons)
        style = ttk.Style()
        style.configure("Custom.TButton", font=button_font)

        # Create a frame to stretch the progress bar across the entire width of the window
        bar_frame = ttk.Frame(self.root)
        bar_frame.place(relx=0.5, rely=0.93, anchor="center")

        # Progress bar stretched across a wider area
        self.progress_bar = ttk.Progressbar(bar_frame, orient='horizontal', mode='determinate', length=800)
        self.progress_bar.pack(fill="x", padx=20, pady=(10, 0))
        
        # --- Elapsed Time Label ---
        self.elapsed_time_label = ttk.Label(bar_frame, text="Elapsed Time: 00:00", anchor="center")
        self.elapsed_time_label.pack(fill="x", pady=(5, 0))

        # --- Footer ---
        footer_frame = ttk.Frame(self.root)
        footer_frame.place(relx=0.5, rely=0.98, anchor="center")

        help_button = ttk.Button(self.root, text="?", command=self.show_readme, width=3)
        help_button.place(x=10, y=10)  # Position at the top-left corner

        render_text_link(
            footer_frame,
            text="Developed by ACME Prototypes",
            font_path=resource_path("PixelifySans-Regular.ttf"),
            font_size=18,
            text_color="white",
            link_url="https://acme-prototypes.com/"
        )
    #endregion Full widht and Footer
#endregion GUI

#region Preview
    def initialize_preview(self):
        """Initialize the preview with default placeholders and settings."""
        self.preview_enabled.set(True)
        self.update_preview()

    def update_preview(self):
        """Update the preview when preview mode or file selection changes."""
        if not self.preview_enabled.get():
            self.control_frame.place_forget()
            self.load_preview_image(resource_path('disabled.png'), animated=True)
            return

        file_path = self.file_path_entry.get()
        if not file_path:
            self.control_frame.place_forget()
            self.load_preview_image(resource_path('enabled.png'), animated=True)
            return

        self.load_preview_image(file_path)

    def animate_image(self, image, pixel_size):
        """Apply pixelation effect to the image by resizing and scaling back up."""
        width, height = image.size
        small_image = image.resize((width // pixel_size, height // pixel_size), Image.Resampling.NEAREST)
        return small_image.resize((width, height), Image.Resampling.NEAREST)

    def load_preview_image(self, image_path, animated=True):
        """Load and display an image or video frame in the preview canvas."""
        try:
            if image_path.lower().endswith(('.mp4', '.avi')):
                self.cap = cv2.VideoCapture(image_path)
                ret, frame = self.cap.read()
                if ret:
                    self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    aspect_ratio = image.width / image.height
                    width, height = (500, int(500 / aspect_ratio)) if aspect_ratio > 1 else (int(500 * aspect_ratio), 500)
                    image = image.resize((width, height), Image.Resampling.LANCZOS)
                    self.display_on_canvas(image)

                    self.control_frame.place(relx=0.5, rely=0.65, anchor="center")  # Bottom center placement

                else:
                    print("Failed to load video.")
                    self.cap.release()
                    self.control_frame.place_forget()
                return

            image = Image.open(image_path)
            aspect_ratio = image.width / image.height
            width, height = (500, int(500 / aspect_ratio)) if aspect_ratio > 1 else (int(500 * aspect_ratio), 500)
            image = image.resize((width, height), Image.Resampling.LANCZOS)

            if animated:
                for pixel_size in range(20, 1, -2):
                    animated_image = self.animate_image(image, pixel_size)
                    self.display_on_canvas(animated_image)
                    time.sleep(0.05)

            self.display_on_canvas(image)
            self.control_frame.place_forget()

        except Exception as e:
            print(f"Failed to load preview image: {e}")

    def play_video_preview(self):
        """Start or resume video playback."""
        if not self.cap or not self.cap.isOpened():
            print("No video loaded for playback.")
            return

        self.playing_video = True
        self.updating_slider = False
        self.play_pause_button.config(text="⏸️")
        self.update_frame()

    def update_frame(self):
        """Update the canvas with the next frame of the video."""
        if not self.playing_video or not self.cap.isOpened():
            return

        ret, frame = self.cap.read()
        if not ret:
            self.playing_video = False
            self.play_pause_button.config(text="▶️")
            return

        if not self.slider_active:
            self.updating_slider = True
            current_frame = int(self.cap.get(cv2.CAP_PROP_POS_FRAMES))
            self.video_slider.set((current_frame / self.total_frames) * 100)
            self.updating_slider = False

        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        aspect_ratio = image.width / image.height
        width, height = (500, int(500 / aspect_ratio)) if aspect_ratio > 1 else (int(500 * aspect_ratio), 500)
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        self.display_on_canvas(image)

        if self.playing_video:
            frame_delay = max(1, int(1000 / self.fps))
            self.root.after(frame_delay, self.update_frame)

    def toggle_play_pause(self):
        """Toggle between play and pause states."""
        if self.playing_video:
            self.playing_video = False
            self.play_pause_button.config(text="▶️")
        else:
            self.play_video_preview()

    def stop_video_preview(self):
        """Stop the video playback, reset to the first frame, and display it."""
        self.playing_video = False
        if self.cap and self.cap.isOpened():
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            if ret:
                image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                aspect_ratio = image.width / image.height
                width, height = (500, int(500 / aspect_ratio)) if aspect_ratio > 1 else (int(500 * aspect_ratio), 500)
                image = image.resize((width, height), Image.Resampling.LANCZOS)
                self.display_on_canvas(image)
        self.play_pause_button.config(text="▶️")
        self.video_slider.set(0)

    def on_slider_change(self, value):
        """Handle slider change to seek video position."""
        if self.cap and self.cap.isOpened():
            if not self.updating_slider:
                self.slider_active = True
                frame_to_seek = int((float(value) / 100) * self.total_frames)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_to_seek)

                if not self.playing_video:
                    ret, frame = self.cap.read()
                    if ret:
                        image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                        aspect_ratio = image.width / image.height
                        width, height = (500, int(500 / aspect_ratio)) if aspect_ratio > 1 else (int(500 * aspect_ratio), 500)
                        image = image.resize((width, height), Image.Resampling.LANCZOS)
                        self.display_on_canvas(image)

                self.slider_active = False

    def display_on_canvas(self, image):
        """Display the given image on the preview canvas."""
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(250, 250, anchor="center", image=self.preview_image)
        self.preview_canvas.update()

    def setup_gui_controls(self, preview_frame):
        """Set up the play/pause button, stop button, and video slider on top of the preview canvas."""

        self.control_frame = tk.Frame(preview_frame, bg='', highlightthickness=0)

        self.play_pause_button = ttk.Button(self.control_frame, text="▶️", command=self.toggle_play_pause)
        self.play_pause_button.pack(side="left", padx=(5, 10))

        self.stop_button = ttk.Button(self.control_frame, text="⏹️", command=self.stop_video_preview)
        self.stop_button.pack(side="left", padx=(5, 10))

        self.video_slider = ttk.Scale(
            self.control_frame, from_=0, to=100, orient='horizontal', length=200,
            command=self.on_slider_change
        )
        self.video_slider.pack(side="left", padx=(5, 10))

        self.control_frame.place_forget()
#endregion

#region Options
    def select_output_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            self.output_folder_entry.delete(0, tk.END)
            self.output_folder_entry.insert(0, folder_path)

    def update_extra_fps_value(self):
        """Update the displayed FPS value when the spinbox changes."""
        self.extra_fps_value = int(self.extra_fps_spinbox.get())
        self.extra_fps_value_label.config(text=f"FPS: {self.extra_fps_value}")
        print(f"Selected Extra FPS: {self.extra_fps_value}")

    def toggle_blur_slider(self):
        """Toggle the blur slider and ensure proper packing order."""
        if self.blur_var.get():
            self.add_blur_slider()
        else:
            self.remove_blur_slider()
        self.repack_widgets()

    def toggle_pixel_slider(self):
        """Toggle the pixel slider and ensure proper packing order."""
        if self.pixelate_var.get():
            self.add_pixel_slider()
        else:
            self.remove_pixel_slider()
        self.repack_widgets()

    def update_expand_size_label(self, event):
        self.face_expand_ratio = self.expand_slider.get()
        if self.expand_value_label:
            self.expand_value_label.config(text=f"{self.face_expand_ratio:.2f}")

    def update_confidence_label(self, event):
        self.confidence_threshold = self.confidence_slider.get()
        if self.confidence_value_label:
            self.confidence_value_label.config(text=f"{self.confidence_threshold:.2f}")

    def update_pixel_label(self, event):
        self.pixel_size = int(self.pixel_slider.get()) if hasattr(self, 'pixel_slider') else self.pixel_size
        if self.pixel_value_label:
            self.pixel_value_label.config(text=f"{self.pixel_size}")

    def update_blur_label(self, event):
        """Update the blur size label safely."""
        if self.blur_value_label and self.blur_value_label.winfo_exists():
            self.blur_size = int(self.blur_slider.get())
            self.blur_value_label.config(text=f"{self.blur_size}")

    def add_blur_slider(self):
        """Add the blur slider and value label, packing the frame."""
        ttk.Label(self.blur_slider_frame, text="Blur Strength:").pack(anchor="w")
        self.blur_slider = ttk.Scale(self.blur_slider_frame, from_=3, to=101, orient='horizontal', length=300, command=self.update_blur_label)
        self.blur_slider.set(self.blur_size)
        self.blur_slider.pack(anchor="w")
        self.blur_value_label = ttk.Label(self.blur_slider_frame, text=f"{self.blur_size}")
        self.blur_value_label.pack(anchor="w")
        self.blur_slider_frame.pack(anchor="w")  # Ensure the frame is shown

    def add_pixel_slider(self):
        """Add the pixel slider and value label, packing the frame."""
        ttk.Label(self.pixel_slider_frame, text="Pixelation Size:").pack(anchor="w")
        self.pixel_slider = ttk.Scale(self.pixel_slider_frame, from_=0.5, to=10, orient='horizontal', length=300, command=self.update_pixel_label)
        self.pixel_slider.set(self.pixel_size)
        self.pixel_slider.pack(anchor="w")
        self.pixel_value_label = ttk.Label(self.pixel_slider_frame, text=f"{self.pixel_size}")
        self.pixel_value_label.pack(anchor="w")
        self.pixel_slider_frame.pack(anchor="w")  # Ensure the frame is shown

    def select_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Media files", "*.mp4;*.avi;*.jpg;*.png")])
        if file_path:
            self.file_path_entry.delete(0, tk.END)
            self.file_path_entry.insert(0, file_path)
            self.display_specs(file_path)
            self.autofill_metadata(file_path)
            self.initialize_preview()

    def select_overlay_image(self):
        """Allow the user to select an overlay image or use the default if none is provided."""
        selected_path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg")])
        
        if selected_path:
            self.overlay_image_path = selected_path
            print(f"Overlay image selected: {self.overlay_image_path}")
        else:
            self.overlay_image_path = resource_path('default.png')
            print(f"No file selected. Using default overlay image: {self.overlay_image_path}")

        if not os.path.exists(self.overlay_image_path):
            messagebox.showerror("Error", "Default overlay image not found!")
            self.overlay_image_path = None

    def display_specs(self, file_path):
        """Display video or image specifications."""
        if file_path.endswith(('.mp4', '.avi')):
            # For video files
            cap = cv2.VideoCapture(file_path)
            resolution = f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}"
            fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Calculate video length (in seconds)
            video_length_seconds = total_frames / fps if fps > 0 else 0
            formatted_length = time.strftime("%M:%S", time.gmtime(video_length_seconds))

            # Display video specs
            specs_text = (
                f"Resolution: {resolution}, Size: {os.path.getsize(file_path) / 1024:.2f} KB, "
                f"FPS: {fps:.2f}, Length: {formatted_length}"
            )
            cap.release()
        else:
            # For image files
            image = cv2.imread(file_path)
            resolution = f"{image.shape[1]}x{image.shape[0]}"

            # Display image specs
            specs_text = f"Resolution: {resolution}, Size: {os.path.getsize(file_path) / 1024:.2f} KB, FPS: N/A, Length: N/A"

        # Update the label with the full specs
        self.specs_label.config(text=specs_text)

    def autofill_metadata(self, file_path):
        file_name = os.path.basename(file_path).split('.')[0]
        self.clip_name_entry.delete(0, tk.END)
        self.clip_name_entry.insert(0, file_name)

        try:
            creation_date = datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%d.%m.%Y")
            self.date_picker.set_date(datetime.strptime(creation_date, "%d.%m.%Y"))
        except Exception as e:
            print(f"Failed to extract date: {e}")

    def process(self):
        file_path = self.file_path_entry.get()
        if not file_path:
            messagebox.showerror("Error", "Please select a file first.")
            return

        ext = os.path.splitext(file_path)[-1]
        is_video = ext in ['.mp4', '.avi']
        default_output = file_path.replace(ext, f"_processed{ext}")

        output_folder = self.output_folder_entry.get().strip()
        if not output_folder:
            messagebox.showerror("Error", "Please select an output folder first.")
            return

        output_path = os.path.join(output_folder, os.path.basename(default_output))

        # Run processing in a separate thread to prevent UI freezing
        threading.Thread(target=self.run_processing, args=(file_path, output_path, is_video, ext)).start()

    def run_processing(self, file_path, output_path, is_video, ext):
        # Start the timer
        start_time = time.time()

        metadata_name = self.clip_name_entry.get().strip().replace("\\", "_").replace("/", "_") or "output"
        metadata_date = self.date_picker.get_date().strftime("%d_%m_%Y")
        metadata_location = self.location_entry.get().strip().replace(" ", "_").replace("\\", "_").replace("/", "_") or "unknown"

        output_filename = f"{metadata_name}_{metadata_location}_{metadata_date}_processed{ext}"
        output_dir = self.output_folder_entry.get().strip() or os.path.dirname(output_path)

        # Debug prints to verify paths
        print(f"Metadata Name: {metadata_name}")
        print(f"Metadata Date: {metadata_date}")
        print(f"Metadata Location: {metadata_location}")
        print(f"Output Directory: {output_dir}")
        print(f"Output Filename: {output_filename}")

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")

        final_output_path = os.path.join(output_dir, output_filename)
        print(f"Final output path: {final_output_path}")

        if is_video:
            temp_video_path = os.path.join(output_dir, "temp_video.mp4")
            print(f"Temporary video path: {temp_video_path}")

            # Process video frames
            cap = cv2.VideoCapture(file_path)
            out = cv2.VideoWriter(temp_video_path, cv2.VideoWriter_fourcc(*'mp4v'), cap.get(cv2.CAP_PROP_FPS),
                                (int(cap.get(3)), int(cap.get(4))))

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            processed_frames = 0

            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                processed_frame = self.process_frame(frame)
                out.write(processed_frame)
                processed_frames += 1
                self.update_progress_bar((processed_frames / total_frames) * 100)

            cap.release()
            out.release()

            # Merge video and audio, add metadata
            try:
                subprocess.run([
                    get_ffmpeg_path(),  # Use the function here to provide the exact FFmpeg path
                    "-i", temp_video_path,
                    "-i", file_path,
                    "-map", "0:v", "-map", "1:a?",  # Use audio from input if available
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-metadata", f"title={metadata_name}",
                    "-metadata", f"date={metadata_date.replace('_', '-')}",
                    "-y",  # Overwrite output file
                    final_output_path
                ], check=True)
                os.remove(temp_video_path)
            except subprocess.CalledProcessError as e:
                print(f"Failed to merge audio or add metadata to video: {e}")
                if not os.path.exists(final_output_path):
                    os.rename(temp_video_path, final_output_path)
        else:
            # Process image and save it
            frame = cv2.imread(file_path)
            processed_frame = self.process_frame(frame)
            output_image_path = os.path.join(output_dir, output_filename.replace(ext, ".jpg"))
            print(f"Output image path: {output_image_path}")

            cv2.imwrite(output_image_path, processed_frame)

            # Add metadata to the processed image
            try:
                image = Image.open(output_image_path)

                # Add metadata to the image
                metadata = PngImagePlugin.PngInfo()
                metadata.add_text("Title", metadata_name)
                metadata.add_text("Date", metadata_date)

                # Save the image with metadata
                image.save(output_image_path, "PNG", pnginfo=metadata)
            except Exception as e:
                print(f"Failed to write metadata to image: {e}")

        # Calculate elapsed time
        elapsed_time = time.time() - start_time
        formatted_time = time.strftime("%M:%S", time.gmtime(elapsed_time))

        # Update the elapsed time label
        self.elapsed_time_label.config(text=f"Elapsed Time: {formatted_time}")
        print(f"Processing completed in {formatted_time}")

        # Display the result and notify the user
        self.show_processed_result(final_output_path)
        messagebox.showinfo("Processing Complete", f"Output saved to: {final_output_path}")

    def show_processed_result(self, output_path):
        """Show the processed result on the preview canvas."""
        if output_path.lower().endswith(('.mp4', '.avi')):
            # If it's a video, load it for preview
            self.cap = cv2.VideoCapture(output_path)
            self.play_video_preview()
        else:
            # If it's an image, display it
            image = Image.open(output_path)
            aspect_ratio = image.width / image.height
            width, height = (500, int(500 / aspect_ratio)) if aspect_ratio > 1 else (int(500 * aspect_ratio), 500)
            image = image.resize((width, height), Image.Resampling.LANCZOS)
            self.display_on_canvas(image)

        # Adjust controls visibility
        if output_path.lower().endswith(('.mp4', '.avi')):
            self.control_frame.place(relx=0.5, rely=0.65, anchor="center")
        else:
            self.control_frame.place_forget()

    def process_frame(self, frame):
        """Process each frame by detecting faces and applying effects."""
        extra_frames = int(self.extra_fps_spinbox.get()) if self.extra_fps_var.get() else 1
        updated_positions = []

        # Detect faces on this frame
        detected_faces = self.detect_faces_yolo(frame)

        # Update face tracking list (store positions with frame countdowns)
        for (x, y, w, h) in detected_faces:
            match_found = False
            for i, (fx, fy, fw, fh, countdown) in enumerate(self.face_positions):
                if self.is_same_face((x, y, w, h), (fx, fy, fw, fh)):  # Check if faces match
                    self.face_positions[i] = (fx, fy, fw, fh, extra_frames)  # Reset countdown
                    match_found = True
                    break

            if not match_found:
                self.face_positions.append((x, y, w, h, extra_frames))

        # Process each tracked face
        for (x, y, w, h, countdown) in self.face_positions:
            expand_w = int(w * self.face_expand_ratio)
            expand_h = int(h * self.face_expand_ratio)
            x_start = max(0, x - expand_w // 2)
            y_start = max(0, y - expand_h // 2)
            x_end = min(frame.shape[1], x + w + expand_w // 2)
            y_end = min(frame.shape[0], y + h + expand_h // 2)

            face_area = frame[y_start:y_end, x_start:x_end]

            # Apply effects based on user settings
            if self.blur_var.get():
                blur_strength = max(3, self.blur_size // 2 * 2 + 1)
                face_area = cv2.GaussianBlur(face_area, (blur_strength, blur_strength), 30)

            if self.pixelate_var.get():
                small = cv2.resize(face_area, (self.pixel_size, self.pixel_size), interpolation=cv2.INTER_LINEAR)
                face_area = cv2.resize(small, (face_area.shape[1], face_area.shape[0]), interpolation=cv2.INTER_NEAREST)

            if self.overlay_var.get() and self.overlay_image_path:
                overlay_img = cv2.imread(self.overlay_image_path, cv2.IMREAD_UNCHANGED)
                if overlay_img is not None:
                    overlay_resized = cv2.resize(overlay_img, (x_end - x_start, y_end - y_start))
                    face_area = self.apply_overlay(face_area, overlay_resized)

            frame[y_start:y_end, x_start:x_end] = face_area

            # Decrement countdown and keep faces with time left
            if countdown > 1:
                updated_positions.append((x, y, w, h, countdown - 1))

        # Update the face tracking list for the next frame
        self.face_positions = updated_positions

        return frame

    def is_same_face(self, face1, face2, threshold=0.2):
        """Determine if two faces are the same based on position and size."""
        x1, y1, w1, h1 = face1
        x2, y2, w2, h2 = face2

        # Check if the faces overlap within a certain threshold
        overlap_x = abs(x1 - x2) < w1 * threshold
        overlap_y = abs(y1 - y2) < h1 * threshold
        size_match = abs(w1 - w2) < w1 * threshold and abs(h1 - h2) < h1 * threshold

        return overlap_x and overlap_y and size_match

    def apply_overlay(self, base_image, overlay):
            """Apply overlay with alpha blending if available."""
            if overlay.shape[2] == 4:  # Check if overlay has an alpha channel
                alpha_overlay = overlay[:, :, 3] / 255.0  # Normalize alpha channel
                alpha_base = 1.0 - alpha_overlay

                for c in range(0, 3):  # Blend each color channel
                    base_image[:, :, c] = (alpha_overlay * overlay[:, :, c] +
                                        alpha_base * base_image[:, :, c])
            else:
                # If no alpha channel, perform a simple overlay
                overlay_bgr = overlay[:, :, :3]
                base_image[:overlay_bgr.shape[0], :overlay_bgr.shape[1]] = overlay_bgr

            return base_image

    def detect_faces_yolo(self, frame):
            results = model(frame, conf=self.confidence_threshold)
            return [(int(x1), int(y1), int(x2 - x1), int(y2 - y1)) for x1, y1, x2, y2 in results[0].boxes.xyxy.tolist()]

    def show_readme(self):
        """Display the README.md file content in a new window."""
        readme_path = resource_path("README.md")  # Adjust to the actual location of your README.md

        if not os.path.exists(readme_path):
            messagebox.showerror("Error", "README.md file not found!")
            return

        with open(readme_path, "r", encoding="utf-8") as file:
            readme_content = file.read()

        # Create a new window to display the README content
        readme_window = tk.Toplevel(self.root)
        readme_window.title("Help - README.md")
        readme_window.geometry("1000x600")


        text_widget = tk.Text(readme_window, wrap="word", font=("Courier New", 12))
        text_widget.insert("1.0", readme_content)
        text_widget.config(state="disabled")  # Make it read-only
        text_widget.pack(expand=True, fill="both", padx=10, pady=10)

        # Add a scrollbar
        scrollbar = ttk.Scrollbar(readme_window, command=text_widget.yview)
        text_widget.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        
    def update_progress_bar(self, progress):
        self.progress_bar['value'] = progress
        self.root.update_idletasks()
#endregion Options
#I love you Mara, thanks for everything, this would not have been possible without you Ⓐ
if __name__ == "__main__":
    # Initialize splash screen
    splash_root = tk.Tk()
    splash_screen = SplashScreen(splash_root)
    splash_screen.show()
    splash_root.mainloop()

    # Initialize main app window
    root = ThemedTk(theme="arc")

    # Ensure tkinter has completed initialization
    root.update_idletasks()

    # Set the icon
    icon_path = resource_path("icon.ico")  # Ensure the path points to a valid .ico or PNG file
    if os.path.exists(icon_path):
        try:
            icon_ref = PhotoImage(file=icon_path)  # Keep a reference to prevent garbage collection
            root.iconphoto(True, icon_ref)
            print("Icon set successfully.")
        except Exception as e:
            print("Failed to set icon:", e)
    else:
        print("Icon file not found:", icon_path)
    ffmpeg_path = get_ffmpeg_path()
    print(f"Using FFmpeg path: {ffmpeg_path}")
    # Launch the application
    app = VideoProcessorApp(root)
    root.mainloop()
