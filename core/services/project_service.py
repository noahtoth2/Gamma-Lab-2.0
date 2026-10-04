
import json
import shutil
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QStandardPaths

from core.filters.artifacts import reaplicar_modificaciones
from core.filters.trials import cut_trials_single_channel

SCHEMA_VERSION = "1.0"

# PAC excluded: no working compute method yet.
ANALYSIS_PLUGIN_NAMES = [
    "FFT", "FFT Average", "PSD", "PSD Average", "Relative PSD",
    "Average", "Event Related Potential", "Wavelet", "Wavelet Average",
]


_BLOCKED_STANDARD_LOCATIONS = [
    QStandardPaths.DesktopLocation,
    QStandardPaths.DocumentsLocation,
    QStandardPaths.DownloadLocation,
    QStandardPaths.PicturesLocation,
    QStandardPaths.MusicLocation,
    QStandardPaths.MoviesLocation,
    QStandardPaths.HomeLocation,
]


def _is_system_folder(folder_str: str) -> bool:
    """True if `folder_str` is a filesystem root or an OS-provided special
    folder (Desktop, Documents, Downloads, ...), not a folder the user made."""
    try:
        target = Path(folder_str).resolve()
    except Exception:
        return False

    if target.parent == target: 
        return True

    for location in _BLOCKED_STANDARD_LOCATIONS:
        for candidate in QStandardPaths.standardLocations(location):
            try:
                if target == Path(candidate).resolve():
                    return True
            except Exception:
                continue
    return False


