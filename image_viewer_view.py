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
        self.path_label = tk.Label(info_frame, text="", anchor='e', bg='lightgray', height=2)
        self.progress_label = tk.Label(info_frame, text="", anchor='e', bg='lightgray', height=2,
                                       font=("Helvetica", 9, "bold"), fg='#444444')
        # Pack RIGHT items first so info_bar's expand fills the left remainder
        self.path_label.pack(side=tk.RIGHT, padx=10)
        self.progress_label.pack(side=tk.RIGHT, padx=20)
        self.info_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

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

        ann_canvas = tk.Canvas(annotation_frame, bd=0, highlightthickness=0)
        ann_scroll = tk.Scrollbar(annotation_frame, orient='vertical', command=ann_canvas.yview)
        ann_canvas.configure(yscrollcommand=ann_scroll.set)
        ann_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        ann_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._ann_list_frame = tk.Frame(ann_canvas)
        self._ann_canvas_win = ann_canvas.create_window((0, 0), window=self._ann_list_frame, anchor='nw')
        self._ann_list_frame.bind(
            "<Configure>",
            lambda e: ann_canvas.configure(scrollregion=ann_canvas.bbox("all")))
        ann_canvas.bind(
            "<Configure>",
            lambda e: ann_canvas.itemconfig(self._ann_canvas_win, width=e.width))
        ann_canvas.bind('<Delete>', self._on_annotation_delete)
        self._ann_canvas = ann_canvas
        self._annotation_rows = []
        self._selected_annotation_idx = None

        # Occluders panel
        occluder_frame = tk.LabelFrame(paned, text="Occluders", font=("Helvetica", 9, "bold"))
        paned.add(occluder_frame, height=160)

        self.btn_burn_occluders = tk.Button(
            occluder_frame, text="Burn to images_masked/",
            command=self.controller.burn_occluders_to_masked,
            bg='#fff3cd', relief=tk.RAISED, font=("Helvetica", 8))
        self.btn_burn_occluders.pack(fill=tk.X, padx=4, pady=(4, 2))

        occ_canvas = tk.Canvas(occluder_frame, bd=0, highlightthickness=0)
        occ_scroll = tk.Scrollbar(occluder_frame, orient='vertical', command=occ_canvas.yview)
        occ_canvas.configure(yscrollcommand=occ_scroll.set)
        occ_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        occ_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._occ_list_frame = tk.Frame(occ_canvas)
        self._occ_canvas_win = occ_canvas.create_window((0, 0), window=self._occ_list_frame, anchor='nw')
        self._occ_list_frame.bind(
            "<Configure>",
            lambda e: occ_canvas.configure(scrollregion=occ_canvas.bbox("all")))
        occ_canvas.bind(
            "<Configure>",
            lambda e: occ_canvas.itemconfig(self._occ_canvas_win, width=e.width))
        self._occ_canvas = occ_canvas
        self._occluder_rows = []

        # Left sidebar wrapper — always visible so the toggle strip persists when panel is hidden
        self._left_wrapper = tk.Frame(root)
        self._left_wrapper.pack(side=tk.LEFT, fill=tk.Y)

        # Toggle strip on the right edge of the wrapper
        self._sets_panel_visible = True
        self.toggle_strip = tk.Frame(self._left_wrapper, width=12, bg='#cccccc', cursor='hand2')
        self.toggle_strip.pack(side=tk.RIGHT, fill=tk.Y)
        self.toggle_strip.pack_propagate(False)
        self._toggle_label = tk.Label(self.toggle_strip, text='◀', bg='#cccccc',
                                      font=("Helvetica", 8), cursor='hand2')
        self._toggle_label.pack(expand=True)
        self.toggle_strip.bind('<Button-1>', lambda e: self.controller.toggle_sets_panel())
        self._toggle_label.bind('<Button-1>', lambda e: self.controller.toggle_sets_panel())

        # Sets panel on the left side of the wrapper
        self.left_panel = tk.Frame(self._left_wrapper, width=180, relief=tk.RIDGE, bd=2)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y)
        self.left_panel.pack_propagate(False)

        sets_frame = tk.LabelFrame(self.left_panel, text="Sets", font=("Helvetica", 9, "bold"))
        sets_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        sets_canvas = tk.Canvas(sets_frame, bd=0, highlightthickness=0)
        sets_scroll = tk.Scrollbar(sets_frame, orient='vertical', command=sets_canvas.yview)
        sets_canvas.configure(yscrollcommand=sets_scroll.set)
        sets_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        sets_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._sets_list_frame = tk.Frame(sets_canvas)
        self._sets_canvas_win = sets_canvas.create_window((0, 0), window=self._sets_list_frame, anchor='nw')
        self._sets_list_frame.bind(
            "<Configure>",
            lambda e: sets_canvas.configure(scrollregion=sets_canvas.bbox("all")))
        sets_canvas.bind(
            "<Configure>",
            lambda e: sets_canvas.itemconfig(self._sets_canvas_win, width=e.width))
        self._sets_canvas = sets_canvas
        self._set_rows = []
        self._active_set_path = None

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

        self.btn_deselect = tk.Button(self.button_frame, text="Deselect",
                                      command=self.controller.deselect_bbox, width=10, **btn_cfg)
        self.btn_deselect.grid(row=0, column=6, padx=5)
        self.controller.add_tooltip(self.btn_deselect, "Shortcut: Escape  |  Clear bbox selection")

        self.btn_delete = tk.Button(self.button_frame, text="Delete Image",
                                    command=self.controller.delete_current_image, width=12, **btn_cfg)
        self.btn_delete.grid(row=0, column=7, padx=5)
        self.controller.add_tooltip(self.btn_delete, "Shortcut: ctrl + b")

        self.btn_fullscreen = tk.Button(self.button_frame, text="Fullscreen",
                                        command=self.controller.toggle_fullscreen, width=10, **btn_cfg)
        self.btn_fullscreen.grid(row=0, column=8, padx=5)
        self.controller.add_tooltip(self.btn_fullscreen, "Shortcut: q")

        # Undo pinned to the bottom right
        self.btn_undo = tk.Button(self.bottom_frame, text="Undo",
                                  command=self.controller.undo_last_action, width=8, **btn_cfg)
        self.btn_undo.grid(row=0, column=2, sticky='e', padx=(10, 0))
        self.controller.add_tooltip(self.btn_undo, "Shortcut: ctrl + z")

        # Row 1: review / inspection controls
        review_frame = tk.Frame(self.button_frame)
        review_frame.grid(row=1, column=0, columnspan=9, pady=(4, 0))

        self.btn_play = tk.Button(review_frame, text="▶ Play", width=8,
                                  command=self.controller.toggle_slideshow, **btn_cfg)
        self.btn_play.pack(side=tk.LEFT, padx=4)
        self.controller.add_tooltip(self.btn_play, "Shortcut: space")

        self.btn_speed = tk.Button(review_frame, text="1.0s", width=5,
                                   command=self.controller.cycle_slideshow_speed, **btn_cfg)
        self.btn_speed.pack(side=tk.LEFT, padx=(0, 12))
        self.controller.add_tooltip(self.btn_speed, "Click to cycle speed: 0.5s / 1s / 2s / 5s")

        self.btn_flag = tk.Button(review_frame, text="Flag (f)", width=10,
                                  command=self.controller.flag_current_image, **btn_cfg)
        self.btn_flag.pack(side=tk.LEFT, padx=4)
        self.controller.add_tooltip(self.btn_flag, "Shortcut: f  |  Mark image for second-pass review")

        self.flag_count_label = tk.Label(review_frame, text="0 flagged", fg='gray',
                                         font=("Helvetica", 8), bg='SystemButtonFace')
        self.flag_count_label.pack(side=tk.LEFT, padx=(0, 12))

        self.btn_prev_flagged = tk.Button(review_frame, text="<< F", width=5,
                                          command=self.controller.jump_to_prev_flagged, **btn_cfg)
        self.btn_prev_flagged.pack(side=tk.LEFT, padx=(4, 1))
        self.controller.add_tooltip(self.btn_prev_flagged, "Previous flagged image  |  Shortcut: ctrl + shift + f")

        self.btn_next_flagged = tk.Button(review_frame, text="F >>", width=5,
                                          command=self.controller.jump_to_next_flagged, **btn_cfg)
        self.btn_next_flagged.pack(side=tk.LEFT, padx=(1, 4))
        self.controller.add_tooltip(self.btn_next_flagged, "Next flagged image  |  Shortcut: ctrl + f")

        self.btn_jump = tk.Button(review_frame, text="Jump to N", width=10,
                                  command=self.controller.jump_to_image_by_number, **btn_cfg)
        self.btn_jump.pack(side=tk.LEFT, padx=4)
        self.controller.add_tooltip(self.btn_jump, "Shortcut: ctrl + g  |  Go to image by number")

        self.btn_cover_mode = tk.Button(review_frame, text="Cover Mode", width=11,
                                        command=self.controller.toggle_cover_mode, **btn_cfg)
        self.btn_cover_mode.pack(side=tk.LEFT, padx=(12, 4))
        self.controller.add_tooltip(self.btn_cover_mode,
                                    "Shortcut: v  |  Draw white covers over static background objects")


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

    def _on_annotation_select_idx(self, idx):
        self._selected_annotation_idx = idx
        self._ann_canvas.focus_set()
        self._highlight_annotation_row(idx)
        self.controller.select_annotation_by_index(idx)

    def _highlight_annotation_row(self, selected_idx):
        for i, row_info in enumerate(self._annotation_rows):
            if i == selected_idx:
                bg = '#cce8ff'
            elif row_info.get('pinned', False):
                bg = '#eef4ff'
            else:
                bg = 'white'
            row_info['frame'].config(bg=bg)
            row_info['label'].config(bg=bg)
            row_info['pin_btn'].config(bg=bg)

    def _on_annotation_delete(self, event):
        if self._selected_annotation_idx is not None:
            self.controller.delete_annotation_by_index(self._selected_annotation_idx)

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

    def update_annotation_list(self, bboxes, class_names, pinned_specs=None):
        """Rebuild annotation rows. pinned_specs is a set of (x1,y1,x2,y2,class_num) tuples."""
        pinned_specs = pinned_specs or set()
        for widget in self._ann_list_frame.winfo_children():
            widget.destroy()
        self._annotation_rows = []
        self._selected_annotation_idx = None

        for i, bbox in enumerate(bboxes):
            class_name = (class_names[int(bbox.class_num)]
                          if int(bbox.class_num) < len(class_names) else str(bbox.class_num))
            spec = (bbox.x1, bbox.y1, bbox.x2, bbox.y2, int(bbox.class_num))
            pinned = spec in pinned_specs
            bg = '#eef4ff' if pinned else 'white'

            row = tk.Frame(self._ann_list_frame, bg=bg, cursor='hand2')
            row.pack(fill=tk.X)

            pin_btn = tk.Button(
                row, text='●' if pinned else '○',
                fg='#2266cc' if pinned else 'gray',
                font=("Helvetica", 9), width=2,
                relief=tk.SUNKEN if pinned else tk.FLAT,
                bd=1, bg=bg,
                command=lambda idx=i: self.controller.toggle_bbox_persistent(idx)
            )
            pin_btn.pack(side=tk.LEFT, padx=(4, 2), pady=2)

            lbl = tk.Label(row, text=f"{i + 1}: {class_name}", anchor='w',
                           font=("Helvetica", 9), bg=bg)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2)

            row_info = {'frame': row, 'pin_btn': pin_btn, 'label': lbl, 'pinned': pinned}
            self._annotation_rows.append(row_info)

            for w in (row, lbl):
                w.bind('<Button-1>', lambda e, idx=i: self._on_annotation_select_idx(idx))

    def set_annotation_pinned(self, index, pinned):
        """Update the pin button appearance for a single annotation row."""
        if not (0 <= index < len(self._annotation_rows)):
            return
        row = self._annotation_rows[index]
        row['pinned'] = pinned
        is_selected = (index == self._selected_annotation_idx)
        bg = '#cce8ff' if is_selected else ('#eef4ff' if pinned else 'white')
        row['frame'].config(bg=bg)
        row['label'].config(bg=bg)
        row['pin_btn'].config(
            text='●' if pinned else '○',
            fg='#2266cc' if pinned else 'gray',
            relief=tk.SUNKEN if pinned else tk.FLAT,
            bg=bg
        )

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

    def update_progress(self, current, total, eta_str):
        pct = 100 * current / total if total else 0
        self.progress_label.config(text=f"img {current:,} / {total:,}  ·  {pct:.1f}%  ·  ≈{eta_str}")

    def update_slideshow_button(self, active, speed):
        if active:
            self.btn_play.config(text="⏸ Pause", bg="lightblue", relief=tk.SUNKEN)
        else:
            self.btn_play.config(text="▶ Play", bg="white", relief=tk.RAISED)
        self.btn_speed.config(text=f"{speed}s")

    def update_flag_button(self, flagged, flag_count):
        if flagged:
            self.btn_flag.config(text="Flagged!", bg="tomato", relief=tk.SUNKEN)
        else:
            self.btn_flag.config(text="Flag (f)", bg="white", relief=tk.RAISED)
        self.flag_count_label.config(text=f"{flag_count} flagged")

    def toggle_fullscreen(self, fullscreen):
        self.root.attributes("-fullscreen", fullscreen)

    def populate_sets_panel(self, sets_data, active_path):
        """Rebuild the sets sidebar rows from a list of {path, name, total, annotated} dicts."""
        for widget in self._sets_list_frame.winfo_children():
            widget.destroy()
        self._set_rows = []

        for data in sets_data:
            path = data['path']
            row = tk.Frame(self._sets_list_frame, bg='white', cursor='hand2')
            row.pack(fill=tk.X, padx=2, pady=1)

            name_label = tk.Label(row, text=data['name'], anchor='w', bg='white',
                                  font=("Helvetica", 9, "bold"))
            name_label.pack(fill=tk.X, padx=6, pady=(4, 0))

            stats_label = tk.Label(row,
                                   text=f"{data['total']} img  ·  {data['annotated']}/{data['total']} ann",
                                   anchor='w', bg='white', font=("Helvetica", 8), fg='gray')
            stats_label.pack(fill=tk.X, padx=6, pady=(0, 4))

            row_info = {'path': path, 'frame': row,
                        'name_label': name_label, 'stats_label': stats_label}
            self._set_rows.append(row_info)

            for widget in (row, name_label, stats_label):
                widget.bind('<Double-Button-1>', lambda e, p=path: self.controller.switch_to_set(p))
                widget.bind('<Button-1>', lambda e, ri=row_info: self._on_set_click(ri))

        self._highlight_active_set(active_path)

    def _on_set_click(self, row_info):
        self._highlight_active_set(row_info['path'])

    def _highlight_active_set(self, active_path):
        self._active_set_path = active_path
        for row_info in self._set_rows:
            is_active = row_info['path'] == active_path
            bg = '#cce8ff' if is_active else 'white'
            row_info['frame'].config(bg=bg)
            row_info['name_label'].config(bg=bg)
            row_info['stats_label'].config(bg=bg)

    def toggle_sets_panel(self):
        self._sets_panel_visible = not self._sets_panel_visible
        if self._sets_panel_visible:
            self.left_panel.pack(side=tk.LEFT, fill=tk.Y, before=self.toggle_strip)
            self._toggle_label.config(text='◀')
        else:
            self.left_panel.pack_forget()
            self._toggle_label.config(text='▶')

    # ------------------------------------------------------------------
    # Occluder panel
    # ------------------------------------------------------------------

    def update_cover_mode_button(self, active):
        if active:
            self.btn_cover_mode.config(text="Covering...", bg="lightyellow", relief=tk.SUNKEN)
        else:
            self.btn_cover_mode.config(text="Cover Mode", bg="white", relief=tk.RAISED)

    def update_occluder_list(self, occluder_rects, persistent_specs=None):
        """Rebuild occluder rows for the current image."""
        persistent_specs = persistent_specs or set()
        for widget in self._occ_list_frame.winfo_children():
            widget.destroy()
        self._occluder_rows = []

        for i, rect in enumerate(occluder_rects):
            x1, y1, x2, y2 = rect
            w, h = abs(x2 - x1), abs(y2 - y1)
            pinned = rect in persistent_specs
            bg = '#fffde7' if pinned else 'white'

            row = tk.Frame(self._occ_list_frame, bg=bg)
            row.pack(fill=tk.X)

            pin_btn = tk.Button(
                row, text='●' if pinned else '○',
                fg='#cc8800' if pinned else 'gray',
                font=("Helvetica", 9), width=2,
                relief=tk.SUNKEN if pinned else tk.FLAT,
                bd=1, bg=bg,
                command=lambda idx=i: self.controller.toggle_occluder_persistent(idx)
            )
            pin_btn.pack(side=tk.LEFT, padx=(4, 2), pady=2)

            lbl = tk.Label(row, text=f"{w}×{h}", anchor='w', font=("Helvetica", 9), bg=bg)
            lbl.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2)

            del_btn = tk.Button(
                row, text='x', fg='red', font=("Helvetica", 9), width=2,
                relief=tk.FLAT, bd=0, bg=bg,
                command=lambda idx=i: self.controller.delete_occluder(idx)
            )
            del_btn.pack(side=tk.RIGHT, padx=(2, 4), pady=2)

            self._occluder_rows.append(
                {'frame': row, 'pin_btn': pin_btn, 'label': lbl, 'del_btn': del_btn, 'pinned': pinned})

    def set_occluder_pinned(self, index, pinned):
        if not (0 <= index < len(self._occluder_rows)):
            return
        row = self._occluder_rows[index]
        row['pinned'] = pinned
        bg = '#fffde7' if pinned else 'white'
        for widget in (row['frame'], row['label'], row['pin_btn'], row['del_btn']):
            widget.config(bg=bg)
        row['pin_btn'].config(
            text='●' if pinned else '○',
            fg='#cc8800' if pinned else 'gray',
            relief=tk.SUNKEN if pinned else tk.FLAT,
        )
