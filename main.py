import os
import tkinter as tk
from tkinter import filedialog, messagebox  # used in _ensure_program_root

from image_viewer_controller import ImageViewerController
from app_config import AppConfig

VERSION = "v0.4.1"


class ImageViewer:
    def __init__(self, root, folder):
        self.controller = ImageViewerController(root, folder)


def _ensure_program_root(root):
    """Prompts the user to pick a location; creates a CATannotation folder there. Returns False if cancelled."""
    if AppConfig.get_program_root():
        return True

    messagebox.showinfo(
        "Welcome to CAT:annotation",
        "Choose where to create your CATannotation projects folder.",
        parent=root)
    location = filedialog.askdirectory(parent=root, title="Select Location for CATannotation Folder")
    if not location:
        return False
    full_path = os.path.join(location, "CATannotation")
    os.makedirs(full_path, exist_ok=True)
    AppConfig.set_program_root(full_path)
    return True


def _is_valid_dataset_folder(path):
    if not path or not os.path.isdir(path):
        return False
    if os.path.isdir(os.path.join(path, "images")):
        return True
    return any(f.lower().endswith(('.jpg', '.jpeg', '.png')) for f in os.listdir(path))


def _get_startup_folder():
    """Returns the last used folder if still valid, otherwise None."""
    last = AppConfig.get_last_folder()
    if _is_valid_dataset_folder(last):
        return last
    return None


if __name__ == "__main__":
    root = tk.Tk()
    root.title("CAT:annotation")
    root.withdraw()

    if not _ensure_program_root(root):
        root.destroy()
        raise SystemExit

    folder = _get_startup_folder()
    root.deiconify()
    app = ImageViewer(root, folder)
    root.mainloop()

    # ----------------------------------------------------------------------------------
    # TODO:
    # 1) Add Program Root for all Projects. Must auto ask if null          [DONE]
    # 2) Add Column (hideable) with project sets info on left under menu
    #       - add view button next to menu. All columns hideable and retrievable
    #       - clean view with info bar only, shortcuts work for clean annot. option
    #       - double click set name to switch to it (autosave changes on change)
    # 3) Add class colours to class column
    # 4) Add Users to project
    # 5) Zoom function for high-res/small-object annotation (small buttons + shortcut)
    # 6) Think about central save options
    # 7) Change name to CAT:annotation                                     [DONE]
    # -----------------------------------------------------------------------------------
