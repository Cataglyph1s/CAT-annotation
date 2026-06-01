import os
import json

_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".catannotation", "config.json")


class AppConfig:

    @staticmethod
    def _load():
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, 'r') as f:
                return json.load(f)
        return {}

    @staticmethod
    def _save(config):
        os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
        with open(_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)

    @staticmethod
    def get_program_root():
        return AppConfig._load().get("program_root")

    @staticmethod
    def set_program_root(path):
        config = AppConfig._load()
        config["program_root"] = path
        AppConfig._save(config)

    @staticmethod
    def get_last_folder():
        return AppConfig._load().get("last_folder")

    @staticmethod
    def set_last_folder(path):
        config = AppConfig._load()
        config["last_folder"] = path
        AppConfig._save(config)
