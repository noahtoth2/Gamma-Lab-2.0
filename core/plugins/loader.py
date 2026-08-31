import importlib.util, sys, yaml
from pathlib import Path
from typing import List, Tuple, Type
from core.plugins.meta import PluginMeta
from core.plugins.interfaces import IPlugin

REQUIRED_KEYS = [
    "id", "name", "category", "subcategory", "version",
    "icon", "logic_class", "ui_class"
]

def _ensure_root_on_path() -> None:
    """
    Add the project root to sys.path so imports like `interfaces`
    work when loading modules by path.
    """
    root = Path(__file__).resolve().parents[2]  # .../gamma-lab-desktop-app
    sroot = str(root)
    if sroot not in sys.path:
        sys.path.insert(0, sroot)

def _load_meta(folder: Path) -> PluginMeta:
    yml = folder / "properties.yml"
    if not yml.exists():
        raise FileNotFoundError(str(yml))
    data = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
    missing = [k for k in REQUIRED_KEYS if k not in data]
    if missing:
        raise ValueError(f"{folder.name}: missing {missing} in properties.yml")
    meta = PluginMeta(**data)
    meta.root = folder
    return meta

def _import_class_from_dir(dirpath: Path, class_name: str) -> Type[IPlugin]:
    """
    Search for class `class_name` inside the plugin folder without assuming
    the file name. Prioritize `plugin.py` then try any .py.
    """
    _ensure_root_on_path()

    candidates: List[Path] = []
    # 1) Priority: plugin.py if present
    if (dirpath / "plugin.py").exists():
        candidates.append(dirpath / "plugin.py")
    # 2) Any other .py in the folder (except __init__.py)
    for p in dirpath.glob("*.py"):
        if p.name in ("plugin.py", "__init__.py"):
            continue
        candidates.append(p)

    last_err = None
    for pyfile in candidates:
        try:
            # Unique module name to avoid collisions
            mod_name = f"plg_{dirpath.name}_{pyfile.stem}"
            spec = importlib.util.spec_from_file_location(mod_name, pyfile)
            if not spec or not spec.loader:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)  # type: ignore
            cls = getattr(module, class_name, None)
            if cls is not None:
                return cls
        except Exception as e:
            last_err = e
            continue

    raise ImportError(f"Class '{class_name}' not found in {dirpath} (last err: {last_err})")

def discover(plugins_root: Path) -> List[Tuple[PluginMeta, Type[IPlugin]]]:
    """
    Recursively walk `plugins_root` and consider a plugin any folder
    that contains a `properties.yml`.
    """
    results: List[Tuple[PluginMeta, Type[IPlugin]]] = []

    # Find all plugin definitions
    for yml in plugins_root.rglob("properties.yml"):
        folder = yml.parent
        # Ignore junk folders
        if any(part == "__pycache__" for part in folder.parts):
            continue
        try:
            meta = _load_meta(folder)
            PluginCls = _import_class_from_dir(folder, meta.logic_class)
            results.append((meta, PluginCls))
        except Exception as e:
            print(f"[PLUGIN] {folder.relative_to(plugins_root)} skipped: {e}")
            continue

    return results
