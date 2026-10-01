import os
import tkinter as tk
from PIL import Image, ImageTk
from bounding_box import BoundingBox
from viewport import compute_axis

MAX_ZOOM = 8.0

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
        self.occlude_mode = False
        self.on_occluder_added = None  # callback(x1, y1, x2, y2) in image pixel coords

        # Zoom / pan viewport state
        self.zoom = 1.0
        self.view_cx = 0.0
        self.view_cy = 0.0
        self._panning = False
        self._pan_start = None  # (canvas_x, canvas_y, view_cx, view_cy) at drag start
        self.on_viewport_changed = None

        # Bindings for bbox
        self.canvas.bind("<Button-1>", self.start_bbox)
        self.canvas.bind("<B1-Motion>", self.draw_bbox)
        self.canvas.bind("<ButtonRelease-1>", self.save_bbox)
        self.canvas.bind("<Button-3>", self.select_bbox)  # Right-click to select a bbox

        # Zoom / pan bindings
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_wheel)
        self.canvas.bind("<Button-2>", self._on_pan_start)
        self.canvas.bind("<B2-Motion>", self._on_pan_motion)
        self.canvas.bind("<ButtonRelease-2>", self._on_pan_end)

        # Bind to the CANVAS's own size changes, not the root window's —
        # the canvas resizes (and needs re-fitting) whenever a side panel is
        # toggled too, which never changes root's own outer dimensions.
        self.canvas.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        """Handle the canvas resizing (window resize or a side panel being
        toggled), keeping the current zoom/pan and in-memory annotations
        (re-cropping/re-scaling only) rather than reloading from disk."""
        if event.widget is self.canvas and self.image:
            self.current_bbox = None
            self._render_viewport()

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
        self.current_bbox = None
        self._panning = False
        self._pan_start = None

        # Open the image
        try:
            self.image = Image.open(image_path)
            self.original_width, self.original_height = self.image.size
        except Exception as e:
            # A corrupt/unreadable file shouldn't crash the whole app — show
            # an inline message and leave this frame blank instead.
            self.image = None
            self.original_width, self.original_height = 0, 0
            self.canvas.create_text(
                10, 10, anchor='nw', fill='red', tags='annotation',
                text=f"Could not open image:\n{os.path.basename(image_path)}\n{e}")
            self._loading = False
            return

        # Reset the viewport to fit-to-canvas, centered, on every new image
        self.zoom = 1.0
        self.view_cx = self.original_width / 2
        self.view_cy = self.original_height / 2

        # Load annotations (bounding boxes) — drawing happens in _render_viewport()
        if label_path and os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) != 5:
                        continue
                    class_num, x_center, y_center, width, height = map(float, parts)
                    bbox = BoundingBox.from_normalized(class_num, x_center, y_center, width, height, self.original_width, self.original_height)
                    self.bboxes.append(bbox)

        self._render_viewport()
        self._loading = False

    def _get_canvas_size(self):
        """Current canvas size, falling back to the image dimensions if the
        canvas isn't laid out yet (winfo_width returns 1 before the window
        is fully rendered). Used consistently by every method that needs to
        reason about canvas size, so zoom/pan math never disagrees with
        what _render_viewport actually used."""
        # update_idletasks processes layout/geometry only — avoids firing queued
        # keypresses or slideshow timers mid-load which would corrupt autosave.
        self.root.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return self.original_width, self.original_height
        return canvas_width, canvas_height

    def _render_viewport(self):
        """Crop the original image to the current zoom/pan viewport and
        redraw it plus all annotations. This is the single place that
        recomputes scale_factor/x_offset/y_offset — every other coordinate
        calculation in this class treats those as given."""
        if self.image is None:
            return

        canvas_width, canvas_height = self._get_canvas_size()
        fit_scale = min(canvas_width / self.original_width, canvas_height / self.original_height)
        scale_factor = fit_scale * self.zoom

        x_lo, x_hi, x_offset = compute_axis(self.original_width, canvas_width, scale_factor, self.view_cx)
        y_lo, y_hi, y_offset = compute_axis(self.original_height, canvas_height, scale_factor, self.view_cy)

        box = (int(round(x_lo)), int(round(y_lo)), max(int(round(x_hi)), int(round(x_lo)) + 1),
               max(int(round(y_hi)), int(round(y_lo)) + 1))
        cropped = self.image.crop(box)
        disp_w = max(1, int(round((box[2] - box[0]) * scale_factor)))
        disp_h = max(1, int(round((box[3] - box[1]) * scale_factor)))
        resized_image = cropped.resize((disp_w, disp_h), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_image)

        self.x_offset = x_offset
        self.y_offset = y_offset
        self.scale_factor = scale_factor

        # Where to place the CROPPED image's own (0,0) on canvas. This is
        # NOT x_offset/y_offset (those satisfy canvas = orig_px*scale+offset
        # for annotations, which are in ORIGINAL image-pixel coords) — the
        # cropped image's local (0,0) is at ORIGINAL pixel box[0]/box[1], so
        # it must be placed at box[0]*scale+x_offset instead. These only
        # coincide with x_offset/y_offset when nothing is actually cropped
        # (box[0]==0); once zoomed/panned, this is ~0 (the crop fills the
        # canvas) while x_offset/y_offset is some large negative pan offset.
        self._img_place_x = box[0] * scale_factor + x_offset
        self._img_place_y = box[1] * scale_factor + y_offset

        self.canvas.delete("all")
        self.canvas.create_image(self._img_place_x, self._img_place_y, anchor=tk.NW, image=self.tk_image)

        self._redraw_annotations()

        if self.on_viewport_changed:
            self.on_viewport_changed()

    def _redraw_annotations(self):
        for bbox in self.bboxes:
            self.draw_bounding_box(bbox, self.x_offset, self.y_offset, self.scale_factor)
        if self.selected_bbox is not None:
            self.canvas.itemconfig(self.selected_bbox.rect_id, outline="blue")
            if self.edit_mode:
                self.show_resize_handles(self.selected_bbox)

    # ------------------------------------------------------------------
    # Zoom / pan
    # ------------------------------------------------------------------

    def _set_zoom(self, new_zoom, view_cx=None, view_cy=None):
        self.zoom = max(1.0, min(MAX_ZOOM, new_zoom))
        if view_cx is not None:
            self.view_cx = view_cx
        if view_cy is not None:
            self.view_cy = view_cy
        self._render_viewport()

    def _on_ctrl_wheel(self, event):
        if self.image is None:
            return
        self.current_bbox = None  # cancel any in-progress draw, same as a resize would
        cursor_img_x = (event.x - self.x_offset) / self.scale_factor
        cursor_img_y = (event.y - self.y_offset) / self.scale_factor
        factor = 1.15 if event.delta > 0 else 1 / 1.15
        fit_scale = self.scale_factor / self.zoom if self.zoom else self.scale_factor
        new_zoom = max(1.0, min(MAX_ZOOM, self.zoom * factor))
        new_scale = fit_scale * new_zoom
        canvas_width, canvas_height = self._get_canvas_size()
        new_cx = cursor_img_x - (event.x - canvas_width / 2) / new_scale
        new_cy = cursor_img_y - (event.y - canvas_height / 2) / new_scale
        self._set_zoom(new_zoom, new_cx, new_cy)

    def zoom_in(self):
        if self.image is None:
            return
        self._set_zoom(self.zoom * 1.25)

    def zoom_out(self):
        if self.image is None:
            return
        self._set_zoom(self.zoom / 1.25)

    def reset_zoom(self):
        if self.image is None:
            return
        self._set_zoom(1.0, self.original_width / 2, self.original_height / 2)

    def _on_pan_start(self, event):
        if self.image is None:
            return
        self.current_bbox = None  # cancel any in-progress draw
        self._panning = True
        self._pan_start = (event.x, event.y, self.view_cx, self.view_cy)

    def _on_pan_motion(self, event):
        if not self._panning or self._pan_start is None:
            return
        sx, sy, start_cx, start_cy = self._pan_start
        dx = (event.x - sx) / self.scale_factor
        dy = (event.y - sy) / self.scale_factor
        self.view_cx = start_cx - dx
        self.view_cy = start_cy - dy
        self._render_viewport()

    def _on_pan_end(self, event):
        self._panning = False
        self._pan_start = None

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
        if not self.edit_mode:
            self.occlude_mode = False

    def toggle_occlude_mode(self):
        self.occlude_mode = not self.occlude_mode

    def draw_occluder(self, x1, y1, x2, y2):
        """Draw a filled white occluder rectangle on the canvas (image pixel coords)."""
        sx1 = x1 * self.scale_factor + self.x_offset
        sy1 = y1 * self.scale_factor + self.y_offset
        sx2 = x2 * self.scale_factor + self.x_offset
        sy2 = y2 * self.scale_factor + self.y_offset
        self.canvas.create_rectangle(sx1, sy1, sx2, sy2,
                                     fill='white', outline='#aaaaaa', width=1, tags='occluder')

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
        if self.occlude_mode:
            self.canvas.create_rectangle(
                self.current_bbox[0], self.current_bbox[1],
                self.current_bbox[2], self.current_bbox[3],
                fill='white', stipple='gray50', outline='orange', width=2, tag="preview")
        else:
            self.canvas.create_rectangle(
                self.current_bbox[0], self.current_bbox[1],
                self.current_bbox[2], self.current_bbox[3],
                outline="blue", width=2, tag="preview")

    def save_bbox(self, event):
        if not self.edit_mode or self.current_bbox is None or self._resizing:
            return
        x1, y1, x2, y2 = self.current_bbox
        if self.original_width > 0 and self.original_height > 0:
            orig_x1 = max(0, min(self.original_width,  int((x1 - self.x_offset) / self.scale_factor)))
            orig_y1 = max(0, min(self.original_height, int((y1 - self.y_offset) / self.scale_factor)))
            orig_x2 = max(0, min(self.original_width,  int((x2 - self.x_offset) / self.scale_factor)))
            orig_y2 = max(0, min(self.original_height, int((y2 - self.y_offset) / self.scale_factor)))
            if self.occlude_mode:
                if self.on_occluder_added:
                    self.on_occluder_added(orig_x1, orig_y1, orig_x2, orig_y2)
            else:
                bbox = BoundingBox(orig_x1, orig_y1, orig_x2, orig_y2, self.current_class)
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
        else:
            # Right-click on empty canvas — deselect
            if self.selected_bbox:
                prev_color = self.class_colors.get(int(self.selected_bbox.class_num), '#555555')
                self.canvas.itemconfig(self.selected_bbox.rect_id, outline=prev_color)
                self.selected_bbox = None
                self.clear_resize_handles()

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
        orig_x = max(0, min(self.original_width,  int((event.x - self.x_offset) / self.scale_factor)))
        orig_y = max(0, min(self.original_height, int((event.y - self.y_offset) / self.scale_factor)))
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
