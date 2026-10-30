import os
import json
import shutil

from core.utils.rutas import carpeta_de_datos

class SettingsService:
    """
    Simple service to save and load persistent settings in a JSON file.

    The file lives in the user's data folder (R39), not next to the code, which is
    read-only once installed. A file left next to the code by an older version is copied once.
    """
    def __init__(self, filename="gamma_lab_settings.json", carpeta=None):
        self.filename = os.path.join(carpeta or carpeta_de_datos(), filename)
        if carpeta is None and not os.path.exists(self.filename):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            anterior = os.path.join(base_dir, filename)
            if os.path.isfile(anterior):
                try:
                    shutil.copyfile(anterior, self.filename)
                except OSError:
                    pass
        self.data = {}
        self.load()

    def load(self):
        """Load the file if it exists."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        else:
            self.data = {}

    def save(self):
        """Persist current settings to the file."""
        try:
            with open(self.filename, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[SettingsService] Error saving settings: {e}")

    def get(self, key, default=None):
        """Get a stored value."""
        return self.data.get(key, default)

    def set(self, key, value):
        """Set a value and persist it."""
        self.data[key] = value
        self.save()
