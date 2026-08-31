from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
import numpy as np
import pywt
from scipy.interpolate import interp1d

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
from core.services.data_store import DataStore
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
        if self.get_active_signal() is None:
            return

        trials = self.get_active_trials()
        if trials is None:
            return
        
        t = trials.time_rel
        if t is None or len(t) < 2:
            self.alerts.error(f"No enough information on time. {sig.name}.")
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
            self.alerts.error("Low frequency cannot be zero or negative.")
            return
        
        scalogram, times, freqs = self.compute_wavelet(sig, fs_calculado, fs, fmin, fmax, cycles)

        if normalize:
            scalogram = self.normalize_tf(scalogram, norm_method)
        
        if scaled:
            scalogram, freqs = self._scale_log(scalogram, freqs)

        self.render_scalogram(times, freqs, scalogram, "Scalogram Wavelet (Morlet)", scaled)
    # end def

    # =====================================================
    # === Wavelet Calculation
    # =====================================================
    def compute_wavelet(self, sig, fs_calculado, fs, fmin, fmax, num_cycles):
        """Compute the Continuous Wavelet Transform (CWT) using Morlet wavelet."""
        freq_seg = 2 * int(fmax - fmin)
        factor = int(round(fs_calculado / fs))
        sig = sig[::factor]

        freq_axis = np.linspace(fmin, fmax, freq_seg)[::-1] 
        wavelet = f"cmor{num_cycles}-1.0"
        central_freq = pywt.central_frequency(wavelet)
        scales = central_freq * fs / freq_axis

        coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs)
        scalogram = np.abs(coef)
        time_axis = np.arange(len(sig)) / fs

        return scalogram, time_axis, freq_axis
    # end def

    # =====================================================
    # === Normalization and Scaling
    # =====================================================
    def normalize_tf(self, tf, method="z-score"):
        """Normalize the time-frequency map."""
        base_mean = np.mean(tf, axis=1, keepdims=True)
        base_std = np.std(tf, axis=1, ddof=0, keepdims=True)
        base_min = np.min(tf)
        base_max = np.max(tf)

        if method == "z-score":
            return (tf - base_mean) / base_std

        elif method == "percent change":
            return ((tf - base_mean) / base_mean) * 100

        elif method == "relative power":
            return tf / base_mean

        elif method == "min-max":
            denom = base_max - base_min
            return (tf - base_min) / denom
        else:
            raise ValueError("Not recognized method.")
    # end def

    def _scale_log(self, scalogram, freqs):
        """Resample the scalogram so that rows are spaced logarithmically."""
        freqs_numeric = np.asarray(freqs, dtype=np.float64)
        
        fmin = np.min(freqs_numeric[freqs_numeric > 0])
        fmax = np.max(freqs_numeric)
        
        n_freqs_new = scalogram.shape[0] 
        
        log_fmin = np.log10(fmin)
        log_fmax = np.log10(fmax)
        
        log_freqs_new = np.linspace(log_fmin, log_fmax, n_freqs_new)
        freqs_new = 10**log_freqs_new 
        
        scalogram_new = np.zeros_like(scalogram)
        
        freqs_orig_sorted = np.sort(freqs_numeric)
        
        for i in range(scalogram.shape[1]):
            data_col = np.flipud(scalogram[:, i]) 
            
            interp_func = interp1d(freqs_orig_sorted, data_col, kind='linear', fill_value='extrapolate')
            scalogram_new[:, i] = interp_func(freqs_new)

        return scalogram_new, freqs_new
    # end def

    def _get_log_ticks_coords(self, f_min_log, f_max_log):
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
        dt = (t_end - t0) / n_times if n_times > 1 else 1.0

        if log_scale:
            Z = np.nan_to_num(scalogram.astype(np.float32))
            ax_title = "Frequency (Hz) - Log"
            
            # Calculate limits in LOG10 scale
            f0_orig = float(freqs[0]) if freqs[0] > 0 else 1e-6
            f_end_orig = float(freqs[-1])
            
            f0_coord = np.log10(f0_orig)
            f_end_coord = np.log10(f_end_orig)
            df_coord = (f_end_coord - f0_coord) / n_freqs if n_freqs > 1 else 1.0
            
            # VTK uses LOG10 coordinates directly
            f0_range, f_end_range = f0_coord, f_end_coord
            df_spacing = df_coord

        else:
            Z = np.flipud(np.nan_to_num(scalogram.astype(np.float32)))
            ax_title = "Frequency (Hz)"
            
            # Ranges in linear scale
            f0_range = float(freqs[0])
            f_end_range = float(freqs[-1])
            df_spacing = (f_end_range - f0_range) / n_freqs if n_freqs > 1 else 1.0
            
        # --- Configure vtkImageData ---
        img = vtk.vtkImageData()
        img.SetDimensions(n_times, n_freqs, 1)
        img.SetSpacing(dt, df_spacing, 1.0)
        img.SetOrigin(t0, f0_range, 0.0)
        
        img.AllocateScalars(vtk.VTK_FLOAT, 1)
        
        for j in range(n_freqs):
            for i in range(n_times):
                img.SetScalarComponentFromFloat(i, j, 0, 0, Z[j, i])
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
        ax_bottom.SetBehavior(0)
        ax_bottom.SetTitle("Time (s)")
        ax_bottom.SetRange(t0, t_end)
        
        # --- Y Axis Configuration ---
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
