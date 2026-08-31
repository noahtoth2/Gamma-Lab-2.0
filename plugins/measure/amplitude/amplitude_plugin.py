# plugins/measure/amplitude/amplitude_plugin.py
import sys
import csv
from datetime import datetime
from typing import Any, Dict, List

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QFileDialog, QHeaderView

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from plugins.measure.amplitude.amplitude_plugin_ui import Ui_Amplitude


class AmplitudeTableModel(QtCore.QAbstractTableModel):
    # User-facing headers in English
    HEADERS = [
        "ID",                 # 0
        "Channel",            # 1 (ctx.channel_name)
        "Graph",              # 2 (e.g., "trial N" from ctx.trial_id)
        "Point 1 (x, y)",     # 3
        "Point 2 (x, y)",     # 4
        "Window start (x1)",  # 5
        "Window end (x2)",    # 6
        "Samples (N)",        # 7
        "Min value (Ymin)",   # 8
        "Max value (Ymax)",   # 9
        "Amplitude (p-p)",    # 10
        "x at min",           # 11
        "x at max",           # 12
        "Timestamp",          # 13
    ]

    # Optional tooltips for headers
    HEADER_TIPS = {
        0: "Unique measurement ID.",
        1: "Channel associated with this measurement (from ctx.channel_name).",
        2: "Graph label derived from context (e.g., 'trial k').",
        3: "Coordinates of the first selected point (x, y).",
        4: "Coordinates of the second selected point (x, y).",
        5: "Lower limit of the X-axis window used for amplitude measurement.",
        6: "Upper limit of the X-axis window used for amplitude measurement.",
        7: "Number of samples considered in the [x1, x2] window.",
        8: "Minimum Y value within the window.",
        9: "Maximum Y value within the window.",
        10: "Peak-to-peak amplitude = Ymax − Ymin.",
        11: "X coordinate where the minimum (Ymin) occurs.",
        12: "X coordinate where the maximum (Ymax) occurs.",
        13: "Timestamp when the measurement was saved.",
    }

    def __init__(self, rows: List[Dict[str, Any]] | None = None, parent=None):
        super().__init__(parent)
        self._rows: List[Dict[str, Any]] = rows or []

    def rowCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QtCore.QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.DisplayRole):
        if orientation == QtCore.Qt.Horizontal:
            if role == QtCore.Qt.DisplayRole and 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
            if role == QtCore.Qt.ToolTipRole:
                return self.HEADER_TIPS.get(section)
        elif role == QtCore.Qt.DisplayRole:
            return str(section + 1)
        return None

    def _fmt(self, v):
        if isinstance(v, float):
            return f"{v:.6g}"
        return "" if v is None else str(v)

    def _fmt_xy(self, x, y):
        if x is None or y is None:
            return ""
        return f"({self._fmt(x)}, {self._fmt(y)})"

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.DisplayRole):
        if not index.isValid() or role not in (QtCore.Qt.DisplayRole, QtCore.Qt.ToolTipRole):
            return None

        r = self._rows[index.row()]
        c = index.column()

        p1x, p1y = r.get("p1x"), r.get("p1y")
        p2x, p2y = r.get("p2x"), r.get("p2y")

        mapping = {
            0: r.get("id"),
            1: r.get("ctx_channel"),
            2: r.get("ctx_graph"),
            3: self._fmt_xy(p1x, p1y),
            4: self._fmt_xy(p2x, p2y),
            5: r.get("x1"),
            6: r.get("x2"),
            7: r.get("n"),
            8: r.get("y_min"),
            9: r.get("y_max"),
            10: r.get("amp_pp"),
            11: r.get("x_at_min"),
            12: r.get("x_at_max"),
            13: r.get("timestamp"),
        }
        return self._fmt(mapping.get(c))

    def set_rows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows or []
        self.endResetModel()

    def get_all_rows(self) -> List[Dict[str, Any]]:
        return list(self._rows)


