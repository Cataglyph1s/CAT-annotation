import tkinter as tk
from image_viewer_controller import ImageViewerController


class ImageViewer:
    def __init__(self, root, folder):
        self.controller = ImageViewerController(root, folder)


if __name__ == "__main__":
    root = tk.Tk()
    root.title("CAT.Annotation")
    folder = "C:/Users/jmouvet/Samira/Datasets/Samira_2_0/Training_Sets/Samira2Dataset003/train"
    app = ImageViewer(root, folder)
    root.mainloop()

    # ----------------------------------------------------------------------------------
    # TODO:
    # 1) Add Program Root for all Projects. Must auto ask if null
    # 2) Add Column (hideable) with project sets info on left under menu
    #       - add view button next to menu. All columns hideable and retrievable
    #       - clean view with info bar only, shortcuts work for clean annot. option
    #       - double click set name to switch to it (autosave changes on change)
    # 3) Add class colours to class column
    # 4) Add Users to project
    # 5) Zoom function for high-res/small-object annotation (small buttons + shortcut)
    # 6) Think about central save options
    # -----------------------------------------------------------------------------------