from functools import partial

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util import numpy_support
import vtk
import numpy as np

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin_ui import Ui_Wavelet_Average
from plugins.analysis.time_frequency.wavelet_average import compute as cw



class Wavelet_average_plugin(IPlugin):
    
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.vtk_widget = None
        self.renwin = None
        self.ui = None
        self.vtk_menu = None
        self._context_view = None
        self._vtk_renderer = None
        self._handle = None
        self._calculando = False
        self.params = {
            "sample_density_range": (0, 10000),
            "frequencies_range": (0, 10000),
            "sample_density_value": 1000,
            "high_frequency_value": 500,
            "low_frequency_value": 1,
            "cycles_range": (1, 20),
            "cycles_value": 2
        }

    # end def

    # =====================================================
    # === Lifecycle
    # =====================================================

    def process(self, data: any):
        """Optional hook; show status message if available."""
        if self.vtk_widget and self.vtk_widget.GetRenderWindow():
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor:
                interactor.Enable()
                self._log("VTK interactor enabled.")
    # end def

    def stop(self):
        """Stop plugin and disable VTK interactor if present."""
        if self.vtk_widget and self.vtk_widget.GetRenderWindow():
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor:
                interactor.Disable()
                self._log("VTK interactor disabled.")
    # end def

    # =====================================================
    # === UI + VTK creation
    # =====================================================
    def get_widget(self, parent=None):
      
        if self.widget is not None:
            self.widget.setParent(parent)
            return self.widget

        self.widget = QWidget(parent)
        self.ui = Ui_Wavelet_Average()
        self.ui.setupUi(self.widget)

        self.alerts.parent = self.widget

        # initialize controls and VTK container
        self._init_controls()
        self._create_vtk_container()

        self.ui.createWaveletButton.clicked.connect(self.on_create_wavelet)
        self.ui.clearButton.clicked.connect(self._on_clear_clicked)
        return self.widget
    # end def

    def _on_clear_clicked(self):
        if self._calculando:
            self.alerts.info("Hay un cálculo de wavelet en curso; espera a que termine.")
            return
        self.ui.sampleDensitySpinBox.setValue(self.params["sample_density_value"])
        self.ui.lowFrequencySpinBox.setValue(self.params["low_frequency_value"])
        self.ui.highFrequencySpinBox.setValue(self.params["high_frequency_value"])
        self.ui.cyclesSpinBox.setValue(self.params["cycles_value"])
        self.ui.normalizeCheckBox.setChecked(False)
        self.ui.normalizeComboBox.setCurrentIndex(0)
        self.ui.scaleCheckBox.setChecked(False)
        self.ui.scaleComboBox.setCurrentIndex(0)
    # end def

    def _init_controls(self):
       

        self.ui.sampleDensitySpinBox.setRange(*self.params["sample_density_range"])
        self.ui.sampleDensitySpinBox.setValue(self.params["sample_density_value"])
        self.ui.highFrequencySpinBox.setRange(*self.params["frequencies_range"])
        self.ui.highFrequencySpinBox.setValue(self.params["high_frequency_value"])
        self.ui.lowFrequencySpinBox.setRange(*self.params["frequencies_range"])
        self.ui.lowFrequencySpinBox.setValue(self.params["low_frequency_value"])
        self.ui.cyclesSpinBox.setRange(*self.params["cycles_range"])
        self.ui.cyclesSpinBox.setValue(self.params["cycles_value"])

        self.ui.normalizeComboBox.setEnabled(False)
        self.ui.normalizeComboBox.addItems(["Z-Score", "Percent change", "Relative power", "Min-Max"])
        self.ui.normalizeCheckBox.stateChanged.connect(
            lambda state: self.ui.normalizeComboBox.setEnabled(state == Qt.Checked)
        )

        self.ui.scaleComboBox.setEnabled(False)
        self.ui.scaleComboBox.addItems(["Log"])
        self.ui.scaleCheckBox.stateChanged.connect(
            lambda state: self.ui.scaleComboBox.setEnabled(state == Qt.Checked)
        )
    # end def

    def _create_vtk_container(self):
       
        try:
            vtk_layout = QVBoxLayout(self.ui.plotArea)
            vtk_layout.setContentsMargins(0, 0, 0, 0)
            self.vtk_widget = QVTKRenderWindowInteractor(self.ui.plotArea)
            vtk_layout.addWidget(self.vtk_widget)

            self.renwin = self.vtk_widget.GetRenderWindow()
            self._context_view = vtk.vtkContextView()
            self._context_view.SetRenderWindow(self.renwin)
            renderer = self._context_view.GetRenderer()
            renderer.SetBackground(0.98, 0.98, 0.98)
            self._vtk_renderer = renderer

            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor and not interactor.GetInitialized():
                interactor.Initialize()

            self._log("VTK container initialized.")
        except Exception as e:
            self._log("Error creating VTK container:", e)
    # end def

    def ensure_vtk(self):
       
        try:
            if not self.vtk_widget or not self.renwin:
                self._log("ensure_vtk: no vtk widget or render window available.")
                return
            if not self._context_view:
                self._context_view = vtk.vtkContextView()
                self._context_view.SetRenderWindow(self.renwin)
            renderer = self._context_view.GetRenderer()
            renderer.SetBackground(0.98, 0.98, 0.98)
            self._vtk_renderer = renderer
        except Exception as e:
            self._log("ensure_vtk error:", e)
    # end def


    # =====================================================
    # === Main logic: compute average CWT and render
    # =====================================================
    def on_create_wavelet(self):
        """Compute average CWT across all active trials and render the average scalogram."""
        tasks = self.kernel.get_service("TaskService") if self.kernel else None
        if tasks is None:
            self.alerts.error("El servicio de tareas no está disponible.")
            return

        if self.get_active_signal() is None:
            return

        trials = self.get_active_trials()
        if trials is None:
            return

        t = trials.time_rel
        if t is None or len(t) < 2:
            self.alerts.error(f"No hay suficiente información de tiempo en {self.active_signal.name}.")
            return

        try:
            data = np.array(trials.trials)  # shape: (n_samples, n_trials) or (n_trials, n_samples)
            # Ensure shape is (n_samples, n_trials)
            if data.ndim == 1:
                data = data[:, np.newaxis]
            if data.shape[0] < data.shape[1]:
                data = data.T
        except Exception as e:
            self.alerts.error(f"No se pudo obtener la matriz de trials: {e}")
            self._log("on_create_wavelet: failed to convert trials to array:", e)
            return

        fs_calculado = round(1.0 / (t[1] - t[0]), 3)

        # UI parameters
        fs = self.ui.sampleDensitySpinBox.value()
        fmin = self.ui.lowFrequencySpinBox.value()
        fmax = self.ui.highFrequencySpinBox.value()
        cycles = float(self.ui.cyclesSpinBox.value())
        normalize = self.ui.normalizeCheckBox.isChecked()
        scaled = self.ui.scaleCheckBox.isChecked()
        norm_method = self.ui.normalizeComboBox.currentText().lower()

        if fmin <= 0:
            self.alerts.error("La frecuencia baja debe ser mayor que cero.")
            return

        # Un cálculo anterior de este plugin (por ejemplo, al reabrir un proyecto)
        # se cancela; sus señales tardías se ignoran porque ya no es la tarea vigente.
        tasks.cancel_all_from(self.meta.id)
        self._terminar_calculo()
        self.stop()

        self._calculando = True
        self.ui.createWaveletButton.setEnabled(False)
        self.ui.createWaveletButton.setText("Computing...")

        handle = tasks.submit(
            cw.wavelet_promedio, owner=self.meta.id,
            data=data, fs_calculado=fs_calculado, fs=fs, fmin=fmin, fmax=fmax,
            cycles=cycles, normalize=normalize, scaled=scaled,
            norm_method=norm_method,
        )
        self._handle = handle
        handle.progress.connect(partial(self._on_wavelet_progress, handle))
        handle.finished.connect(partial(self._on_wavelet_done, handle))
        handle.failed.connect(partial(self._on_wavelet_failed, handle))
        handle.cancelled.connect(partial(self._on_wavelet_cancelled, handle))

    # end def

    def _terminar_calculo(self):
        self._calculando = False
        self._handle = None
        if self.ui is not None:
            self.ui.createWaveletButton.setEnabled(True)
            self.ui.createWaveletButton.setText("Generate")

    def _on_wavelet_progress(self, handle, percent, message):
        if handle is not self._handle:
            return
        self._log(f"{message} ({percent}%)")
        self._notify(f"{message} ({percent}%)")

    def _on_wavelet_failed(self, handle, message):
        if handle is not self._handle:
            return
        self._terminar_calculo()
        self.alerts.error(f"No se pudo calcular la wavelet: {message}")

    def _on_wavelet_cancelled(self, handle):
        if handle is not self._handle:
            return
        self._terminar_calculo()

    def _on_wavelet_done(self, handle, result):
        """Callback when the task finishes, already on the UI thread."""
        if handle is not self._handle:
            return
        try:
            # Si el proyecto se cerró mientras calculaba, ya no hay dónde dibujar.
            if self.ui is None:
                return
            times, freqs, avg_scalogram, scaled = result

            self.ensure_vtk()

            self.render_scalogram(times, freqs, avg_scalogram, "Wavelet Average (Morlet)", scaled)
            self._log("Rendering complete.")
            self.mark_project_dirty()
        except Exception as e:
            self._log("Render failed:", e)
            self.alerts.error(f"No se pudo dibujar el escalograma: {e}")
        finally:
            self._terminar_calculo()
            self.process("Done")

    # =====================================================
    # === Project save/restore
    # =====================================================
    def get_analysis_params(self) -> dict:
        return {
            "sample_density": self.ui.sampleDensitySpinBox.value(),
            "low_freq": self.ui.lowFrequencySpinBox.value(),
            "high_freq": self.ui.highFrequencySpinBox.value(),
            "cycles": self.ui.cyclesSpinBox.value(),
            "normalize_enabled": self.ui.normalizeCheckBox.isChecked(),
            "normalize_mode": self.ui.normalizeComboBox.currentText(),
            "scale_enabled": self.ui.scaleCheckBox.isChecked(),
            "scale_mode": self.ui.scaleComboBox.currentText(),
        }

    def apply_analysis_params(self, params: dict):
        self.ui.sampleDensitySpinBox.setValue(params.get("sample_density", self.ui.sampleDensitySpinBox.value()))
        self.ui.lowFrequencySpinBox.setValue(params.get("low_freq", self.ui.lowFrequencySpinBox.value()))
        self.ui.highFrequencySpinBox.setValue(params.get("high_freq", self.ui.highFrequencySpinBox.value()))
        self.ui.cyclesSpinBox.setValue(params.get("cycles", self.ui.cyclesSpinBox.value()))

        self.ui.normalizeCheckBox.setChecked(params.get("normalize_enabled", False))
        idx = self.ui.normalizeComboBox.findText(params.get("normalize_mode", ""))
        if idx >= 0:
            self.ui.normalizeComboBox.setCurrentIndex(idx)

        self.ui.scaleCheckBox.setChecked(params.get("scale_enabled", False))
        idx = self.ui.scaleComboBox.findText(params.get("scale_mode", ""))
        if idx >= 0:
            self.ui.scaleComboBox.setCurrentIndex(idx)

        self.on_create_wavelet()


    # =====================================================
    # === Wavelet computation (single trial)
    # =====================================================
    def compute_wavelet(self, sig, fs_calculado, fs, fmin, fmax, num_cycles):
        return cw.compute_wavelet(sig, fs_calculado, fs, fmin, fmax, num_cycles)

    # end def

    # =====================================================
    # === Normalization and scaling helpers
    # =====================================================
    def normalize_tf(self, tf, method="z-score"):
        return cw.normalize_tf(tf, method, log=self._log)

    # end def

    def _scale_log(self, scalogram, freqs):
        return cw.scale_log(scalogram, freqs, log=self._log)

    # end def

    def _get_log_ticks_coords(self, f_min_log, f_max_log):
        """Return tick coordinates and labels for log10 axis (inputs are log10 values)."""
        start = np.floor(f_min_log)
        end = np.ceil(f_max_log)

        tick_coords = np.arange(start, end + 0.5, 0.5)
        tick_coords = tick_coords[(tick_coords >= f_min_log) & (tick_coords <= f_max_log)]

        labels = []
        for t_coord in tick_coords:
            label_val = 10**t_coord
            labels.append(f"{label_val:.1f}")

        return tick_coords, labels
    # end def

    # =====================================================
    # === Rendering (VTK)
    # =====================================================
    def render_scalogram(self, t, freqs, scalogram, title="Scalogram", log_scale=False):
        
        if t is None or freqs is None or scalogram is None:
            self._log("render_scalogram aborted: empty data.")
            return

        if len(freqs) < 2 or len(t) < 2 or scalogram.size == 0:
            self._log("render_scalogram aborted: invalid scalogram.")
            return

        if not self.vtk_widget or not self._context_view:
            self._log("render_scalogram: VTK not initialized.")
            return

        context_view = self._context_view
        scene = context_view.GetScene()
        scene.ClearItems()
        scene.RemoveAllItems()

        # Preprocess scalogram array and compute geometry
        n_freqs, n_times = scalogram.shape
        if n_times <= 0 or n_freqs <= 0:
            self._log("render_scalogram: invalid scalogram shape:", scalogram.shape)
            return

        t0, t_end = float(t[0]), float(t[-1]) if len(t) > 1 else (0.0, float(t[0]) if len(t) > 0 else 1.0)[1]
        dt = (t_end - t0) / n_times if n_times > 1 else 1.0

        if log_scale:
            Z = np.nan_to_num(scalogram.astype(np.float32))
            ax_title = "Frequency (Hz) - Log"

            f0_orig = float(freqs[0]) if freqs[0] > 0 else 1e-6
            f_end_orig = float(freqs[-1])

            f0_coord = np.log10(f0_orig)
            f_end_coord = np.log10(f_end_orig)
            df_coord = (f_end_coord - f0_coord) / n_freqs if n_freqs > 1 else 1.0

            f0_range, f_end_range = f0_coord, f_end_coord
            df_spacing = df_coord
        else:
            Z = np.flipud(np.nan_to_num(scalogram.astype(np.float32)))
            ax_title = "Frequency (Hz)"

            f0_range = float(freqs[0])
            f_end_range = float(freqs[-1])
            df_spacing = (f_end_range - f0_range) / n_freqs if n_freqs > 1 else 1.0

        # Configure vtkImageData
        img = vtk.vtkImageData()
        img.SetDimensions(n_times, n_freqs, 1)
        img.SetSpacing(dt, df_spacing, 1.0)
        img.SetOrigin(t0, f0_range, 0.0)

        Z_plano = np.ascontiguousarray(Z, dtype=np.float32).ravel()
        arr = numpy_support.numpy_to_vtk(Z_plano, deep=True, array_type=vtk.VTK_FLOAT)
        img.GetPointData().SetScalars(arr)
        img.Modified()

        # Compute limits and LUT
        vmin, vmax = np.min(Z), np.max(Z)
        vmin, vmax = np.round([vmin, vmax], 2)
        lut = self._build_lut("viridis", vmin, vmax)

        # Create chart
        chart = vtk.vtkChartHistogram2D()
        chart.SetInputData(img, 0)
        chart.SetTransferFunction(lut)

        ax_bottom, ax_left = chart.GetAxis(vtk.vtkAxis.BOTTOM), chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_bottom.SetBehavior(0)
        ax_bottom.SetTitle("Time (s)")
        ax_bottom.SetRange(t0, t_end)

        ax_left.SetTitle(ax_title)
        ax_left.SetBehavior(0)
        ax_left.SetLogScale(False)
        ax_left.SetRange(f0_range, f_end_range)

        if log_scale:
            tick_values, tick_labels = self._get_log_ticks_coords(f0_range, f_end_range)

            tick_positions_array = vtk.vtkDoubleArray()
            [tick_positions_array.InsertNextValue(float(pos)) for pos in tick_values]

            tick_labels_array = vtk.vtkStringArray()
            [tick_labels_array.InsertNextValue(label) for label in tick_labels]

            ax_left.SetCustomTickPositions(tick_positions_array, tick_labels_array)
            ax_left.SetNumberOfTicks(0)
        else:
            ax_left.SetTickLabelAlgorithm(vtk.vtkAxis.TICK_WILKINSON_EXTENDED)
            ax_left.SetNumberOfTicks(-1)
            ax_left.SetPrecision(2)

        ax_bottom.GetLabelProperties().SetColor(0, 0, 0)
        ax_left.GetLabelProperties().SetColor(0, 0, 0)

        scene.AddItem(chart)

        # --- Contextual menu ---
        try:
            self.vtk_menu = VTKContextMenu(chart, self.vtk_widget, parent=self.widget)
            self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))

        except Exception as e:
            self.alerts.error("Error creating contextual map\n" + str(e), "Menu error")

        context_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)
        context_view.GetRenderWindow().Render()
    # end def

    # =====================================================
    # === Colormap LUT & helpers
    # =====================================================
    def _build_lut(self, mode: str, vmin: float, vmax: float) -> vtk.vtkLookupTable:
        """Build a lookup table (similar to 'jet' like mapping)."""
        N = 256
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(N)
        lut.SetRange(vmin, vmax)
        lut.Build()

        for i in range(N):
            t = i / (N - 1)

            if t < 0.125:
                r, g, b = 0, 0, 0.5 + 0.5 * (t / 0.125)
            elif t < 0.375:
                r, g, b = 0, (t - 0.125) / 0.25, 1
            elif t < 0.625:
                r, g, b = (t - 0.375) / 0.25, 1, 1 - (t - 0.375) / 0.25
            elif t < 0.875:
                r, g, b = 1, 1 - (t - 0.625) / 0.25, 0
            else:
                r, g, b = 1, 0.15 * (1 - (t - 0.875) / 0.125), 0

            r = 0.9 * r + 0.03
            g = 0.9 * g + 0.03
            b = 0.9 * b + 0.03

            lut.SetTableValue(i, r, g, b, 1.0)

        return lut
    # end def

    def _lut_to_ctf(self, lut: vtk.vtkLookupTable) -> vtk.vtkColorTransferFunction:
        """Convert a VTK lookup table into a vtkColorTransferFunction."""
        ctf = vtk.vtkColorTransferFunction()
        ctf.ClampingOn()
        n = lut.GetNumberOfTableValues()
        if n <= 0:
            return ctf
        vmin, vmax = lut.GetRange()
        if vmax == vmin:
            vmin -= 0.5
            vmax += 0.5
        for i in range(n):
            rgba = lut.GetTableValue(i)
            x = vmin + (vmax - vmin) * (i / (n - 1))
            ctf.AddRGBPoint(x, *rgba[:3])
        return ctf
    # end def
