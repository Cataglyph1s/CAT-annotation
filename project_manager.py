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