class ProjectService:
    def __init__(self, kernel):
        self.kernel = kernel
        self.project_dir: Path | None = None
        self.glab_path: Path | None = None
        self.project_name: str | None = None  # e.g. "23n09000_gammalab" (no extension)
        self.dirty = False  # True when there are changes not yet written to the .glab
        self.on_change = None  # callback() fired on open/save/rename/close

    # ---------------- naming ----------------
    @staticmethod
    def default_project_name(signal_name: str) -> str:
        stem = Path(signal_name).stem if signal_name else "untitled"
        return f"{stem}_gammalab"

    def set_project_name(self, name: str):
        name = (name or "").strip()
        if not name:
            return
        self.project_name = name
        self.dirty = True
        self._notify()

    def mark_dirty(self):
        """Flag that something changed (e.g. a measurement) since the last save."""
        self.dirty = True

    @property
    def is_open(self) -> bool:
        return self.project_dir is not None

    def archivos_dir(self) -> Path | None:
        """Folder where exports should land. Created on demand."""
        if not self.project_dir:
            return None
        d = self.project_dir / "archivos"
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    # ---------------- internals ----------------
    def _notify(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass

    def _datastore(self):
        return self.kernel.get_service("DataStore") if self.kernel else None

    # ---------------- save ----------------
    def save(self, parent_widget=None):
        """Save to the already-known project location, or fall back to Save As."""
        if not self.is_open:
            return self.save_as(parent_widget)

        store = self._datastore()
        ds = store.get_active_signal() if store else None
        if ds is None:
            raise RuntimeError("There is no active signal to save.")

        # rename target if the project was renamed since the last save
        expected_path = self.project_dir / f"{self.project_name}.glab"
        if expected_path != self.glab_path:
            if self.glab_path and self.glab_path.exists():
                try:
                    self.glab_path.rename(expected_path)
                except Exception:
                    pass
            self.glab_path = expected_path

        self._write_manifest(ds)
        self.dirty = False
        self._notify()
        return self.glab_path

    def save_as(self, parent_widget=None):
        
        store = self._datastore()
        ds = store.get_active_signal() if store else None
        if ds is None:
            raise RuntimeError("There is no active signal to save.")

        default_name = self.project_name or self.default_project_name(ds.name)
        src = Path(getattr(ds, "source_path", "") or "")
        start_dir = str(self.project_dir or (src.parent if src.exists() else Path.cwd()))

        while True:
            folder_str = QFileDialog.getExistingDirectory(
                parent_widget, "Select Project Folder", start_dir, QFileDialog.ShowDirsOnly
            )
            if not folder_str:
                return None
            if _is_system_folder(folder_str):
                QMessageBox.warning(
                    parent_widget,
                    "Invalid Project Folder",
                    "You can't save a project directly inside a system folder "
                    "(Desktop, Documents, Downloads, Pictures, Music, Videos, or "
                    "your user folder). Please create or choose a folder of your own.",
                )
                start_dir = folder_str
                continue
            break

        self.project_dir = Path(folder_str)
        self.glab_path = self.project_dir / f"{default_name}.glab"
        self.project_name = default_name

        self._write_manifest(ds)
        self.dirty = False
        self._notify()
        return self.glab_path

    def _write_manifest(self, ds):
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.archivos_dir()

        signal_filename = self._copy_signal_into_project(ds)

        store = self._datastore()
        measurements = (store.get("measurements", []) if store else []) or []
        measurements_json = [self._measurement_to_json(m) for m in measurements]

        manifest = {
            "schema_version": SCHEMA_VERSION,
            "project_name": self.project_name,
            "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "signal": {
                "filename": signal_filename,
                "format": getattr(ds, "format", None),
                "name": getattr(ds, "name", None),
                "sampling_rate": getattr(ds, "sampling_rate", None),
                "sampling_rate_source": getattr(ds, "sampling_rate_source", None),
            },
            "measurements": measurements_json,
            "trials": self._trials_to_json(ds),
            "analysis": self._analysis_to_json(),
        }
        self.glab_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def _analysis_to_json(self) -> dict:
        
        result = {}
        if not self.kernel:
            return result
        for name in ANALYSIS_PLUGIN_NAMES:
            plugin = self.kernel.get_plugin(name)
            if plugin is None or getattr(plugin, "widget", None) is None:
                continue
            getter = getattr(plugin, "get_analysis_params", None)
            if not callable(getter):
                continue
            try:
                params = getter()
            except Exception:
                continue
            if params:
                result[name] = params
        return result

    @staticmethod
    def _trials_to_json(ds) -> list:
        
        if not hasattr(ds, "get_all_trials_datasets"):
            return []
        discards_map = ds.get_discarded_trials_map() if hasattr(ds, "get_discarded_trials_map") else {}
        entries = []
        for td in ds.get_all_trials_datasets():
            params = (td.metadata or {}).get("generation_params")
            if not params:
                continue  # generated before this feature existed, or by another path
            discarded = sorted(discards_map.get((ds.name, td.channel_name), set()))
            entry = {"generation_params": params, "discarded_indices": discarded}
            # Las modificaciones de artifact_remove se guardan como receta, no
            # como datos: el proyecto guarda cómo se generó cada cosa (nº 21).
            mods = (td.metadata or {}).get("modificaciones")
            if mods:
                entry["modifications"] = list(mods)
            entries.append(entry)
        return entries

    def _copy_signal_into_project(self, ds):
        src = Path(getattr(ds, "source_path", "") or "")
        if not src.exists():
            return None
        dest = self.project_dir / src.name
        try:
            if dest.resolve() != src.resolve():
                shutil.copy2(src, dest)
        except Exception:
            pass
        return dest.name

    @staticmethod
    def _measurement_to_json(m: dict) -> dict:
        m2 = dict(m)
        for k in ("p1", "p2"):
            if k in m2 and isinstance(m2[k], (tuple, list)):
                m2[k] = list(m2[k])
        return m2

    @staticmethod
    def _measurement_from_json(m: dict) -> dict:
        m2 = dict(m)
        for k in ("p1", "p2"):
            if k in m2 and isinstance(m2[k], list):
                m2[k] = tuple(m2[k])
        return m2

    # ---------------- open ----------------
    def open(self, glab_path_str, parent_widget=None):
        glab_path = Path(glab_path_str)
        manifest = json.loads(glab_path.read_text(encoding="utf-8"))

        self.project_dir = glab_path.parent
        self.glab_path = glab_path
        self.project_name = manifest.get("project_name") or glab_path.stem

        sig_info = manifest.get("signal") or {}
        signal_filename = sig_info.get("filename")
        ds = None
        if signal_filename:
            signal_path = self.project_dir / signal_filename
            if signal_path.exists():
                ds = self._load_signal_file(signal_path)

        if ds is not None and sig_info.get("sampling_rate_source") == "manual":
            saved_fs = sig_info.get("sampling_rate")
            if saved_fs:
                try:
                    ds.set_sampling_rate(float(saved_fs))
                except ValueError:
                    pass

        if ds is not None:
            self._restore_trials(ds, manifest.get("trials") or [])

        store = self._datastore()
        if store is not None:
            measurements = manifest.get("measurements") or []
            store.set("measurements", [self._measurement_from_json(m) for m in measurements])

        if ds is not None:
            self._restore_analysis(manifest.get("analysis") or {})

        self.dirty = False
        self._notify()
        return manifest

    def _load_signal_file(self, path: Path):
        """Load the signal file and make it active. Returns the SignalDataset, or None."""
        fileio = self.kernel.get_service("FileIO") if self.kernel else None
        store = self._datastore()
        if not fileio or not store:
            return None

        ext = path.suffix.lower()
        ds = None
        if ext == ".abf" and hasattr(fileio, "load_abf"):
            ds = fileio.load_abf(str(path))
        elif ext == ".edf" and hasattr(fileio, "load_edf"):
            ds = fileio.load_edf(str(path))
        elif ext == ".mat" and hasattr(fileio, "load_mat"):
            ds = fileio.load_mat(str(path))

        if ds is not None:
            key = store.add_signal(ds, ds.name)
            store.set_active_signal(key)
            if self.kernel:
                try:
                    self.kernel.emit_event("signal_added", {"key": key})
                except Exception:
                    pass
        return ds

    @staticmethod
    def _restore_trials(ds, trials_info: list):
      
        for entry in trials_info:
            params = entry.get("generation_params") or {}
            if not params:
                continue
            try:
                td = cut_trials_single_channel(ds=ds, **params)
                td.metadata["generation_params"] = params
                ds.add_trial_dataset(td)
                for idx in entry.get("discarded_indices", []):
                    ds.discard_trial(ds.name, td.channel_name, idx)
                # Después de los descartes, porque cada receta guarda los
                # descartes que estaban vigentes cuando se aplicó (nº 21).
                recetas = entry.get("modifications") or []
                if recetas:
                    n = reaplicar_modificaciones(td, recetas)
                    if n != len(recetas):
                        print(f"[ProjectService] Se reaplicaron {n} de {len(recetas)} "
                              f"modificaciones de artefactos en el canal {td.channel_name}.")
            except Exception:
                pass

    def _restore_analysis(self, analysis_info: dict):
       
        if not analysis_info or not self.kernel:
            return
        mainwin = self.kernel.get_service("MainWindow")
        parent = getattr(mainwin, "plugin_area", None) if mainwin else None

        for name, params in analysis_info.items():
            plugin = self.kernel.get_plugin(name)
            if plugin is None:
                continue
            try:
                if not getattr(plugin, "started", False):
                    plugin.start(self.kernel)
                    plugin.started = True
                widget = plugin.get_widget(parent=parent)
                if mainwin is not None and widget is not None:
                    mainwin.plugin_widgets[name] = widget
                    if mainwin.plugin_layout is not None and mainwin.plugin_layout.indexOf(widget) == -1:
                        mainwin.plugin_layout.addWidget(widget)
                    widget.setVisible(False)
                setter = getattr(plugin, "apply_analysis_params", None)
                if callable(setter):
                    setter(params)
            except Exception as e:
                print(f"[ProjectService] Could not restore analysis '{name}':", e)

    # ---------------- close ----------------
    def close(self):
        self.project_dir = None
        self.glab_path = None
        self.project_name = None
        self.dirty = False
        self._notify()
