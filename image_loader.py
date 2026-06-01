import os
import json

_DEFAULT_CLASS_MAPPING = {
    0: "train", 1: "person", 2: "car", 3: "motorcycle",
    4: "bicycle", 5: "forklift", 6: "truck", 7: "excavator",
    8: "bus", 9: "railway",
}


class ImageLoader:
    def __init__(self, folder):
        self.folder = folder
        self.images_folder, self.labels_folder = self._resolve_folders(folder)
        self.index_file = os.path.join(folder, "index.json")
        self.image_files = sorted(
            f for f in os.listdir(self.images_folder)
            if f.lower().endswith(('.jpg', '.png', '.jpeg'))
        )
        self.class_mapping = self._load_class_mapping()

    def _resolve_folders(self, folder):
        """Return (images_folder, labels_folder) for any supported layout."""
        images_subdir = os.path.join(folder, "images")
        if os.path.isdir(images_subdir):
            # Standard layout: folder/images/ + folder/labels/
            return images_subdir, os.path.join(folder, "labels")

        # Nested layout: .../images/subset/ → look for .../labels/subset/
        parent = os.path.dirname(folder)
        if os.path.basename(parent) == "images":
            grandparent = os.path.dirname(parent)
            subset = os.path.basename(folder)
            labels_sibling = os.path.join(grandparent, "labels", subset)
            if os.path.isdir(labels_sibling):
                return folder, labels_sibling

        # Flat layout: images and labels in the same folder
        return folder, folder

    def _load_class_mapping(self):
        """Return class mapping from dataset.yaml if found, else the default."""
        parent = os.path.dirname(self.folder)
        grandparent = os.path.dirname(parent)
        for directory in [self.folder, parent, grandparent]:
            yaml_path = os.path.join(directory, "dataset.yaml")
            if not os.path.exists(yaml_path):
                continue
            mapping = self._parse_yaml_names(yaml_path)
            if mapping:
                return mapping
        return dict(_DEFAULT_CLASS_MAPPING)

    @staticmethod
    def _parse_yaml_names(yaml_path):
        """Minimal parser for the 'names' block of a YOLO dataset.yaml."""
        try:
            with open(yaml_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            in_names, result, list_idx = False, {}, 0
            for line in lines:
                stripped = line.strip()
                if stripped.startswith('names:'):
                    in_names = True
                    continue
                if in_names:
                    if stripped and not line[0].isspace():
                        break
                    if ':' in stripped:
                        k, _, v = stripped.partition(':')
                        try:
                            result[int(k.strip())] = v.strip()
                        except ValueError:
                            pass
                    elif stripped.startswith('- '):
                        result[list_idx] = stripped[2:].strip()
                        list_idx += 1
            return result if result else None
        except Exception:
            return None

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

    def clean_label_files(self):
        """Remove duplicate and malformed lines from all label files."""
        cleaned = 0
        for image_file in self.image_files:
            label_path = os.path.join(self.labels_folder, image_file.rsplit('.', 1)[0] + '.txt')
            if not os.path.exists(label_path):
                continue
            with open(label_path, 'r') as f:
                lines = f.readlines()
            seen = set()
            valid = []
            for line in lines:
                stripped = line.strip()
                parts = stripped.split()
                if len(parts) != 5:
                    continue
                try:
                    map(float, parts)
                except ValueError:
                    continue
                if stripped not in seen:
                    seen.add(stripped)
                    valid.append(stripped)
            if len(valid) != len([l for l in lines if l.strip()]):
                with open(label_path, 'w') as f:
                    f.write('\n'.join(valid) + ('\n' if valid else ''))
                cleaned += 1
        return cleaned

    def load_last_image_index(self):
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                data = json.load(f)
                return data.get("last_image_index", 0)
        return 0

    def save_last_image_index(self, index):
        with open(self.index_file, 'w') as f:
            json.dump({"last_image_index": index}, f)
