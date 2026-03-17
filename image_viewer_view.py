import tkinter as tk
from tkinter import messagebox


class ImageViewerView:
    def __init__(self, root, controller):
        self.root = root
        self.controller = controller

        # Set the minimum window size
        self.root.minsize(800, 600)
        self.root.geometry("1200x800")

        # Top bar with menu button
        top_frame = tk.Frame(root, bg='lightgray', relief=tk.FLAT, bd=1)
        top_frame.pack(side=tk.TOP, fill=tk.X)
        self.menu_button = tk.Menubutton(top_frame, text="☰", relief=tk.FLAT,
                                         bg='lightgray', font=("Helvetica", 11),
                                         padx=8, pady=2)
        self.menu_button.pack(side=tk.LEFT)
        self.app_menu = tk.Menu(self.menu_button, tearoff=0)
        self.menu_button.config(menu=self.app_menu)
        self.app_menu.add_command(label="New Project...", command=self.controller.open_project_wizard)
        self.app_menu.add_separator()
        self.app_menu.add_command(label="Open Folder...", command=self.controller.open_folder)
        self.app_menu.add_command(label="Import Video...", command=self.controller.open_video_importer)

        # Info bar at the bottom
        info_frame = tk.Frame(root, relief=tk.SUNKEN, bd=1, bg='lightgray')
        info_frame.pack(side=tk.BOTTOM, fill=tk.X)
        self.info_bar = tk.Label(info_frame, text="Info: ", anchor='w', bg='lightgray', height=2)
        self.info_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.path_label = tk.Label(info_frame, text="", anchor='e', bg='lightgray', height=2)
        self.path_label.pack(side=tk.RIGHT, padx=10)

        # Bottom layout for buttons
        self.bottom_frame = tk.Frame(root)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        self.bottom_frame.columnconfigure(1, weight=1)

        # Auto-save pinned to the bottom left
        self.btn_autosave = tk.Button(self.bottom_frame, text="Auto-Save: ON",
                                      command=self.controller.toggle_autosave,
                                      width=14, height=2, bg="lightgreen", relief=tk.RAISED)
        self.btn_autosave.grid(row=0, column=0, sticky='w', padx=(0, 10))

        # Centre button bar
        self.button_frame = tk.Frame(self.bottom_frame)
        self.button_frame.grid(row=0, column=1)

        # Right panel directly on root, packed before canvas
        self.right_panel = tk.Frame(root, width=200, relief=tk.RIDGE, bd=2)
        self.right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self.right_panel.pack_propagate(False)

        paned = tk.PanedWindow(self.right_panel, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=6)
        paned.pack(fill=tk.BOTH, expand=True)

        # Top third: class legend
        class_frame = tk.LabelFrame(paned, text="Classes", font=("Helvetica", 9, "bold"))
        paned.add(class_frame, height=250)

        class_canvas = tk.Canvas(class_frame, bd=0, highlightthickness=0)
        class_scroll = tk.Scrollbar(class_frame, orient='vertical', command=class_canvas.yview)
        class_canvas.configure(yscrollcommand=class_scroll.set)
        class_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        class_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._class_list_frame = tk.Frame(class_canvas)
        self._class_canvas_win = class_canvas.create_window(
            (0, 0), window=self._class_list_frame, anchor='nw')
        self._class_list_frame.bind(
            "<Configure>",
            lambda e: class_canvas.configure(scrollregion=class_canvas.bbox("all")))
        class_canvas.bind(
            "<Configure>",
            lambda e: class_canvas.itemconfig(self._class_canvas_win, width=e.width))
        self._class_canvas = class_canvas
        self._class_rows = []      # list of {num, frame, label}
        self._selected_class = 0

        # Bottom two thirds: annotation list
        annotation_frame = tk.LabelFrame(paned, text="Annotations", font=("Helvetica", 9, "bold"))
        paned.add(annotation_frame)
        self.annotation_listbox = tk.Listbox(annotation_frame, font=("Helvetica", 9), selectmode=tk.SINGLE,
                                             bd=0, highlightthickness=0)
        self.annotation_listbox.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        self.annotation_listbox.bind('<Delete>', self._on_annotation_delete)
        self.annotation_listbox.bind('<<ListboxSelect>>', self._on_annotation_select)

        self.create_buttons()

        # Variable to track if annotations are being shown
        self.showing_annotations = False

    def create_buttons(self):
        btn_cfg = {"height": 2, "bg": "white", "relief": tk.RAISED}

        self.btn_edit = tk.Button(self.button_frame, text="Edit Mode",
                                  command=self.controller.toggle_edit_mode, width=10, **btn_cfg)
        self.btn_edit.grid(row=0, column=0, padx=5)
        self.controller.add_tooltip(self.btn_edit, "Shortcut: e")

        self.btn_prev = tk.Button(self.button_frame, text="<< Prev",
                                  command=self.controller.show_prev_image, width=10, **btn_cfg)
        self.btn_prev.grid(row=0, column=1, padx=5)
        self.controller.add_tooltip(self.btn_prev, "Shortcut: a")

        self.btn_next = tk.Button(self.button_frame, text="Next >>",
                                  command=self.controller.show_next_image, width=10, **btn_cfg)
        self.btn_next.grid(row=0, column=2, padx=5)
        self.controller.add_tooltip(self.btn_next, "Shortcut: d")

        self.btn_show_annotations = tk.Button(self.button_frame, text="Show Annotations",
                                              command=self.show_annotations, width=16, **btn_cfg)
        self.btn_show_annotations.grid(row=0, column=3, padx=5)
        self.controller.add_tooltip(self.btn_show_annotations, "Toggle annotation visibility")

        self.btn_save = tk.Button(self.button_frame, text="Save",
                                  command=self.controller.save_bounding_boxes, width=8, **btn_cfg)
        self.btn_save.grid(row=0, column=4, padx=(20, 5))
        self.controller.add_tooltip(self.btn_save, "Shortcut: ctrl + s")

        self.btn_delete_bbox = tk.Button(self.button_frame, text="Delete BBox",
                                         command=self.controller.delete_selected_bbox, width=12, **btn_cfg)
        self.btn_delete_bbox.grid(row=0, column=5, padx=5)
        self.controller.add_tooltip(self.btn_delete_bbox, "Shortcut: g")

        self.btn_delete = tk.Button(self.button_frame, text="Delete Image",
                                    command=self.controller.delete_current_image, width=12, **btn_cfg)
        self.btn_delete.grid(row=0, column=6, padx=5)
        self.controller.add_tooltip(self.btn_delete, "Shortcut: ctrl + b")

        self.btn_fullscreen = tk.Button(self.button_frame, text="Fullscreen",
                                        command=self.controller.toggle_fullscreen, width=10, **btn_cfg)
        self.btn_fullscreen.grid(row=0, column=7, padx=5)
        self.controller.add_tooltip(self.btn_fullscreen, "Shortcut: q")

        # Undo pinned to the bottom right
        self.btn_undo = tk.Button(self.bottom_frame, text="Undo",
                                  command=self.controller.undo_last_action, width=8, **btn_cfg)
        self.btn_undo.grid(row=0, column=2, sticky='e', padx=(10, 0))
        self.controller.add_tooltip(self.btn_undo, "Shortcut: ctrl + z")


    def _on_class_row_click(self, class_num):
        self.select_class(class_num)
        self.controller.set_current_class(class_num)

    def select_class(self, class_num):
        """Highlight the selected class row."""
        self._selected_class = class_num
        for row_info in self._class_rows:
            is_selected = row_info['num'] == class_num
            bg = '#cce8ff' if is_selected else 'white'
            row_info['frame'].config(bg=bg)
            row_info['label'].config(bg=bg)

    def _on_annotation_select(self, event):
        selection = self.annotation_listbox.curselection()
        if selection:
            self.controller.select_annotation_by_index(selection[0])

    def _on_annotation_delete(self, event):
        selection = self.annotation_listbox.curselection()
        if selection:
            self.controller.delete_annotation_by_index(selection[0])

    def populate_class_list(self, class_mapping, class_colors=None):
        """Populate the class legend with colour swatches, IDs and names."""
        if class_colors is None:
            class_colors = {}
        for widget in self._class_list_frame.winfo_children():
            widget.destroy()
        self._class_rows = []
        for num, name in class_mapping.items():
            color = class_colors.get(num, '#555555')
            row = tk.Frame(self._class_list_frame, bg='white', cursor='hand2')
            row.pack(fill=tk.X)
            swatch = tk.Label(row, bg=color, width=2, relief=tk.RAISED)
            swatch.pack(side=tk.LEFT, padx=(6, 5), pady=4, ipady=5)
            label = tk.Label(row, text=f"{num}: {name}", anchor='w',
                             font=("Helvetica", 9), bg='white')
            label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            for widget in (row, swatch, label):
                widget.bind('<Button-1>', lambda e, n=num: self._on_class_row_click(n))
            self._class_rows.append({'num': num, 'frame': row, 'label': label})
        if self._class_rows:
            self.select_class(0)

    def update_annotation_list(self, bboxes, class_names):
        """Update the annotation list for the current image."""
        self.annotation_listbox.delete(0, tk.END)
        for i, bbox in enumerate(bboxes):
            class_name = class_names[int(bbox.class_num)] if int(bbox.class_num) < len(class_names) else str(bbox.class_num)
            self.annotation_listbox.insert(tk.END, f"{i + 1}: {class_name}")

    def show_annotations(self):
        """Toggle bounding box visibility on the current image."""
        visible = self.controller.toggle_annotations()
        self.update_annotations_button(visible)

    def update_autosave_button(self, enabled):
        if enabled:
            self.btn_autosave.config(text="Auto-Save: ON", bg="lightgreen")
        else:
            self.btn_autosave.config(text="Auto-Save: OFF", bg="lightgray")

    def update_annotations_button(self, visible):
        if visible:
            self.btn_show_annotations.config(text="Hide Annotations", bg="lightgreen", relief=tk.RAISED)
        else:
            self.btn_show_annotations.config(text="Show Annotations", bg="tomato", relief=tk.SUNKEN)

    def update_edit_button(self, active):
        """Update the edit mode button appearance based on active state."""
        if active:
            self.btn_edit.config(text="Edit Mode ON", relief=tk.SUNKEN, bg="lightgreen")
        else:
            self.btn_edit.config(text="Edit Mode", relief=tk.RAISED, bg="white")

    def update_info_bar(self, text):
        self.info_bar.config(text=f"Info: {text}")

    def update_path(self, path):
        self.path_label.config(text=path)

    def toggle_fullscreen(self, fullscreen):
        self.root.attributes("-fullscreen", fullscreen)
