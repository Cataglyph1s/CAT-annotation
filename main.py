import os
import tkinter as tk
from tkinter import filedialog, messagebox

from image_viewer_controller import ImageViewerController
from app_config import AppConfig

VERSION = "v0.2.0"


class ImageViewer:
    def __init__(self, root, folder):
        self.controller = ImageViewerController(root, folder)


def _ensure_program_root(root):
    """Prompts the user to set the program root if not yet configured. Returns False if cancelled."""
    if AppConfig.get_program_root():
        return True
    messagebox.showinfo(
        "Welcome to CAT:annotation",
        "Please select a root folder where all your projects will be stored.",
        parent=root)
    path = filedialog.askdirectory(parent=root, title="Select Program Root Folder")
    if not path:
        return False
    AppConfig.set_program_root(path)
    return True


def _get_startup_folder(root):
    """Returns the last used folder if still valid, otherwise prompts the user."""
    last = AppConfig.get_last_folder()
    if last and os.path.isdir(last) and os.path.isdir(os.path.join(last, "images")):
        return last
    if last:
        messagebox.showwarning(
            "Folder not found",
            f"The last used folder could not be found:\n{last}\n\nPlease select a folder to open.",
            parent=root)
    path = filedialog.askdirectory(parent=root, title="Select a dataset folder to open")
    return path or None


if __name__ == "__main__":
    root = tk.Tk()
    root.title("CAT:annotation")
    root.withdraw()

    if not _ensure_program_root(root):
        root.destroy()
        raise SystemExit

    folder = _get_startup_folder(root)
    if not folder:
        root.destroy()
        raise SystemExit

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
