import os
import json

class ImageLoader:
    def __init__(self, folder):
        self.folder = folder
        self.images_folder = os.path.join(folder, "images")
        self.labels_folder = os.path.join(folder, "labels")

        self.index_file = os.path.join(folder, "index.json")

        self.image_files = [f for f in os.listdir(self.images_folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        self.image_files.sort()

        self.class_mapping = {
            0: "train",
            1: "person",
            2: "car",
            3: "motorcycle",
            4: "bicycle",
            5: "forklift",
            6: "truck",
            7: "excavator",
            8: "bus",
            9: "railway"
        }

    def get_image_and_label(self, index):
        """Returns paths to the image and corresponding label based on the index."""
        image_path = os.path.join(self.images_folder, self.image_files[index])
        label_path = os.path.join(self.labels_folder, self.image_files[index].rsplit('.', 1)[0] + '.txt')
        return image_path, label_path

    def get_class_info(self):
        return "\n".join([f"{key}: {value}" for key, value in self.class_mapping.items()])

    def get_class_names(self):
        return list(self.class_mapping.values())

    def num_images(self):
        return len(self.image_files)

    def has_images(self):
        return bool(self.image_files)

    def get_label_path(self, index):
        return os.path.join(self.labels_folder, self.image_files[index].rsplit('.', 1)[0] + '.txt')

    def delete_image(self, index):
        """Deletes both the image and its corresponding label file."""
        image_path, label_path = self.get_image_and_label(index)

        if os.path.exists(image_path):
            os.remove(image_path)

        if os.path.exists(label_path):
            os.remove(label_path)

        # Remove the file from the internal list of image files
        del self.image_files[index]

    def has_images(self):
        """Checks if there are any images available."""
        return bool(self.image_files)

    def load_last_image_index(self):
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                data = json.load(f)
                return data.get("last_image_index", 0)
        return 0

    def save_last_image_index(self, index):
        with open(self.index_file, 'w') as f:
            json.dump({"last_image_index": index}, f)