# ----------------------------
# Plugin
# ----------------------------
class AmplitudePlugin(IPlugin):

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)

        # UI
        self.widget: QtWidgets.QWidget | None = None
        self.ui: Ui_Amplitude | None = None

        # Model
        self.model: AmplitudeTableModel | None = None


    # ---------- Lifecycle ----------
    def initialize(self, kernel):
        self.kernel = kernel
        self._log("initialize()")

    def start(self, kernel):
        self.kernel = kernel
        self.mainwin = kernel.get_service("MainWindow")
        self._log("start()")

    def stop(self):
        self._log("stop()")

    def process(self, data: Any):
        self._log("process(): refreshing table")
        self._reload_from_store()

    # ---------- UI ----------
    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget(): creating UI")
            self.alerts.parent = parent
            self.ui = Ui_Amplitude()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)  # assumes Form: AmplitudeForm

            # Model + table setup
            self.model = AmplitudeTableModel([])
            tv = self.ui.tableView
            tv.setModel(self.model)
            tv.setSortingEnabled(True)
            tv.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            tv.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            tv.setAlternatingRowColors(True)
            tv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tv.verticalHeader().setVisible(False)

            # Export button
            self.ui.pushButton.setText("Export CSV")
            self.ui.pushButton.clicked.connect(self._on_export_csv)

            # Initial load
            self._reload_from_store()
        else:
            self.widget.setParent(parent)
        return self.widget

    # ---------- DataStore ----------
    def _reload_from_store(self):
        rows = self._load_amplitude_rows_from_store()
        if self.model:
            self.model.set_rows(rows)
        self._notify(f"Amplitude: {len(rows)} measurements")

    def _load_amplitude_rows_from_store(self) -> List[Dict[str, Any]]:
        """
        Reads DataStore['measurements'] (also tolerates 'meassurements'),
        filters entries of type 'amplitude' and normalizes them to:
          id, p1x, p1y, p2x, p2y, x1, x2, n, y_min, y_max, amp_pp, x_at_min, x_at_max, timestamp
        Additionally extracts context fields as in the slope example:
          ctx_channel = ctx.channel_name
          ctx_graph   = f"trial {ctx.trial_id+1}" (string)
        """
        store = None
        try:
            if self.mainwin:
                store = self.mainwin.kernel.get_service("DataStore")
            if store is None and self.kernel:
                store = self.kernel.get_service("DataStore")
        except Exception:
            store = None

        if store is None:
            self.alerts.error("DataStore service not found.")
            return []

        # Try to read from DataStore
        raw = None
        for key in ("measurements", "meassurements"):
            try:
                if hasattr(store, "get"):
                    raw = store.get(key)
                elif hasattr(store, "get_data"):
                    raw = store.get_data(key)
                elif hasattr(store, "get_value"):
                    raw = store.get_value(key)
                else:
                    raw = None
            except Exception:
                raw = None
            if raw:
                break

        if not raw or not isinstance(raw, (list, tuple)):
            self._log("DataStore['measurements'] is empty or invalid.")
            return []

        rows: List[Dict[str, Any]] = []
        seq = 0
        for item in raw:
            try:
                if not isinstance(item, dict) or item.get("type") != "amplitude":
                    continue

                p1 = item.get("p1"); p2 = item.get("p2")
                if not (isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)) and len(p1) == 2 and len(p2) == 2):
                    p1x = p1y = p2x = p2y = None
                else:
                    p1x, p1y = _f(p1[0]), _f(p1[1])
                    p2x, p2y = _f(p2[0]), _f(p2[1])

                # amplitude metrics
                x1        = _f(item.get("x1"))
                x2        = _f(item.get("x2"))
                n         = _i(item.get("n"))
                y_min     = _f(item.get("y_min"))
                y_max     = _f(item.get("y_max"))
                amp_pp    = _f(item.get("amp_pp"))
                x_at_min  = _f(item.get("x_at_min"))
                x_at_max  = _f(item.get("x_at_max"))

                mid = item.get("id")
                if not mid:
                    seq += 1
                    mid = f"amplitude-{seq:03d}"

                ts = item.get("timestamp") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                ctx = item.get("ctx") or {}
                ch_name = ctx.get("channel_name")
                
                trial_id = ctx.get("trial_id")
                graph_from_ctx = ctx.get("graph_id")
                
                if isinstance(trial_id, int) and trial_id >= 0:
                    graph_uid = f"trial {trial_id + 1}"
                    
                elif isinstance(graph_from_ctx, str) and graph_from_ctx.strip():
                    graph_uid = graph_from_ctx
                else:
                    graph_uid = ""
                    
                rows.append({
                    "id": mid,
                    "ctx_channel": ch_name,
                    "ctx_graph": graph_uid,
                    "p1x": p1x, "p1y": p1y, "p2x": p2x, "p2y": p2y,
                    "x1": x1, "x2": x2, "n": n,
                    "y_min": y_min, "y_max": y_max, "amp_pp": amp_pp,
                    "x_at_min": x_at_min, "x_at_max": x_at_max,
                    "timestamp": ts
                })
            except Exception as e:
                self._log("Invalid row in measurements (amplitude):", e)

        return rows

    # ---------- Export ----------
    def _on_export_csv(self):
        if not self.model:
            return
        rows = self.model.get_all_rows()
        if not rows:
            self.alerts.error("No measurements to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "Export amplitude measurements to CSV",
            "amplitude_measurements.csv",
            "CSV (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                # Header: same order as UI
                w.writerow(AmplitudeTableModel.HEADERS)
                for r in rows:
                    p1 = f"({r.get('p1x', '')},{r.get('p1y', '')})" if r.get("p1x") is not None and r.get("p1y") is not None else ""
                    p2 = f"({r.get('p2x', '')},{r.get('p2y', '')})" if r.get("p2x") is not None and r.get("p2y") is not None else ""
                    w.writerow([
                        r.get("id", ""),
                        r.get("ctx_channel", ""),
                        r.get("ctx_graph", ""),
                        p1,
                        p2,
                        r.get("x1", ""),
                        r.get("x2", ""),
                        r.get("n", ""),
                        r.get("y_min", ""),
                        r.get("y_max", ""),
                        r.get("amp_pp", ""),
                        r.get("x_at_min", ""),
                        r.get("x_at_max", ""),
                        r.get("timestamp", ""),
                    ])
            self._notify(f"CSV exported: {path}")
        except Exception as e:
            self.alerts.error(f"Failed to export CSV:\n{e}")


# --- Local helpers for safe casting ---
def _f(v):
    try:
        return float(v) if v is not None else None
    except Exception:
        return None

def _i(v):
    try:
        return int(v) if v is not None else None
    except Exception:
        try:
            return int(float(v))
        except Exception:
            return None
