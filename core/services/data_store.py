'''
    Service to store all processed entities, such as the raw signal and trials datasets.
    Accessed via key/value pairs.
'''

import threading
from functools import wraps

from core.model.signal_dataset import SignalDataset


class EscrituraNoPermitida(PermissionError):
    """Alguien que no es el propietario intentó escribir en el DataStore (R54)."""


def _escribe(metodo):
    """Marca un método como escritura: exige ser el hilo propietario y toma el candado."""
    @wraps(metodo)
    def envuelto(self, *args, **kwargs):
        self._exigir_propietario()
        with self._lock:
            return metodo(self, *args, **kwargs)
    return envuelto


class DataStore:
    """Estado compartido de la sesión (R54).

    - **Un solo escritor:** solo el hilo que creó el DataStore (el de la interfaz)
      puede escribir. Una tarea del orquestador devuelve su resultado por la señal
      `finished`, que llega a ese hilo, y es ahí donde se publica; si intenta escribir
      directamente, recibe `EscrituraNoPermitida` en vez de provocar una carrera.
    - **Lectura segura:** todas las operaciones toman un candado reentrante, así que
      un hilo que lee nunca ve el diccionario a medias.
    - **Dueño por dato (opcional):** `set(clave, valor, owner=...)` reserva la clave
      para ese dueño; otro dueño no puede sobrescribirla mientras exista.
    """

    def __init__(self):
        self._data = {}
        self._lock = threading.RLock()
        self._propietario = threading.get_ident()
        self._duenos = {}

    # ---------- propiedad ----------
    def _exigir_propietario(self):
        if threading.get_ident() != self._propietario:
            raise EscrituraNoPermitida(
                "El DataStore solo se escribe desde el hilo de la interfaz; "
                "una tarea debe devolver su resultado y publicarlo allí.")

    def reasignar_propietario(self):
        """El hilo que llama pasa a ser el único escritor (p. ej. un DataStore creado en otro hilo)."""
        with self._lock:
            self._propietario = threading.get_ident()

    def dueno_de(self, key):
        with self._lock:
            return self._duenos.get(key)

    # ---------- lectura ----------
    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def has(self, key):
        with self._lock:
            return key in self._data

    def items(self):
        with self._lock:
            return list(self._data.items())

    def get_signals(self):
        """Todas las señales guardadas (instancias de SignalDataset)."""
        with self._lock:
            return {k: v for k, v in self._data.items() if isinstance(v, SignalDataset)}

    def get_active_signal(self):
        """La señal activa (SignalDataset), o None si no hay."""
        with self._lock:
            key = self._data.get("active_signal")
            if key and key in self._data:
                return self._data[key]
            return None

    def get_active_signal_key(self):
        with self._lock:
            return self._data.get("active_signal")

    def is_active_signal(self, key: str):
        with self._lock:
            return self._data.get("active_signal") == key

    # ---------- escritura ----------
    @_escribe
    def set(self, key, value, owner=None):
        actual = self._duenos.get(key)
        if owner is not None and actual is not None and actual != owner:
            raise EscrituraNoPermitida(f"'{key}' pertenece a '{actual}'; '{owner}' no puede escribirlo.")
        if owner is not None:
            self._duenos[key] = owner
        self._data[key] = value

    @_escribe
    def remove(self, key):
        del self._data[key]
        self._duenos.pop(key, None)

    @_escribe
    def add_signal(self, signal, key: str = None):
        """Añade una señal con el nombre del archivo (o una clave generada). Devuelve la clave."""
        if key is None:
            base_key = "raw_signal"
            i = 1
            while f"{base_key}_{i}" in self._data:
                i += 1
            key = f"{base_key}_{i}"
        self._data[key] = signal
        return key

    @_escribe
    def set_active_signal(self, key: str):
        """Fija la señal activa. ValueError si la clave no existe o no es una señal."""
        if key not in self._data:
            raise ValueError(f"The signal with key '{key}' does not exist in the DataStore.")
        if not isinstance(self._data[key], SignalDataset):
            raise ValueError(f"Item '{key}' is not a valid signal (SignalDataset).")
        self._data["active_signal"] = key

    @_escribe
    def release_signals(self, conservar=None):
        """Quita del DataStore las señales (con sus trials y derivados) salvo la de la clave `conservar`.

        También borra las mediciones y el trial actual, que pertenecen a la señal que se va (R11, R52).
        Devuelve las claves quitadas.
        """
        quitadas = [k for k, v in self._data.items() if isinstance(v, SignalDataset) and k != conservar]
        for k in quitadas:
            del self._data[k]
            self._duenos.pop(k, None)
        if self._data.get("active_signal") in quitadas:
            del self._data["active_signal"]
        self._data.pop("current_trial", None)
        if "measurements" in self._data:
            self._data["measurements"] = []
        return quitadas

    @_escribe
    def clear_active_signal(self):
        """Quita la referencia a la señal activa (no la borra del DataStore)."""
        self._data.pop("active_signal", None)
