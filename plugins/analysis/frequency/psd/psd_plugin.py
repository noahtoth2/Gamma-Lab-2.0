import sys
import numpy as np
import vtk
from PyQt5 import QtWidgets, QtCore
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from scipy.signal import welch

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
# UI and VTK adapter
from plugins.analysis.frequency.psd.psd_plugin_ui import Ui_Psd
from core.utils.adapters import trials_matrix_to_vtk_table

class Psd_plugin(IPlugin):
    """
    Power Spectral Density (PSD) plugin with selectable modes:
    All Trials, Average, Individual. Mirrors other signal plugins.
    """
    
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.ui: Ui_Psd | None = None

        # VTK
        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None
        self.chart: vtk.vtkChartXY | None = None
        self.vtk_menu: VTKContextMenu | None = None


    def stop(self):
        self._log("stop() - cleanup VTK")
        if self.vtk_interactor:
            self.vtk_interactor.Disable()
        
    def process(self, data):
        if self.vtk_interactor:
            self.vtk_interactor.Enable()
        self._log(f"[PSD] Process: enable {data}")

    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget(): creating UI")
            self.ui = Ui_Psd()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget

            self._log("UI created. plotArea:", bool(self.ui.plotArea),
                      "panel:", bool(self.ui.layoutWidget),
                      "splitter:", bool(self.ui.splitter))
            
            self._ensure_vtk()
            # Detrend combobox is provided by the UI
            self._wire_ui()
            self._init_defaults()  # MATLAB-like defaults

            # Show watermark until the chart is generated
            try:
                if self.mainwin:
                    self.mainwin.show_watermark()
            except Exception:
                pass

            # logs post-show (dimensiones reales)
            QtCore.QTimer.singleShot(0, self._log_sizes)
        else:
            self.widget.setParent(parent)
        return self.widget

    def _log_sizes(self):
        if self.widget:
            self._log(f"Widget size={self.widget.size().width()}x{self.widget.size().height()}")
        if self.ui and self.ui.plotArea:
            self._log(f"plotArea size={self.ui.plotArea.size().width()}x{self.ui.plotArea.size().height()}")
    
    # --- UI helpers ---

    def _init_defaults(self):
        """Set MATLAB-like defaults and a wide plotting range."""
        # Window: hamming
        try:
            idx = self.ui.windowComboBox.findText("hamming", QtCore.Qt.MatchFixedString)
            if idx >= 0:
                self.ui.windowComboBox.setCurrentIndex(idx)
        except Exception:
            pass
        # nperseg: 256, noverlap: 128, nfft: 256
        self.ui.npersegSpinBox.setValue(256)
        self._sync_noverlap()  # sets noverlap=128 and nfft=256
        # Detrend: none
        if hasattr(self.ui, "detrendComboBox"):
            self.ui.detrendComboBox.setProperty("variant", "input")
            self.ui.detrendComboBox.setCurrentText("none")
            
        # Default plotting range (Low=0.0, High=500.0)
        self.ui.lowFrequencySpinBox.setValue(0.0)
        self.ui.highFrequencySpinBox.setValue(500.0)
        
        # Mode: Individual, Trial: 0
        try:
            midx = self.ui.modeComboBox.findText("Individual", QtCore.Qt.MatchFixedString)
            if midx >= 0:
                self.ui.modeComboBox.setCurrentIndex(midx)
        except Exception:
            pass
        self.ui.trialIndexSpinBox.setValue(0)
    # --- End UI helpers ---

    def _wire_ui(self):
        self._log("wire ui")
        self.ui.calculatePsdButton.clicked.connect(self._on_calculate_clicked)
        self.ui.lowFrequencySpinBox.valueChanged.connect(self._sync_range)
        self.ui.highFrequencySpinBox.valueChanged.connect(self._sync_range)
        self.ui.npersegSpinBox.setRange(0, 500)
        self.ui.npersegSpinBox.setValue(256)
        self.ui.noverlapSpinBox.setRange(0, 500)
        self.ui.noverlapSpinBox.setValue(128)
        self.ui.nfftSpinBox.setRange(0, 500)
        self.ui.nfftSpinBox.setValue(256)
        self.ui.sampleDensitySpinBox.setRange(0, 10000)
        self.ui.sampleDensitySpinBox.setSingleStep(10)
        self.ui.sampleDensitySpinBox.setValue(1000)
        self.ui.highFrequencySpinBox.setDecimals(2)
        self.ui.highFrequencySpinBox.setRange(0.0, 10000)
        self.ui.highFrequencySpinBox.setSingleStep(1.0)
        self.ui.highFrequencySpinBox.setValue(40.0)
        self.ui.lowFrequencySpinBox.setDecimals(2)
        self.ui.lowFrequencySpinBox.setRange(0.0, 10000)
        self.ui.lowFrequencySpinBox.setSingleStep(1.0)
        self.ui.lowFrequencySpinBox.setValue(0.0)
        
        # Keep noverlap synced with nperseg
        self.ui.npersegSpinBox.valueChanged.connect(self._sync_noverlap)
        
        # Mode combobox
        self.ui.modeComboBox.currentTextChanged.connect(self._on_mode_changed)

    def _on_mode_changed(self, mode_text: str):
        """Show or hide the individual trial selector."""
        is_individual = (mode_text == "Individual")
        self.ui.trialIndexLabel.setVisible(is_individual)
        self.ui.trialIndexSpinBox.setVisible(is_individual)
        
        # Enable the spinbox only when visible and there are trials
        num_trials = self.ui.trialIndexSpinBox.maximum() + 1
        self.ui.trialIndexSpinBox.setEnabled(is_individual and num_trials > 0)

    def _sync_noverlap(self):
        """Set noverlap to half of nperseg by default."""
        nperseg = self.ui.npersegSpinBox.value()
        self.ui.noverlapSpinBox.setValue(nperseg // 2)
        # Make nfft follow nperseg (common behavior)
        self.ui.nfftSpinBox.setValue(nperseg)

    # ------- VTK -------
    def _ensure_vtk(self, *args):  # no unused args
        self._log("ensure_vtk(): enter")
        if self.vtk_interactor:
             self.ui.plotArea.layout().addWidget(self.vtk_interactor)
             return

        self.vtk_interactor = QVTKRenderWindowInteractor(self.ui.plotArea)
        self.ui.plotArea.setLayout(QtWidgets.QVBoxLayout())
        self.ui.plotArea.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.plotArea.layout().addWidget(self.vtk_interactor)
        self._log("ensure_vtk(): interactor embedded")

        self.vtk_view = vtk.vtkContextView()
        self.vtk_view.SetRenderWindow(self.vtk_interactor.GetRenderWindow())
        self.vtk_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        try:
            self.vtk_interactor.Initialize()
        except Exception:
            pass
        self._log("ensure_vtk(): scheduled init")


    # ------- actions -------
    def _on_calculate_clicked(self):
        self._log("_on_calculate_clicked()")

        # 1) Load trials from active signal
        fs, X, ch_name = self._load_trials_from_store()
        if X is None or fs is None:
            self._notify("PSD: no trials in active signal.")
            # Disable selector on failure
            self.ui.trialIndexSpinBox.setEnabled(False)
            self.ui.trialIndexSpinBox.setRange(0, 0)
            return
            
        # Target Fs default = fs (no downsample)
        if self.ui.sampleDensitySpinBox.value() <= 0:
             self.ui.sampleDensitySpinBox.setValue(fs)
        # Range 0..fs/2
        if self.ui.lowFrequencySpinBox.value() >= self.ui.highFrequencySpinBox.value():
            self.ui.lowFrequencySpinBox.setValue(0.0)
            self.ui.highFrequencySpinBox.setValue(fs/2.0)
            
        # Update UI with number of trials
        num_trials = X.shape[1]
        self.ui.trialIndexSpinBox.setRange(0, num_trials - 1)
        # Enable for Individual mode
        is_individual = (self.ui.modeComboBox.currentText() == "Individual")
        self.ui.trialIndexSpinBox.setEnabled(is_individual)


        # 2) UI parameters
        try:
            target_fs = float(self.ui.sampleDensitySpinBox.value())
            lo = float(self.ui.lowFrequencySpinBox.value())
            hi = float(self.ui.highFrequencySpinBox.value())
            
            # Welch parameters
            window = self.ui.windowComboBox.currentText()
            nperseg = self.ui.npersegSpinBox.value()
            noverlap = self.ui.noverlapSpinBox.value()
            nfft = self.ui.nfftSpinBox.value()
            
            # Detrend
            detrend = self.ui.detrendComboBox.currentText()
            
            # Mode parameters
            mode = self.ui.modeComboBox.currentText()
            trial_idx = self.ui.trialIndexSpinBox.value()

            if lo > hi:
                lo, hi = hi, lo
            
            # Validate Welch parameters
            if nperseg <= 1:
                raise ValueError("N-per-seg must be > 1.")
            if noverlap < 0:
                raise ValueError("N-overlap cannot be negative.")
            # The noverlap>=nperseg adjustment is handled inside _compute_psd
            
        except Exception as e:
            self.alerts.error(f"Parameter error: {str(e)}")
            return

        # 3) PSD (always compute for all trials)
        try:
            freq, power_all_trials, fs_eff = self._compute_psd(
                X, fs, target_fs, window, nperseg, noverlap, nfft, detrend
            )
            # power_all_trials has shape (Nf, T)
            
        except Exception as e:
            self._log(f"Error in _compute_psd: {e}")
            self.alerts.error(f"Could not compute PSD: {e}")
                                 
            return
            
        # Choose what to plot based on mode
        power_to_plot = None
        plot_title = ""
        
        if mode == "All Trials":
            power_to_plot = power_all_trials
            plot_title = f"PSD (All Trials) - {ch_name}"
            
        elif mode == "Average":
            # Per-frequency average (axis=1)
            power_to_plot = np.mean(power_all_trials, axis=1, keepdims=True)
            plot_title = f"PSD (Average) - {ch_name}"
            
        elif mode == "Individual":
            if not (0 <= trial_idx < num_trials):
                self._notify(f"Error: Trial index {trial_idx} out of range.")
                return
            # Pick only that trial column
            power_to_plot = power_all_trials[:, trial_idx:trial_idx+1]
            plot_title = f"PSD (Trial {trial_idx}) - {ch_name}"
            

        # 4) Plot
        if power_to_plot is not None:
            self._plot_psd(freq, power_to_plot, plot_title, lo, hi, ch_name)
            self._notify(f"PSD ({mode}) ready: fs_eff={fs_eff:.2f} Hz, {freq.size} bins")
        else:
            self._notify(f"Error: Calculation mode '{mode}' not recognized.")


    def _sync_range(self):
        # Simplify sync (no sender())
        lo = float(self.ui.lowFrequencySpinBox.value())
        hi = float(self.ui.highFrequencySpinBox.value())
        if lo > hi:
            # Force hi to match lo when needed
            self.ui.highFrequencySpinBox.setValue(lo)
        self._log(f"range sync: low={self.ui.lowFrequencySpinBox.value()}, "
                  f"high={self.ui.highFrequencySpinBox.value()}")

    # ====== DATA ======
    def _load_trials_from_store(self):
        if not self.mainwin:
            return None, None, None

        if self.get_active_signal() is None:
            return None, None, None

        td = self.get_active_trials()

        if td is None or td.trials.size == 0:
            return None, None, None

        fs = float(getattr(td, "sampling_rate", 0.0))
        X = np.asarray(getattr(td, "trials", None), dtype=np.float64) # (Ns, T)
        ch = getattr(td, "channel_name", "")
        if X is None or X.ndim != 2 or fs <= 0:
            self._log("Invalid TrialDataset (fs<=0 or trials not 2D).")
            return None, None, None

        self._log(f"Trials: Ns={X.shape[0]}, T={X.shape[1]}, fs={fs}")
        return fs, X, ch

    # ====== PSD Logic ======
    def _compute_psd(self, X: np.ndarray, fs: float, target_fs: float,
                     window: str, nperseg: int, noverlap: int, nfft: int, detrend: str):
        
        Ns, T = X.shape
        # Downsample
        srt = max(1, int(round(fs / float(target_fs)))) if (target_fs and target_fs > 0) else 1
        fs_eff = fs / srt
        Xds = X[::srt, :] if srt > 1 else X
        Ns_eff = Xds.shape[0]
        
        # --- Robust clamps ---
        if nperseg > Ns_eff:
            self._log(f"Warning: nperseg ({nperseg}) > Ns_eff ({Ns_eff}). Adjusting to {Ns_eff}.")
            nperseg = Ns_eff
        if noverlap >= nperseg:
            self._log("Warning: noverlap >= nperseg. Adjusting to nperseg//2.")
            noverlap = nperseg // 2
        # nfft < nperseg clamp (fuerza nfft = max(nfft, nperseg))
        if nfft < nperseg:
            self._log("Adjusting nfft to nperseg to satisfy SciPy.")
            nfft = nperseg

        # Detrend SciPy: False for 'none', string for 'constant'/'linear'
        detrend_arg = False if detrend == "none" else detrend

        self._log(f"Welch params: fs_eff={fs_eff}, window={window}, nperseg={nperseg}, "
                  f"noverlap={noverlap}, nfft={nfft}, detrend={detrend_arg}, axis=0")

        freq, power = welch(
            Xds,
            fs=fs_eff,
            window=window,
            nperseg=nperseg,
            noverlap=noverlap,
            nfft=nfft,
            detrend=detrend_arg,  # detrend argument
            scaling='density', # V^2/Hz
            axis=0
        )
        
        # Clean NaN/Inf artifacts from output
        power = np.nan_to_num(power, nan=0.0, posinf=np.inf, neginf=0.0).astype(np.float64)
        freq = freq.astype(np.float64) # (Nf,)

        self._log(f"PSD: srt={srt}, fs_eff={fs_eff:.3f} Hz, Nf={freq.size}, T={power.shape[1]}")
        return freq, power, fs_eff

    # ====== Plot in VTK ======
    def _plot_psd(self, freq: np.ndarray, power: np.ndarray, 
                   plot_title: str, lo: float, hi: float, ch_name: str):
        """
        Build a vtkTable and draw power curves.
        'power' is (Nf, T) or (Nf, 1).
        Applies frequency filter and auto-fit Y limits.
        """
        if self.vtk_view is None:
            self._ensure_vtk()

        # Frequency range filter (X axis)
        sel = (freq >= lo) & (freq <= hi)
        freq_v = freq[sel]
        # 'power' is already 2D (Nf_sel, T) or (Nf_sel, 1)
        power_v = power[sel, :]

        # Limit number of curves if too many trials
        num_curves = power_v.shape[1]
        MAX_PLOTS = 200
        if num_curves > MAX_PLOTS:
            self._log(f"There are {num_curves} trials → showing {MAX_PLOTS}")
            power_v = power_v[:, :MAX_PLOTS]

        table = trials_matrix_to_vtk_table(freq_v, power_v)

        # Fresh chart
        scene = self.vtk_view.GetScene()
        scene.ClearItems()
        self.chart = vtk.vtkChartXY()
        scene.AddItem(self.chart)

        ax_b = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_l = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_b.SetGridVisible(True); ax_l.SetGridVisible(True)
        ax_b.SetTitle("Frequency (Hz)")
        ax_l.SetTitle("PSD (V^2/Hz)")
        
        # Auto-fit Y axis to avoid clipping peaks
        if power_v.size > 0:
            # Max across visible data
            y_max_data = np.max(power_v)
            # Add 10% headroom
            y_max_limit = y_max_data * 1.10 
            # Lower limit for PSD is 0.0
            y_min_limit = 0.0 
            
            # Apply to left axis (Y)
            ax_l.SetMinimum(y_min_limit)
            ax_l.SetMaximum(y_max_limit)
            self._log(f"Auto Y fit: range=[{y_min_limit:.2e}, {y_max_limit:.2e}]")

        try:
            # Use dynamic title
            self.chart.SetTitle(plot_title)
        except Exception:
            pass
        
        # One plot per column (1 or T)
        num_cols = table.GetNumberOfColumns()
        self._log(f"Plotting {num_cols-1} PSD curves.")
        
        # If single curve, make it thicker
        line_width = 0.5 if num_curves > 1 else 2.0
        
        for c in range(1, num_cols):
            plot = self.chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, 0, c)
            plot.SetWidth(line_width) 

       # --- Context menu ---
        try:
            self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor,
                                           self.active_signal.name, ch_name,
                                           self.meta.id, parent=self.widget)

        except Exception as e:
            self.alerts.error(f"Error creating the context menu.\n {str(e)}")

        self.vtk_view.GetRenderWindow().Render()

        # Hide watermark once content is present
        try:
            if self.mainwin:
                self.mainwin.hide_watermark()
        except Exception:
            pass
