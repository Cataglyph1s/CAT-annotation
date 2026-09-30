import os
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw
from segmentation_annotation import SegmentationAnnotation
from viewport import compute_axis

MAX_ZOOM = 8.0


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

        # Tool mode: 'polygon' (default, click-to-add-vertex) or 'brush'
        # (paint/erase a per-pixel mask, vectorized to a polygon on commit —
        # the label format only understands polygons, see segmentation_annotation.py)
        self.tool_mode = 'polygon'
        self.brush_size = 15  # radius, in displayed-canvas pixels
        self._disp_width = 0
        self._disp_height = 0
        self._brush_mask = None
        self._brush_draw = None
        self._brush_active = False
        self._brush_overlay_id = None
        self._brush_overlay_img = None
        self._brush_cursor_id = None

        # Zoom / pan viewport state
        self.zoom = 1.0
        self.view_cx = 0.0
        self.view_cy = 0.0
        self._panning = False
        self._pan_start = None
        self.on_viewport_changed = None

        self.on_seg_added = None

        self.canvas.bind('<Button-1>', self._on_button1)
        self.canvas.bind('<Double-Button-1>', self._on_double_click)
        self.canvas.bind('<Motion>', self._on_mouse_move)
        self.canvas.bind('<B1-Motion>', self._on_b1_motion)
        self.canvas.bind('<ButtonRelease-1>', self._on_button1_release)
        self.canvas.bind('<Button-3>', self._on_right_click)
        self.canvas.bind('<B3-Motion>', self._on_b3_motion)
        self.canvas.bind('<MouseWheel>', self._on_mouse_wheel)
        self.canvas.bind('<Control-MouseWheel>', self._on_ctrl_wheel)
        self.canvas.bind('<Button-2>', self._on_pan_start)
        self.canvas.bind('<B2-Motion>', self._on_pan_motion)
        self.canvas.bind('<ButtonRelease-2>', self._on_pan_end)
        # Bind to the CANVAS's own size changes, not the root window's — the
        # canvas resizes (and needs re-fitting) whenever a side panel is
        # toggled too, which never changes root's own outer dimensions.
        self.canvas.bind('<Configure>', self._on_resize)

    # ------------------------------------------------------------------
    # Image loading
    # ------------------------------------------------------------------

    def _on_resize(self, event):
        if event.widget is self.canvas and self.image:
            self._cancel_session()
            self._render_viewport()

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
        self._brush_active = False
        self._brush_mask = None
        self._brush_draw = None
        self._brush_overlay_id = None
        self._brush_overlay_img = None
        self._brush_cursor_id = None
        self._panning = False
        self._pan_start = None

        self.image = Image.open(image_path)
        self.original_width, self.original_height = self.image.size

        # Reset the viewport to fit-to-canvas, centered, on every new image
        self.zoom = 1.0
        self.view_cx = self.original_width / 2
        self.view_cy = self.original_height / 2

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
                    except (ValueError, IndexError):
                        continue

        self._render_viewport()
        self._loading = False

    def _get_canvas_size(self):
        """Current canvas size, falling back to the image dimensions if the
        canvas isn't laid out yet (winfo_width returns 1 before the window
        is fully rendered). Used consistently by every method that needs to
        reason about canvas size, so zoom/pan math never disagrees with
        what _render_viewport actually used."""
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
        self._disp_width, self._disp_height = disp_w, disp_h
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

        self.canvas.delete('all')
        self.canvas.create_image(self._img_place_x, self._img_place_y, anchor=tk.NW, image=self.tk_image)

        self._redraw_annotations()

        if self.on_viewport_changed:
            self.on_viewport_changed()

    def _redraw_annotations(self):
        for seg in self.segs:
            self._draw_seg(seg)
        if self.selected_seg is not None and self.selected_seg.polygon_id:
            self.canvas.itemconfig(self.selected_seg.polygon_id, outline='white', width=3)
            if self.edit_mode:
                self._show_vertex_handles(self.selected_seg)

    def _cancel_session(self):
        """Discard any in-progress polygon draw or brush stroke — used
        before a zoom/pan/resize changes the coordinate system out from
        under an in-progress session."""
        if self._drawing:
            self._cancel_drawing()
        self._cancel_brush()

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
        self._cancel_session()
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
        self._cancel_session()
        self._set_zoom(self.zoom * 1.25)

    def zoom_out(self):
        if self.image is None:
            return
        self._cancel_session()
        self._set_zoom(self.zoom / 1.25)

    def reset_zoom(self):
        if self.image is None:
            return
        self._cancel_session()
        self._set_zoom(1.0, self.original_width / 2, self.original_height / 2)

    def _on_pan_start(self, event):
        if self.image is None:
            return
        self._cancel_session()
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

    # ------------------------------------------------------------------
    # Brush tool
    #
    # Painting happens on a working mask sized to match the displayed
    # (already scaled) image, so painting is cheap and responsive. On
    # commit the mask is vectorized (cv2.findContours) into image-pixel
    # polygon points — the only format the label files / training
    # pipeline understand. Multiple disconnected blobs are bridged into
    # a single closed point path so they still save as one instance/line,
    # the same technique Ultralytics' own dataset converter uses for
    # multi-part instances.
    # ------------------------------------------------------------------

    def _ensure_brush_mask(self):
        if self._brush_mask is None:
            self._brush_mask = Image.new('L', (self._disp_width, self._disp_height), 0)
            self._brush_draw = ImageDraw.Draw(self._brush_mask)

    def _brush_start(self, event, erase=False):
        self._brush_active = True
        self._ensure_brush_mask()
        self._brush_paint(event, erase=erase)

    def _brush_paint(self, event, erase=False):
        self._ensure_brush_mask()
        mx = event.x - self.x_offset
        my = event.y - self.y_offset
        r = self.brush_size
        self._brush_draw.ellipse([mx - r, my - r, mx + r, my + r], fill=(0 if erase else 255))
        self._update_brush_overlay()
        self._update_brush_cursor(event.x, event.y)

    def _update_brush_overlay(self):
        if self._brush_mask is None:
            return
        color = self.class_colors.get(self.current_class, '#55ff55')
        r16, g16, b16 = self.root.winfo_rgb(color)
        r, g, b = r16 // 256, g16 // 256, b16 // 256
        overlay = Image.new('RGBA', self._brush_mask.size, (r, g, b, 0))
        overlay.putalpha(self._brush_mask.point(lambda v: 120 if v else 0))
        self._brush_overlay_img = ImageTk.PhotoImage(overlay)
        if self._brush_overlay_id is None:
            self._brush_overlay_id = self.canvas.create_image(
                self.x_offset, self.y_offset, anchor=tk.NW,
                image=self._brush_overlay_img, tags='brush_overlay')
        else:
            self.canvas.itemconfig(self._brush_overlay_id, image=self._brush_overlay_img)
        if self._brush_cursor_id is not None:
            self.canvas.tag_raise(self._brush_cursor_id)

    def _update_brush_cursor(self, cx, cy):
        r = self.brush_size
        if self._brush_cursor_id is None:
            self._brush_cursor_id = self.canvas.create_oval(
                cx - r, cy - r, cx + r, cy + r,
                outline='yellow', width=2, tags='brush_cursor')
        else:
            self.canvas.coords(self._brush_cursor_id, cx - r, cy - r, cx + r, cy + r)
            self.canvas.tag_raise(self._brush_cursor_id)

    def _cancel_brush(self):
        self._brush_active = False
        self._brush_mask = None
        self._brush_draw = None
        if self._brush_overlay_id is not None:
            self.canvas.delete(self._brush_overlay_id)
            self._brush_overlay_id = None
        self._brush_overlay_img = None
        if self._brush_cursor_id is not None:
            self.canvas.delete(self._brush_cursor_id)
            self._brush_cursor_id = None

    def _finish_brush_mask(self):
        if self._brush_mask is None or not self._brush_active:
            self._cancel_brush()
            return
        import numpy as np
        import cv2

        mask_arr = np.array(self._brush_mask)
        contours, _ = cv2.findContours(mask_arr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c.reshape(-1, 2) for c in contours if len(c) >= 3]
        if not contours:
            self._cancel_brush()
            return
        merged = contours[0] if len(contours) == 1 else self._merge_contours(contours)

        inv_scale = (1.0 / self.scale_factor) if self.scale_factor else 1.0
        points = [(float(x) * inv_scale, float(y) * inv_scale) for x, y in merged]
        seg = SegmentationAnnotation(points, self.current_class)
        self.segs.append(seg)
        self._cancel_brush()
        self._draw_seg(seg)
        if self.on_seg_added:
            self.on_seg_added()

    @staticmethod
    def _merge_contours(contours):
        """Join multiple disjoint contours into a single closed point path,
        bridging each one in via its nearest point to the running path —
        keeps a multi-blob mask representable as one polygon/instance line."""
        merged = list(contours[0])
        for part in contours[1:]:
            best = None
            for i, mp in enumerate(merged):
                for j, pp in enumerate(part):
                    d = (mp[0] - pp[0]) ** 2 + (mp[1] - pp[1]) ** 2
                    if best is None or d < best[0]:
                        best = (d, i, j)
            _, mi, pj = best
            reordered = list(part[pj:]) + list(part[:pj])
            merged = merged[:mi + 1] + [reordered[0]] + reordered + [merged[mi]] + merged[mi + 1:]
        return merged

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
        ix, iy = self._clamp_to_image(event.x, event.y)
        cx = ix * self.scale_factor + self.x_offset
        cy = iy * self.scale_factor + self.y_offset
        self._pending_canvas_pts.append((cx, cy))
        self._update_preview()

    def _on_double_click(self, event):
        if not self.edit_mode:
            return
        if self.tool_mode == 'brush':
            self._finish_brush_mask()
            return
        if not self._drawing:
            return
        # Button-1 fired once already for this second click, adding a duplicate vertex — remove it
        if self._pending_canvas_pts:
            self._pending_canvas_pts.pop()
        self._close_polygon()

    def _on_mouse_move(self, event):
        if self.tool_mode == 'brush':
            if self.edit_mode:
                self._update_brush_cursor(event.x, event.y)
            return
        if self._drawing:
            self._update_preview(event.x, event.y)

    def _on_right_click(self, event):
        if self.tool_mode == 'brush' and self.edit_mode:
            self._brush_start(event, erase=True)
            return
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
    # Button-1 / brush dispatch
    #
    # <Button-1>/<B1-Motion>/<ButtonRelease-1> serve double duty: polygon
    # mode uses them for adding vertices and dragging a selected vertex;
    # brush mode uses them for painting. Each dispatches on self.tool_mode.
    # ------------------------------------------------------------------

    def _on_button1(self, event):
        if self.tool_mode == 'brush' and self.edit_mode:
            self._brush_start(event)
            return
        self._on_left_click(event)

    def _on_b1_motion(self, event):
        if self.tool_mode == 'brush' and self.edit_mode:
            if self._brush_active:
                self._brush_paint(event)
            return
        self._drag_vertex(event)

    def _on_button1_release(self, event):
        if self.tool_mode == 'brush':
            return
        self._end_drag_vertex(event)

    def _on_b3_motion(self, event):
        if self.tool_mode == 'brush' and self.edit_mode and self._brush_active:
            self._brush_paint(event, erase=True)

    def _on_mouse_wheel(self, event):
        if self.tool_mode != 'brush' or not self.edit_mode:
            return
        step = 2
        if event.delta > 0:
            self.brush_size = min(150, self.brush_size + step)
        else:
            self.brush_size = max(2, self.brush_size - step)
        self._update_brush_cursor(event.x, event.y)

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
        idx = self._drag_vertex_idx
        ix, iy = self._clamp_to_image(event.x, event.y)
        seg.points[idx] = (ix, iy)

        # Update polygon outline in-place (no delete/recreate — keeps drag bindings intact)
        canvas_pts = []
        for x, y in seg.points:
            canvas_pts.extend([x * self.scale_factor + self.x_offset,
                                y * self.scale_factor + self.y_offset])
        if seg.polygon_id:
            self.canvas.coords(seg.polygon_id, *canvas_pts)
        if seg.text_id:
            n = len(seg.points)
            cx = sum(canvas_pts[i] for i in range(0, len(canvas_pts), 2)) / n
            cy = sum(canvas_pts[i] for i in range(1, len(canvas_pts), 2)) / n
            self.canvas.coords(seg.text_id, cx, cy)

        # Move just the dragged handle
        if idx < len(self._vertex_handles):
            r = 5
            ncx = ix * self.scale_factor + self.x_offset
            ncy = iy * self.scale_factor + self.y_offset
            self.canvas.coords(self._vertex_handles[idx],
                                ncx - r, ncy - r, ncx + r, ncy + r)

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
            self._cancel_brush()
            self._clear_vertex_handles()

    def toggle_tool_mode(self):
        """Switch between 'polygon' and 'brush' annotation tools, discarding
        any in-progress polygon/brush session on the way."""
        if self._drawing:
            self._cancel_drawing()
        self._cancel_brush()
        self.tool_mode = 'brush' if self.tool_mode == 'polygon' else 'polygon'
        return self.tool_mode

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

    def _clamp_to_image(self, canvas_x, canvas_y):
        """Convert canvas coords to image-pixel coords, clamped to image bounds."""
        if self.scale_factor == 0:
            return 0.0, 0.0
        ix = max(0.0, min(float(self.original_width - 1),
                          (canvas_x - self.x_offset) / self.scale_factor))
        iy = max(0.0, min(float(self.original_height - 1),
                          (canvas_y - self.y_offset) / self.scale_factor))
        return ix, iy

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
