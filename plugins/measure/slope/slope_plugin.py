# plugins/measure/slope/slope_plugin.py
import os
import csv
from datetime import datetime
from typing import Any, Dict, List

from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QFileDialog, QHeaderView

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.services.settings_service import SettingsService
from plugins.measure.slope.slope_plugin_ui import Ui_Slope


class SlopeTableModel(QtCore.QAbstractTableModel):
    """
    Table model for slope measurements.
    """
    HEADERS = [
        "ID",                 # 0
        "Channel",            # 1  <-- ctx.channel_name
        "Graph",          # 2  <-- ctx.graph_id
        "Point 1 (x, y)",     # 3
        "Point 2 (x, y)",     # 4
        "Δx",                 # 5
        "Δy",                 # 6
        "Slope (m)",          # 7
        "Distance",           # 8
        "Timestamp",          # 9
    ]

    HEADER_TIPS = {
        0: "Unique measurement ID.",
        1: "Channel associated with this measurement (from ctx.channel_name).",
        2: "Unique Graph ID from which the measurement was taken (ctx.graph_id).",
        3: "Coordinates of the first point (x, y).",
        4: "Coordinates of the second point (x, y).",
        5: "Difference in x: Δx = x2 − x1.",
        6: "Difference in y: Δy = y2 − y1.",
        7: "Slope m = Δy / Δx (if Δx = 0, m = ∞).",
        8: "Euclidean distance between P1 and P2.",
        9: "Timestamp when the measurement was saved.",
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
            5: r.get("dx"),
            6: r.get("dy"),
            7: r.get("slope"),
            8: r.get("dist"),
            9: r.get("timestamp"),
        }
        return self._fmt(mapping.get(c))

    def set_rows(self, rows: List[Dict[str, Any]]):
        self.beginResetModel()
        self._rows = rows or []
        self.endResetModel()

    def get_all_rows(self) -> List[Dict[str, Any]]:
        return list(self._rows)


# ----------------------------
# Slope Plugin
# ----------------------------
class SlopePlugin(IPlugin):

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.settings = SettingsService()


        # UI
        self.widget: QtWidgets.QWidget | None = None
        self.ui: Ui_Slope | None = None

        # Table model
        self.model: SlopeTableModel | None = None


    # ---------- Lifecycle ----------

    def stop(self):
        self._log("stop()")

    def process(self, data: Any):
        self._log("process(): refreshing table")
        self._reload_from_store()

    # ---------- UI ----------
    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget(): creating UI")
            self.ui = Ui_Slope()
            self.widget = QtWidgets.QWidget(parent)
            self.alerts.parent = self.widget
            self.ui.setupUi(self.widget)

            # Model + table setup
            self.model = SlopeTableModel([])
            tv = self.ui.tableView
            tv.setModel(self.model)
            tv.setSortingEnabled(True)
            tv.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            tv.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            tv.setAlternatingRowColors(True)
            tv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            tv.verticalHeader().setVisible(False)

            # Export CSV button
            self.ui.pushButton.setText("Export CSV")
            self.ui.pushButton.clicked.connect(self._on_export_csv)

            # Initial load
            self._reload_from_store()
        else:
            self.widget.setParent(parent)
        return self.widget

    # ---------- DataStore ----------
    def _reload_from_store(self):
        rows = self._load_slope_rows_from_store()
        if self.model:
            self.model.set_rows(rows)
        self._notify(f"Slope: {len(rows)} measurements")

    def _load_slope_rows_from_store(self) -> List[Dict[str, Any]]:
        """
        Reads DataStore['measurements'] (or 'meassurements'),
        filters type='slope', and normalizes rows with:
            id, p1x, p1y, p2x, p2y, dx, dy, slope, dist, timestamp
        Also extracts from context:
            ctx_channel = ctx.channel_name
            ctx_graph   = ctx.graph_id
        """
        # Get DataStore service
        store = self.get_datastore()
        if store is None:
            return []

        # Raw list
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
            self._log("DataStore['measurements'] empty or invalid.")
            return []

        rows: List[Dict[str, Any]] = []
        seq = 0
        for item in raw:
            try:
                if not isinstance(item, dict) or item.get("type") != "slope":
                    continue

                p1 = item.get("p1")
                p2 = item.get("p2")
                if not (isinstance(p1, (list, tuple)) and isinstance(p2, (list, tuple)) and len(p1) == 2 and len(p2) == 2):
                    continue

                p1x, p1y = float(p1[0]), float(p1[1])
                p2x, p2y = float(p2[0]), float(p2[1])

                dx = item.get("dx");    dx = float(dx) if dx is not None else (p2x - p1x)
                dy = item.get("dy");    dy = float(dy) if dy is not None else (p2y - p1y)
                slope = item.get("slope"); slope = float(slope) if slope is not None else (dy / dx if dx != 0 else float("inf"))
                dist = item.get("dist"); dist = float(dist) if dist is not None else ((dx**2 + dy**2) ** 0.5)

                mid = item.get("id")
                if not mid:
                    seq += 1
                    mid = f"slope-{seq:03d}"

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
                    "id": mid, "type": "slope",
                    "p1x": p1x, "p1y": p1y, "p2x": p2x, "p2y": p2y,
                    "dx": dx, "dy": dy, "slope": slope, "dist": dist,
                    "timestamp": ts,
                    "ctx_channel": ch_name,
                    "ctx_graph": graph_uid,
                })
            except Exception as e:
                self._log("Invalid row in measurements:", e)

        return rows

    # ---------- Export ----------
    def _on_export_csv(self):
        if not self.model:
            return
        rows = self.model.get_all_rows()
        if not rows:
            self.alerts.warning("No measurements to export.")
            return

        path_initial = self.settings.get("last_export_dir", os.getcwd())

        path, _ = QFileDialog.getSaveFileName(
            self.widget,
            "Export slope measurements to CSV",
            path_initial + "slope_measurements.csv",
            "CSV (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                # Header: same order as UI
                w.writerow(SlopeTableModel.HEADERS)
                for r in rows:
                    p1 = "" if (r.get("p1x") is None or r.get("p1y") is None) else f"({r.get('p1x')},{r.get('p1y')})"
                    p2 = "" if (r.get("p2x") is None or r.get("p2y") is None) else f"({r.get('p2x')},{r.get('p2y')})"
                    w.writerow([
                        r.get("id", ""),
                        r.get("ctx_channel", ""),
                        r.get("ctx_graph", ""),
                        p1,
                        p2,
                        r.get("dx", ""),
                        r.get("dy", ""),
                        r.get("slope", ""),
                        r.get("dist", ""),
                        r.get("timestamp", ""),
                    ])
            self._notify(f"CSV exported successfully: {path}")
        except Exception as e:
            self.alerts.error(f"Failed to export CSV:\n{e}")
