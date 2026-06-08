import os
import time
import json

from PIL import Image, ImageDraw
from bounding_box import BoundingBox
from image_loader import ImageLoader
from bbox_editor import BoundingBoxEditor
from image_viewer_view import ImageViewerView
from video_importer import VideoImporter
from project_manager import ProjectManager
from project_wizard import ProjectWizard
from app_config import AppConfig

import tkinter as tk
from tkinter import messagebox, filedialog


class ImageViewerController:
    def __init__(self, root, folder):
        self.root = root
        self.folder = folder
        self.fullscreen = False
        self.loader = None
        self.current_index = 0

        # Initialize the action stack
        self.action_stack = []
        self.max_actions = 50
        self.autosave = True

        # Slideshow state
        self._slideshow_active = False
        self._slideshow_speeds = [0.5, 1.0, 2.0, 5.0]
        self._slideshow_speed_idx = 1  # default 1.0s
        self._slideshow_after_id = None

        # Review state
        self._flagged_images = set()
        self._nav_times = []  # timestamps of recent show_image() calls for ETA
        self._persistent_bboxes = set()  # (x1,y1,x2,y2,class_num) tuples pinned to carry across frames
        self._occluders = {}             # {filename: [(x1,y1,x2,y2), ...]} loaded from occluders.json
        self._persistent_occluders = set()  # (x1,y1,x2,y2) carried to each new frame

        # Create view first — establishes bottom bar and content_frame
        self.view = ImageViewerView(root, self)

        # Canvas on root, packed after right_panel so it fills remaining space correctly
        self.editor = BoundingBoxEditor(root)
        self.canvas = self.editor.canvas
        self.canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Callbacks from editor
        self.editor.on_bbox_added = self._on_bbox_added
        self.editor.on_occluder_added = self._on_occluder_added

        # Bind keyboard shortcuts
        self.bind_shortcuts()

        if folder:
            self.loader = ImageLoader(folder)
            self.current_index = self.loader.load_last_image_index()
            self.editor.class_mapping = self.loader.class_mapping
            self._apply_project_config(folder)
            self._flagged_images = self._load_flags()
            self._occluders = self._load_occluders()
            self.view.populate_class_list(self.loader.class_mapping, self.editor.class_colors)
            if self.loader.num_images() < 5000:
                cleaned = self.loader.clean_label_files()
                if cleaned:
                    self.view.update_info_bar(f"Cleaned {cleaned} corrupted label file(s) on launch.")
            self.show_image()
            self._populate_sets_sidebar()
        else:
            self.view.update_info_bar("No project loaded. Use the ☰ menu to create or open a project.")
            root.after(200, self.open_project_wizard)

    def bind_shortcuts(self):
        """Binds all keyboard shortcuts to their respective functions."""
        self.root.bind('<d>', lambda e: self.show_next_image())
        self.root.bind('<a>', lambda e: self.show_prev_image())
        self.root.bind('<e>', lambda e: self.toggle_edit_mode())
        self.root.bind('<g>', lambda e: self.delete_selected_bbox())
        self.root.bind('<q>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Control-s>', lambda e: self.save_bounding_boxes())
        self.root.bind('<Control-b>', lambda e: self.delete_current_image())
        self.root.bind('<Control-z>', lambda e: self.undo_last_action())
        self.root.bind('<space>', lambda e: self.toggle_slideshow())
        self.root.bind('<f>', lambda e: self.flag_current_image())
        self.root.bind('<Control-f>', lambda e: self.jump_to_next_flagged())
        self.root.bind('<Control-g>', lambda e: self.jump_to_image_by_number())
        self.root.bind('<v>', lambda e: self.toggle_cover_mode())

        # Bind numeric keys for class selection when in edit mode
        for i in range(10):
            self.root.bind(f'<Key-{i}>', self.class_shortcut)

    def show_image(self):
        """Displays the current image and its bounding boxes."""
        if self.loader is None:
            return
        if not self.loader.has_images():
            messagebox.showinfo("Info", "No images left.")
            self.root.quit()
            return

        image_path, label_path = self.loader.get_image_and_label(self.current_index)
        self.editor.load_image(image_path, label_path, fullscreen=self.fullscreen)
        self.loader.save_last_image_index(self.current_index)
        self.editor.annotations_visible = True
        self.view.update_annotations_button(True)
        self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)
        self.view.update_path(image_path)
        filename = self.loader.image_files[self.current_index]
        self.view.update_flag_button(filename in self._flagged_images, len(self._flagged_images))
        self._update_progress()
        self._draw_current_occluders()
        self._refresh_occluder_list()

    def show_next_image(self):
        if self.loader is None:
            return
        if self.autosave:
            self.save_bounding_boxes()
        self.current_index = (self.current_index + 1) % self.loader.num_images()
        self.show_image()
        self._inject_persistent_bboxes()
        self._inject_persistent_occluders()

    def show_prev_image(self):
        if self.loader is None:
            return
        if self.autosave:
            self.save_bounding_boxes()
        self.current_index = (self.current_index - 1) % self.loader.num_images()
        self.show_image()
        self._inject_persistent_bboxes()
        self._inject_persistent_occluders()

    def toggle_edit_mode(self):
        """Toggles between edit and view modes."""
        self.editor.toggle_edit_mode()
        if not self.editor.edit_mode:
            self.editor.clear_resize_handles()
        self.view.update_edit_button(self.editor.edit_mode)
        self.view.update_cover_mode_button(self.editor.occlude_mode)
        self.view.update_info_bar("Edit Mode Activated" if self.editor.edit_mode else "Edit Mode Deactivated")

    def set_current_class(self, class_num):
        """Sets the active class and reassigns selected bbox if one is selected."""
        if self.loader is None:
            return
        self.editor.current_class = class_num
        if self.editor.selected_bbox:
            if not self.editor.edit_mode:
                self.view.update_info_bar("Enable Edit Mode to change annotation class.")
                return
            self.change_selected_bbox_class(class_num)
        else:
            self.view.update_info_bar(f"Class set to {class_num}: {self.loader.class_mapping[class_num]}")

    def change_selected_bbox_class(self, class_num):
        """Changes the class of the currently selected bounding box."""
        bbox = self.editor.selected_bbox
        old_spec = (bbox.x1, bbox.y1, bbox.x2, bbox.y2, int(bbox.class_num))
        bbox.class_num = class_num
        new_spec = (bbox.x1, bbox.y1, bbox.x2, bbox.y2, int(bbox.class_num))
        if old_spec in self._persistent_bboxes:
            self._persistent_bboxes.discard(old_spec)
            self._persistent_bboxes.add(new_spec)
        label = f"{class_num}: {self.loader.class_mapping.get(class_num, str(class_num))}"
        color = self.editor.class_colors.get(class_num, '#555555')
        self.canvas.itemconfigure(bbox.text_id, text=label, fill=color)
        self.canvas.itemconfigure(bbox.rect_id, outline=color)
        self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)
        self.view.update_info_bar(f"Changed to {class_num}: {label}")

    def toggle_fullscreen(self):
        """Toggles the fullscreen mode."""
        self.fullscreen = not self.fullscreen
        self.view.toggle_fullscreen(self.fullscreen)
        self.show_image()

    def add_tooltip(self, widget, text):
        """Shows a tooltip in the info bar instead of creating a popup."""
        def on_enter(event):
            self.view.update_info_bar(text)

        def on_leave(event):
            self.view.update_info_bar("")

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def class_shortcut(self, event):
        """Handles class selection via number key shortcuts."""
        if self.loader is None:
            return
        class_num = int(event.char)
        if class_num in self.loader.class_mapping:
            self.view.select_class(class_num)
            self.set_current_class(class_num)

    def save_bounding_boxes(self):
        """Saves bounding boxes to the corresponding label file."""
        if self.loader is None:
            return
        label_path = self.loader.get_label_path(self.current_index)

        img_width, img_height = self.editor.original_width, self.editor.original_height

        with open(label_path, 'w') as f:
            for bbox in self.editor.bboxes:
                yolo_bbox = bbox.to_normalized(img_width, img_height)
                f.write(yolo_bbox + "\n")
        self.view.update_info_bar("Saved successfully.")

    def _apply_project_config(self, folder):
        """Loads project.json for the given folder and applies class names and colours."""
        config = ProjectManager.load_project_config(folder)
        if config:
            class_list = config.get('classes', [])
            self.loader.class_mapping = {c['id']: c['name'] for c in class_list}
            self.editor.class_colors = {c['id']: c['color'] for c in class_list}
        else:
            self.editor.class_colors = {}

    def _load_folder(self, folder):
        """Reinitialises loader and editor state for a new folder. Returns True on success."""
        try:
            new_loader = ImageLoader(folder)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load folder:\n{e}")
            return False
        self.folder = folder
        self.loader = new_loader
        self._apply_project_config(folder)
        self.editor.class_mapping = self.loader.class_mapping
        self.current_index = self.loader.load_last_image_index()
        self.action_stack.clear()
        self._flagged_images = self._load_flags()
        self._nav_times.clear()
        self._persistent_bboxes.clear()
        self._occluders = self._load_occluders()
        self._persistent_occluders.clear()
        AppConfig.set_last_folder(folder)
        self.view.populate_class_list(self.loader.class_mapping, self.editor.class_colors)
        if self.loader.num_images() < 5000:
            cleaned = self.loader.clean_label_files()
            if cleaned:
                self.view.update_info_bar(f"Cleaned {cleaned} corrupted label file(s).")
        self.show_image()
        self._populate_sets_sidebar()
        return True

    # ------------------------------------------------------------------
    # Slideshow
    # ------------------------------------------------------------------

    def toggle_slideshow(self):
        if self._slideshow_active:
            self._stop_slideshow()
        else:
            self._start_slideshow()

    def _start_slideshow(self):
        if self.loader is None:
            return
        self._slideshow_active = True
        speed = self._slideshow_speeds[self._slideshow_speed_idx]
        self.view.update_slideshow_button(True, speed)
        self._schedule_next_slide()

    def _stop_slideshow(self):
        self._slideshow_active = False
        if self._slideshow_after_id:
            self.root.after_cancel(self._slideshow_after_id)
            self._slideshow_after_id = None
        speed = self._slideshow_speeds[self._slideshow_speed_idx]
        self.view.update_slideshow_button(False, speed)

    def _schedule_next_slide(self):
        speed_ms = int(self._slideshow_speeds[self._slideshow_speed_idx] * 1000)
        self._slideshow_after_id = self.root.after(speed_ms, self._advance_slideshow)

    def _advance_slideshow(self):
        if not self._slideshow_active:
            return
        if self.loader is None or not self.loader.has_images():
            self._stop_slideshow()
            return
        self.show_next_image()
        self._schedule_next_slide()

    def cycle_slideshow_speed(self):
        self._slideshow_speed_idx = (self._slideshow_speed_idx + 1) % len(self._slideshow_speeds)
        speed = self._slideshow_speeds[self._slideshow_speed_idx]
        self.view.update_slideshow_button(self._slideshow_active, speed)
        if self._slideshow_active:
            if self._slideshow_after_id:
                self.root.after_cancel(self._slideshow_after_id)
            self._schedule_next_slide()

    # ------------------------------------------------------------------
    # Flag system
    # ------------------------------------------------------------------

    def _flags_path(self):
        return os.path.join(self.folder, "flagged.txt") if self.folder else None

    def _load_flags(self):
        path = self._flags_path()
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_flags(self):
        path = self._flags_path()
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(sorted(self._flagged_images)))

    def flag_current_image(self):
        if self.loader is None:
            return
        filename = self.loader.image_files[self.current_index]
        if filename in self._flagged_images:
            self._flagged_images.discard(filename)
            self._save_flags()
            self.view.update_flag_button(False, len(self._flagged_images))
            self.view.update_info_bar(f"Unflagged: {filename}")
        else:
            self._flagged_images.add(filename)
            self._save_flags()
            self.view.update_flag_button(True, len(self._flagged_images))
            self.view.update_info_bar(f"Flagged: {filename}  [{len(self._flagged_images)} total]")

    def jump_to_next_flagged(self):
        if self.loader is None or not self._flagged_images:
            self.view.update_info_bar("No flagged images.")
            return
        n = self.loader.num_images()
        for offset in range(1, n + 1):
            idx = (self.current_index + offset) % n
            if self.loader.image_files[idx] in self._flagged_images:
                self.current_index = idx
                self.show_image()
                return

    # ------------------------------------------------------------------
    # Progress + ETA
    # ------------------------------------------------------------------

    def _update_progress(self):
        if self.loader is None:
            return
        current = self.current_index + 1
        total = self.loader.num_images()
        now = time.monotonic()
        self._nav_times.append(now)
        if len(self._nav_times) > 30:
            self._nav_times.pop(0)
        eta_str = self._calc_eta(total - current)
        self.view.update_progress(current, total, eta_str)

    def _calc_eta(self, remaining):
        if len(self._nav_times) < 3 or remaining <= 0:
            return "?"
        elapsed = self._nav_times[-1] - self._nav_times[0]
        count = len(self._nav_times) - 1
        if elapsed <= 0:
            return "?"
        avg = elapsed / count
        secs = avg * remaining
        if secs < 60:
            return f"{int(secs)}s"
        if secs < 3600:
            return f"{int(secs // 60)}m"
        if secs < 86400:
            return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"
        return f"{int(secs // 86400)}d {int((secs % 86400) // 3600)}h"

    # ------------------------------------------------------------------
    # Jump to image N
    # ------------------------------------------------------------------

    def jump_to_image_by_number(self):
        if self.loader is None:
            return
        from tkinter import simpledialog
        n = self.loader.num_images()
        num = simpledialog.askinteger(
            "Jump to image",
            f"Enter image number (1 – {n:,}):",
            minvalue=1, maxvalue=n,
            parent=self.root,
        )
        if num is not None:
            self.current_index = num - 1
            self.show_image()

    # ------------------------------------------------------------------
    # Persistent annotations (pin-to-carry-forward)
    # ------------------------------------------------------------------

    def toggle_bbox_persistent(self, index):
        """Pin or unpin a bbox so it is copied to every subsequent frame."""
        if not (0 <= index < len(self.editor.bboxes)):
            return
        bbox = self.editor.bboxes[index]
        spec = (bbox.x1, bbox.y1, bbox.x2, bbox.y2, int(bbox.class_num))
        if spec in self._persistent_bboxes:
            self._persistent_bboxes.discard(spec)
            self.view.set_annotation_pinned(index, False)
            self.view.update_info_bar("Annotation unpinned.")
        else:
            self._persistent_bboxes.add(spec)
            self.view.set_annotation_pinned(index, True)
            self.view.update_info_bar("Annotation pinned — will be copied to each new frame.")

    def _inject_persistent_bboxes(self):
        """Add any pinned bbox templates into the current frame if not already present."""
        if not self._persistent_bboxes or self.loader is None:
            return
        existing = {
            (b.x1, b.y1, b.x2, b.y2, int(b.class_num))
            for b in self.editor.bboxes
        }
        added = False
        for spec in self._persistent_bboxes:
            if spec not in existing:
                bbox = BoundingBox(spec[0], spec[1], spec[2], spec[3], spec[4])
                self.editor.bboxes.append(bbox)
                self.editor.draw_bounding_box(
                    bbox, self.editor.x_offset, self.editor.y_offset, self.editor.scale_factor)
                existing.add(spec)
                added = True
        if added:
            self.view.update_annotation_list(
                self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)
            if self.autosave:
                self.save_bounding_boxes()

    # ------------------------------------------------------------------
    # Occluder system
    # ------------------------------------------------------------------

    def _occluders_path(self):
        return os.path.join(self.folder, "occluders.json") if self.folder else None

    def _load_occluders(self):
        path = self._occluders_path()
        if path and os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return {k: [tuple(r) for r in v] for k, v in data.items()}
        return {}

    def _save_occluders(self):
        path = self._occluders_path()
        if path:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({k: [list(r) for r in v] for k, v in self._occluders.items()}, f, indent=2)

    def _draw_current_occluders(self):
        if self.loader is None:
            return
        filename = self.loader.image_files[self.current_index]
        for rect in self._occluders.get(filename, []):
            self.editor.draw_occluder(*rect)

    def _refresh_occluder_list(self):
        if self.loader is None:
            return
        filename = self.loader.image_files[self.current_index]
        rects = self._occluders.get(filename, [])
        self.view.update_occluder_list(rects, self._persistent_occluders)

    def _on_occluder_added(self, x1, y1, x2, y2):
        if self.loader is None:
            return
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        if x2 - x1 < 5 or y2 - y1 < 5:
            return
        filename = self.loader.image_files[self.current_index]
        rect = (x1, y1, x2, y2)
        self._occluders.setdefault(filename, []).append(rect)
        self.editor.draw_occluder(*rect)
        self._save_occluders()
        self._refresh_occluder_list()

    def _inject_persistent_occluders(self):
        if not self._persistent_occluders or self.loader is None:
            return
        filename = self.loader.image_files[self.current_index]
        existing = set(self._occluders.get(filename, []))
        added = False
        for spec in self._persistent_occluders:
            if spec not in existing:
                self._occluders.setdefault(filename, []).append(spec)
                self.editor.draw_occluder(*spec)
                existing.add(spec)
                added = True
        if added:
            self._save_occluders()
            self._refresh_occluder_list()

    def toggle_cover_mode(self):
        if self.loader is None:
            return
        self.editor.toggle_occlude_mode()
        if self.editor.occlude_mode and not self.editor.edit_mode:
            self.editor.toggle_edit_mode()
            self.view.update_edit_button(True)
        self.view.update_cover_mode_button(self.editor.occlude_mode)
        if self.editor.occlude_mode:
            self.view.update_info_bar("Cover Mode ON — draw white boxes over static background objects.")
        else:
            self.view.update_info_bar("Cover Mode OFF.")

    def toggle_occluder_persistent(self, index):
        if self.loader is None:
            return
        filename = self.loader.image_files[self.current_index]
        rects = self._occluders.get(filename, [])
        if not (0 <= index < len(rects)):
            return
        spec = rects[index]
        if spec in self._persistent_occluders:
            self._persistent_occluders.discard(spec)
            self.view.set_occluder_pinned(index, False)
            self.view.update_info_bar("Occluder unpinned.")
        else:
            self._persistent_occluders.add(spec)
            self.view.set_occluder_pinned(index, True)
            self.view.update_info_bar("Occluder pinned — covers this area in all subsequent frames.")

    def delete_occluder(self, index):
        if self.loader is None:
            return
        filename = self.loader.image_files[self.current_index]
        rects = self._occluders.get(filename, [])
        if not (0 <= index < len(rects)):
            return
        spec = rects[index]
        self._persistent_occluders.discard(spec)
        self._occluders[filename].pop(index)
        if not self._occluders[filename]:
            del self._occluders[filename]
        self._save_occluders()
        self.canvas.delete('occluder')
        self._draw_current_occluders()
        self._refresh_occluder_list()

    def burn_occluders_to_masked(self):
        if self.loader is None or not self._occluders:
            self.view.update_info_bar("No occluders to burn.")
            return
        count_images = len(self._occluders)
        masked_dir = os.path.join(self.loader.folder, "images_masked")
        if not messagebox.askyesno(
                "Burn occluders",
                f"Write {count_images} modified image(s) to:\n{masked_dir}\n\n"
                "Original files are not changed."):
            return
        os.makedirs(masked_dir, exist_ok=True)
        burned = 0
        for filename, rects in self._occluders.items():
            src = os.path.join(self.loader.images_folder, filename)
            if not os.path.exists(src):
                continue
            img = Image.open(src).convert('RGB')
            draw = ImageDraw.Draw(img)
            for x1, y1, x2, y2 in rects:
                draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255))
            img.save(os.path.join(masked_dir, filename))
            burned += 1
        self.view.update_info_bar(f"Burned {burned} image(s) to {masked_dir}")

    # ------------------------------------------------------------------
    # Sets sidebar
    # ------------------------------------------------------------------

    def _get_project_root(self, folder):
        """Walk up from folder to find the directory containing project.json."""
        for path in [folder, os.path.dirname(folder)]:
            if os.path.exists(os.path.join(path, 'project.json')):
                return path
        return None

    def _populate_sets_sidebar(self):
        """Scan the project root for sets and refresh the sidebar."""
        if self.loader is None or not self.folder:
            return
        project_root = self._get_project_root(self.folder)
        if not project_root:
            return
        set_paths = ProjectManager.list_sets(project_root)
        sets_data = []
        for path in set_paths:
            total, annotated = ProjectManager.get_set_stats(path)
            sets_data.append({'path': path, 'name': os.path.basename(path),
                              'total': total, 'annotated': annotated})
        active = os.path.normpath(self.folder)
        normalized = [{**d, 'path': os.path.normpath(d['path'])} for d in sets_data]
        self.view.populate_sets_panel(normalized, active)

    def switch_to_set(self, set_path):
        """Load a different set from the sidebar."""
        if os.path.normpath(set_path) == os.path.normpath(self.folder):
            return
        if self.autosave:
            self.save_bounding_boxes()
        self._load_folder(set_path)

    def toggle_sets_panel(self):
        self.view.toggle_sets_panel()

    def open_project_wizard(self):
        """Opens the New Project wizard."""
        ProjectWizard(self.root, on_project_created=self._on_project_created)

    def _on_project_created(self, first_set_path):
        """Called by ProjectWizard after a project is saved; loads the first image set."""
        self._load_folder(first_set_path)
        self.view.update_info_bar("Project created and loaded.")

    def open_video_importer(self):
        """Opens the video importer window. Auto-switches to the output folder on completion."""
        VideoImporter(self.root, on_import_done=self._on_import_done)

    def _on_import_done(self, folder):
        """Called by VideoImporter after a successful import."""
        if self._load_folder(folder):
            self.view.update_info_bar("Import complete. Folder loaded.")

    def open_folder(self):
        """Opens a folder picker and reloads the application with the selected dataset folder."""
        folder = filedialog.askdirectory(title="Select Dataset Folder")
        if not folder:
            return
        self._load_folder(folder)

    def toggle_autosave(self):
        self.autosave = not self.autosave
        self.view.update_autosave_button(self.autosave)
        self.view.update_info_bar("Auto-Save enabled." if self.autosave else "Auto-Save disabled.")

    def _on_bbox_added(self):
        if self.loader is None:
            return
        self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)

    def toggle_annotations(self):
        return self.editor.toggle_annotations()

    def select_annotation_by_index(self, index):
        if 0 <= index < len(self.editor.bboxes):
            self.editor.selected_bbox = self.editor.bboxes[index]
            if self.editor.edit_mode:
                self.editor.show_resize_handles(self.editor.selected_bbox)
            else:
                self.editor.clear_resize_handles()

    def delete_annotation_by_index(self, index):
        """Deletes a bounding box by its index in the list."""
        if not self.editor.edit_mode:
            self.view.update_info_bar("Enable Edit Mode to delete annotations.")
            return
        if 0 <= index < len(self.editor.bboxes):
            bbox = self.editor.bboxes[index]
            self._persistent_bboxes.discard((bbox.x1, bbox.y1, bbox.x2, bbox.y2, int(bbox.class_num)))
            self.canvas.delete(bbox.rect_id)
            self.canvas.delete(bbox.text_id)
            self.editor.bboxes.pop(index)
            self.editor.clear_resize_handles()
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)
            self.view.update_info_bar("Deleted successfully.")

    def delete_current_image(self):
        """Deletes the current image and its corresponding label."""
        if self.loader is None:
            return
        if not self.editor.edit_mode:
            self.view.update_info_bar("Enable Edit Mode to delete images.")
            return
        self.loader.delete_image(self.current_index)
        # Clear bboxes before showing the next image so autosave cannot write
        # the deleted image's annotations onto the file that now occupies this index.
        self.editor.bboxes.clear()
        self.current_index = min(self.current_index, self.loader.num_images() - 1)
        self.show_image()

    def delete_selected_bbox(self):
        """Deletes the selected bounding box and updates the file."""
        if not self.editor.edit_mode:
            self.view.update_info_bar("Enable Edit Mode to delete annotations.")
            return
        if self.editor.selected_bbox:
            bbox = self.editor.selected_bbox
            self._persistent_bboxes.discard((bbox.x1, bbox.y1, bbox.x2, bbox.y2, int(bbox.class_num)))
            self.add_action("delete", bbox)

            # Remove from canvas and list
            self.canvas.delete(bbox.rect_id)
            self.canvas.delete(bbox.text_id)
            self.editor.bboxes.remove(bbox)
            self.editor.selected_bbox = None
            self.editor.clear_resize_handles()
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)
            self.view.update_info_bar("Deleted successfully.")
        else:
            self.view.update_info_bar("No bounding box selected.")

    def add_action(self, action_type, bbox):
        """Adds an action to the stack for undo functionality."""
        if len(self.action_stack) >= self.max_actions:
            self.action_stack.pop(0)
        self.action_stack.append((action_type, bbox.copy()))

    def undo_last_action(self):
        """Undoes the last action by reversing it."""
        if self.loader is None:
            return
        if not self.action_stack:
            print("No actions to undo.")
            return

        action_type, bbox = self.action_stack.pop()
        if action_type == "delete":
            self.editor.draw_bounding_box(bbox, self.editor.x_offset, self.editor.y_offset, self.editor.scale_factor)
            self.editor.bboxes.append(bbox)
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)

        elif action_type == "add":
            self.canvas.delete(bbox.rect_id)
            self.editor.bboxes.remove(bbox)
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names(), self._persistent_bboxes)