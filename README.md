No Face No Case
===================
------------------------------------------------------
USAGE INSTRUCTIONS
------------------------------------------------------

1. FILE SETUP:
   - Select a media file (video/image) using the "Browse" button.
   - Choose an output folder and set metadata (filename, date, location).

2. CONFIGURE EFFECTS:
   - Enable pixelation, blur, or overlay effects.
   - Adjust effect parameters using sliders.

3. START PROCESSING:
   - Click the "Process" button.
   - Track progress & elapsed time.
   - Output file saved in the selected directory.

4. PREVIEW & CONTROLS:
   - Preview window for real-time inspection.
   - Video playback controls: Play, pause, stop, and seek.

------------------------------------------------------
CUSTOMIZABLE OPTIONS
------------------------------------------------------

Option                  | Description                              | Adjustable Values
------------------------|------------------------------------------|----------------------
Pixelation              | Enable/disable pixelation effect        | Checkbox
Pixel Size             | Adjust pixel size                        | Slider (0.5 to 10)
Blurring               | Enable/disable blur effect               | Checkbox
Blur Strength          | Adjust blur intensity                    | Slider (3 to 101)
Overlay Image          | Apply a custom image to detected faces   | File selection
Face Expansion             | Expand detected face area                | Slider (0.5 to 2.0)
Confidence Threshold   | Adjust face detection accuracy           | Slider (0.1 to 1.0)
Extra FPS             | Enable additional frame processing        | Checkbox + Spinbox (1-15)
Preview Mode          | Enable/disable real-time preview         | Checkbox
Media Playback        | Play, pause, stop, and seek videos       | Play, Pause, Stop + Slider

------------------------------------------------------

NOTES
------------------------------------------------------
- Ensure ffmpeg is installed and added to PATH if not using the exe.
- Pre-trained YOLO model is required for face detection.
- Performance may vary for large media files.

------------------------------------------------------
LICENSE
------------------------------------------------------
This project is licensed under the MIT License.

------------------------------------------------------
CREDITS
------------------------------------------------------
Developed by ACME Prototypes.
Visit: https://acme-prototypes.com/

