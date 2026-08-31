from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QWidget

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore

from plugins.preprocessing.prepare.filter.filter_plugin_ui import Ui_Filter

import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from scipy.signal import butter, sosfiltfilt

import numpy as np

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

        self.ui.applyFilterButton.clicked.connect(self.on_apply_filter)
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
            if trials.trials is None:
                return

            signal_data = self.active_signal.signals[0, :]
            trial_data = trials.trials[:, 0]
            fs = self.active_signal.sampling_rate
            print(f"Sampling Rate: {fs} Hz")

            low = float(self.ui.lowFrequencySpinBox.value())
            high = float(self.ui.highFrequencySpinBox.value())
            order = int(self.ui.orderSpinBox.value())
            type_filter = self.ui.typeSelectComboBox.currentText().lower()

            filtered_signal = self.run_filter(signal_data, low, high, order, fs, type_filter)
            filtered_trial = self.run_filter(trial_data, low, high, order, fs, type_filter)

            self._render_filtered(filtered_signal, self.active_signal.sampling_rate, unit="mV", type = "signal")
            self._render_filtered(filtered_trial, self.active_signal.sampling_rate, unit="mV", type = "trial")

        except ValueError as ve:
            self.alerts.error(str(ve))
        except Exception as e:
            self.alerts.error(f"Unexpected error in on_apply_filter: {str(e)}")
            self._log("Unexpected error in on_apply_filter:", e)
    # end def

    def run_filter(self, signal, low, high, order, fs, type="butterworth"):
        """ Applies a bandpass filter to the signal."""
        try:
            signal = np.asarray(signal, dtype=np.float64)
            nyq = 0.5 * fs
            lowcut = low / nyq
            highcut = high / nyq

            # Sanity check: ensure frequencies are valid
            if lowcut <= 0 or highcut >= 1 or lowcut >= highcut:
                raise ValueError(f"Invalid cutoff frequencies: low={lowcut}, high={highcut}")

            if type.lower() == "butterworth":
                sos = butter(order, [lowcut, highcut], btype="band", output="sos")
            else:
                raise NotImplementedError(f"Filter '{type}' not implemented.")

            # Use sosfiltfilt for numerical stability (zero-phase)
            filtered = sosfiltfilt(sos, signal)

            if np.any(np.isnan(filtered)):
                raise ValueError("Filter output contains NaN values.")

            return filtered

        except Exception as e:
            self._log("Error running filter:", e)
            return np.zeros_like(signal)
    # end def

    def _render_filtered(self, filtered_output, fs: float, unit: str = "mV", type: str = ""):
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
            plot = chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, 0, 1)
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

            chart.SetTitle(f"Filtered {type.capitalize()}")

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
