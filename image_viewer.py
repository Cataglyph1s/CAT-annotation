import os
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from image_loader import ImageLoader
from bbox_editor import BoundingBoxEditor

'''
class ImageViewer:
    def __init__(self, root, folder):
        self.root = root
        self.root.title("CATAnnotation")

        # Set the minimum window size
        self.root.minsize(1200, 900)
        self.root.geometry("1000x800")

        # Add key bindings
        self.root.bind('<d>', lambda e: self.show_next_image())
        self.root.bind('<a>', lambda e: self.show_prev_image())
        self.root.bind('<e>', lambda e: self.toggle_edit_mode())
        self.root.bind('<g>', lambda e: self.delete_selected_bbox())
        self.root.bind('<q>', lambda e: self.toggle_fullscreen())
        self.root.bind('<Control-s>', lambda e: self.save_bounding_boxes())
        self.root.bind('<Control-b>', lambda e: self.delete_current_image())

        # Bind numeric keys for class selection when in edit mode
        for i in range(10):
            self.root.bind(f'<Key-{i}>', self.class_shortcut)

        self.fullscreen = False
        self.folder = folder
        self.loader = ImageLoader(folder)
        self.current_index = self.loader.load_last_image_index()

        self.editor = BoundingBoxEditor(self.root)
        self.canvas = self.editor.canvas
        self.canvas.pack(padx=400, pady=80, side=tk.TOP, expand=True, fill=tk.BOTH)

        # Bottom layout for buttons
        self.bottom_frame = tk.Frame(root)
        self.bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        # Bottom grid for buttons (aligned to the left)
        self.button_frame = tk.Frame(self.bottom_frame)
        self.button_frame.pack(side=tk.LEFT, expand=True)

        # Info bar at the bottom for tooltips or messages
        self.info_bar = tk.Label(root, text="Info: ", anchor='w', relief=tk.SUNKEN, bg='lightgray', height=2)
        self.info_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Dropdown class selection inside sidebar
        self.class_var = tk.IntVar()
        self.class_dropdown = ttk.Combobox(self.bottom_frame, textvariable=self.class_var,
                                           state="readonly", values=self.loader.get_class_names())
        self.class_dropdown.current(0)
        self.class_dropdown.pack(padx=10, pady=10)

        self.btn_prev = tk.Button(self.button_frame, text="<< Prev", command=self.show_prev_image, height=2, width=10)
        self.btn_prev.grid(row=0, column=0, padx=10)
        self.add_tooltip(self.btn_prev, "Shortcut: a")

        self.btn_next = tk.Button(self.button_frame, text="Next >>", command=self.show_next_image, height=2, width=10)
        self.btn_next.grid(row=0, column=1, padx=10)
        self.add_tooltip(self.btn_next, "Shortcut: d")

        self.btn_edit = tk.Button(self.button_frame, text="Edit Mode",
                                  command=self.toggle_edit_mode, height=2, width=10)
        self.btn_edit.grid(row=0, column=2, padx=10)
        self.add_tooltip(self.btn_edit, "Shortcut: e")

        self.btn_delete_bbox = tk.Button(self.button_frame, text="Delete BBox",
                                         command=self.delete_selected_bbox, height=2, width=15)
        self.btn_delete_bbox.grid(row=0, column=3, padx=10)
        self.add_tooltip(self.btn_delete_bbox, "Shortcut: g")

        self.btn_save = tk.Button(self.button_frame, text="Save",
                                  command=self.save_bounding_boxes, height=2, width=10)
        self.btn_save.grid(row=0, column=4, padx=10)
        self.add_tooltip(self.btn_save, "Shortcut: ctrl + s")

        self.btn_fullscreen = tk.Button(self.button_frame, text="Fullscreen",
                                        command=self.toggle_fullscreen, height=2, width=15)
        self.btn_fullscreen.grid(row=0, column=5, padx=10)
        self.add_tooltip(self.btn_fullscreen, "Shortcut: q")

        self.btn_delete = tk.Button(self.button_frame, text="Delete Image",
                                    command=self.delete_current_image, height=2, width=15)
        self.btn_delete.grid(row=0, column=6, padx=10)
        self.add_tooltip(self.btn_delete, "Shortcut: ctrl + b")

        self.show_image()

    def add_tooltip(self, widget, text):
        """Shows tooltip in the info bar instead of creating a popup."""

        def on_enter(event):
            self.info_bar.config(text=f"Info: {text}")

        def on_leave(event):
            self.info_bar.config(text="Info: ")  # Clear the info bar

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        self.root.attributes("-fullscreen", self.fullscreen)
        self.show_image()

    def show_image(self):
        if not self.loader.has_images():
            messagebox.showinfo("Info", "No images left.")
            self.root.quit()
            return

        image_path, label_path = self.loader.get_image_and_label(self.current_index)
        self.editor.load_image(image_path, label_path, fullscreen=self.fullscreen)
        self.loader.save_last_image_index(self.current_index)

    def class_shortcut(self, event):
        """Handles class selection via number key shortcuts."""
        if self.editor.edit_mode:  # Only allow class change in edit mode
            class_num = int(event.char)  # Convert the key pressed to an integer (0-9)
            class_list = self.loader.get_class_names()

            if 0 <= class_num < len(class_list):
                self.class_var.set(class_num)
                self.class_dropdown.current(class_num)
                self.info_bar.config(text=f"Class {class_num} selected.")

    def show_next_image(self):
        self.current_index = (self.current_index + 1) % self.loader.num_images()
        self.show_image()

    def show_prev_image(self):
        self.current_index = (self.current_index - 1) % self.loader.num_images()
        self.show_image()

    def toggle_edit_mode(self):
        self.editor.toggle_edit_mode(self.class_dropdown)
        self.info_bar.config(text="Edit Mode Activated" if self.editor.edit_mode else "Edit Mode Deactivated")

    def save_bounding_boxes(self):
        """Save bounding boxes in YOLO format to the label file."""
        label_path = self.loader.get_label_path(self.current_index)

        img_width, img_height = self.editor.tk_image.width(), self.editor.tk_image.height()

        # Open file and save all bounding boxes in YOLO format
        with open(label_path, 'w') as f:
            for bbox in self.editor.bboxes:
                yolo_bbox = bbox.to_normalized(img_width, img_height)
                f.write(yolo_bbox + "\n")

    def delete_image(self, index):
        """Deletes both the image and the corresponding annotation file."""
        image_path, label_path = self.get_image_and_label(index)

        if os.path.exists(image_path):
            os.remove(image_path)  # Delete the image file

        if os.path.exists(label_path):
            os.remove(label_path)  # Delete the corresponding label file

        del self.image_files[index]

    def delete_current_image(self):
        """Deletes the current image and its corresponding label."""
        self.loader.delete_image(self.current_index)  # Deletes both the image and label
        self.show_next_image()  # Shows the next image in the list

    def delete_selected_bbox(self):
        """Delete the selected bounding box both from the canvas and the annotation file."""
        if self.editor.selected_bbox:
            # Remove from canvas
            self.canvas.delete(self.editor.selected_bbox.rect_id)

            # Remove from the list of bounding boxes
            self.editor.bboxes.remove(self.editor.selected_bbox)

            # Get the current label file path
            label_path = self.loader.get_label_path(self.current_index)

            # Remove the annotation line from the label file
            img_width, img_height = self.editor.tk_image.width(), self.editor.tk_image.height()

            # Convert the selected bbox to normalized YOLO format to identify its corresponding line
            bbox_to_remove = self.editor.selected_bbox.to_normalized(img_width, img_height)

            with open(label_path, 'r') as f:
                lines = f.readlines()

            # Rewrite the file without the removed bbox line
            with open(label_path, 'w') as f:
                for line in lines:
                    if line.strip() != bbox_to_remove:  # Skip the line matching the bbox
                        f.write(line)

            # Clear selected bbox after deletion
            self.editor.selected_bbox = None

        else:
            print("No bounding box selected to delete.")

'''