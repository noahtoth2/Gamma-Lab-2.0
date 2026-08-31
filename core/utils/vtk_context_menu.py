# ui/vtk_context_menu.py
from PyQt5.QtWidgets import QMenu, QApplication
from PyQt5.QtCore import Qt
from vtk import vtkChartXY, vtkChart
import os

from core.services.export_service import ExportService
from core.services.measurement_service import MeasurementService
from core.services.settings_service import SettingsService


class VTKContextMenu:
    """
    General context menu for VTK-based views.
    - Zoom and shortcuts (Ctrl/Shift + wheel)
    - Registerable custom actions
    - Delegation to services: ExportService and MeasurementService
    - Extended context for measurements (view_id, trial_id, channel_name, plugin, domain, graph_id)
    """
    last_export_dir = os.getcwd()

    _CLICK_EPS = 8
    _PICK_RADIUS_PX = 20

    def __init__(
        self,
        chart: vtkChartXY,
        vtk_widget,
        signal_name=None,           
        channel_name=None,           
        plugin_name=None,
        *,
        measurements_enabled=True,
        measure_scope=None,    
        parent=None
    ):
        self.chart = chart
        self.vtk_widget = vtk_widget
        self.parent = parent

        self.signal_name = signal_name
        self.channel_name = channel_name
        self.plugin_name = plugin_name

        self._measurements_enabled = bool(measurements_enabled)
        self._measure_scope = dict(measure_scope or {})   # defensive copy

        self.custom_actions = []
        self._datastore = None
        self._debug = True

        # Persistent settings service
        self.settings = SettingsService()

        # Wire zoom/mouse
        self._install_wheel_shortcuts()
        self._install_mouse_observers()

        # Ensure zoom with mouse wheel
        for ch in self._get_charts():
            if ch:
                ch.SetZoomWithMouseWheel(True)
                ch.SetAxisZoom(0, True)
                ch.SetAxisZoom(1, True)

        # Context menu
        self.vtk_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.vtk_widget.customContextMenuRequested.connect(self.show_menu)

        # Services
        def _get_names():
            return (self.signal_name or "signal",
                    self.channel_name or None,
                    self.plugin_name or "plugin")


        def _get_last_dir():
            return self.settings.get("last_export_dir", os.getcwd())

        def _set_last_dir(path):
            self.settings.set("last_export_dir", path)
            VTKContextMenu.last_export_dir = path

        self.export_service = ExportService(
            parent=self.parent,
            vtk_widget=self.vtk_widget,
            get_active_chart=self._active_chart,
            get_names=_get_names,
            last_dir_getter=_get_last_dir,
            last_dir_setter=_set_last_dir
        )

        def _ds_get(k, default=None):
            try:
                return self._datastore.get(k, default) if self._datastore else default
            except Exception:
                return default

        def _ds_set(k, v):
            try:
                if self._datastore:
                    self._datastore.set(k, v)
            except Exception:
                pass

        self.measure_service = MeasurementService(
            parent=self.parent,
            vtk_widget=self.vtk_widget,
            get_active_chart=self._active_chart,
            datastore_get=_ds_get,
            datastore_set=_ds_set,
            pick_radius_px=self._PICK_RADIUS_PX,
            debug=False 
        )

        if self._measure_scope:
            self._apply_measure_scope_to_service()

    # ---------- utils ----------
    def _log(self, *args):
        if self._debug:
            print(*args)

    def _get_charts(self):
        if isinstance(self.chart, list):
            return [ch for ch in self.chart if ch is not None]
        return [self.chart] if self.chart is not None else []

    def _active_chart(self):
        return (self.chart[0] if isinstance(self.chart, list) and self.chart else self.chart)

    # ---------- public setters ----------
    def set_signal_name(self, name):
        self.signal_name = name

    def set_channel_name(self, name):
        self.channel_name = name
        self._measure_scope["channel_name"] = name
        self._apply_measure_scope_to_service()

    def set_plugin_name(self, name):
        self.plugin_name = name
        self._measure_scope["plugin"] = name
        self._apply_measure_scope_to_service()

    def set_chart(self, chart):
        self.chart = chart
        if hasattr(self, "measure_service") and self.measure_service:
            if hasattr(self.measure_service, "on_chart_changed"):
                self.measure_service.on_chart_changed()

    def set_datastore(self, store):
        """Inject the DataStore service (dict-like with get/set)."""
        self._datastore = store

    def set_measurements_enabled(self, enabled: bool):
        self._measurements_enabled = bool(enabled)

    def set_measurement_context(
        self,
        *,
        view_id: str = None,
        trial_id: int | None = None,
        channel_name: str = None,
        plugin: str = None,
        domain: str = None,
        graph_id: str = None
    ):
        if view_id is not None:      self._measure_scope["view_id"] = view_id
        if trial_id is not None:     self._measure_scope["trial_id"] = trial_id
        if channel_name is not None: self._measure_scope["channel_name"] = channel_name
        if plugin is not None:       self._measure_scope["plugin"] = plugin
        if domain is not None:       self._measure_scope["domain"] = domain
        if graph_id is not None:     self._measure_scope["graph_id"] = graph_id
        self._apply_measure_scope_to_service()

    def _apply_measure_scope_to_service(self):
        try:
            self.measure_service.set_context(**self._measure_scope)
        except Exception:
            pass

    # ---------- wheel ----------
    def _install_wheel_shortcuts(self):
        old_wheel_event = self.vtk_widget.wheelEvent

        def custom_wheel_event(event):
            modifiers = QApplication.keyboardModifiers()
            for ch in self._get_charts():
                if not ch:
                    continue
                ch.SetZoomWithMouseWheel(True)
                if modifiers == Qt.ControlModifier:
                    ch.SetAxisZoom(0, True);  ch.SetAxisZoom(1, False)
                elif modifiers == Qt.ShiftModifier:
                    ch.SetAxisZoom(0, False); ch.SetAxisZoom(1, True)
                else:
                    ch.SetAxisZoom(0, True);  ch.SetAxisZoom(1, True)
            old_wheel_event(event)

        self.vtk_widget.wheelEvent = custom_wheel_event

    # ---------- menu ----------
    def add_action(self, text, callback):
        self.custom_actions.append((text, callback))

    def _can_measure_current_chart(self) -> bool:
        ch = self._active_chart()
        if not ch:
            return False
        try:
            return ch.GetNumberOfPlots() > 0
        except Exception:
            return False

    def show_menu(self, pos):
        menu = QMenu()

        # Zoom
        zoom_menu = menu.addMenu("Zoom")
        zoom_menu.addAction("Horizontal (X)", lambda: self.set_zoom_mode("x"))
        zoom_menu.addAction("Vertical (Y)",   lambda: self.set_zoom_mode("y"))
        zoom_menu.addAction("Both axes (X+Y)", lambda: self.set_zoom_mode("xy"))
        zoom_menu.addAction("Reset view", self.reset_zoom)

        # Measurements
        measure_menu = menu.addMenu("Measurements")
        act_slope = measure_menu.addAction(
            "Slope (2 points)",
            lambda: self.measure_service.start('slope')
        )
        act_amp = measure_menu.addAction(
            "Amplitude (2 points)",
            lambda: self.measure_service.start('amplitude')
        )
        act_slope_all_trials = measure_menu.addAction(
            "Slope (all trials)",
            lambda: self.measure_service.start('slope_all_trials')
        )

        can_measure = self._measurements_enabled and self._can_measure_current_chart()
        act_slope.setEnabled(can_measure and self.measure_service.state == 'idle')
        act_amp.setEnabled(can_measure and self.measure_service.state == 'idle')
        act_slope_all_trials.setEnabled(can_measure and self.measure_service.state == 'idle')

        act_cancel = measure_menu.addAction("Cancel measurement (Esc)", self.measure_service.cancel)
        act_cancel.setEnabled(self.measure_service.state != 'idle')
        measure_menu.addSeparator()

        act_show_lines = measure_menu.addAction("Show/Hide all lines", self.measure_service.toggle_overlay)
        act_show_lines.setEnabled(can_measure)
        act_delete_last = measure_menu.addAction("Delete last measurement", self.measure_service.remove_last_measurement)
        act_delete_last.setEnabled(can_measure)
        act_delete_all = measure_menu.addAction("Delete ALL measurements", self.measure_service.clear_all_measurements)
        act_delete_all.setEnabled(can_measure)

        # Export
        menu.addSeparator()
        export_img_menu = menu.addMenu("Export as image")
        export_img_menu.addAction("png",  lambda: self.export_service.export_image("png"))
        export_img_menu.addAction("jpg",  lambda: self.export_service.export_image("jpg"))
        export_img_menu.addAction("jpeg", lambda: self.export_service.export_image("jpeg"))  # fix: 'jpegpg' -> 'jpeg'
        export_img_menu.addAction("bmp",  lambda: self.export_service.export_image("bmp"))
        export_img_menu.addAction("tiff", lambda: self.export_service.export_image("tiff"))

        export_table_menu = menu.addMenu("Export table")
        export_table_menu.addAction("csv",  lambda: self.export_service.export_table("csv"))
        export_table_menu.addAction("json", lambda: self.export_service.export_table("json"))
        export_table_menu.addAction("xlsx", lambda: self.export_service.export_table("xlsx"))

        # Acciones personalizadas
        if self.custom_actions:
            menu.addSeparator()
            for text, cb in self.custom_actions:
                menu.addAction(text, cb)

        menu.exec_(self.vtk_widget.mapToGlobal(pos))

    # ---------- export ----------
    def export_image(self, fmt: str, filename: str = None):
        self.export_service.export_image(fmt, filename)

    def export_table(self, fmt: str, filename: str = None):
        self.export_service.export_table(fmt, filename)

    # ---------- zoom ----------
    def set_zoom_mode(self, mode):
        for ch in self._get_charts():
            if not ch:
                continue
            if mode == "x":
                ch.SetAxisZoom(0, True);  ch.SetAxisZoom(1, False)
            elif mode == "y":
                ch.SetAxisZoom(0, False); ch.SetAxisZoom(1, True)
            elif mode == "xy":
                ch.SetAxisZoom(0, True);  ch.SetAxisZoom(1, True)

    def reset_zoom(self):
        for ch in self._get_charts():
            try:
                ch.RecalculateBounds()
            except AttributeError:
                pass

    # ---------- eventos mouse ----------
    def _install_mouse_observers(self):
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        iren.AddObserver("LeftButtonPressEvent", self._on_left_press, 1.0)
        iren.AddObserver("LeftButtonReleaseEvent", self._on_left_release, 1.0)
        iren.AddObserver("MouseMoveEvent", self._on_mouse_move_block_hover, 1.0)

    def _on_left_press(self, obj, evt):
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        sx, sy = iren.GetEventPosition()
        self.measure_service.on_left_press(sx, sy)

    def _on_left_release(self, obj, evt):
        if self.measure_service.state == 'idle':
            return
        iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        sx, sy = iren.GetEventPosition()
        self.measure_service.on_left_release(sx, sy, click_eps=self._CLICK_EPS)

    def _on_mouse_move_block_hover(self, obj, evt):
        if self.measure_service.state == 'idle':
            return
        return 1

    # ---------- hooks/contexto ----------
    def rebuild_measurement_overlays(self):
        if hasattr(self, "measure_service") and self.measure_service:
            self.measure_service.rebuild_overlays_for_current_context()

    def clear_measurement_overlays(self):
        if hasattr(self, "measure_service") and self.measure_service:
            self.measure_service.clear_visual_overlays()

    def on_view_rebuilt(self, chart, *, view_id: str, trial_id: int | None, channel_name: str | None,
        plugin: str | None = None, domain: str | None = None, graph_id: str | None = None):
        
        """Actualizar chart + contexto extendido y reconstruir overlays."""
        self.set_chart(chart)
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

        plugin = plugin or self.plugin_name

        self.set_measurement_context(
            view_id=view_id,
            trial_id=trial_id,
            channel_name=channel_name,
            plugin=plugin,
            domain=domain,
            graph_id=graph_id
        )
        self.rebuild_measurement_overlays()
