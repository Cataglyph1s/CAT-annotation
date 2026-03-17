import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


class VideoImporter:
    SUPPORTED_FORMATS = (
        ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv"),
        ("All files", "*.*"),
    )

    def __init__(self, root, on_import_done=None):
        self.on_import_done = on_import_done

        self._progress = 0
        self._status = ""
        self._done = False
        self._error = None
        self._output_folder = None

        self.window = tk.Toplevel(root)
        self.window.title("Import Video")
        self.window.geometry("520x240")
        self.window.resizable(False, False)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
        frame = tk.Frame(self.window)
        frame.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)

        # Video file row
        tk.Label(frame, text="Video file:", anchor='w', width=14).grid(row=0, column=0, sticky='w', **pad)
        self.video_path = tk.StringVar()
        tk.Entry(frame, textvariable=self.video_path, width=38).grid(row=0, column=1, sticky='ew', **pad)
        tk.Button(frame, text="Browse", command=self._browse_video, width=8).grid(row=0, column=2, **pad)

        # Output folder row
        tk.Label(frame, text="Output folder:", anchor='w', width=14).grid(row=1, column=0, sticky='w', **pad)
        self.output_path = tk.StringVar()
        tk.Entry(frame, textvariable=self.output_path, width=38).grid(row=1, column=1, sticky='ew', **pad)
        tk.Button(frame, text="Browse", command=self._browse_output, width=8).grid(row=1, column=2, **pad)

        # Target FPS row
        tk.Label(frame, text="Target FPS:", anchor='w', width=14).grid(row=2, column=0, sticky='w', **pad)
        fps_frame = tk.Frame(frame)
        fps_frame.grid(row=2, column=1, sticky='w', **pad)
        self.target_fps = tk.StringVar(value="1.0")
        tk.Entry(fps_frame, textvariable=self.target_fps, width=8).pack(side=tk.LEFT)
        tk.Label(fps_frame, text="  (frames per second to extract)", fg='gray').pack(side=tk.LEFT)

        # Status label
        self.status_label = tk.Label(frame, text="", anchor='w', fg='gray')
        self.status_label.grid(row=3, column=0, columnspan=3, sticky='ew', padx=10)

        # Progress bar
        self.progress_bar = ttk.Progressbar(frame, orient='horizontal', mode='determinate', maximum=100)
        self.progress_bar.grid(row=4, column=0, columnspan=3, sticky='ew', padx=10, pady=(0, 6))

        # Buttons
        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=3, sticky='e')
        tk.Button(btn_frame, text="Cancel", width=10, command=self.window.destroy).pack(side=tk.LEFT, padx=4)
        self.import_btn = tk.Button(btn_frame, text="Import", width=10, bg="lightgreen",
                                    relief=tk.RAISED, command=self._start_import)
        self.import_btn.pack(side=tk.LEFT, padx=4)

        frame.columnconfigure(1, weight=1)

    def _browse_video(self):
        path = filedialog.askopenfilename(parent=self.window, title="Select Video File",
                                          filetypes=self.SUPPORTED_FORMATS)
        if path:
            self.video_path.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(parent=self.window, title="Select Output Folder")
        if path:
            self.output_path.set(path)

    def _start_import(self):
        video_path = self.video_path.get().strip()
        output_folder = self.output_path.get().strip()

        if not video_path:
            messagebox.showwarning("Missing input", "Please select a video file.", parent=self.window)
            return
        if not os.path.isfile(video_path):
            messagebox.showwarning("Invalid file", "Video file not found.", parent=self.window)
            return
        if not output_folder:
            messagebox.showwarning("Missing input", "Please select an output folder.", parent=self.window)
            return

        try:
            target_fps = float(self.target_fps.get())
            if target_fps <= 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid FPS", "Target FPS must be a positive number.", parent=self.window)
            return

        self._output_folder = output_folder
        self._progress = 0
        self._status = ""
        self._done = False
        self._error = None

        self.import_btn.config(state=tk.DISABLED)
        t = threading.Thread(target=self._run_import,
                             args=(video_path, output_folder, target_fps),
                             daemon=True)
        t.start()
        self.window.after(100, self._poll)

    def _run_import(self, video_path, output_folder, target_fps):
        try:
            import cv2
        except ImportError:
            self._error = "opencv-python is not installed.\nRun: pip install opencv-python"
            self._done = True
            return

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self._error = "Could not open video file."
            self._done = True
            return

        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        if video_fps <= 0:
            video_fps = 25.0

        frame_interval = max(1, round(video_fps / target_fps))

        images_dir = os.path.join(output_folder, "images")
        labels_dir = os.path.join(output_folder, "labels")
        os.makedirs(images_dir, exist_ok=True)
        os.makedirs(labels_dir, exist_ok=True)

        video_name = os.path.splitext(os.path.basename(video_path))[0]
        frame_idx = 0
        saved = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                filename = f"{video_name}_{frame_idx:06d}.jpg"
                cv2.imwrite(os.path.join(images_dir, filename), frame,
                            [cv2.IMWRITE_JPEG_QUALITY, 95])
                saved += 1

            frame_idx += 1
            if total_frames > 0:
                self._progress = int((frame_idx / total_frames) * 100)
            self._status = f"Extracting... {saved} frames saved"

        cap.release()
        self._progress = 100
        self._status = f"Done — {saved} frames saved to {images_dir}"
        self._done = True

    def _poll(self):
        self.progress_bar['value'] = self._progress
        self.status_label.config(text=self._status)

        if self._done:
            if self._error:
                messagebox.showerror("Import Error", self._error, parent=self.window)
                self.import_btn.config(state=tk.NORMAL)
            else:
                if self.on_import_done:
                    self.on_import_done(self._output_folder)
                self.window.destroy()
        else:
            self.window.after(100, self._poll)
