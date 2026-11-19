import os
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QListWidgetItem
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import numpy as np
from vtkmodules.util import numpy_support
from typing import Tuple

from core.utils.emf_writer import anotar_mapa
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from plugins.analysis.time.erp import compute as ce
from plugins.analysis.time.erp.erp_plugin_ui import Ui_ErpPlot
from core.utils.adapters import trials_matrix_to_vtk_table
from core.utils.trial_labels import trials_used
from functools import partial
from core.utils.submuestreo import agregar_columna, agregar_linea


def calcular_erp(t, M, idx, ctx=None):
    """Selects the trials (1-based `idx`) and prepares the heat map. Pure, for the TaskService."""
    sel = M[np.array(idx) - 1, :]
    return sel, ce.preparar_mapa_calor(t, sel)


class Erp_plugin(IPlugin):
    MAX_CURVAS = 200

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.vtk_widget = None
        self.renwin = None
        self.td = None
        self.ch_name = None
        
        self.vtk_top: QVTKRenderWindowInteractor | None = None
        self.vtk_bot: QVTKRenderWindowInteractor | None = None
        self.view_top: vtk.vtkContextView | None = None
        self.view_bot: vtk.vtkContextView | None = None

        self._t = None
        self._sel = None
        self._sel_ids = None
        self._group_idx = 0


    def process(self, data: any):
        print(f"ERP received data: {data}")

        print("[TrialsPlugin] process")
        if self.vtk_top and self.vtk_top.GetRenderWindow().GetInteractor():
            self.vtk_top.GetRenderWindow().GetInteractor().Enable()

        if self.vtk_bot and self.vtk_bot.GetRenderWindow().GetInteractor():
                self.vtk_bot.GetRenderWindow().GetInteractor().Enable()

      

    def stop(self):
        print("[TrialsPlugin] stop")
        if self.vtk_top and self.vtk_top.GetRenderWindow().GetInteractor():
            self.vtk_top.GetRenderWindow().GetInteractor().Disable()

        if self.vtk_bot and self.vtk_bot.GetRenderWindow().GetInteractor():
            self.vtk_bot.GetRenderWindow().GetInteractor().Disable()


    def get_widget(self, parent=None):
        if self.widget is None:
            self.ui = Ui_ErpPlot(parent)
            self.widget = self.ui
            self.alerts.parent = self.widget
            self.ensure_vtk()
            self._wire_ui()
        else:
            self.widget.setParent(parent)
        return self.widget

    def ensure_vtk(self):
        self.vtk_top = QVTKRenderWindowInteractor(self.ui.butterflyPlot)
        self.ui.butterflyPlot.setLayout(QtWidgets.QVBoxLayout())
        self.ui.butterflyPlot.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.butterflyPlot.layout().addWidget(self.vtk_top)

        self.view_top = vtk.vtkContextView()
        self.view_top.SetRenderWindow(self.vtk_top.GetRenderWindow())
        self.view_top.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        self.vtk_bot = QVTKRenderWindowInteractor(self.ui.heatmapPlot)
        self.ui.heatmapPlot.setLayout(QtWidgets.QVBoxLayout())
        self.ui.heatmapPlot.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.heatmapPlot.layout().addWidget(self.vtk_bot)

        self.view_bot = vtk.vtkContextView()
        self.view_bot.SetRenderWindow(self.vtk_bot.GetRenderWindow())
        self.view_bot.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        try:
            self.vtk_top.Initialize()
            self.vtk_bot.Initialize()
        except Exception:
            pass
    
    def _wire_ui(self):
        self.ui.plotErpButton.clicked.connect(self._on_plot_clicked)
        self.ui.clearButton.clicked.connect(self._on_clear_clicked)
        self.ui.spnFrom.valueChanged.connect(self._sync_range)
        self.ui.spnTo.valueChanged.connect(self._sync_range)
        self.ui.txtFilter.textChanged.connect(self._apply_filter)
        self.ui.cmbGroupSize.currentIndexChanged.connect(self._on_group_size_changed)
        self.ui.spnGroupSize.valueChanged.connect(self._on_group_size_changed)
        self.ui.btnPrevGroup.clicked.connect(lambda: self._move_group(-1))
        self.ui.btnNextGroup.clicked.connect(lambda: self._move_group(+1))
        self.ui.chkShowAverage.toggled.connect(lambda _: self._render_group())

    def _on_clear_clicked(self):
        self.ui.chkSelectAll.setChecked(True)
        self.ui.chkSingleTrial.setChecked(False)
        self.ui.chkUseRange.setChecked(False)
        self.ui.spnSingleTrial.setValue(1)
        self.ui.spnFrom.setValue(1)
        self.ui.spnTo.setValue(1)
        self.ui.txtFilter.clear()
        self.ui.cmbGroupSize.setCurrentIndex(0)
        self.ui.chkShowAverage.setChecked(True)

    def _load_trials_from_store(self):
        """
        Find the active signal in the DataStore and return the latest TrialDataset:
        X:  np.ndarray (Ns, T)  trials matrix (columns = trials)
        """
        if not self.mainwin:
            return None, None, None

        if self.get_active_signal() is None:
            return None, None, None

        td = self.get_active_trials()
        if td is None:
            return None, None, None

        if not hasattr(td, "time_rel") or not hasattr(td, "trials"):
            self.alerts.error("The TrialDataset does not contain 'time_rel' or 'trials'.", "Incomplete Trials")
            return None, None, None

        t = np.asarray(td.time_rel, dtype=float)
        M = np.asarray(td.trials, dtype=float)

        if M.ndim != 2 or t.ndim != 1:
            self.alerts.error("The TrialDataset has invalid dimensions.", "Invalid dimensions")

            return None, None, None

        if M.shape[0] == t.size:
            M = M.T
        elif M.shape[1] == t.size:
            pass
        else:
            self.alerts.error("time_rel does not match trials.", "Inconsistency")

            return None, None, None

        return t, M, td
            
    def _collect_selected_indices(self, n_trials: int) -> list[int]:
        """Return indices (1-based) according to selection mode."""
        if self.ui.chkSelectAll.isChecked():
            return list(range(1, n_trials + 1))
        if self.ui.chkSingleTrial.isChecked():
            return [min(max(1, self.ui.spnSingleTrial.value()), n_trials)]
        if self.ui.chkUseRange.isChecked():
            a = min(max(1, self.ui.spnFrom.value()), n_trials)
            b = min(max(1, self.ui.spnTo.value()), n_trials)
            if a > b:
                a, b = b, a
            return list(range(a, b + 1))
        out: list[int] = []
        for i in range(self.ui.lstTrials.count()):
            it = self.ui.lstTrials.item(i)
            if it.checkState() == QtCore.Qt.Checked:
                out.append(i + 1)
        return out
    
    def _sync_range(self):
        if self.ui.spnFrom.value() > self.ui.spnTo.value():
            self.ui.spnTo.setValue(self.ui.spnFrom.value())

    def _select_none(self):
        for i in range(self.ui.lstTrials.count()):
            self.ui.lstTrials.item(i).setCheckState(QtCore.Qt.Unchecked)

    def _select_visible(self):
        f = self.ui.txtFilter.text().strip().lower()
        for i in range(self.ui.lstTrials.count()):
            it = self.ui.lstTrials.item(i)
            visible = (f in it.data(QtCore.Qt.UserRole)) if f else True
            if visible:
                it.setCheckState(QtCore.Qt.Checked)

    def _invert_selection(self):
        for i in range(self.ui.lstTrials.count()):
            it = self.ui.lstTrials.item(i)
            it.setCheckState(
                QtCore.Qt.Checked if it.checkState() == QtCore.Qt.Unchecked else QtCore.Qt.Unchecked
            )

    def _apply_filter(self, text: str):
        f = (text or "").lower().strip()
        for i in range(self.ui.lstTrials.count()):
            it = self.ui.lstTrials.item(i)
            match = (f in it.data(QtCore.Qt.UserRole)) if f else True
            self.ui.lstTrials.setRowHidden(i, not match)

    def _on_plot_clicked(self):
        t, M, td = self._load_trials_from_store()
        if t is None or M is None:
            return

        n_trials, n_samples = M.shape
        self._ensure_trials_list(n_trials)

        idx = self._collect_selected_indices(n_trials)
        if not idx:
            self._notify("No trials selected.", "warning")
            return

        self.ch_name = getattr(td, "channel_name", "")
        used = trials_used(idx, n_trials, channel=self.ch_name)

        self._last_idx0 = [int(i) - 1 for i in idx]

        self.run_task(calcular_erp, partial(self._on_erp_done, t, used, n_trials),
                      t=t, M=M, idx=list(idx))

    def _on_erp_done(self, t, used, n_trials, resultado):
        sel, mapa = resultado
        self._trials_used = used
        self._t = np.asarray(t, dtype=float)
        self._sel = sel
        ids = list(getattr(self, "_last_idx0", []) or [])
        self._sel_ids = ids if len(ids) == sel.shape[0] else list(range(sel.shape[0]))
        self._group_idx = 0
        self._render_group()
        self._render_heatmap(t, sel, title=f"Trials: {used['label']}", preparado=mapa)

        self._notify(f"ERP: {used['label']} plotted. Channel: {self.ch_name}")
        self.publish_current_trial()
        self.mark_project_dirty()

    def get_analysis_params(self) -> dict:
        if self.ui.chkSelectAll.isChecked():
            mode = "all"
        elif self.ui.chkSingleTrial.isChecked():
            mode = "single"
        elif self.ui.chkUseRange.isChecked():
            mode = "range"
        else:
            mode = "manual"

        checked_indices = []
        if mode == "manual":
            for i in range(self.ui.lstTrials.count()):
                if self.ui.lstTrials.item(i).checkState() == QtCore.Qt.Checked:
                    checked_indices.append(i + 1)

        return {
            "mode": mode,
            "single_trial": self.ui.spnSingleTrial.value(),
            "range_from": self.ui.spnFrom.value(),
            "range_to": self.ui.spnTo.value(),
            "manual_checked_indices": checked_indices,
            "trials_used": self._trials_used,
            "group_size": self.ui.cmbGroupSize.currentText(),
            "custom_group_size": self.ui.spnGroupSize.value(),
            "show_average": self.ui.chkShowAverage.isChecked(),
        }

    def apply_analysis_params(self, params: dict):
        mode = params.get("mode", "all")
        self.ui.chkSelectAll.setChecked(mode == "all")
        self.ui.chkSingleTrial.setChecked(mode == "single")
        self.ui.chkUseRange.setChecked(mode == "range")
        self.ui.spnSingleTrial.setValue(params.get("single_trial", self.ui.spnSingleTrial.value()))
        self.ui.spnFrom.setValue(params.get("range_from", self.ui.spnFrom.value()))
        self.ui.spnTo.setValue(params.get("range_to", self.ui.spnTo.value()))
        gi = self.ui.cmbGroupSize.findText(str(params.get("group_size", "All")))
        self.ui.cmbGroupSize.setCurrentIndex(gi if gi >= 0 else 0)
        self.ui.spnGroupSize.setValue(int(params.get("custom_group_size", self.ui.spnGroupSize.value())))
        self.ui.chkShowAverage.setChecked(bool(params.get("show_average", True)))

        if mode == "manual":
            self._on_plot_clicked()
            checked = set(params.get("manual_checked_indices", []))
            for i in range(self.ui.lstTrials.count()):
                it = self.ui.lstTrials.item(i)
                it.setCheckState(QtCore.Qt.Checked if (i + 1) in checked else QtCore.Qt.Unchecked)

        self._on_plot_clicked()

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

    
    def cleanup_vtk(self):
        """Properly release VTK resources before destroying the widget."""
        try:
            if self.vtk_widget:
                print("[TrialsPlugin] Releasing VTK resources...")
                rw = self.vtk_widget.GetRenderWindow()
                if rw:
                    iren = rw.GetInteractor()
                    if iren:
                        iren.TerminateApp()
                    rw.Finalize()
                self.vtk_widget.SetRenderWindow(None)
                self.vtk_widget = None
                self.renwin = None
        except Exception as e:
            print("[TrialsPlugin] cleanup_vtk() error:", e)
            
    def _group_size(self, n: int) -> int:
        ui = getattr(self, "ui", None)
        if ui is None or not hasattr(ui, "cmbGroupSize"):
            return max(1, n)
        txt = ui.cmbGroupSize.currentText()
        if txt == "All":
            return max(1, n)
        if txt == "Custom":
            return max(1, ui.spnGroupSize.value())
        try:
            return max(1, int(txt))
        except ValueError:
            return max(1, n)

    def _n_groups(self) -> int:
        if self._sel is None:
            return 1
        n = self._sel.shape[0]
        return max(1, -(-n // self._group_size(n)))

    def _on_group_size_changed(self, *_):
        self.ui.spnGroupSize.setEnabled(self.ui.cmbGroupSize.currentText() == "Custom")
        self._group_idx = 0
        self._render_group()

    def _move_group(self, step: int):
        if self._sel is None:
            return
        self._group_idx = (self._group_idx + step) % self._n_groups()
        self._render_group()

    def _render_group(self):
        """Draw the current group of selected trials with its average on top."""
        if self._sel is None or self._t is None:
            return
        n = self._sel.shape[0]
        size = self._group_size(n)
        ng = self._n_groups()
        self._group_idx = min(self._group_idx, ng - 1)
        a = self._group_idx * size
        b = min(n, a + size)
        ids = list(self._sel_ids[a:b]) if self._sel_ids is not None else list(range(a, b))
        label = (getattr(self, "_trials_used", None) or {}).get("label", "")
        if ng > 1:
            seguidos = ids == list(range(ids[0], ids[-1] + 1))
            txt = f"trials {ids[0] + 1}-{ids[-1] + 1}" if seguidos else ", ".join(str(i + 1) for i in ids)
            title = f"ERP — {self.ch_name} — group {self._group_idx + 1}/{ng} ({txt})"
        else:
            title = f"ERP — {self.ch_name} — {label}"
        ui = getattr(self, "ui", None)
        if ui is not None and hasattr(ui, "lblGroup"):
            ui.lblGroup.setText(f"Group {self._group_idx + 1}/{ng}  ({b - a} trials)")
            ui.btnPrevGroup.setEnabled(ng > 1)
            ui.btnNextGroup.setEnabled(ng > 1)
        self._render_butterfly(self._t, self._sel[a:b], title=title, trial_ids=ids)

    def _render_butterfly(self, t: np.ndarray, sel: np.ndarray, title: str = None, trial_ids=None):
        """
        Draw lines (1 per trial) with vtkChartXY and, on top, their average in black.
        t: (T,), sel: (K, T), trial_ids: 0-based index of each row (for the measurements).
        """
        assert self.view_top is not None
        scene = self.view_top.GetScene()
        scene.ClearItems()

        t = np.asarray(t, dtype=float)
        sel = np.asarray(sel, dtype=float)
        if trial_ids is None or len(trial_ids) != sel.shape[0]:
            trial_ids = list(range(sel.shape[0]))
        trial_ids = [int(i) for i in trial_ids]

        dibujar = sel
        if sel.shape[0] > self.MAX_CURVAS:
            self._log(f"Hay {sel.shape[0]} trials, se dibujan {self.MAX_CURVAS}")
            dibujar = sel[:self.MAX_CURVAS]

        chart = vtk.vtkChartXY()
        scene.AddItem(chart)

        for row, k in zip(dibujar, trial_ids):
            plot = agregar_linea(chart, t, row, "time", f"trial_{k + 1}")
            plot.SetWidth(0.5)
            plot.SetLabel(f"Trial {k + 1}")

        ui = getattr(self, "ui", None)
        show_avg = True
        if ui is not None and hasattr(ui, "chkShowAverage"):
            show_avg = ui.chkShowAverage.isChecked()
        if show_avg and sel.shape[0] > 1:
            with np.errstate(all="ignore"):
                avg = np.nanmean(sel, axis=0)
            plot = agregar_linea(chart, t, avg, "time", "average")
            plot.SetColor(0, 0, 0, 255)
            plot.SetWidth(3.0)
            plot.SetLabel("Average")

        ax_bottom = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_left = chart.GetAxis(vtk.vtkAxis.LEFT)

        chart.SetTitle(f"Butterfly Plot — {title}" if title else "Butterfly Plot")
        ax_bottom.SetTitle("Time (s)")
        ax_left.SetTitle("Amplitude")

        try:
            if getattr(self, "vtk_menu", None) is None:
                self.vtk_menu = VTKContextMenu(chart, self.vtk_top, self.active_signal.name, self.ch_name,
                                               self.meta.id, parent=self.widget)
            else:
                self.vtk_menu.set_chart(chart)
                self.vtk_menu.set_signal_name(self.active_signal.name)
                self.vtk_menu.set_channel_name(self.ch_name)
            svc = self.vtk_menu.measure_service
            mw = getattr(self, "mainwin", None)
            if mw is not None and hasattr(mw, "_refresh_measurement_tables"):
                svc.on_change = mw._refresh_measurement_tables
            t_m, sel_m, ids_m = t, sel, trial_ids
            self.vtk_menu.set_trials_source(lambda: (t_m, sel_m.T, ids_m), visible_trial_ids=ids_m)
            self.vtk_menu.set_measurement_context(
                view_id="erp", plugin=self.meta.id, domain="time", graph_id="butterfly",
                channel_name=f"{self.active_signal.name}:{self.ch_name}")
            self.vtk_menu.rebuild_measurement_overlays()
        except Exception as e:
            self.alerts.error(f"Error creating contextual menu\n {str(e)}", "Contextual menu")

        self.view_top.GetRenderWindow().Render()

    def _render_heatmap(self, t: np.ndarray, sel: np.ndarray, title: str = None, preparado=None):
        """2D heatmap with correct time axes"""
        assert self.view_bot is not None
        scene = self.view_bot.GetScene()
        scene.ClearItems()

        X, t, vmin, vmax, t0, t_end, dt, factor = preparado or ce.preparar_mapa_calor(t, sel)
        K, Tn = X.shape
        self._log(f"Heatmap: {K} trials x {Tn} muestras, submuestreo x{factor}, "
                  f"rango [{vmin:.3f}, {vmax:.3f}], t0={t0:.3f}s, dt={dt:.6f}s")

        img = vtk.vtkImageData()
        img.SetDimensions(Tn, K, 1)
        img.SetSpacing(dt, 1.0, 1.0)
        img.SetOrigin(t0, 0.0, 0.0)

        X_plano = np.ascontiguousarray(X, dtype=np.float32).ravel()
        arr = numpy_support.numpy_to_vtk(X_plano, deep=True, array_type=vtk.VTK_FLOAT)
        img.GetPointData().SetScalars(arr)
        img.Modified()
        
        self._log(f"Heatmap VTK: rango={img.GetScalarRange()} "
                  f"spacing={img.GetSpacing()} origen={img.GetOrigin()}")

        lut = self._build_lut("blue", vmin, vmax)

        chart = vtk.vtkChartHistogram2D()
        chart.SetInputData(img, 0)
        chart.SetTransferFunction(lut)
        anotar_mapa(chart, img, lut)
        
        ax_bottom = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_left = chart.GetAxis(vtk.vtkAxis.LEFT)
        
        ax_bottom.SetTitle("Time (s)")
        ax_left.SetTitle("Trials")
        if title:
            chart.SetTitle(title)
        
        ax_bottom.SetRange(t0, t_end)
        ax_left.SetRange(0, K)
        
        scene.AddItem(chart)
        
        try:
            self.vtk_menu_bot = VTKContextMenu(chart, self.vtk_bot, self.active_signal.name,self.ch_name,self.meta.id, parent=self.widget)
            self.vtk_menu_bot.add_action("Change LUT", self._on_change_lut)
        except Exception as e:
            self.alerts.error(f"Error creating contextual menu\n {str(e)}", "Contextual menu")


        self.view_bot.GetRenderWindow().Render()


    def _on_change_lut(self):
        self.alerts.warning("Change color map (not implemented).", "Change LUT")


    def _build_lut(self, mode: str, vmin: float, vmax: float) -> vtk.vtkScalarsToColors:
        mode = (mode or "blue").lower()
        N = 256
        bg = self.view_bot.GetRenderer().GetBackground()

        def finalize(lut: vtk.vtkLookupTable) -> vtk.vtkLookupTable:
            lut.SetRange(vmin, vmax)
            lut.SetNumberOfTableValues(N)
            lut.Build()
            lut.SetNanColor(*bg, 1.0)
            lut.SetUseBelowRangeColor(True); lut.SetBelowRangeColor(*bg, 1.0)
            lut.SetUseAboveRangeColor(True); lut.SetAboveRangeColor(*bg, 1.0)
            return lut

        if mode in ("blue_red", "br"):
            gamma = 0.6
            lut = vtk.vtkLookupTable()
            lut = finalize(lut)
            for i in range(N):
                s = (i / (N - 1)) ** gamma
                if s < 0.5:
                    k = s / 0.5
                    r = k*1.0 + (1-k)*0.00
                    g = k*1.0 + (1-k)*0.10
                    b = k*1.0 + (1-k)*0.60
                else:
                    k = (s - 0.5) / 0.5
                    r = k*0.80 + (1-k)*1.0
                    g = k*0.00 + (1-k)*1.0
                    b = k*0.00 + (1-k)*1.0
                lut.SetTableValue(i, r, g, b, 1.0)
            return lut

        if mode in ("blue", "blue_r"):
            light = (0.93, 0.97, 1.00)
            dark  = (0.00, 0.10, 0.60)
            gamma = 0.6
            lut = vtk.vtkLookupTable()
            lut = finalize(lut)
            for i in range(N):
                s = (i / (N - 1)) ** gamma
                if mode == "blue_r":
                    s = 1.0 - s
                r = light[0] + s * (dark[0] - light[0])
                g = light[1] + s * (dark[1] - light[1])
                b = light[2] + s * (dark[2] - light[2])
                lut.SetTableValue(i, r, g, b, 1.0)
            return lut

        if mode == "jet":
            ...
            return lut

        ctf = vtk.vtkColorTransferFunction()
        ctf.ClampingOn()
        ctf.SetRange(vmin, vmax)
        ctf.AddRGBPoint(vmin,                 0.267, 0.005, 0.329)
        ctf.AddRGBPoint((2*vmin+vmax)/3.0,    0.229, 0.322, 0.545)
        ctf.AddRGBPoint((vmin+2*vmax)/3.0,    0.127, 0.566, 0.550)
        ctf.AddRGBPoint(vmax,                 0.993, 0.906, 0.144)

        lut = vtk.vtkLookupTable()
        lut = finalize(lut)
        gamma = 0.8
        for i in range(N):
            s = (i / (N - 1)) ** gamma
            x = vmin + s * (vmax - vmin)
            r, g, b = ctf.GetColor(x)
            lut.SetTableValue(i, r, g, b, 1.0)
        return lut
