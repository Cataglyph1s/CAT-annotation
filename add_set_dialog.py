import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from project_manager import ProjectManager


def _parse_yaml_classes(folder):
    """Search for dataset.yaml in folder or its parent. Returns {id: name} or None."""
    for search_dir in [folder, os.path.dirname(folder)]:
        yaml_path = os.path.join(search_dir, 'dataset.yaml')
        if not os.path.exists(yaml_path):
            continue
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                content = f.read()
            names = {}
            in_names = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith('names:'):
                    rest = stripped[6:].strip()
                    if rest.startswith('['):
                        for i, item in enumerate(rest.strip('[]').split(',')):
                            names[i] = item.strip().strip('"\'')
                        break
                    in_names = True
                    continue
                if in_names:
                    if stripped and ':' in stripped and stripped[0].isdigit():
                        idx, name = stripped.split(':', 1)
                        names[int(idx.strip())] = name.strip()
                    elif stripped and not stripped[0].isdigit():
                        in_names = False
            return names or None
        except Exception:
            return None
    return None


class AddSetDialog:
    def __init__(self, root, project_path, project_classes, on_done=None):
        """
        project_classes: {id: name} from project.json
        on_done: callback(set_path, n_img, n_lbl)
        """
        self.root = root
        self.project_path = project_path
        self.project_classes = project_classes
        self.on_done = on_done

        self._source_folder = None
        self._source_classes = None
        self._class_map_vars = {}

        self.window = tk.Toplevel(root)
        self.window.title("Add Set to Project")
        self.window.geometry("540x280")
        self.window.resizable(False, False)
        self.window.grab_set()

        self._build_ui()

    def _build_ui(self):
        pad = {'padx': 14, 'pady': 6}

        tk.Label(self.window, text="Add Set to Project",
                 font=("Helvetica", 12, "bold")).pack(anchor='w', **pad)
        tk.Frame(self.window, height=1, bg='lightgray').pack(fill=tk.X, padx=14)

        # Set name
        name_row = tk.Frame(self.window)
        name_row.pack(fill=tk.X, padx=14, pady=(8, 4))
        tk.Label(name_row, text="Set name:", width=12, anchor='w').pack(side=tk.LEFT)
        self._set_name_var = tk.StringVar(
            value=ProjectManager.suggest_set_name(self.project_path))
        tk.Entry(name_row, textvariable=self._set_name_var, width=28).pack(side=tk.LEFT)

        # Mode radios
        tk.Frame(self.window, height=1, bg='lightgray').pack(fill=tk.X, padx=14, pady=(4, 0))
        tk.Label(self.window, text="Source", font=("Helvetica", 10, "bold")).pack(
            anchor='w', padx=14, pady=(6, 0))
        self._mode_var = tk.StringVar(value="empty")
        tk.Radiobutton(self.window, text="Create empty set",
                       variable=self._mode_var, value="empty",
                       command=self._on_mode_change).pack(anchor='w', padx=28, pady=2)
        tk.Radiobutton(self.window, text="Import from YOLO folder",
                       variable=self._mode_var, value="import",
                       command=self._on_mode_change).pack(anchor='w', padx=28, pady=2)

        # Source folder section — built but hidden until import mode is selected
        self._source_frame = tk.Frame(self.window)

        src_row = tk.Frame(self._source_frame)
        src_row.pack(fill=tk.X, padx=14, pady=(6, 2))
        tk.Label(src_row, text="Source folder:", width=13, anchor='w').pack(side=tk.LEFT)
        self._source_var = tk.StringVar()
        tk.Entry(src_row, textvariable=self._source_var, width=26,
                 state='readonly').pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(src_row, text="Browse", width=8,
                  command=self._browse_source).pack(side=tk.LEFT)

        # Class mapping LabelFrame (hidden until a source folder is picked)
        self._class_map_outer = tk.LabelFrame(
            self._source_frame, text="Class mapping", font=("Helvetica", 9))

        map_canvas = tk.Canvas(self._class_map_outer, bd=0, highlightthickness=0, height=130)
        map_scroll = tk.Scrollbar(self._class_map_outer, orient='vertical', command=map_canvas.yview)
        map_canvas.configure(yscrollcommand=map_scroll.set)
        map_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        map_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._map_inner = tk.Frame(map_canvas)
        map_win = map_canvas.create_window((0, 0), window=self._map_inner, anchor='nw')
        self._map_inner.bind('<Configure>',
                             lambda e: map_canvas.configure(
                                 scrollregion=map_canvas.bbox('all')))
        map_canvas.bind('<Configure>',
                        lambda e: map_canvas.itemconfig(map_win, width=e.width))

        # Status + buttons (always visible, anchored at bottom)
        self._status_var = tk.StringVar()
        self._status_label = tk.Label(self.window, textvariable=self._status_var,
                                      fg='gray', font=("Helvetica", 8), anchor='w')
        self._status_label.pack(fill=tk.X, padx=14, pady=(6, 0))

        tk.Frame(self.window, height=1, bg='lightgray').pack(fill=tk.X, padx=14, pady=(6, 0))
        btn_row = tk.Frame(self.window)
        btn_row.pack(fill=tk.X, padx=14, pady=10)
        tk.Button(btn_row, text="Cancel", width=10,
                  command=self.window.destroy).pack(side=tk.LEFT)
        self._confirm_btn = tk.Button(btn_row, text="Add Set", width=12,
                                      bg='lightgreen', relief=tk.RAISED,
                                      command=self._confirm)
        self._confirm_btn.pack(side=tk.RIGHT)

    def _on_mode_change(self):
        if self._mode_var.get() == "import":
            self._source_frame.pack(fill=tk.X, before=self._status_label)
            self.window.geometry("540x500")
            self.window.resizable(False, True)
        else:
            self._source_frame.pack_forget()
            self._class_map_outer.pack_forget()
            self.window.geometry("540x280")
            self.window.resizable(False, False)
            self._status_var.set("")

    def _browse_source(self):
        folder = filedialog.askdirectory(parent=self.window, title="Select source YOLO folder")
        if not folder:
            return
        self._source_folder = folder
        self._source_var.set(folder)
        self._load_source_classes(folder)

    def _load_source_classes(self, folder):
        for w in self._map_inner.winfo_children():
            w.destroy()
        self._class_map_vars.clear()

        source_classes = _parse_yaml_classes(folder)
        self._source_classes = source_classes

        if not source_classes:
            self._status_var.set("No dataset.yaml found — labels will be copied as-is.")
            self._class_map_outer.pack_forget()
            return

        proj_options = [f"{i}: {n}" for i, n in sorted(self.project_classes.items())]
        proj_by_name = {n.lower(): i for i, n in self.project_classes.items()}

        all_matched = True
        for src_id, src_name in sorted(source_classes.items()):
            var = tk.StringVar()
            auto_id = proj_by_name.get(src_name.lower())
            if auto_id is not None:
                var.set(f"{auto_id}: {self.project_classes[auto_id]}")
            else:
                var.set("— skip —")
                all_matched = False
            self._class_map_vars[src_id] = var

            row = tk.Frame(self._map_inner)
            row.pack(fill=tk.X, padx=6, pady=2)
            tk.Label(row, text=f"src {src_id}: {src_name}",
                     width=24, anchor='w', font=("Helvetica", 8)).pack(side=tk.LEFT)
            tk.Label(row, text="→", width=3).pack(side=tk.LEFT)
            ttk.Combobox(row, textvariable=var,
                         values=["— skip —"] + proj_options,
                         width=22, state='readonly').pack(side=tk.LEFT, padx=(4, 0))

        self._class_map_outer.pack(fill=tk.X, padx=14, pady=(4, 2))

        if all_matched:
            self._status_var.set("All classes matched by name automatically.")
        else:
            self._status_var.set("Some classes could not be auto-matched — please check the mapping.")

    def _build_class_map(self):
        result = {}
        for src_id, var in self._class_map_vars.items():
            val = var.get()
            if not val or val == "— skip —":
                continue
            result[src_id] = int(val.split(':')[0])
        return result

    def _confirm(self):
        set_name = self._set_name_var.get().strip()
        if not set_name:
            messagebox.showwarning("Missing input", "Please enter a set name.",
                                   parent=self.window)
            return

        if os.path.exists(os.path.join(self.project_path, set_name)):
            messagebox.showwarning("Name taken",
                                   f"A folder named '{set_name}' already exists in this project.",
                                   parent=self.window)
            return

        if self._mode_var.get() == "empty":
            try:
                set_path = ProjectManager.create_image_set(self.project_path, set_name)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.window)
                return
            self.window.destroy()
            if self.on_done:
                self.on_done(set_path, 0, 0)
            return

        # Import mode
        if not self._source_folder or not os.path.isdir(self._source_folder):
            messagebox.showwarning("No source", "Please select a valid source folder.",
                                   parent=self.window)
            return

        class_map = self._build_class_map() if self._source_classes else None

        self._confirm_btn.config(state='disabled')
        self._status_var.set("Copying files…")
        self.window.update_idletasks()

        def do_import():
            try:
                set_path, n_img, n_lbl = ProjectManager.import_set_from_yolo(
                    self.project_path, set_name, self._source_folder, class_map)
                self.window.after(0, lambda: self._finish(set_path, n_img, n_lbl))
            except Exception as e:
                self.window.after(0, lambda err=e: self._on_error(err))

        threading.Thread(target=do_import, daemon=True).start()

    def _finish(self, set_path, n_img, n_lbl):
        self.window.destroy()
        if self.on_done:
            self.on_done(set_path, n_img, n_lbl)

    def _on_error(self, err):
        self._confirm_btn.config(state='normal')
        self._status_var.set("")
        messagebox.showerror("Import error", str(err), parent=self.window)
