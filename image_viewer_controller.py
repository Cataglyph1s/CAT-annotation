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
        self.loader = ImageLoader(folder)
        self.current_index = self.loader.load_last_image_index()

        # Initialize the action stack
        self.action_stack = []
        self.max_actions = 50
        self.autosave = True

        # Create view first — establishes bottom bar and content_frame
        self.view = ImageViewerView(root, self)

        # Canvas on root, packed after right_panel so it fills remaining space correctly
        self.editor = BoundingBoxEditor(root)
        self.editor.class_mapping = self.loader.class_mapping
        self.canvas = self.editor.canvas
        self.canvas.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)

        # Callback so editor can notify controller when a bbox is added
        self.editor.on_bbox_added = self._on_bbox_added

        # Apply project config (class colours) if a project.json is found
        self._apply_project_config(folder)

        # Bind keyboard shortcuts
        self.bind_shortcuts()

        self.view.populate_class_list(self.loader.class_mapping, self.editor.class_colors)
        cleaned = self.loader.clean_label_files()
        self.show_image()
        if cleaned:
            self.view.update_info_bar(f"Cleaned {cleaned} corrupted label file(s) on launch.")

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

        # Bind numeric keys for class selection when in edit mode
        for i in range(10):
            self.root.bind(f'<Key-{i}>', self.class_shortcut)

    def show_image(self):
        """Displays the current image and its bounding boxes."""
        if not self.loader.has_images():
            messagebox.showinfo("Info", "No images left.")
            self.root.quit()
            return

        image_path, label_path = self.loader.get_image_and_label(self.current_index)
        self.editor.load_image(image_path, label_path, fullscreen=self.fullscreen)
        self.loader.save_last_image_index(self.current_index)
        self.editor.annotations_visible = True
        self.view.update_annotations_button(True)
        self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names())
        self.view.update_path(image_path)

    def show_next_image(self):
        if self.autosave:
            self.save_bounding_boxes()
        self.current_index = (self.current_index + 1) % self.loader.num_images()
        self.show_image()

    def show_prev_image(self):
        if self.autosave:
            self.save_bounding_boxes()
        self.current_index = (self.current_index - 1) % self.loader.num_images()
        self.show_image()

    def toggle_edit_mode(self):
        """Toggles between edit and view modes."""
        self.editor.toggle_edit_mode()
        if not self.editor.edit_mode:
            self.editor.clear_resize_handles()
        self.view.update_edit_button(self.editor.edit_mode)
        self.view.update_info_bar("Edit Mode Activated" if self.editor.edit_mode else "Edit Mode Deactivated")

    def set_current_class(self, class_num):
        """Sets the active class and reassigns selected bbox if one is selected."""
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
        bbox.class_num = class_num
        label = f"{class_num}: {self.loader.class_mapping.get(class_num, str(class_num))}"
        color = self.editor.class_colors.get(class_num, '#555555')
        self.canvas.itemconfigure(bbox.text_id, text=label, fill=color)
        self.canvas.itemconfigure(bbox.rect_id, outline=color)
        self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names())
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
        class_num = int(event.char)
        if class_num in self.loader.class_mapping:
            self.view.select_class(class_num)
            self.set_current_class(class_num)

    def save_bounding_boxes(self):
        """Saves bounding boxes to the corresponding label file."""
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
        AppConfig.set_last_folder(folder)
        self.view.populate_class_list(self.loader.class_mapping, self.editor.class_colors)
        cleaned = self.loader.clean_label_files()
        self.show_image()
        if cleaned:
            self.view.update_info_bar(f"Cleaned {cleaned} corrupted label file(s).")
        return True

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
        self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names())

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
            self.canvas.delete(bbox.rect_id)
            self.canvas.delete(bbox.text_id)
            self.editor.bboxes.pop(index)
            self.editor.clear_resize_handles()
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names())
            self.view.update_info_bar("Deleted successfully.")

    def delete_current_image(self):
        """Deletes the current image and its corresponding label."""
        if not self.editor.edit_mode:
            self.view.update_info_bar("Enable Edit Mode to delete images.")
            return
        self.loader.delete_image(self.current_index)
        self.show_next_image()

    def delete_selected_bbox(self):
        """Deletes the selected bounding box and updates the file."""
        if not self.editor.edit_mode:
            self.view.update_info_bar("Enable Edit Mode to delete annotations.")
            return
        if self.editor.selected_bbox:
            self.add_action("delete", self.editor.selected_bbox)

            # Remove from canvas and list
            self.canvas.delete(self.editor.selected_bbox.rect_id)
            self.canvas.delete(self.editor.selected_bbox.text_id)
            self.editor.bboxes.remove(self.editor.selected_bbox)
            self.editor.selected_bbox = None
            self.editor.clear_resize_handles()
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names())
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
        if not self.action_stack:
            print("No actions to undo.")
            return

        action_type, bbox = self.action_stack.pop()
        if action_type == "delete":
            self.editor.draw_bounding_box(bbox, self.editor.x_offset, self.editor.y_offset, self.editor.scale_factor)
            self.editor.bboxes.append(bbox)
            self.view.update_annotation_list(self.editor.bboxes, self.loader.get_class_names())

        elif action_type == "add":
            self.canvas.delete(bbox.rect_id)
            self.editor.bboxes.remove(bbox)