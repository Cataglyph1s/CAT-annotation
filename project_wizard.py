import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, colorchooser

from project_manager import ProjectManager
from video_importer import VideoImporter
from app_config import AppConfig

DEFAULT_COLORS = [
    '#E6194B', '#3CB44B', '#FFE119', '#4363D8', '#F58231',
    '#911EB4', '#42D4F4', '#F032E6', '#BFEF45', '#F4A460',
]


class ProjectWizard:
    def __init__(self, root, on_project_created=None):
        self.root = root
        self.on_project_created = on_project_created

        self._classes = []       # list of {'name': str, 'color': str}
        self._project_path = None
        self._sets = []          # list of set folder paths

        self.window = tk.Toplevel(root)
        self.window.title("New Project")
        self.window.geometry("660x580")
        self.window.resizable(False, False)
        self.window.grab_set()

        self._build_screen1()
        self._build_screen2()
        self._show_screen1()

        program_root = AppConfig.get_program_root()
        if program_root:
            self.base_folder.set(program_root)

    # ------------------------------------------------------------------
    # Screen 1 — project name, location, classes
    # ------------------------------------------------------------------

    def _build_screen1(self):
        self.frame1 = tk.Frame(self.window)
        pad = {'padx': 14, 'pady': 6}

        tk.Label(self.frame1, text="New Project — Step 1 of 2",
                 font=("Helvetica", 12, "bold")).pack(anchor='w', **pad)
        tk.Frame(self.frame1, height=1, bg='lightgray').pack(fill=tk.X, padx=14)

        # Project name
        row = tk.Frame(self.frame1)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="Project name:", width=14, anchor='w').pack(side=tk.LEFT)
        self.project_name = tk.StringVar()
        tk.Entry(row, textvariable=self.project_name, width=38).pack(side=tk.LEFT)

        # Location
        row = tk.Frame(self.frame1)
        row.pack(fill=tk.X, **pad)
        tk.Label(row, text="Location:", width=14, anchor='w').pack(side=tk.LEFT)
        self.base_folder = tk.StringVar()
        tk.Entry(row, textvariable=self.base_folder, width=30).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(row, text="Browse", width=8, command=self._browse_base_folder).pack(side=tk.LEFT)

        # Classes header
        tk.Frame(self.frame1, height=1, bg='lightgray').pack(fill=tk.X, padx=14, pady=(8, 0))
        tk.Label(self.frame1, text="Classes", font=("Helvetica", 10, "bold")).pack(anchor='w', padx=14, pady=(6, 0))

        # Add class row
        add_row = tk.Frame(self.frame1)
        add_row.pack(fill=tk.X, padx=14, pady=(4, 0))
        self.class_entry = tk.Entry(add_row, width=32)
        self.class_entry.pack(side=tk.LEFT, padx=(0, 6))
        self.class_entry.bind('<Return>', lambda e: self._add_class())
        tk.Button(add_row, text="+", width=3, command=self._add_class).pack(side=tk.LEFT)

        # Scrollable class list
        list_outer = tk.Frame(self.frame1, relief=tk.SUNKEN, bd=1)
        list_outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=(6, 8))

        self._class_canvas = tk.Canvas(list_outer, bd=0, highlightthickness=0)
        scrollbar = tk.Scrollbar(list_outer, orient='vertical', command=self._class_canvas.yview)
        self._class_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._class_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._class_rows_frame = tk.Frame(self._class_canvas)
        self._class_canvas_win = self._class_canvas.create_window(
            (0, 0), window=self._class_rows_frame, anchor='nw')
        self._class_rows_frame.bind("<Configure>",
                                    lambda e: self._class_canvas.configure(
                                        scrollregion=self._class_canvas.bbox("all")))
        self._class_canvas.bind("<Configure>",
                                lambda e: self._class_canvas.itemconfig(
                                    self._class_canvas_win, width=e.width))

        # Next button
        btn_row = tk.Frame(self.frame1)
        btn_row.pack(fill=tk.X, padx=14, pady=(0, 12))
        tk.Button(btn_row, text="Next >", width=10, bg='lightgreen',
                  relief=tk.RAISED, command=self._go_to_screen2).pack(side=tk.RIGHT)

    def _browse_base_folder(self):
        path = filedialog.askdirectory(parent=self.window, title="Select Project Location")
        if path:
            self.base_folder.set(path)

    def _add_class(self):
        name = self.class_entry.get().strip()
        if not name:
            return
        color = DEFAULT_COLORS[len(self._classes) % len(DEFAULT_COLORS)]
        self._classes.append({'name': name, 'color': color})
        self._refresh_class_rows()
        self.class_entry.delete(0, tk.END)
        self.class_entry.focus_set()

    def _refresh_class_rows(self):
        for widget in self._class_rows_frame.winfo_children():
            widget.destroy()
        for i, cls in enumerate(self._classes):
            row = tk.Frame(self._class_rows_frame)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=f"{i}:", width=3, anchor='e').pack(side=tk.LEFT)
            tk.Label(row, text=cls['name'], width=22, anchor='w').pack(side=tk.LEFT, padx=(4, 8))
            # Colour swatch
            swatch = tk.Label(row, bg=cls['color'], width=4, relief=tk.RAISED)
            swatch.pack(side=tk.LEFT, padx=(0, 4))
            tk.Button(row, text="Pick colour", width=10,
                      command=lambda idx=i: self._pick_color(idx)).pack(side=tk.LEFT, padx=(0, 10))
            tk.Button(row, text="Remove", width=7, fg='red',
                      command=lambda idx=i: self._remove_class(idx)).pack(side=tk.LEFT)

    def _pick_color(self, idx):
        result = colorchooser.askcolor(
            color=self._classes[idx]['color'],
            parent=self.window,
            title=f"Pick colour for {idx}: {self._classes[idx]['name']}")
        if result and result[1]:
            self._classes[idx]['color'] = result[1]
            self._refresh_class_rows()

    def _remove_class(self, idx):
        self._classes.pop(idx)
        self._refresh_class_rows()

    def _go_to_screen2(self):
        name = self.project_name.get().strip()
        base = self.base_folder.get().strip()
        if not name:
            messagebox.showwarning("Missing input", "Please enter a project name.", parent=self.window)
            return
        if not base or not os.path.isdir(base):
            messagebox.showwarning("Missing input", "Please select a valid location.", parent=self.window)
            return
        if not self._classes:
            messagebox.showwarning("No classes", "Please add at least one class.", parent=self.window)
            return

        new_path = os.path.join(base, name)
        if new_path != self._project_path:
            self._sets = []  # reset sets if project location changed

        try:
            self._project_path = ProjectManager.create_project(
                base, name,
                [{'id': i, 'name': c['name'], 'color': c['color']}
                 for i, c in enumerate(self._classes)]
            )
        except Exception as e:
            messagebox.showerror("Error", f"Could not create project:\n{e}", parent=self.window)
            return

        self._update_screen2_header()
        self._refresh_set_suggestion()
        self._show_screen2()

    # ------------------------------------------------------------------
    # Screen 2 — image sets
    # ------------------------------------------------------------------

    def _build_screen2(self):
        self.frame2 = tk.Frame(self.window)
        pad = {'padx': 14, 'pady': 6}

        tk.Label(self.frame2, text="New Project — Step 2 of 2",
                 font=("Helvetica", 12, "bold")).pack(anchor='w', **pad)
        tk.Frame(self.frame2, height=1, bg='lightgray').pack(fill=tk.X, padx=14)

        self.screen2_info = tk.Label(self.frame2, text="", anchor='w', fg='gray',
                                     font=("Helvetica", 9))
        self.screen2_info.pack(anchor='w', padx=14, pady=(4, 0))

        # Add set row
        tk.Label(self.frame2, text="Image Sets", font=("Helvetica", 10, "bold")).pack(
            anchor='w', padx=14, pady=(10, 0))

        add_row = tk.Frame(self.frame2)
        add_row.pack(fill=tk.X, padx=14, pady=(4, 0))
        tk.Label(add_row, text="Set name:", width=10, anchor='w').pack(side=tk.LEFT)
        self.set_name_var = tk.StringVar()
        self.set_name_entry = tk.Entry(add_row, textvariable=self.set_name_var, width=20)
        self.set_name_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.set_name_entry.bind('<Return>', lambda e: self._add_set())
        tk.Button(add_row, text="Add Set", width=10, command=self._add_set).pack(side=tk.LEFT)

        # Scrollable sets list
        sets_outer = tk.Frame(self.frame2, relief=tk.SUNKEN, bd=1)
        sets_outer.pack(fill=tk.BOTH, expand=True, padx=14, pady=(6, 4))

        self._sets_canvas = tk.Canvas(sets_outer, bd=0, highlightthickness=0)
        sets_scrollbar = tk.Scrollbar(sets_outer, orient='vertical', command=self._sets_canvas.yview)
        self._sets_canvas.configure(yscrollcommand=sets_scrollbar.set)
        sets_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._sets_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._set_rows_frame = tk.Frame(self._sets_canvas)
        self._sets_canvas_win = self._sets_canvas.create_window(
            (0, 0), window=self._set_rows_frame, anchor='nw')
        self._set_rows_frame.bind("<Configure>",
                                  lambda e: self._sets_canvas.configure(
                                      scrollregion=self._sets_canvas.bbox("all")))
        self._sets_canvas.bind("<Configure>",
                               lambda e: self._sets_canvas.itemconfig(
                                   self._sets_canvas_win, width=e.width))

        # Status label
        self.set_status = tk.Label(self.frame2, text="", anchor='w', fg='gray')
        self.set_status.pack(anchor='w', padx=14)

        # Bottom buttons
        btn_row = tk.Frame(self.frame2)
        btn_row.pack(fill=tk.X, padx=14, pady=(4, 12))
        tk.Button(btn_row, text="< Back", width=10, command=self._go_back).pack(side=tk.LEFT)
        tk.Button(btn_row, text="Save & Load", width=12, bg='lightgreen',
                  relief=tk.RAISED, command=self._save_and_load).pack(side=tk.RIGHT)

    def _update_screen2_header(self):
        self.screen2_info.config(
            text=f"Project: {os.path.basename(self._project_path)}   —   {self._project_path}")

    def _refresh_set_suggestion(self):
        if self._project_path:
            self.set_name_var.set(ProjectManager.suggest_set_name(self._project_path))

    def _add_set(self):
        name = self.set_name_var.get().strip()
        if not name:
            messagebox.showwarning("Missing input", "Please enter a set name.", parent=self.window)
            return
        try:
            set_path = ProjectManager.create_image_set(self._project_path, name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not create set:\n{e}", parent=self.window)
            return
        self._sets.append(set_path)
        self._refresh_set_rows()
        self._refresh_set_suggestion()
        self.set_status.config(text=f"Set '{name}' created.")

    def _refresh_set_rows(self):
        for widget in self._set_rows_frame.winfo_children():
            widget.destroy()
        for set_path in self._sets:
            name = os.path.basename(set_path)
            img_count = self._count_images(set_path)

            row = tk.Frame(self._set_rows_frame, relief=tk.GROOVE, bd=1)
            row.pack(fill=tk.X, padx=6, pady=3)

            tk.Label(row, text=name, width=16, anchor='w',
                     font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=8, pady=6)
            tk.Button(row, text="Import Images", width=14,
                      command=lambda p=set_path: self._import_images(p)).pack(side=tk.LEFT, padx=4, pady=4)
            tk.Button(row, text="Import Video", width=12,
                      command=lambda p=set_path: self._import_video(p)).pack(side=tk.LEFT, padx=4, pady=4)
            tk.Label(row, text=f"{img_count} image(s)", fg='gray',
                     anchor='w').pack(side=tk.LEFT, padx=8)

    def _count_images(self, set_path):
        images_dir = os.path.join(set_path, "images")
        if not os.path.isdir(images_dir):
            return 0
        return len([f for f in os.listdir(images_dir)
                    if f.lower().endswith(('.jpg', '.jpeg', '.png'))])

    def _import_images(self, set_path):
        source = filedialog.askdirectory(parent=self.window, title="Select folder with images")
        if not source:
            return
        self.set_status.config(text="Copying images...")
        self.window.update_idletasks()

        def do_copy():
            try:
                count = ProjectManager.copy_images(source, set_path)
                self.window.after(0, lambda: self._on_images_copied(count))
            except Exception as e:
                self.window.after(0, lambda err=e: messagebox.showerror(
                    "Error", str(err), parent=self.window))

        threading.Thread(target=do_copy, daemon=True).start()

    def _on_images_copied(self, count):
        self.set_status.config(text=f"{count} image(s) copied.")
        self._refresh_set_rows()

    def _import_video(self, set_path):
        VideoImporter(self.window,
                      on_import_done=lambda f: self._on_video_imported(f),
                      initial_output_folder=set_path)

    def _on_video_imported(self, folder):
        self.set_status.config(
            text=f"Video imported to '{os.path.basename(folder)}'.")
        self._refresh_set_rows()

    def _go_back(self):
        self._show_screen1()

    def _save_and_load(self):
        if not self._sets:
            messagebox.showwarning("No sets",
                                   "Please add at least one image set before saving.",
                                   parent=self.window)
            return
        first_set = self._sets[0]
        self.window.destroy()
        if self.on_project_created:
            self.on_project_created(first_set)

    # ------------------------------------------------------------------
    # Frame switching
    # ------------------------------------------------------------------

    def _show_screen1(self):
        self.frame2.pack_forget()
        self.frame1.pack(fill=tk.BOTH, expand=True)

    def _show_screen2(self):
        self.frame1.pack_forget()
        self.frame2.pack(fill=tk.BOTH, expand=True)
