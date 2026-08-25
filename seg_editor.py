import os
import tkinter as tk
from PIL import Image, ImageTk
from segmentation_annotation import SegmentationAnnotation


class SegEditor:
    def __init__(self, root, canvas_parent=None):
        self.root = root
        parent = canvas_parent if canvas_parent else root
        self.canvas = tk.Canvas(parent)

        self.image = None
        self.image_path = None
        self.label_path = None
        self.tk_image = None
        self.segs = []
        self.selected_seg = None
        self.edit_mode = False
        self.current_class = 0
        self.class_mapping = {}
        self.class_colors = {}
        self.original_width = 0
        self.original_height = 0
        self.annotations_visible = True
        self.x_offset = 0
        self.y_offset = 0
        self.scale_factor = 1
        self._loading = False

        # Drawing state
        self._drawing = False
        self._pending_canvas_pts = []

        # Vertex drag state
        self._vertex_handles = []
        self._drag_vertex_idx = None
        self._suppress_next_click = False

        self.on_seg_added = None

        self.canvas.bind('<Button-1>', self._on_left_click)
        self.canvas.bind('<Double-Button-1>', self._on_double_click)
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.root.bind('<Configure>', self._on_resize)

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def _on_resize(self, event):
        if event.widget is self.root and self.image:
            self.load_image(self.image_path, self.label_path)

    def load_image(self, image_path, label_path=None, fullscreen=False):
        if self._loading:
            return
        self._loading = True
        self.image_path = image_path
        self.label_path = label_path

        self.canvas.delete('all')
        self.segs.clear()
        self.selected_seg = None
        self._vertex_handles = []
        self._pending_canvas_pts = []
        self._drawing = False
        self._suppress_next_click = False

        self.image = Image.open(image_path)
        self.original_width, self.original_height = self.image.size

        self.root.update_idletasks()

        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            canvas_width, canvas_height = self.original_width, self.original_height

        scale_factor = min(canvas_width / self.original_width, canvas_height / self.original_height)
        new_width = int(self.original_width * scale_factor)
        new_height = int(self.original_height * scale_factor)

        resized_image = self.image.resize((new_width, new_height), Image.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized_image)

        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.scale_factor = scale_factor
        self.canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=self.tk_image)

        if label_path and os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 7:  # class + at least 3 points (6 floats)
                        continue
                    try:
                        class_num = int(parts[0])
                        flat_coords = [float(p) for p in parts[1:]]
                        if len(flat_coords) % 2 != 0:
                            flat_coords = flat_coords[:-1]
                        seg = SegmentationAnnotation.from_normalized(
                            class_num, flat_coords, self.original_width, self.original_height
                        )
                        self.segs.append(seg)
                        self._draw_seg(seg)
                    except (ValueError, IndexError):
                        continue

        self._loading = False

    # ------------------------------------------------------------------
    # Drawing polygons
    # ------------------------------------------------------------------

    def _draw_seg(self, seg):
        if len(seg.points) < 3:
            return
        canvas_pts = []
        for x, y in seg.points:
            canvas_pts.extend([x * self.scale_factor + self.x_offset,
                                y * self.scale_factor + self.y_offset])
        class_id = seg.class_num
        color = self.class_colors.get(class_id, '#555555')
        class_name = self.class_mapping.get(class_id, str(class_id))
        label = f'{class_id}: {class_name}'
        poly = self.canvas.create_polygon(
            *canvas_pts,
            fill=color, stipple='gray25',
            outline=color, width=2,
            tags='annotation'
        )
        cx = sum(canvas_pts[i] for i in range(0, len(canvas_pts), 2)) / len(seg.points)
        cy = sum(canvas_pts[i] for i in range(1, len(canvas_pts), 2)) / len(seg.points)
        text = self.canvas.create_text(
            cx, cy, text=label, fill='white',
            font=('Helvetica', 9, 'bold'), tags='annotation'
        )
        seg.polygon_id = poly
        seg.text_id = text

    def _redraw_seg(self, seg):
        if seg.polygon_id:
            self.canvas.delete(seg.polygon_id)
        if seg.text_id:
            self.canvas.delete(seg.text_id)
        seg.polygon_id = None
        seg.text_id = None
        self._draw_seg(seg)
        if self.selected_seg is seg:
            if seg.polygon_id:
                self.canvas.itemconfig(seg.polygon_id, outline='white', width=3)

    def _update_preview(self, cursor_x=None, cursor_y=None):
        self.canvas.delete('preview')
        if not self._pending_canvas_pts:
            return
        pts = list(self._pending_canvas_pts)
        if cursor_x is not None:
            pts = pts + [(cursor_x, cursor_y)]
        if len(pts) >= 2:
            flat = []
            for cx, cy in pts:
                flat.extend([cx, cy])
            self.canvas.create_line(*flat, fill='cyan', width=2, dash=(4, 2), tags='preview')
        # Draw closing line to first vertex when there are 3+ pending pts and cursor present
        if cursor_x is not None and len(self._pending_canvas_pts) >= 2:
            fx, fy = self._pending_canvas_pts[0]
            self.canvas.create_line(cursor_x, cursor_y, fx, fy,
                                    fill='cyan', width=1, dash=(2, 4), tags='preview')
        r = 4
        for cx, cy in self._pending_canvas_pts:
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill='cyan', outline='white', tags='preview')
        if cursor_x is not None:
            self.canvas.create_oval(cursor_x - r, cursor_y - r,
                                    cursor_x + r, cursor_y + r,
                                    fill='yellow', outline='white', tags='preview')

    def _close_polygon(self):
        if len(self._pending_canvas_pts) < 3:
            self._cancel_drawing()
            return
        points = [
            ((cx - self.x_offset) / self.scale_factor,
             (cy - self.y_offset) / self.scale_factor)
            for cx, cy in self._pending_canvas_pts
        ]
        seg = SegmentationAnnotation(points, self.current_class)
        self.segs.append(seg)
        self._cancel_drawing()
        self._draw_seg(seg)
        if self.on_seg_added:
            self.on_seg_added()

    def _cancel_drawing(self):
        self._drawing = False
        self._pending_canvas_pts = []
        self.canvas.delete('preview')

    # ------------------------------------------------------------------
    # Mouse / keyboard events
    # ------------------------------------------------------------------

    def _on_left_click(self, event):
        if not self.edit_mode:
            return
        if self._suppress_next_click:
            self._suppress_next_click = False
            return
        if not self._drawing:
            self._deselect()
            self._drawing = True
            self._pending_canvas_pts = []
        self._pending_canvas_pts.append((event.x, event.y))
        self._update_preview()

    def _on_double_click(self, event):
        if not self.edit_mode or not self._drawing:
            return
        # Button-1 fired once already for this second click, adding a duplicate vertex — remove it
        if self._pending_canvas_pts:
            self._pending_canvas_pts.pop()
        self._close_polygon()

    def _on_mouse_move(self, event):
        if self._drawing:
            self._update_preview(event.x, event.y)

    def _on_right_click(self, event):
        if self._drawing:
            self._cancel_drawing()
            return
        x = (event.x - self.x_offset) / self.scale_factor
        y = (event.y - self.y_offset) / self.scale_factor
        for seg in reversed(self.segs):  # topmost first
            if self._point_in_polygon(x, y, seg.points):
                self._select_seg(seg)
                return
        self._deselect()

    # ------------------------------------------------------------------
    # Selection and vertex editing
    # ------------------------------------------------------------------

    def _select_seg(self, seg):
        self._deselect()
        self.selected_seg = seg
        if seg.polygon_id:
            self.canvas.itemconfig(seg.polygon_id, outline='white', width=3)
        if self.edit_mode:
            self._show_vertex_handles(seg)

    def _deselect(self):
        self._clear_vertex_handles()
        if self.selected_seg:
            if self.selected_seg.polygon_id:
                color = self.class_colors.get(self.selected_seg.class_num, '#555555')
                self.canvas.itemconfig(self.selected_seg.polygon_id, outline=color, width=2)
            self.selected_seg = None

    def _show_vertex_handles(self, seg):
        self._clear_vertex_handles()
        r = 5
        for vi, (x, y) in enumerate(seg.points):
            cx = x * self.scale_factor + self.x_offset
            cy = y * self.scale_factor + self.y_offset
            h = self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                        fill='white', outline='blue', width=2,
                                        tags='vertex_handle')
            self.canvas.tag_bind(h, '<Button-1>',
                                 lambda e, idx=vi: self._start_drag_vertex(e, idx))
            self.canvas.tag_bind(h, '<B1-Motion>', self._drag_vertex)
            self.canvas.tag_bind(h, '<ButtonRelease-1>', self._end_drag_vertex)
            self._vertex_handles.append(h)

    def _clear_vertex_handles(self):
        for h in self._vertex_handles:
            self.canvas.delete(h)
        self._vertex_handles = []
        self._drag_vertex_idx = None

    def _start_drag_vertex(self, event, idx):
        self._drag_vertex_idx = idx
        self._suppress_next_click = True  # tag_bind fires before canvas bind

    def _drag_vertex(self, event):
        if self._drag_vertex_idx is None or self.selected_seg is None:
            return
        seg = self.selected_seg
        ix = max(0.0, min(float(self.original_width),
                          (event.x - self.x_offset) / self.scale_factor))
        iy = max(0.0, min(float(self.original_height),
                          (event.y - self.y_offset) / self.scale_factor))
        seg.points[self._drag_vertex_idx] = (ix, iy)
        self._redraw_seg(seg)
        self._show_vertex_handles(seg)

    def _end_drag_vertex(self, event):
        self._drag_vertex_idx = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def toggle_edit_mode(self):
        self.edit_mode = not self.edit_mode
        if not self.edit_mode:
            if self._drawing:
                self._cancel_drawing()
            self._clear_vertex_handles()

    def toggle_annotations(self):
        self.annotations_visible = not self.annotations_visible
        state = 'normal' if self.annotations_visible else 'hidden'
        self.canvas.itemconfigure('annotation', state=state)
        return self.annotations_visible

    def close_polygon_if_drawing(self):
        if self._drawing:
            self._close_polygon()

    def cancel_drawing(self):
        if self._drawing:
            self._cancel_drawing()

    def delete_selected_seg(self):
        if self.selected_seg is None:
            return
        self._clear_vertex_handles()
        if self.selected_seg.polygon_id:
            self.canvas.delete(self.selected_seg.polygon_id)
        if self.selected_seg.text_id:
            self.canvas.delete(self.selected_seg.text_id)
        if self.selected_seg in self.segs:
            self.segs.remove(self.selected_seg)
        self.selected_seg = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _point_in_polygon(px, py, points):
        n = len(points)
        inside = False
        j = n - 1
        for i in range(n):
            xi, yi = points[i]
            xj, yj = points[j]
            if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
                inside = not inside
            j = i
        return inside
