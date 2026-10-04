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
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore
from plugins.analysis.time_frequency.wavelet import compute as cw
from plugins.analysis.time_frequency.wavelet.wavelet_plugin_ui import Ui_Wavelet


class Wavelet_plugin(IPlugin):
    """Time-Frequency Analysis Plugin (Wavelet CWT with PyWavelets + VTK Visualization)"""

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
    # === Plugin lifecycle
    # =====================================================

    def process(self, data: any):
        if self.vtk_widget:
            self.vtk_widget.Enable()

        if self.vtk_widget and self.vtk_widget.GetRenderWindow():
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            interactor.Enable()
    # end def

    def stop(self):
        if self.vtk_widget and self.vtk_widget.GetRenderWindow():
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor:
                interactor.Disable()
    # end def

    # =====================================================
    # === Create widget UI + VTK
    # =====================================================
    def get_widget(self, parent=None):
        if self.widget is not None:
            self.widget.setParent(parent)
            return self.widget

        self.widget = QWidget(parent)
        self.ui = Ui_Wavelet()
        self.ui.setupUi(self.widget)
        self.alerts.parent = self.widget

        self.init_controls()
        self.ensure_vtk()


        return self.widget
    # end def

    # =====================================================
    # === Utilities
    # =====================================================
    def init_controls(self):
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

        self.ui.createWaveletButton.clicked.connect(self.on_create_wavelet)
        self.ui.clearButton.clicked.connect(self._on_clear_clicked)
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

    def ensure_vtk(self):
        """Initialize VTK components for rendering."""
        try:
            if self.vtk_widget and self._context_view and self.renwin:
                return

            # --- Create VTK Widget ---
            if not self.vtk_widget:
                vtk_layout = QVBoxLayout(self.ui.plotArea)
                vtk_layout.setContentsMargins(0, 0, 0, 0)

                self.vtk_widget = QVTKRenderWindowInteractor(self.ui.plotArea)
                vtk_layout.addWidget(self.vtk_widget)

            # --- Create Render Window ---
            if not self.renwin:
                self.renwin = self.vtk_widget.GetRenderWindow()

            # --- Create Context View ---
            if not self._context_view:
                self._context_view = vtk.vtkContextView()
                self._context_view.SetRenderWindow(self.renwin)

            # --- Config renderer ---
            renderer = self._context_view.GetRenderer()
            renderer.SetBackground(0.98, 0.98, 0.98)
            self._vtk_renderer = renderer

            # --- Initialize interactor ---
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor and not interactor.GetInitialized():
                interactor.Initialize()
            # end if

        except Exception as e:
            self._log("Error ensure_vtk:", e)
    # end def

    

    # =====================================================
    # === Main Logic: CWT + Render
    # =====================================================
    def on_create_wavelet(self):
        """ Load active signal, compute CWT wavelet and render scalogram in VTK """
        tasks = self.kernel.get_service("TaskService") if self.kernel else None
        if tasks is None:
            self.alerts.error("El servicio de tareas no está disponible.")
            return

        signal = self.get_active_signal()
        if signal is None:
            return

        trials = self.get_active_trials()
        if trials is None:
            return
        
        t = trials.time_rel
        if t is None or len(t) < 2:
            self.alerts.error(f"No hay suficiente información de tiempo en {signal.name}.")
            return

        try:
            sig = trials.trials[:, 0] if trials.trials.ndim == 2 else np.ravel(trials.trials)
        except Exception:
            sig = np.array(trials.trials, dtype=float).ravel()

        sig = np.nan_to_num(np.asarray(sig).flatten(), nan=0.0, posinf=0.0, neginf=0.0)
        fs_calculado = round(1.0 / (t[1] - t[0]), 3)

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
        if fmax <= fmin:
            self.alerts.error(f"La frecuencia alta ({fmax:g} Hz) debe ser mayor que la baja ({fmin:g} Hz).")
            return

        # El factor de submuestreo es entero, asi que una densidad que no divida
        # a la del archivo no se puede alcanzar. Se valida y se avisa contra la
        # que de verdad se va a usar, no contra la pedida (problema nº 18).
        fs_efectiva, _ = cw.tasa_efectiva(fs_calculado, fs)
        if fmax > fs_efectiva / 2:
            self.alerts.error(f"La frecuencia alta ({fmax:g} Hz) no puede superar {fs_efectiva / 2:g} Hz, "
                              f"la mitad de la densidad efectiva ({fs_efectiva:g} Hz).")
            return
        if abs(fs_efectiva - fs) > 1e-9:
            self.alerts.info(f"La densidad de {fs:g} Hz no divide a los {fs_calculado:g} Hz del archivo; "
                             f"se usará {fs_efectiva:.1f} Hz, la más cercana alcanzable.")

        # Un cálculo anterior de este plugin (por ejemplo, al reabrir un proyecto)
        # se cancela; sus señales tardías se ignoran porque ya no es la tarea vigente.
        tasks.cancel_all_from(self.meta.id)
        self._terminar_calculo()
        self.stop()

        self._calculando = True
        self.ui.createWaveletButton.setEnabled(False)
        self.ui.createWaveletButton.setText("Computing...")

        # Con escala logarítmica la CWT se calcula directamente sobre el eje
        # logarítmico, así que la normalización trabaja sobre filas reales.
        handle = tasks.submit(
            cw.wavelet_individual, owner=self.meta.id,
            sig=sig, fs_calculado=fs_calculado, fs=fs, fmin=fmin, fmax=fmax,
            cycles=cycles, normalize=normalize, scaled=scaled,
            norm_method=norm_method, t0=float(t[0]),
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
    # end def

    def _on_wavelet_progress(self, handle, percent, message):
        if handle is not self._handle:
            return
        self._log(f"{message} ({percent}%)")
        self._notify(f"{message} ({percent}%)")
    # end def

    def _on_wavelet_failed(self, handle, message):
        if handle is not self._handle:
            return
        self._terminar_calculo()
        self.alerts.error(f"No se pudo calcular la wavelet: {message}")
    # end def

    def _on_wavelet_cancelled(self, handle):
        if handle is not self._handle:
            return
        self._terminar_calculo()
    # end def

    def _on_wavelet_done(self, handle, result):
        """Se ejecuta ya en el hilo de la interfaz."""
        if handle is not self._handle:
            return
        try:
            # Si el proyecto se cerró mientras calculaba, ya no hay dónde dibujar.
            if self.ui is None:
                return
            times, freqs, scalogram, scaled = result

            self.ensure_vtk()

            self.render_scalogram(times, freqs, scalogram, "Scalogram Wavelet (Morlet)", scaled)
            self.mark_project_dirty()
        except Exception as e:
            self._log("render_scalogram:", e)
            self.alerts.error(f"No se pudo dibujar el escalograma: {e}")
        finally:
            self._terminar_calculo()
            self.process("Done")
    # end def

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
    # === Wavelet Calculation
    # =====================================================
    def compute_wavelet(self, sig, fs_calculado, fs, fmin, fmax, num_cycles, escala_log=False, t0=0.0):
        return cw.compute_wavelet(sig, fs_calculado, fs, fmin, fmax, num_cycles,
                                  escala_log=escala_log, t0=t0)

    # end def

    # =====================================================
    # === Normalization and Scaling
    # =====================================================
    def normalize_tf(self, tf, method="z-score"):
        return cw.normalize_tf(tf, method, log=self._log)

    # end def

    def _scale_log(self, scalogram, freqs):
        return cw.scale_log(scalogram, freqs, log=self._log)

    # end def

    def _get_log_ticks_coords(self, f_min_log, f_max_log):
        """Marcas 1-2-5 de cada década; entradas y posiciones en log10, etiquetas en Hz."""
        valores = [m * 10.0 ** k
                   for k in range(int(np.floor(f_min_log)), int(np.ceil(f_max_log)) + 1)
                   for m in (1, 2, 5)]
        valores = [v for v in valores if f_min_log - 1e-9 <= np.log10(v) <= f_max_log + 1e-9]
        if len(valores) < 2:
            valores = [10 ** f_min_log, 10 ** f_max_log]

        return np.log10(valores), [f"{v:.3g}" for v in valores]
    # end def

    # =====================================================
    # === Render 2D scalogram in VTK
    # =====================================================
    def render_scalogram(self, t, freqs, scalogram, title="Scalogram", log_scale=False):
        if not self.vtk_widget:
            return

        context_view = self._context_view
        scene = context_view.GetScene()
        scene.ClearItems()
        
        # --- Preprocessing and Assignment ---
        n_freqs, n_times = scalogram.shape
        t0, t_end = float(t[0]), float(t[-1])
        # vtkChartHistogram2D dibuja cada punto con un paso de ancho, así que
        # n pasos cubren exactamente de t0 a t_end.
        dt = (t_end - t0) / n_times if n_times > 1 else 1.0

        # Filas ordenadas de la frecuencia más baja a la más alta, con el origen
        # en la mínima y paso positivo (en log10 si la escala es logarítmica).
        f = np.asarray(freqs, dtype=float)
        Z = np.nan_to_num(scalogram.astype(np.float32))
        if f[0] > f[-1]:
            Z = np.flipud(Z)
            f = f[::-1]
        if log_scale:
            ax_title = "Frequency (Hz) - Log"
            f0_range, f_end_range = float(np.log10(max(f[0], 1e-6))), float(np.log10(f[-1]))
        else:
            ax_title = "Frequency (Hz)"
            f0_range, f_end_range = float(f[0]), float(f[-1])
        df_spacing = (f_end_range - f0_range) / n_freqs if n_freqs > 1 else 1.0

        # --- Configure vtkImageData ---
        img = vtk.vtkImageData()
        img.SetDimensions(n_times, n_freqs, 1)
        img.SetSpacing(dt, df_spacing, 1.0)
        img.SetOrigin(t0, f0_range, 0.0)
        
        Z_plano = np.ascontiguousarray(Z, dtype=np.float32).ravel()
        arr = numpy_support.numpy_to_vtk(Z_plano, deep=True, array_type=vtk.VTK_FLOAT)
        img.GetPointData().SetScalars(arr)
        img.Modified()

        # --- Calculate limits and LUT ---
        vmin, vmax = np.min(Z), np.max(Z)
        vmin, vmax = np.round([vmin, vmax], 2)
        lut = self._build_lut("viridis", vmin, vmax)
        
        # --- Create 2D Chart ---
        chart = vtk.vtkChartHistogram2D()
        chart.SetInputData(img, 0)
        chart.SetTransferFunction(lut)

        ax_bottom, ax_left = chart.GetAxis(vtk.vtkAxis.BOTTOM), chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_bottom.SetBehavior(vtk.vtkAxis.FIXED)
        ax_bottom.SetTitle("Time (s)")
        ax_bottom.SetRange(t0, t_end)

        # --- Y Axis Configuration ---
        ax_left.SetTitle(ax_title)
        ax_left.SetBehavior(vtk.vtkAxis.FIXED)
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
            # Standard linear mode
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
            self.alerts.info(f"Error creating contextual map\n {str(e)}", "Contextual map")

            
        context_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)
        context_view.GetRenderWindow().Render()
    # end def

    # =====================================================
    # === Colormap LUT
    # =====================================================
    def _build_lut(self, mode: str, vmin: float, vmax: float) -> vtk.vtkLookupTable:
        N = 256
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(N)
        lut.SetRange(vmin, vmax)
        lut.Build()

        for i in range(N):
            t = i / (N - 1)

            # --- JET ---
            if t < 0.125:
                r, g, b = 0, 0, 0.5 + 0.5 * (t / 0.125)      # bright blue
            elif t < 0.375:
                r, g, b = 0, (t - 0.125) / 0.25, 1           # cyan
            elif t < 0.625:
                r, g, b = (t - 0.375) / 0.25, 1, 1 - (t - 0.375) / 0.25  # green
            elif t < 0.875:
                r, g, b = 1, 1 - (t - 0.625) / 0.25, 0        # yellow
            else:
                r, g, b = 1, 0.15 * (1 - (t - 0.875) / 0.125), 0  # bright red

            r = 0.9 * r + 0.03
            g = 0.9 * g + 0.03
            b = 0.9 * b + 0.03

            lut.SetTableValue(i, r, g, b, 1.0)

        return lut
    # end def

    # =====================================================
    # === Convert LUT to CTF
    # =====================================================
    def _lut_to_ctf(self, lut: vtk.vtkLookupTable) -> vtk.vtkColorTransferFunction:
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
# end class
