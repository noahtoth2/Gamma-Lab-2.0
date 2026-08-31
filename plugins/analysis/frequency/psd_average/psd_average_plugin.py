import sys
import numpy as np
import vtk
from PyQt5 import QtWidgets, QtCore
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from scipy.signal import welch

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
# UI and VTK adapter
from plugins.analysis.frequency.psd_average.psd_average_plugin_ui import Ui_Psd_average
from core.utils.adapters import trials_matrix_to_vtk_table

class Psd_average_plugin(IPlugin):
    """
    Plugin to compute Average Power Spectral Density (PSD)
    across all trials (per-frequency average).
    Mirrors the structure used by other signal plugins.
    """
    
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)

        # UI
        self.ui: Ui_Psd_average | None = None

        # VTK
        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None
        self.chart: vtk.vtkChartXY | None = None
        self.vtk_menu: VTKContextMenu | None = None



    def start(self, kernel):
        self._log("start() - getting MainWindow")
        self.mainwin = kernel.get_service("MainWindow")
        self.started = True

    def stop(self):
        self._log("stop() - cleanup VTK")
        if self.vtk_interactor:
            self.vtk_interactor.Disable()
        
    def process(self, data):
        if self.vtk_interactor:
            self.vtk_interactor.Enable()
        self._log(f"Process: enable {data}")

    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget(): creating UI")
            self.ui = Ui_Psd_average()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget

            self._log("UI created. plotArea:", bool(self.ui.plotArea),
                      "panel:", bool(self.ui.layoutWidget),
                      "splitter:", bool(self.ui.splitter))
            
            self._ensure_vtk()
            self._wire_ui()

            # post-show logs (actual sizes)
            QtCore.QTimer.singleShot(0, self._log_sizes)
        else:
            self.widget.setParent(parent)
        return self.widget

    def _log_sizes(self):
        if self.widget:
            self._log(f"Widget size={self.widget.size().width()}x{self.widget.size().height()}")
        if self.ui and self.ui.plotArea:
            self._log(f"plotArea size={self.ui.plotArea.size().width()}x{self.ui.plotArea.size().height()}")

    def _wire_ui(self):
        self._log("wire ui")
        self.ui.calculatePsdAvgButton.clicked.connect(self._on_calculate_clicked)
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
        
        # Keep noverlap synced to nperseg
        self.ui.npersegSpinBox.valueChanged.connect(self._sync_noverlap)

    def _sync_noverlap(self):
        """Set noverlap to half of nperseg by default."""
        nperseg = self.ui.npersegSpinBox.value()
        self.ui.noverlapSpinBox.setValue(nperseg // 2)
        # Make nfft follow nperseg (common behavior)
        self.ui.nfftSpinBox.setValue(nperseg)

    # ------- VTK -------
    def _ensure_vtk(self):
        self._log("ensure_vtk(): enter")
        if self.vtk_interactor:
             self.ui.plotArea.layout().addWidget(self.vtk_interactor)
             return

        self.vtk_interactor = QVTKRenderWindowInteractor(self.ui.plotArea)
        self.ui.plotArea.setLayout(QtWidgets.QVBoxLayout())
        self.ui.plotArea.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.plotArea.layout().addWidget(self.vtk_interactor)
        self._log("ensure_vtk(): embedded interactor")

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
            self._notify("PSD Average: no trials in active signal.")
            return

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

            if lo > hi:
                lo, hi = hi, lo
            
            if noverlap >= nperseg:
                 raise ValueError("N-overlap must be lower than N-per-seg.")
        
        except Exception as e:
            self.alerts.error(f"Parameter error: {e}")
            return

        # 3) PSD (always compute for all trials)
        try:
            freq, power_all_trials, fs_eff = self._compute_psd(X, fs, target_fs,
                                                    window, nperseg, noverlap, nfft)
            # power_all_trials shape: (Nf, T) -> equivalent to 'pxx'
            
        except Exception as e:
            self._log(f"Error in _compute_psd: {str(e)}")
            self.alerts.error(f"Could not compute PSD: {str(e)}", "Computation Error")
            return
            
        # --- Average logic ---
        # Per-frequency mean across trials (axis=1)
        # Equivalent to mean(pxx') in MATLAB
        power_to_plot = np.mean(power_all_trials, axis=1, keepdims=True)
        plot_title = f"PSD (Average) - {ch_name}"

        # 4) Plot
        self._plot_psd(freq, power_to_plot, plot_title, lo, hi, ch_name)
        self._notify(f"PSD (Average) ready: fs_eff={fs_eff:.2f} Hz, {freq.size} bins")


    def _sync_range(self):
        lo = float(self.ui.lowFrequencySpinBox.value())
        hi = float(self.ui.highFrequencySpinBox.value())
        if lo > hi:
            sender = self.widget.sender()
            if sender is self.ui.lowFrequencySpinBox:
                self.ui.highFrequencySpinBox.setValue(lo)
            else:
                self.ui.lowFrequencySpinBox.setValue(hi)
        self._log(f"range sync: low={lo}, high={hi}")

    def _notify(self, msg: str):
        if self.mainwin:
            try:
                self.mainwin.statusBar().showMessage(msg, 3000)
                return
            except Exception:
                pass
        self._log(msg)

    # ====== DATA ======
    def _load_trials_from_store(self):
        if not self.mainwin:
            return None, None, None

        if self.get_active_signal() is None:
            return None, None, None
        
        td = self.get_active_trials()
        if td is None or getattr(td, "trials", None) is None:
            return None, None, None    

        fs = float(getattr(td, "sampling_rate", 0.0))
        X  = np.asarray(getattr(td, "trials", None), dtype=np.float64)  # (Ns, T)
        ch = getattr(td, "channel_name", "")
        if X is None or X.ndim != 2 or fs <= 0:
            self._log("Invalid TrialDataset (fs<=0 or trials not 2D).")
            return None, None, None

        self._log(f"Trials: Ns={X.shape[0]}, T={X.shape[1]}, fs={fs}")
        return fs, X, ch


    # ====== PSD Logic (NaN -> 0) ======
    def _compute_psd(self, X: np.ndarray, fs: float, target_fs: float,
                     window: str, nperseg: int, noverlap: int, nfft: int):
        
        Ns, T = X.shape
        if target_fs and target_fs > 0:
            srt = max(1, int(round(fs / float(target_fs))))
        else:
            srt = 1

        fs_eff = fs / srt
        Xds = X[::srt, :] if srt > 1 else X
        Ns_eff = Xds.shape[0]
        
        # Replace NaNs/Inf with zeros
        # 1) Find NaNs
        nan_mask = np.isnan(Xds)
        num_nans = np.sum(nan_mask)
        if num_nans > 0:
            self._log(f"Warning: found {num_nans} NaN points. Replacing with 0.")
            # 2) Replace NaNs with 0 (in-place)
            np.nan_to_num(Xds, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        
        # 3) Use all trials
        X_clean = Xds

        if nperseg > Ns_eff:
            self._log(f"Warning: nperseg ({nperseg}) > Ns_eff ({Ns_eff}). "
                      f"Adjusting nperseg to {Ns_eff}.")
            nperseg = Ns_eff
        if noverlap >= nperseg:
            self._log(f"Warning: noverlap >= nperseg. Adjusting noverlap.")
            noverlap = nperseg // 2

        self._log(f"Welch params: fs_eff={fs_eff}, window={window}, nperseg={nperseg}, "
                  f"noverlap={noverlap}, nfft={nfft}, axis=0")

        # 4) Run Welch on cleaned data
        freq, power = welch(
            X_clean, # <-- Usar X_clean
            fs=fs_eff,
            window=window,
            nperseg=nperseg,
            noverlap=noverlap,
            nfft=nfft,
            scaling='density', # V^2/Hz
            axis=0
        )
        
        power = power.astype(np.float64) # (Nf, T)
        freq = freq.astype(np.float64)   # (Nf,)

        self._log(f"PSD: srt={srt}, fs_eff={fs_eff:.3f} Hz, Nf={freq.size}, T_calc={power.shape[1]}")
        return freq, power, fs_eff

    # ====== Plot en VTK ======
    def _plot_psd(self, freq: np.ndarray, power: np.ndarray, 
                  plot_title: str, lo: float, hi: float, ch_name: str):
        
        if self.vtk_view is None:
            self._ensure_vtk()

        # Frequency range filter
        sel = (freq >= lo) & (freq <= hi)
        freq_v = freq[sel]
        power_v = power[sel, :]  # (Nf_sel, 1)

        # power_v is already (Nf, 1), so num_curves will be 1
        num_curves = power_v.shape[1] 
        table = trials_matrix_to_vtk_table(freq_v, power_v)

        # Crear chart limpio
        scene = self.vtk_view.GetScene()
        scene.ClearItems()
        self.chart = vtk.vtkChartXY()
        scene.AddItem(self.chart)

        ax_b = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_l = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_b.SetGridVisible(True); ax_l.SetGridVisible(True)
        ax_b.SetTitle("Frequency (Hz)")
        ax_l.SetTitle("PSD (V^2/Hz)")
        
        try:
            self.chart.SetTitle(plot_title)
        except Exception:
            pass
        
        # Only one column (c=1)
        self._log(f"Plotting {table.GetNumberOfColumns()-1} PSD Average curve.")
        
        plot = self.chart.AddPlot(vtk.vtkChart.LINE)
        plot.SetInputData(table, 0, 1) # Plot only the first (and only) column
        plot.SetWidth(2.0) # Thick line for the average

       # --- Context menu ---
        try:
            self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor, 
                                           self.active_signal.name, ch_name, 
                                           self.meta.id, parent=self.widget)
        except Exception as e:
            self.alerts.error(f"Error creating the context menu.\n {str(e)}")

   
        self.vtk_view.GetRenderWindow().Render()
        # Hide watermark once a chart is displayed
        try:
            if self.mainwin:
                self.mainwin.hide_watermark()
        except Exception:
            pass
