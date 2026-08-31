import os
import json

class SettingsService:
    """
    Simple service to save and load persistent settings in a JSON file.
    """
    def __init__(self, filename="gamma_lab_settings.json"):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.filename = os.path.join(base_dir, filename)
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
