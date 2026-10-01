# CAT:annotation

**Computer-Assisted Training Annotation Tool**

> ⚠️ This project is a work in progress. Features are actively being developed and things may change between versions.

Current version: **v0.4.5**

---

## What it does

CAT:annotation is a desktop tool for reviewing and annotating image datasets in YOLO format — both bounding-box detection and polygon segmentation. It is built for speed — keyboard-first navigation, auto-save, slideshow mode, zoom/pan for small objects, and persistent annotations across frames make it practical for large video-derived datasets.

---

## Getting started

### Requirements

- Python 3.8+
- `Pillow`
- `opencv-python` (used by segmentation Brush Mode to vectorize painted masks into polygons)
- `numpy`

Install dependencies:
```
pip install -r requirements.txt
```

### Launch

```
python main.py
```

On first launch you will be prompted to create a new project or open an existing folder.

### Supported folder layouts

| Layout | Example |
|--------|---------|
| Standard | `set/images/` + `set/labels/` |
| Nested (YOLO split) | `dataset/images/train/` + `dataset/labels/train/` |
| Flat | images and labels in the same folder |

Class names are loaded automatically from `dataset.yaml` if one is found in the folder or its parent. Otherwise the default 8-class Samira mapping is used.

The project mode (bounding box vs. segmentation) is set per project — a segmentation project stores polygons in `labels_seg/` instead of `labels/`.

---

## Building a standalone .exe

For sharing with colleagues who don't have Python set up:

```
pip install pyinstaller
build.bat
```

This produces `dist/CAT-annotation/` — a folder containing `CAT-annotation.exe` and its dependencies. Ship the whole folder (zip it); colleagues run the `.exe` from inside it, no Python install required. `pyinstaller` is a build-only tool and isn't in `requirements.txt` since it's not needed to just run the app from source.

The build uses `main.spec` (`--onedir`, no console window). `--onedir` launches noticeably faster than a `--onefile` build, at the cost of shipping a folder instead of a single file — worth it for an internal tool that isn't launched from, say, a USB stick.

---

## Keyboard shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `d` or `p` | Next image |
| `a` or `o` | Previous image |
| `Ctrl+G` | Jump to image by number |
| `Space` | Play / pause slideshow |
| `q` | Toggle fullscreen |

### Annotation

| Key | Action |
|-----|--------|
| `e` | Toggle Edit Mode (required to draw or delete) |
| `0` – `9` | Select annotation class |
| Right-click on bbox/polygon | Select it |
| Right-click on empty area | Deselect |
| `Escape` | Deselect current annotation |
| `g` | Delete selected annotation |
| `Ctrl+Z` | Undo last action |
| `Ctrl+S` | Save annotations |
| `Ctrl+B` | Delete current image and its label |
| `Return` | Close the polygon currently being drawn (segmentation, polygon tool) |

### Segmentation Brush Mode

| Key / mouse | Action |
|---|---|
| `b` | Toggle Brush Mode on/off (segmentation projects only) |
| Left-drag | Paint |
| Right-drag | Erase |
| Scroll wheel | Grow / shrink brush size |
| Double-click | Finish the current mask → vectorized into a polygon and added as one instance |

### Zoom & pan

| Key / mouse | Action |
|---|---|
| `Ctrl` + Scroll wheel | Zoom in/out, centered on the cursor |
| Middle-click drag | Pan around a zoomed-in image |
| `Ctrl` `+` / `Ctrl` `=` | Zoom in (toolbar `+` button) |
| `Ctrl` `-` | Zoom out (toolbar `-` button) |
| `Ctrl` `0` | Reset to fit-to-canvas (toolbar `Fit` button) |

### Review

| Key | Action |
|-----|--------|
| `f` | Flag / unflag current image |
| `Ctrl+F` | Jump to next flagged image (F >>) |
| `Ctrl+Shift+F` | Jump to previous flagged image (<< F) |
| `v` | Toggle Cover Mode (draw white occluders) — bounding-box projects only |

---

## Workflow

### Basic annotation (bounding box)

1. Open a folder via **☰ → Open Folder** or create a project via **☰ → New Project**
2. Press `e` to enter Edit Mode
3. Select a class with `0`–`9` or by clicking the class legend on the right
4. Drag to draw a bounding box
5. Press `Escape` or right-click empty space to deselect before switching class
6. Auto-Save writes to disk on every navigation step (toggle with the Auto-Save button)

### Segmentation annotation

Segmentation projects support two ways to draw a mask, toggled with the **Brush Mode** button (or `b`) next to Edit Mode:

**Polygon tool (default)**
1. Press `e` to enter Edit Mode
2. Click to place each vertex
3. Double-click (or press `Return`) to close the polygon
4. Drag any vertex handle on a selected polygon to reshape it

