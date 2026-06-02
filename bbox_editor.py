import os
import tkinter as tk
from PIL import Image, ImageTk
from bounding_box import BoundingBox

class BoundingBoxEditor:
    def __init__(self, root, canvas_parent=None):
        self.root = root

        # Create the canvas, it will resize dynamically
        parent = canvas_parent if canvas_parent else root
        self.canvas = tk.Canvas(parent)

        self.image = None
        self.tk_image = None
        self.bboxes = []
        self.selected_bbox = None
        self.current_bbox = None
        self.edit_mode = False
        self.current_class = 0
        self.on_bbox_added = None
        self.class_mapping = {}
        self.class_colors = {}
        self.original_width = 0  # Store original image width
        self.original_height = 0  # Store original image height
        self.annotations_visible = True
        self.x_offset = 0
        self.y_offset = 0
        self.scale_factor = 1
        self._loading = False
        self._resize_handles = []
        self._resize_bbox = None
        self._drag_corner = None
        self._resizing = False

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
        if self._loading:
            return
        self._loading = True
        self.image_path = image_path  # Store paths to reload after resize
        self.label_path = label_path

        self.canvas.delete("all")
        self.bboxes.clear()
        self.selected_bbox = None
        self._resize_handles = []
        self._resize_bbox = None
        self._drag_corner = None
        self._resizing = False

        # Open the image
        self.image = Image.open(image_path)

        # Store original dimensions
        self.original_width, self.original_height = self.image.size

        # update_idletasks processes layout/geometry only — avoids firing queued
        # keypresses or slideshow timers mid-load which would corrupt autosave.
        self.root.update_idletasks()

        # Get canvas size; fall back to image dimensions if canvas isn't laid out yet
        # (winfo_width returns 1 before the window is fully rendered).
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width, canvas_height = self.original_width, self.original_height

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
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.scale_factor = scale_factor
        self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.tk_image)

        # Load annotations (bounding boxes) after resizing the image
        if label_path and os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    class_num, x_center, y_center, width, height = map(float, parts)
                    bbox = BoundingBox.from_normalized(class_num, x_center, y_center, width, height, self.original_width, self.original_height)
                    self.bboxes.append(bbox)
                    self.draw_bounding_box(bbox, x_offset, y_offset, scale_factor)

        self._loading = False

    def draw_bounding_box(self, bbox, x_offset, y_offset, scale_factor):
        """Draw bounding boxes with proper scaling and offset."""
        # Scale the bounding box coordinates
        scaled_x1 = bbox.x1 * scale_factor + x_offset
        scaled_y1 = bbox.y1 * scale_factor + y_offset
        scaled_x2 = bbox.x2 * scale_factor + x_offset
        scaled_y2 = bbox.y2 * scale_factor + y_offset

        # Draw the rectangle
        class_id = int(bbox.class_num)
        class_name = self.class_mapping.get(class_id, str(class_id))
        label = f"{class_id}: {class_name}"
        color = self.class_colors.get(class_id, '#555555')
        rect = self.canvas.create_rectangle(scaled_x1, scaled_y1, scaled_x2, scaled_y2, outline=color, width=2, tags="annotation")
        text = self.canvas.create_text(scaled_x1, scaled_y1 - 4, anchor=tk.SW, text=label, fill=color, tags="annotation")
        bbox.rect_id = rect
        bbox.text_id = text

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode

    def start_bbox(self, event):
        if not self.edit_mode or self._resizing:
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
        if not self.edit_mode or self.current_bbox is None or self._resizing:
            return

        x1, y1, x2, y2 = self.current_bbox
        class_num = self.current_class
        if self.original_width > 0 and self.original_height > 0:
            # Convert canvas coords back to original image pixel coords
            orig_x1 = int((x1 - self.x_offset) / self.scale_factor)
            orig_y1 = int((y1 - self.y_offset) / self.scale_factor)
            orig_x2 = int((x2 - self.x_offset) / self.scale_factor)
            orig_y2 = int((y2 - self.y_offset) / self.scale_factor)
            bbox = BoundingBox(orig_x1, orig_y1, orig_x2, orig_y2, class_num)
            self.bboxes.append(bbox)
            self.draw_bounding_box(bbox, self.x_offset, self.y_offset, self.scale_factor)
            if self.on_bbox_added:
                self.on_bbox_added()
        self.current_bbox = None

    def select_bbox(self, event):
        orig_x = (event.x - self.x_offset) / self.scale_factor
        orig_y = (event.y - self.y_offset) / self.scale_factor
        for bbox in self.bboxes:
            if bbox.x1 <= orig_x <= bbox.x2 and bbox.y1 <= orig_y <= bbox.y2:
                if self.selected_bbox and self.selected_bbox != bbox:
                    prev_color = self.class_colors.get(int(self.selected_bbox.class_num), '#555555')
                    self.canvas.itemconfig(self.selected_bbox.rect_id, outline=prev_color)
                self.selected_bbox = bbox
                self.canvas.itemconfig(bbox.rect_id, outline="blue")
                break

    def show_resize_handles(self, bbox):
        """Draw corner handles on the selected bounding box."""
        self.clear_resize_handles()
        self._resize_bbox = bbox
        r = 6
        corners = [
            ('tl', bbox.x1, bbox.y1),
            ('tr', bbox.x2, bbox.y1),
            ('bl', bbox.x1, bbox.y2),
            ('br', bbox.x2, bbox.y2),
        ]
        for corner_id, ox, oy in corners:
            cx = ox * self.scale_factor + self.x_offset
            cy = oy * self.scale_factor + self.y_offset
            handle = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                fill='white', outline='blue', width=2, tags='resize_handle'
            )
            self.canvas.tag_bind(handle, '<Button-1>',
                                 lambda e, c=corner_id: self._start_resize(e, c))
            self.canvas.tag_bind(handle, '<B1-Motion>', self._do_resize)
            self.canvas.tag_bind(handle, '<ButtonRelease-1>', self._end_resize)
            self._resize_handles.append(handle)

    def clear_resize_handles(self):
        for h in self._resize_handles:
            self.canvas.delete(h)
        self._resize_handles = []
        self._resize_bbox = None
        self._drag_corner = None
        self._resizing = False

    def _start_resize(self, event, corner_id):
        self._drag_corner = corner_id
        self._resizing = True
        self.current_bbox = None  # cancel any in-progress draw

    def _do_resize(self, event):
        if not self._drag_corner or not self._resize_bbox:
            return
        bbox = self._resize_bbox
        orig_x = int((event.x - self.x_offset) / self.scale_factor)
        orig_y = int((event.y - self.y_offset) / self.scale_factor)
        if 'l' in self._drag_corner:
            bbox.x1 = orig_x
        if 'r' in self._drag_corner:
            bbox.x2 = orig_x
        if 't' in self._drag_corner:
            bbox.y1 = orig_y
        if 'b' in self._drag_corner:
            bbox.y2 = orig_y
        # Update the rectangle and label on canvas
        sx1 = bbox.x1 * self.scale_factor + self.x_offset
        sy1 = bbox.y1 * self.scale_factor + self.y_offset
        sx2 = bbox.x2 * self.scale_factor + self.x_offset
        sy2 = bbox.y2 * self.scale_factor + self.y_offset
        self.canvas.coords(bbox.rect_id, sx1, sy1, sx2, sy2)
        self.canvas.coords(bbox.text_id, sx1, sy1 - 4)
        # Move handles to new corner positions
        r = 6
        corners = [(bbox.x1, bbox.y1), (bbox.x2, bbox.y1),
                   (bbox.x1, bbox.y2), (bbox.x2, bbox.y2)]
        for handle, (ox, oy) in zip(self._resize_handles, corners):
            cx = ox * self.scale_factor + self.x_offset
            cy = oy * self.scale_factor + self.y_offset
            self.canvas.coords(handle, cx - r, cy - r, cx + r, cy + r)

    def _end_resize(self, event):
        self._drag_corner = None
        self._resizing = False

    def toggle_annotations(self):
        self.annotations_visible = not self.annotations_visible
        state = 'normal' if self.annotations_visible else 'hidden'
        self.canvas.itemconfigure("annotation", state=state)
        return self.annotations_visible

    def delete_selected_bbox(self):
        if self.selected_bbox:
            self.canvas.delete(self.selected_bbox.rect_id)  # Remove bounding box
