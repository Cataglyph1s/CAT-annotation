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