**Brush tool**
1. Press `e` to enter Edit Mode, then toggle **Brush Mode** on
2. Left-drag to paint, right-drag to erase — a live colored overlay shows the working mask; scroll to resize the brush
3. Double-click to finish — the painted mask is vectorized into a polygon and added as a new instance
4. If a mask ends up with disconnected blobs, they're bridged into a single polygon so it still saves as one instance
5. Brush Mode currently creates new instances only — reshaping an existing polygon still uses the vertex-drag handles from the polygon tool

### Zoom & pan (either mode)

Useful for precisely placing boxes/polygons on small objects in high-resolution images:

1. Hold `Ctrl` and scroll over the image to zoom in/out, centered on the cursor — or use the `-` / `100%` / `+` / `Fit` controls in the toolbar
2. Middle-click and drag to pan around once zoomed in
3. Zoom always re-crops from the original full-resolution image, so zoomed-in detail stays sharp rather than blurring
4. Zoom/pan resets to fit-to-canvas automatically when you move to the next/previous image

### Dataset review (large sets)

1. Use `Space` to start the slideshow — click the speed button to cycle 0.5s / 1s / 2s / 5s per frame
2. Press `f` to flag images that need attention, use `Ctrl+F` to revisit them
3. Use `Ctrl+G` to jump directly to an image by number
4. Progress and ETA (based on a 30-frame rolling average) are shown in the bottom bar

### Persistent annotations

Any bounding box can be **pinned** so it is automatically copied to every subsequent frame:

1. Click the `○` button next to an annotation in the Annotations panel → turns `●`
2. Navigate forward — the pinned annotation appears on each new frame
3. Click `●` to unpin

### Covering static objects (anti-overfitting)

If a background object is stationary across many frames the model may memorise its position. Use Cover Mode to paint over it (bounding-box projects only):

1. Press `v` (or click **Cover Mode**) — Edit Mode activates automatically
2. Drag a rectangle over the object — a white filled box appears
3. Pin it in the **Occluders (this image)** panel so it carries to all subsequent frames
4. When done, use **☰ → Dataset Tools → Burn to images_masked/** to write masked copies of all affected images
5. Point your training pipeline at `images_masked/` instead of `images/` — originals are untouched

### Converting tiny annotations to occluders

Very small boxes carry little to no usable shape signal once resized down to your model's training input, and add noise to training. **☰ → Dataset Tools → Convert tiny boxes → occluders + burn** cleans these up:

1. Enter a minimum box dimension in pixels **at your training input size** (e.g. 640×640) — you're prompted for this each run, so you can tune it per dataset without editing code
2. A confirmation dialog shows how many boxes will be affected across how many images, based on each image's actual resolution scaled down to that training size
3. On confirm, the tool:
   - Removes all sub-threshold boxes from the label files (all classes)
   - Adds their coordinates to `occluders.json` as white occluder rectangles
   - Burns the full set to `images_masked/` with those areas whited out

> **Note:** label files are modified in place. Back up your `labels/` folder first if you want to be safe.

### Collapsible panels

The **Sets** panel (left), the **Classes / Annotations / Occluders** panel (right), and the bottom **button toolbar** can each be collapsed independently to reclaim canvas space — click the thin arrow strip on each panel's edge to toggle it:

| Panel | Strip location | Arrows |
|---|---|---|
| Sets (left) | right edge of the panel | `◀` open / `▶` collapsed |
| Classes/Annotations/Occluders (right) | left edge of the panel | `▶` open / `◀` collapsed |
| Button toolbar (bottom) | top edge of the toolbar | `▼` open / `▲` collapsed |

If a project has multiple sets (e.g. `train/`, `val/`) they appear in the **Sets** panel — double-click a set to switch to it.

---

## Project structure

```
my_project/
├── project.json          # class names and colours
├── train/
│   ├── images/
│   ├── labels/            # bounding-box projects
│   ├── labels_seg/        # segmentation projects (polygon instances, one per line)
│   ├── images_masked/    # created by Burn Occluders / Dataset Tools
│   ├── occluders.json    # occluder rectangles per image
│   ├── flagged.txt       # flagged image filenames
│   └── index.json        # last viewed image index
└── val/
    └── ...
```

---

## Notes

- Bounding-box label files follow the YOLO format: `class x_center y_center width height` (normalised 0–1)
- Segmentation label files follow the YOLO-seg polygon format: `class x1 y1 x2 y2 ...` (normalised 0–1), one instance per line
- Deleting an image removes both the image file and its label file
- The undo stack holds up to 50 actions and is cleared when switching sets; in segmentation projects, only image deletion is undoable
- ETA is a rolling average of the last 30 navigation steps
- Zoom/pan always re-crops from the original image at its full resolution, rather than magnifying an already-downscaled preview
- `occluders.json`, `flagged.txt`, and `index.json` are plain last-write-wins files with no locking — safe for one person working on a given set at a time, but two people editing the *same* set simultaneously can overwrite each other's flags/occluders/position
