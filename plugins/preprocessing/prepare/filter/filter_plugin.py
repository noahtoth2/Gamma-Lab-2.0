from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QWidget

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.utils.trial_labels import trials_used
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore

from plugins.preprocessing.prepare.filter.filter_plugin_ui import Ui_Filter

import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from scipy.signal import butter, sosfiltfilt

import numpy as np
from functools import partial

from core.filters.artifacts import receta_filtro
from core.filters.bandpass import filtrar_banda, filtrar_columnas
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import (
    descartar_derivado, escribir_modificacion, preparar_modificacion)
<<<<<<< HEAD
=======
from core.utils.submuestreo import agregar_columna
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238


def filtrar_vista_previa(signal, trial, low, high, order, fs, type="butterworth", ctx=None):
    """The two traces the preview shows: (filtered signal, filtered first trial)."""
    sig = filtrar_banda(signal, low, high, order, fs, type)
    if ctx is not None:
        ctx.progress(50, "Filtered signal")
    return sig, filtrar_banda(trial, low, high, order, fs, type)


class Filter_plugin(IPlugin):
    """Filter plugin for signal processing"""

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.vtk_widget = None
        self.renwin = None
        self.ui = None
        self.vtk_menu = None
        self._context_view = None

        # VTK widgets
        self.vtk_top: QVTKRenderWindowInteractor | None = None
        self.vtk_bot: QVTKRenderWindowInteractor | None = None
        self.view_top: vtk.vtkContextView | None = None
        self.view_bot: vtk.vtkContextView | None = None
 
    # end def

    # =====================================================
    # === Plugin lifecycle
    # =====================================================


    def process(self, data: any):
        if self.vtk_widget:
            self.vtk_widget.Enable()

        if self.vtk_top and self.vtk_top.GetRenderWindow().GetInteractor():
            self.vtk_top.GetRenderWindow().GetInteractor().Enable()

        if self.vtk_bot and self.vtk_bot.GetRenderWindow().GetInteractor():
                self.vtk_bot.GetRenderWindow().GetInteractor().Enable()
    # end def


    def stop(self):
        if self.vtk_top and self.vtk_top.GetRenderWindow().GetInteractor():
            self.vtk_top.GetRenderWindow().GetInteractor().Disable()

        if self.vtk_bot and self.vtk_bot.GetRenderWindow().GetInteractor():
            self.vtk_bot.GetRenderWindow().GetInteractor().Disable()
    # end def

    
    # =====================================================
    # === Create widget UI + VTK
    # =====================================================
    def get_widget(self, parent=None):
        if self.widget is not None:
            self.widget.setParent(parent)
            return self.widget

        self.widget = QWidget(parent)
        self.alerts.parent = self.widget

        self.ui = Ui_Filter()
        self.ui.setupUi(self.widget)


        self.init_controls()
        self.ensure_vtk()


        return self.widget
    # end def
    
    # =====================================================
    # === Utilities
    # =====================================================
    def init_controls(self):
        self.ui.main_splitter.setStretchFactor(0, 0)
        self.ui.main_splitter.setStretchFactor(1, 1)
        self.ui.main_splitter.widget(1).setMaximumWidth(300)

        self.ui.highFrequencySpinBox.setRange(0, 1000)
        self.ui.highFrequencySpinBox.setValue(4.0)
        self.ui.lowFrequencySpinBox.setRange(0, 1000)
        self.ui.lowFrequencySpinBox.setValue(0.5)
        self.ui.orderSpinBox.setRange(0, 100)
        self.ui.orderSpinBox.setValue(8)
        self.ui.typeSelectComboBox.addItems(["Butterworth", "Chebyshev", "Elliptic"])

        # "Filter" filters the trials for real (R79); "Preview" only draws the result
        self.ui.applyFilterButton.clicked.connect(self.on_apply_to_trials)
        self.ui.previewButton.clicked.connect(self.on_apply_filter)
        self.ui.restoreOriginalButton.clicked.connect(self.on_restore_original)
        self.ui.Btn_clear_params.clicked.connect(self._on_clear_clicked)
    # end def

    def _on_clear_clicked(self):
        self.ui.highFrequencySpinBox.setValue(4.0)
        self.ui.lowFrequencySpinBox.setValue(0.5)
        self.ui.orderSpinBox.setValue(8)
        self.ui.typeSelectComboBox.setCurrentIndex(0)
    # end def

    def ensure_vtk(self):
        """Initialize VTK components for rendering."""

        # Filtered signal
        self.vtk_top = QVTKRenderWindowInteractor(self.ui.filteredSignal)
        self.ui.filteredSignal.setLayout(QtWidgets.QVBoxLayout())
        self.ui.filteredSignal.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.filteredSignal.layout().addWidget(self.vtk_top)

        self.view_top = vtk.vtkContextView()
        self.view_top.SetRenderWindow(self.vtk_top.GetRenderWindow())
        self.view_top.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        # Filtered trial
        self.vtk_bot = QVTKRenderWindowInteractor(self.ui.filteredTrial)
        self.ui.filteredTrial.setLayout(QtWidgets.QVBoxLayout())
        self.ui.filteredTrial.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.filteredTrial.layout().addWidget(self.vtk_bot)

        self.view_bot = vtk.vtkContextView()
        self.view_bot.SetRenderWindow(self.vtk_bot.GetRenderWindow())
        self.view_bot.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        try:
            self.vtk_top.Initialize()
            self.vtk_bot.Initialize()
        except Exception:
            pass

        except Exception as e:
            self._log("Error ensure_vtk:", e)
    # end def

    
    # =====================================================
    # === Main Logic: Filter + Render
    # =====================================================
    def on_apply_filter(self):
        try:
            if self.get_active_signal() is None:
                return

            trials = self.get_active_trials()
            if trials is None or trials.trials is None:
                return

            # La vista previa filtra siempre el canal 0 de la senal cruda y el
            # primer trial valido; se indica tal cual en los titulos.
            signal_data = self.active_signal.signals[0, :]
            trial_data = trials.trials[:, 0]
            nombres = list(getattr(self.active_signal, "channel_names", []) or [])
            canal_senal = nombres[0] if nombres else "canal 1"
            self._trials_used = trials_used([1], trials.trials.shape[1], "single",
                                            channel=trials.channel_name)
            fs = self.active_signal.sampling_rate
            print(f"Sampling Rate: {fs} Hz")

            low = float(self.ui.lowFrequencySpinBox.value())
            high = float(self.ui.highFrequencySpinBox.value())
            order = int(self.ui.orderSpinBox.value())
            type_filter = self.ui.typeSelectComboBox.currentText().lower()

            # Filtering in the TaskService (R71); the preview is drawn when it finishes
            self.run_task(filtrar_vista_previa,
                          partial(self._on_filter_done, canal_senal, trials.channel_name),
                          on_failed=lambda m: self.alerts.warning(m, "Invalid parameters"),
                          signal=np.array(signal_data, copy=True), trial=np.array(trial_data, copy=True),
                          low=low, high=high, order=order, fs=fs, type=type_filter)

        except ValueError as ve:
            self.alerts.warning(str(ve), "Invalid parameters")
        except Exception as e:
            self.alerts.error(f"Unexpected error in on_apply_filter: {str(e)}")
            self._log("Unexpected error in on_apply_filter:", e)
    # end def

    # ---- R79: filtering the trials leaves a derived set; the originals are never written ----
    def on_apply_to_trials(self):
        try:
            if self.get_active_signal() is None:
                return
            low = float(self.ui.lowFrequencySpinBox.value())
            high = float(self.ui.highFrequencySpinBox.value())
            order = int(self.ui.orderSpinBox.value())
            tipo = self.ui.typeSelectComboBox.currentText().lower()
            prep = preparar_modificacion(self.kernel)
            if prep is None:
                self.alerts.info("No hay trials para filtrar.")
                return
            fs = float(prep.td_base.sampling_rate)
            self.run_task(filtrar_columnas, partial(self._on_trials_filtered, prep, low, high, order, tipo, fs),
                          on_failed=lambda m: self.alerts.warning(m, "Invalid parameters"),
                          trials=prep.trials, low=low, high=high, order=order, fs=fs, type=tipo)
        except Exception as e:
            self.alerts.error(f"No se pudo filtrar los trials: {e}")

    def _on_trials_filtered(self, prep, low, high, order, tipo, fs, salida):
        try:
            escribir_modificacion(self.kernel, prep, salida, "filter",
                                  receta_dict=receta_filtro(low, high, order, tipo, fs, prep.discarded))
            self.mark_project_dirty()
            self._notify(f"Filtro {low:g}-{high:g} Hz aplicado a los trials de {prep.channel_name}; "
                         f"los originales se conservan")
        except Exception as e:
            self.alerts.error(f"No se pudo registrar el filtrado: {e}", "Error al aplicar")

    def on_restore_original(self):
        try:
            _, canal, hubo = descartar_derivado(self.kernel)
        except Exception as e:
            self.alerts.error(f"No se pudieron restaurar los trials originales: {e}")
            return
        if not hubo:
            self.alerts.info("Este canal no tiene modificaciones que deshacer.")
            return
        self.mark_project_dirty()
        if hasattr(self.kernel, "event"):
            try:
                self.kernel.event.emit("trials_generated", {"channel": canal})
            except Exception:
                pass
        self._notify(f"Trials originales restaurados en {canal}")

    def _on_filter_done(self, canal_senal, canal_trials, resultado):
        filtered_signal, filtered_trial = resultado
        self._render_filtered(filtered_signal, self.active_signal.sampling_rate, unit="mV", type="signal",
                              title=f"Filtered Signal — {canal_senal} (señal completa)")
        self._render_filtered(filtered_trial, self.active_signal.sampling_rate, unit="mV", type="trial",
                              title=f"Filtered Trial — {self._trials_used['label']} — {canal_trials}")
        self._notify(f"Filtro aplicado a {canal_senal} (señal completa) y a "
                     f"{self._trials_used['label']} de {canal_trials} (vista previa)")
        self.publish_current_trial()

    def current_trial_state(self):
        """La vista previa del filtro usa siempre el primer trial valido."""
        _, td = self._active_trials_quiet()
        if td is None:
            return None
        return self.build_trial_state("single", position=1, total=int(td.trials.shape[1]),
                                      channel=td.channel_name, note="vista previa del filtro")

    def run_filter(self, signal, low, high, order, fs, type="butterworth"):
        """ Applies a bandpass filter to the signal."""
        try:
            return filtrar_banda(signal, low, high, order, fs, type)
        except Exception as e:
            self._log("Error running filter:", e)
            return np.zeros_like(signal)
    # end def

    def _render_filtered(self, filtered_output, fs: float, unit: str = "mV", type: str = "",
                         title: str = None):
        """
        Render filtered signal or trial using the correct vtkContextView.
        """
        try:
            # --- Select proper rendering context ---
            if type == "signal":
                vtk_widget = self.vtk_top
                view = self.view_top
            elif type == "trial":
                vtk_widget = self.vtk_bot
                view = self.view_bot
            else:
                print("[Filter] Unknown render type. Expected 'signal' or 'trial'.")
                return

            if not vtk_widget or not view:
                print(f"[Filter] VTK context for '{type}' not initialized.")
                return

            # --- Get render window & scene ---
            renwin = view.GetRenderWindow()
            if not renwin:
                print(f"[Filter] Could not get RenderWindow for '{type}'.")
                return

            scene = view.GetScene()
            if not scene:
                print(f"[Filter] Could not get Scene for '{type}'.")
                return

            # --- Clear any previous charts ---
            scene.ClearItems()

            # --- Validate filtered output ---
            if not isinstance(filtered_output, np.ndarray):
                print(f"[Filter] filtered_output for '{type}' is not np.ndarray")
                return

            # --- Build time and signal arrays for plotting ---
            n_points = len(filtered_output)

            arr_time = vtk.vtkFloatArray()
            arr_time.SetName("Time (s)")

            arr_signal = vtk.vtkFloatArray()
            arr_signal.SetName("Filtered Signal")

            for i in range(n_points):
                t = i / fs
                arr_time.InsertNextValue(t)
                arr_signal.InsertNextValue(float(filtered_output[i]))

            # --- Build VTK table ---
            table = vtk.vtkTable()
            table.AddColumn(arr_time)
            table.AddColumn(arr_signal)

            # --- Create and configure chart ---
            chart = vtk.vtkChartXY()
            plot = agregar_columna(chart, table, 1)
            plot.SetWidth(1.2)
            plot.SetColor(0, 0, 0)
            plot.SetLabel(f"Filtered {type.capitalize()}")

            # Axes configuration
            ax_b = chart.GetAxis(vtk.vtkAxis.BOTTOM)
            ax_l = chart.GetAxis(vtk.vtkAxis.LEFT)
            ax_b.SetGridVisible(True)
            ax_l.SetGridVisible(True)
            ax_b.SetTitle("Time (s)")
            ax_l.SetTitle(unit)

            chart.SetTitle(title or f"Filtered {type.capitalize()}")

            # --- Add chart to scene ---
            scene.AddItem(chart)

            # --- Contextual menu ---
            try:
                if type == "signal":
                    self.vtk_menu = VTKContextMenu(chart, self.vtk_top, parent=self.widget)
                elif type == "trial":
                    self.vtk_menu = VTKContextMenu(chart, self.vtk_bot, parent=self.widget)
                else:
                    raise ValueError("Invalid type for contextual menu")

                self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))

            except Exception as e:
                self.alerts.error(f"Error creating contextual menu: {e}")

            # --- Render final ---
            try:
                renwin.Render()
                vtk_widget.update()
                print(f"[Filter] {type.capitalize()} chart rendered successfully.")
            except Exception as e:
                print(f"[Filter] Render error in {type}:", e)

        except Exception as e:
            print(f"[Filter] Error rendering {type}:", e)
    # end def

# end class
