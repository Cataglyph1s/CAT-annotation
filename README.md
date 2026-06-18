# CAT:annotation

**Computer-Assisted Training Annotation Tool**

> ⚠️ This project is a work in progress. Features are actively being developed and things may change between versions.

Current version: **v0.4.1**

---

## What it does

CAT:annotation is a desktop tool for reviewing and annotating image datasets in YOLO format. It is built for speed — keyboard-first navigation, auto-save, slideshow mode, and persistent annotations across frames make it practical for large video-derived datasets.

---

## Getting started

### Requirements

- Python 3.8+
- `Pillow`

Install dependencies:
```
pip install pillow
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
| Right-click on bbox | Select bbox |
| Right-click on empty area | Deselect |
| `Escape` | Deselect current bbox |
| `g` | Delete selected bbox |
| `Ctrl+Z` | Undo last action |
| `Ctrl+S` | Save annotations |
| `Ctrl+B` | Delete current image and its label |

### Review

| Key | Action |
|-----|--------|
| `f` | Flag / unflag current image |
| `Ctrl+F` | Jump to next flagged image (F >>) |
| `Ctrl+Shift+F` | Jump to previous flagged image (<< F) |
| `v` | Toggle Cover Mode (draw white occluders) |

---

## Workflow

### Basic annotation

1. Open a folder via **☰ → Open Folder** or create a project via **☰ → New Project**
2. Press `e` to enter Edit Mode
3. Select a class with `0`–`9` or by clicking the class legend on the right
4. Drag to draw a bounding box
5. Press `Escape` or right-click empty space to deselect before switching class
6. Auto-Save writes to disk on every navigation step (toggle with the Auto-Save button)

### Dataset review (large sets)

1. Use `Space` to start the slideshow — click the speed button to cycle 0.5s / 1s / 2s / 5s per frame
2. Press `f` to flag images that need attention, use `Ctrl+F` to revisit them
3. Use `Ctrl+G` to jump directly to an image by number
4. Progress and ETA (based on a 30-frame rolling average) are shown in the bottom bar

### Persistent annotations

Any annotation can be **pinned** so it is automatically copied to every subsequent frame:

1. Click the `○` button next to an annotation in the Annotations panel → turns `●`
2. Navigate forward — the pinned annotation appears on each new frame
3. Click `●` to unpin

### Covering static objects (anti-overfitting)

If a background object is stationary across many frames the model may memorise its position. Use Cover Mode to paint over it:

1. Press `v` (or click **Cover Mode**) — Edit Mode activates automatically
2. Drag a rectangle over the object — a white filled box appears
3. Pin it in the **Occluders** panel so it carries to all subsequent frames
4. When done, click **Burn to images_masked/** to write masked copies of all affected images
5. Point your training pipeline at `images_masked/` instead of `images/` — originals are untouched

### Converting tiny annotations to occluders

Bounding boxes with a normalised area (width × height) below **0.0024** are too small for YOLOv8n/s to detect reliably at 640 px input and add noise to training. The Occluders panel provides a one-click fix:

1. Click **"Convert tiny boxes → occluders + burn"** in the Occluders panel
2. A confirmation dialog shows how many boxes will be affected across how many images
3. On confirm, the tool:
   - Removes all sub-threshold boxes from the label files (all classes)
   - Adds their coordinates to `occluders.json` as white occluder rectangles
   - Burns the full set to `images_masked/` with those areas whited out

> **Note:** label files are modified in place. Back up your `labels/` folder first if you want to be safe.

Size reference at 640 px input:

| Normalised area (w × h) | Equivalent px | Verdict |
|---|---|---|
| < 0.00024 | < ~10 × 10 px | Pure noise |
| < 0.0024 | < ~32 × 32 px | Below reliable detection threshold (this tool's cutoff) |
| 0.0024 – 0.023 | 32 – 96 px | Small but trainable |
| > 0.023 | > 96 px | Trains reliably |

### Multiple sets

If a project has multiple sets (e.g. `train/`, `val/`) they appear in the **Sets** panel on the left. Double-click a set to switch to it. Click `◀` / `▶` to collapse or expand the panel.

---

## Project structure

```
my_project/
├── project.json          # class names and colours
├── train/
│   ├── images/
│   ├── labels/
│   ├── images_masked/    # created by Burn Occluders
│   ├── occluders.json    # occluder rectangles per image
│   ├── flagged.txt       # flagged image filenames
│   └── index.json        # last viewed image index
└── val/
    └── ...
```

---

## Notes

- Label files follow the YOLO format: `class x_center y_center width height` (normalised 0–1)
- Deleting an image removes both the image file and its label file
- The undo stack holds up to 50 actions and is cleared when switching sets
- ETA is a rolling average of the last 30 navigation steps
