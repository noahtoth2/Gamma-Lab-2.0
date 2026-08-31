'''
    Service to store all processed entities, such as the raw signal and trials datasets.
    Accessed via key/value pairs.
'''

from core.model.signal_dataset import SignalDataset

class DataStore:
    def __init__(self):
        self._data = {}

    # Store an entity by a unique key
    def set(self, key, value):
        self._data[key] = value

    # Get an entity by its key
    def get(self, key, default=None):
        return self._data.get(key, default)

    # Check if a key exists
    def has(self, key):
        return key in self._data
    
    # Return all items (key, value)
    def items(self):
        return list(self._data.items())
    
    # Remove an entity by its key
    def remove(self, key):
        del self._data[key]


    """
        Add a new signal to the DataStore using the file name (or a generated key).
        Returns the key used.
    """

    def add_signal(self, signal, key: str = None):
        if key is None:
            base_key = "raw_signal"
            i = 1
            while f"{base_key}_{i}" in self._data:
                i += 1
            key = f"{base_key}_{i}"
        self._data[key] = signal
        return key
    

    # Return all stored signals that are instances of SignalDataset.
    def get_signals(self):
        return {k: v for k, v in self._data.items() if isinstance(v, SignalDataset)}
    

    def set_active_signal(self, key: str):
        """
        Set the active signal using the key of a stored signal.
        Raises ValueError if the key does not exist or is not a signal.
        """
        if key not in self._data:
            raise ValueError(f"The signal with key '{key}' does not exist in the DataStore.")
        if not isinstance(self._data[key], SignalDataset):
            raise ValueError(f"Item '{key}' is not a valid signal (SignalDataset).")

        self._data["active_signal"] = key


    # Return the active signal (SignalDataset instance). Returns None if not set.
    def get_active_signal(self):
        key = self._data.get("active_signal")
        if key and key in self._data:
            return self._data[key]
        return None

    # Return the active signal key (string) or None if not set.
    def get_active_signal_key(self):
        return self._data.get("active_signal")

    # Clear the active signal reference (does not delete the signal from the DataStore).
    def clear_active_signal(self):
        if "active_signal" in self._data:
            del self._data["active_signal"]
    
    # Check whether a key corresponds to the active signal
    def is_active_signal(self, key: str):
        return self._data.get("active_signal") == key
