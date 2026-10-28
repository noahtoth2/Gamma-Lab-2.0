from core import kernel
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.utils.trial_labels import trials_used
from core.utils.submuestreo import agregar_linea
from PyQt5 import QtCore
from functools import partial
from PyQt5.QtWidgets import QListWidgetItem

from plugins.analysis.time.average import compute as ca
from plugins.analysis.time.average.average_plugin_ui import Ui_Average
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
import numpy as np



class Average_plugin(IPlugin):
    def __init__(self, meta:PluginMeta):
        super().__init__(meta)
        self.vtk_widget = None
        self.renwin = None
        self.ui = None
        self.vtk_menu: VTKContextMenu | None = None


    def process(self, data: any):
        if self.vtk_widget:
            self.vtk_widget.Enable()

    def stop(self):
        print("Stopping Average")

        if self.vtk_widget:
            self.vtk_widget.Disable()   


    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_Average()
            self.ui.setupUi(self.widget)
            # Assign the widget to alerts
            self.alerts.parent = self.widget

            self.ensure_vtk()

            # Connect "Calculate Average" button
            self.ui.calculateAverageButton.clicked.connect(self._on_calculate_average)
            self.ui.clearButton.clicked.connect(self._on_clear_clicked)
            self.ui.spnFrom.valueChanged.connect(self._sync_range)
            self.ui.spnTo.valueChanged.connect(self._sync_range)
            self.ui.txtFilter.textChanged.connect(self._apply_filter)

        else:
            self.widget.setParent(parent)

        return self.widget

    def _on_clear_clicked(self):
        self.ui.chkSelectAll.setChecked(True)
        self.ui.chkSingleTrial.setChecked(False)
        self.ui.chkUseRange.setChecked(False)
        self.ui.spnSingleTrial.setValue(1)
        self.ui.spnFrom.setValue(1)
        self.ui.spnTo.setValue(1)
        self.ui.txtFilter.clear()

    def _ensure_trials_list(self, n_trials: int):
        """Rebuild the list if empty or out-of-date."""
        if self.ui.lstTrials.count() == n_trials and n_trials > 0:
            return
        self.ui.lstTrials.clear()
        self.ui.spnSingleTrial.setMaximum(max(1, n_trials))
        self.ui.spnFrom.setMaximum(max(1, n_trials))
        self.ui.spnTo.setMaximum(max(1, n_trials))
        if self.ui.spnTo.value() == 0:
            self.ui.spnTo.setValue(n_trials)

        for i in range(1, n_trials + 1):
            it = QListWidgetItem(f"Trial-{i}")
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Checked)
            it.setData(QtCore.Qt.UserRole, f"trial-{i}".lower())
            self.ui.lstTrials.addItem(it)

    def _on_calculate_average(self):
        """Load the active SignalDataset from the DataStore and use its associated TrialDataset."""

        if self.get_active_signal() is None:
            return
        
        
        trials = self.get_active_trials()
        if trials is None:
            return

        n_trials = trials.trials.shape[1]
        self._ensure_trials_list(n_trials)
        idx = self._collect_selected_indices(n_trials)
        if not idx:
            self._notify("No trials selected.", "warning")
            return

        # R41: only the selected trials enter the average
        if len(idx) == n_trials:
            used = trials_used(idx, n_trials, "average", channel=trials.channel_name)
        else:
            used = trials_used(idx, n_trials, channel=trials.channel_name)
            used["label"] = f"promedio de {used['label']}"

        # Per-sample average across trials, in the TaskService (R71)
        self.run_task(ca.promedio_trials, partial(self._on_average_done, trials, used),
                      on_failed=lambda m: self.alerts.error(f"No se pudo calcular el promedio: {m}"),
                      trials=np.array(trials.trials, copy=True), idx=list(idx))

    # ====== Trial selection (same rules as ERP) ======
    def _collect_selected_indices(self, n_trials: int) -> list[int]:
        """Positions (1-based, among valid trials) according to the selection mode."""
        ui = self.ui
        if ui.chkSelectAll.isChecked():
            return list(range(1, n_trials + 1))
        if ui.chkSingleTrial.isChecked():
            return [min(max(1, ui.spnSingleTrial.value()), n_trials)]
        if ui.chkUseRange.isChecked():
            a = min(max(1, ui.spnFrom.value()), n_trials)
            b = min(max(1, ui.spnTo.value()), n_trials)
            if a > b:
                a, b = b, a
            return list(range(a, b + 1))
        return [i + 1 for i in range(ui.lstTrials.count())
                if ui.lstTrials.item(i).checkState() == QtCore.Qt.Checked]

    def _sync_range(self):
        if self.ui.spnFrom.value() > self.ui.spnTo.value():
            self.ui.spnTo.setValue(self.ui.spnFrom.value())

    def _apply_filter(self, text: str):
        f = (text or "").lower().strip()
        for i in range(self.ui.lstTrials.count()):
            match = (f in self.ui.lstTrials.item(i).data(QtCore.Qt.UserRole)) if f else True
            self.ui.lstTrials.setRowHidden(i, not match)

    def _on_average_done(self, trials, used, av_data):
        t = trials.time_rel

        self._trials_used = used
        self._notify(f"Average computed with {used['label']}")

        
        # Render in VTK
        self.render_average(t, av_data, trials.channel_name, trials.unit)
        self.publish_current_trial()
        self.mark_project_dirty()

    # ====== Project save/restore ======
    def get_analysis_params(self) -> dict:
        ui = self.ui
        if ui.chkSelectAll.isChecked():
            mode = "all"
        elif ui.chkSingleTrial.isChecked():
            mode = "single"
        elif ui.chkUseRange.isChecked():
            mode = "range"
        else:
            mode = "manual"
        manual = [i + 1 for i in range(ui.lstTrials.count())
                  if ui.lstTrials.item(i).checkState() == QtCore.Qt.Checked] if mode == "manual" else []
        return {
            "used": True,
            "mode": mode,
            "single_trial": ui.spnSingleTrial.value(),
            "range_from": ui.spnFrom.value(),
            "range_to": ui.spnTo.value(),
            "manual_checked_indices": manual,
            "trials_used": self._trials_used,
        }

    def apply_analysis_params(self, params: dict):
        ui = self.ui
        mode = params.get("mode", "all")   # projects saved before R41 have no mode: all trials
        ui.chkSelectAll.setChecked(mode == "all")
        ui.chkSingleTrial.setChecked(mode == "single")
        ui.chkUseRange.setChecked(mode == "range")
        ui.spnSingleTrial.setValue(params.get("single_trial", ui.spnSingleTrial.value()))
        ui.spnFrom.setValue(params.get("range_from", ui.spnFrom.value()))
        ui.spnTo.setValue(params.get("range_to", ui.spnTo.value()))
        if mode == "manual":
            trials = self.get_active_trials()
            if trials is not None:
                self._ensure_trials_list(trials.trials.shape[1])
            checked = set(params.get("manual_checked_indices", []))
            for i in range(ui.lstTrials.count()):
                ui.lstTrials.item(i).setCheckState(QtCore.Qt.Checked if (i + 1) in checked else QtCore.Qt.Unchecked)
        self._on_calculate_average()

    def render_average(self, t, av_data, channel_name=None, unit=None):
        """
        Render the average using vtkContextView + vtkChartXY
        t: 1D array of times
        av_data: 1D array of average values
        """
        if self.view is None:
            self.ensure_vtk()

        # Basic validations
        t = np.asarray(t, dtype=float)
        av = np.asarray(av_data, dtype=float)
        if t.ndim != 1 or av.ndim != 1 or t.size != av.size:
            self.alerts.error( "Time and signal vectors must have the same 1D length.", "Render error")
            return

        # Clear scene
        scene = self.view.GetScene()
        scene.ClearItems()

        chart = vtk.vtkChartXY()
        scene.AddItem(chart)

        # Draw line (R73: at most 2000 points on screen; the data stays complete)
        plot = agregar_linea(chart, t, av, "Time (s)", f"{channel_name or 'Signal'} [{unit or ''}]")
        try:
            plot.SetWidth(1.5)
            # SetColor expects RGBA (0..255) in some versions
            plot.SetColor(0, 0, 0, 255)
        except Exception:
            pass

        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Time (s)")
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle(unit or "Amplitude")
        etiqueta = (self._trials_used or {}).get("label")
        chart.SetTitle(f"Average - {channel_name or ''}" + (f" — {etiqueta}" if etiqueta else ""))

        # --- Context menu ---

        signal_name = self.active_signal.name
        ch_name = channel_name or "channel"
        graph_uid = f"average"
        
        if self.vtk_menu is not None:
            self.vtk_menu.on_view_rebuilt(
                chart,
                view_id="average",
                trial_id=None,
                channel_name=f"{signal_name}:{ch_name}",
                plugin=self.meta.id,
                domain=self.meta.subcategory,
                graph_id=graph_uid
            )
        # --- End context menu ---

        # Force render
        try:
            self.view.GetRenderWindow().Render()
        except Exception:
            # Fallback: if view lacks a RenderWindow use vtk_widget
            try:
                self.vtk_widget.GetRenderWindow().Render()
            except Exception:
                pass


    def ensure_vtk(self):
        """Create and initialize VTK widgets and the context view."""
        # Create QVTK inside the container defined in the .ui
        if not self.vtk_widget:
            self.vtk_widget = QVTKRenderWindowInteractor(self.ui.plotArea)
            
            layout = QVBoxLayout(self.ui.plotArea)
            layout.setContentsMargins(0, 0, 0, 0)
            self.ui.plotArea.setLayout(layout)
            layout.addWidget(self.vtk_widget)

        # ContextView (facilitates charting)
        self.view = vtk.vtkContextView()
        self.view.SetRenderWindow(self.vtk_widget.GetRenderWindow())
        self.view.GetRenderer().SetBackground(0.98, 0.98, 0.98)
        self.vtk_widget.Initialize()
        
        # Menu
        if self.vtk_menu is None:
            base_scope = {
                "view_id": "average",
                "graph_id": "average:blank",
                "trial_id": None,           
                "channel_name": None,       
                "plugin": "average",
                "domain": "time",
            }
            try:
                self.vtk_menu = VTKContextMenu(
                    chart=None,
                    vtk_widget=self.vtk_widget,
                    plugin_name="average",
                    measurements_enabled=True,
                    measure_scope=base_scope,
                    parent=self.widget
                )
                self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))
            except Exception as e:            
                self.alerts.error(f"Error creating contextual menu\n {str(e)}", "Contextual menu")



   
