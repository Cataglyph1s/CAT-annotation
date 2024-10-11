import os
import tkinter as tk
from PIL import Image, ImageTk
from bounding_box import BoundingBox

class BoundingBoxEditor:
    def __init__(self, root):
        self.root = root

        # Create the canvas, it will resize dynamically
        self.canvas = tk.Canvas(root)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.image = None
        self.tk_image = None
        self.bboxes = []
        self.selected_bbox = None
        self.current_bbox = None
        self.edit_mode = False
        self.original_width = 0  # Store original image width
        self.original_height = 0  # Store original image height

        # Bindings for bbox
        self.canvas.bind("<Button-1>", self.start_bbox)
        self.canvas.bind("<B1-Motion>", self.draw_bbox)
        self.canvas.bind("<ButtonRelease-1>", self.save_bbox)
        self.canvas.bind("<Button-3>", self.select_bbox)  # Right-click to select a bbox

        # Bind to handle window resize events
        self.root.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        """Handle the window resizing, ensuring the image and bounding boxes scale to fit."""
        if self.image:
            self.load_image(self.image_path, self.label_path)

    def load_image(self, image_path, label_path=None, fullscreen=False):
        self.image_path = image_path  # Store paths to reload after resize
        self.label_path = label_path

        self.canvas.delete("all")
        self.bboxes.clear()
        self.selected_bbox = None

        # Open the image
        self.image = Image.open(image_path)

        # Store original dimensions
        self.original_width, self.original_height = self.image.size

        # Update the root to ensure the canvas size is accurate
        self.root.update()

        # Get canvas size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        # Calculate the scaling factor to maintain aspect ratio
        scale_factor = min(canvas_width / self.original_width, canvas_height / self.original_height)

        # Resize the image proportionally to fit the canvas
        new_width = int(self.original_width * scale_factor)
        new_height = int(self.original_height * scale_factor)

        # Resize the image and convert it to PhotoImage for tkinter
        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_image)

        # Center the image in the canvas
        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2
        self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.tk_image)

        # Load annotations (bounding boxes) after resizing the image
        if label_path and os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    class_num, x_center, y_center, width, height = map(float, parts)
                    bbox = BoundingBox.from_normalized(class_num, x_center, y_center, width, height, self.original_width, self.original_height)
                    self.bboxes.append(bbox)
                    self.draw_bounding_box(bbox, x_offset, y_offset, scale_factor)

    def draw_bounding_box(self, bbox, x_offset, y_offset, scale_factor):
        """Draw bounding boxes with proper scaling and offset."""
        # Scale the bounding box coordinates
        scaled_x1 = bbox.x1 * scale_factor + x_offset
        scaled_y1 = bbox.y1 * scale_factor + y_offset
        scaled_x2 = bbox.x2 * scale_factor + x_offset
        scaled_y2 = bbox.y2 * scale_factor + y_offset

        # Draw the rectangle
        rect = self.canvas.create_rectangle(scaled_x1, scaled_y1, scaled_x2, scaled_y2, outline="red", width=2)
        self.canvas.create_text(scaled_x1, scaled_y1 - 10, anchor=tk.NW, text=f"Class: {bbox.class_num}", fill="red")
        bbox.rect_id = rect  # Save the rectangle ID

    def toggle_edit_mode(self, class_dropdown):
        self.edit_mode = not self.edit_mode
        self.current_class = class_dropdown.current()

    def start_bbox(self, event):
        if not self.edit_mode:
            return
        self.current_bbox = [event.x, event.y, event.x, event.y]

    def draw_bbox(self, event):
        if not self.edit_mode or self.current_bbox is None:
            return

        self.current_bbox[2] = event.x
        self.current_bbox[3] = event.y
        self.canvas.delete("preview")
        self.canvas.create_rectangle(self.current_bbox[0],
                                     self.current_bbox[1],
                                     self.current_bbox[2],
                                     self.current_bbox[3],
                                     outline="blue", width=2, tag="preview")

    def save_bbox(self, event):
        if not self.edit_mode or self.current_bbox is None:
            return

        x1, y1, x2, y2 = self.current_bbox
        class_num = self.current_class
        # Normalize the coordinates before saving
        if self.original_width > 0 and self.original_height > 0:
            bbox = BoundingBox(x1 / self.original_width, y1 / self.original_height,
                               x2 / self.original_width, y2 / self.original_height, class_num)
            self.bboxes.append(bbox)
            self.draw_bounding_box(bbox)
        self.current_bbox = None

    def select_bbox(self, event):
        for bbox in self.bboxes:
            if bbox.x1 <= event.x <= bbox.x2 and bbox.y1 <= event.y <= bbox.y2:
                self.selected_bbox = bbox
                self.canvas.itemconfig(bbox.rect_id, outline="blue")  # Highlight selected bbox
                break

    def delete_selected_bbox(self):
        if self.selected_bbox:
            self.canvas.delete(self.selected_bbox.rect_id)  # Remove bounding box
