import os
import json
import shutil


class ProjectManager:

    @staticmethod
    def create_project(base_folder, project_name, classes):
        """Creates the project folder and writes project.json. Returns the project path."""
        project_path = os.path.join(base_folder, project_name)
        os.makedirs(project_path, exist_ok=True)
        config = {
            "name": project_name,
            "classes": classes  # list of {id, name, color}
        }
        with open(os.path.join(project_path, "project.json"), 'w') as f:
            json.dump(config, f, indent=2)
        return project_path

    @staticmethod
    def create_image_set(project_path, set_name):
        """Creates a named set subfolder with images/ and labels/ inside it. Returns the set path."""
        set_path = os.path.join(project_path, set_name)
        os.makedirs(os.path.join(set_path, "images"), exist_ok=True)
        os.makedirs(os.path.join(set_path, "labels"), exist_ok=True)
        return set_path

    @staticmethod
    def copy_images(source_folder, dest_set_path):
        """Copies image files from source_folder into dest_set_path/images/. Returns count copied."""
        images_dir = os.path.join(dest_set_path, "images")
        os.makedirs(images_dir, exist_ok=True)
        count = 0
        for filename in os.listdir(source_folder):
            if filename.lower().endswith(('.jpg', '.jpeg', '.png')):
                shutil.copy2(os.path.join(source_folder, filename), images_dir)
                count += 1
        return count

    @staticmethod
    def load_project_config(folder):
        """Looks for project.json in folder or its parent. Returns the config dict or None."""
        for path in [folder, os.path.dirname(folder)]:
            config_path = os.path.join(path, "project.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
        return None

    @staticmethod
    def suggest_set_name(project_path):
        """Returns the next auto-suggested set name based on existing set_ folders."""
        try:
            existing = os.listdir(project_path)
        except OSError:
            existing = []
        count = len([d for d in existing
                     if d.startswith("set_") and os.path.isdir(os.path.join(project_path, d))])
        return f"set_{count + 1:03d}"

    @staticmethod
    def list_sets(project_path):
        """Returns sorted list of set folder paths that contain an images/ subdirectory."""
        sets = []
        try:
            for name in sorted(os.listdir(project_path)):
                full = os.path.join(project_path, name)
                if os.path.isdir(full) and os.path.exists(os.path.join(full, 'images')):
                    sets.append(full)
        except OSError:
            pass
        return sets

    @staticmethod
    def import_set_from_yolo(project_path, set_name, source_folder, class_map=None):
        """
        Create a new set in project_path by copying from a YOLO-format source folder.
        Handles standard (images/ + labels/), flat, and mixed layouts.
        class_map: {src_id: project_id} or None (copy labels verbatim).
        Returns (set_path, images_copied, labels_done).
        """
        set_path = ProjectManager.create_image_set(project_path, set_name)
        dst_images = os.path.join(set_path, 'images')
        dst_labels = os.path.join(set_path, 'labels')

        # Resolve source images folder
        src_images = source_folder
        if os.path.isdir(os.path.join(source_folder, 'images')):
            src_images = os.path.join(source_folder, 'images')

        # Resolve source labels folder
        src_labels = None
        candidate = os.path.join(source_folder, 'labels')
        if os.path.isdir(candidate):
            src_labels = candidate
        elif src_images == source_folder:
            # flat layout: labels sit alongside images in the same folder
            src_labels = source_folder

        # Copy images
        img_exts = {'.jpg', '.jpeg', '.png'}
        images_copied = 0
        for fname in os.listdir(src_images):
            if os.path.splitext(fname)[1].lower() in img_exts:
                shutil.copy2(os.path.join(src_images, fname),
                             os.path.join(dst_images, fname))
                images_copied += 1

        # Copy / remap labels
        labels_done = 0
        if src_labels and os.path.isdir(src_labels):
            for fname in os.listdir(src_labels):
                if not fname.endswith('.txt'):
                    continue
                src_path = os.path.join(src_labels, fname)
                dst_path = os.path.join(dst_labels, fname)
                if class_map:
                    ProjectManager._remap_label_file(src_path, dst_path, class_map)
                else:
                    shutil.copy2(src_path, dst_path)
                labels_done += 1

        return set_path, images_copied, labels_done

    @staticmethod
    def _remap_label_file(src_path, dst_path, class_map):
        """Copy a YOLO .txt label file, remapping class IDs. Lines with unmapped IDs are dropped."""
        lines_out = []
        with open(src_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                src_id = int(parts[0])
                if src_id not in class_map:
                    continue
                parts[0] = str(class_map[src_id])
                lines_out.append(' '.join(parts))
        with open(dst_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines_out))
            if lines_out:
                f.write('\n')

    @staticmethod
    def get_set_stats(set_path):
        """Returns (total_images, annotated_images) for a set folder."""
        img_exts = {'.jpg', '.jpeg', '.png'}
        images_dir = os.path.join(set_path, 'images')
        labels_dir = os.path.join(set_path, 'labels')
        total = 0
        if os.path.exists(images_dir):
            total = sum(1 for f in os.listdir(images_dir)
                        if os.path.splitext(f)[1].lower() in img_exts)
        annotated = 0
        if os.path.exists(labels_dir):
            for fname in os.listdir(labels_dir):
                if fname.endswith('.txt'):
                    lp = os.path.join(labels_dir, fname)
                    if os.path.getsize(lp) > 0:
                        annotated += 1
        return total, annotated
