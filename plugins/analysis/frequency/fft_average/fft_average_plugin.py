import os
import sys
from core.plugins.interfaces import IPlugin
import vtk
import numpy as np
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtWidgets, QtCore

from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
from core.utils.adapters import trials_matrix_to_vtk_table
from plugins.analysis.frequency.fft_average.fft_average_plugin_ui import Ui_Fft_Average

class Fft_average_plugin(IPlugin):
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        
        self.ui: Ui_Fft_Average | None = None
        
        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None
        self.chart: vtk.vtkChartXY | None = None
        

    def stop(self):
        self._log("stop")
        if self.vtk_interactor:
            self.vtk_interactor.Disable()
    

    def process(self, data):
        self._log(f"process(): {data}")
        if self.vtk_interactor:
            self.vtk_interactor.Enable()
    
    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget(): creating UI")
            self.ui = Ui_Fft_Average()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget

            self._log("UI created. plotArea:", bool(self.ui.plotArea),
                      "panel:", bool(self.ui.layoutWidget),
                      "splitter:", bool(self.ui.splitter))
            self._wire_ui()

        else:
            self.widget.setParent(parent)
        return self.widget
        

    ## === UI === ##
    def _wire_ui(self):
        self._log("wire ui")
        self.ui.calculateFftAvgButton.clicked.connect(self._on_calculate_clicked)
        self.ui.lowFrequencySpinBox.valueChanged.connect(self._sync_range)
        self.ui.highFrequencySpinBox.valueChanged.connect(self._sync_range)
        self.ui.sampleDensitySpinBox.setRange(0, 10000)
        self.ui.sampleDensitySpinBox.setSingleStep(10)
        self.ui.sampleDensitySpinBox.setValue(1000)
        self.ui.highFrequencySpinBox.setDecimals(2)
        self.ui.highFrequencySpinBox.setRange(0.0, 10000)
        self.ui.highFrequencySpinBox.setSingleStep(1.0)
        self.ui.highFrequencySpinBox.setValue(500.0)
        self.ui.lowFrequencySpinBox.setDecimals(2)
        self.ui.lowFrequencySpinBox.setRange(0.0, 10000)
        self.ui.lowFrequencySpinBox.setSingleStep(1.0)
        self.ui.lowFrequencySpinBox.setValue(0.0)

    def _on_calculate_clicked(self):
            self._log("_on_calculate_clicked()")
            # 1) Load trials from the active signal
            fs, X, ch_name = self._load_trials_from_store()
            if X is None or fs is None:
                self._notify("FFT Average: no trials in the active signal.")
                return

            # 2) UI parameters
            target_fs = float(self.ui.sampleDensitySpinBox.value())  # 0 = no resampling
            lo = float(self.ui.lowFrequencySpinBox.value())
            hi = float(self.ui.highFrequencySpinBox.value())
            if lo > hi:
                lo, hi = hi, lo

            # 3) FFT
            per_trial = False
            freq, mag_avg, fs_eff = self._compute_fft_average(X, fs, target_fs, per_trial = per_trial)

            # 4) Plot
            self._plot_fft_average(freq, mag_avg, ch_name, lo, hi, fs_eff)
            self._notify(f"FFT ready: fs_eff={fs_eff:.2f} Hz, {freq.size} bins, trials={mag_avg.shape[1]}")

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
    
        # ------- VTK -------
    def _ensure_vtk(self):
        self._log("ensure_vtk(): enter")
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

      
    # ====== DATA ======
    def _load_trials_from_store(self):
        """
        Find the active signal in the DataStore and return:
          fs: float (TrialDataset sampling_rate)
          X:  np.ndarray (Ns, T)  trials matrix (columns = trials)
          ch_name: channel name (optional for title)
        """

         
        if self.get_active_signal() is None:
            return None, None, None

        td = self.get_active_trials()

        if td is None or td.trials.size == 0:
            return None, None, None

        fs = float(getattr(td, "sampling_rate", 0.0))
        X  = np.asarray(getattr(td, "trials", None), dtype=np.float64)  # (Ns, T)
        ch = getattr(td, "channel_name", "")
        if X is None or X.ndim != 2 or fs <= 0:
            self._log("Invalid TrialDataset (fs<=0 or trials not 2D).")
            return None, None, None

        self._log(f"Trials: Ns={X.shape[0]}, T={X.shape[1]}, fs={fs}")
        return fs, X, ch
    
    # ====== FFT - AVERAGE ======
    def _compute_fft_average(self, X: np.ndarray, fs: float, target_fs: float, *, per_trial: bool = False):
        """
        MATLAB-style FFT with optional averaging across trials.
        - X: (Ns, T)  (columns = trials)
        - fs: original sampling rate
        - target_fs: if > 0, resample via decimation (srt = round(fs/target_fs))

        Returns:
        freq: (Nf,)
        mag:  (Nf, T) if per_trial=True, or (Nf, 1) if averaged
        fs_eff: float
        """
        Ns, T = X.shape
        # Decimation as in MATLAB
        if target_fs and target_fs > 0:
            srt = max(1, int(round(fs / float(target_fs))))
        else:
            srt = 1
        fs_eff = fs / srt
        Xds = X[::srt, :] if srt > 1 else X

        # === FFT mean ===
        Ns_eff = Xds.shape[0]
        mFourier = np.fft.fft(Xds, n=Ns_eff, axis=0)           # (Ns_eff, T)
        mFourier = mFourier[: (Ns_eff // 2) + 1, :]            # (Nf, T)
        mag = np.abs(mFourier).astype(np.float64)              # (Nf, T)
        freq = np.linspace(0.0, fs_eff/2.0, mFourier.shape[0])

        if per_trial:
            # Equivalent to GF==1 in MATLAB: return all curves
            mag_out = mag  # (Nf, T)
        else:
            # Average across trials (like mean(m_FFT',1) in MATLAB)
            # Use nanmean to ignore NaNs if any
            mag_mean = np.nanmean(mag, axis=1)        # (Nf,)
            mag_out  = mag_mean[:, None]              # (Nf, 1) para reutilizar el mismo plotter

        self._log(f"FFT_AVG: srt={srt}, fs_eff={fs_eff:.3f} Hz, Nf={freq.size}, "
                f"T={T}, per_trial={per_trial}")
        return freq, mag_out, fs_eff

    # ====== Plot in VTK ======
    def _plot_fft_average(self, freq: np.ndarray, mag: np.ndarray, ch_name: str, lo: float, hi: float, fs_eff: float):
        """
        Build a vtkTable using trials_matrix_to_vtk_table(freq, mag)
        and draw one line per trial. Apply [lo, hi] filter.
        """
        if self.vtk_view is None:
            self._ensure_vtk()

        hi = min(hi, fs_eff/2.0)
        lo = max(lo, 0.0)
        if lo >= hi:
            self._notify("Empty frequency range after adjusting to Nyquist."); return
        sel = (freq >= lo) & (freq <= hi)
        self._log(f"Plot bins: {sel.sum()} of {freq.size}")
        freq_v = freq[sel]
        mag_v  = mag[sel, :]  # (Nf_sel, T)

        # Limit number of displayed curves
        MAX_PLOTS = 200
        if mag_v.shape[1] > MAX_PLOTS:
            self._log(f"There are {mag_v.shape[1]} trials → showing {MAX_PLOTS}")
            mag_v = mag_v[:, :MAX_PLOTS]

        table = trials_matrix_to_vtk_table(freq_v, mag_v)

        # Create clean chart
        scene = self.vtk_view.GetScene()
        scene.ClearItems()
        self.chart = vtk.vtkChartXY()
        scene.AddItem(self.chart)

        ax_b = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_l = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_b.SetGridVisible(True); ax_l.SetGridVisible(True)
        ax_b.SetTitle("Frequency (Hz)")
        ax_l.SetTitle("Magnitude")
        try:
            if ch_name:
                self.chart.SetTitle(f"FFT - {ch_name}")
        except Exception:
            pass
        
        # One plot per column
        num_cols = table.GetNumberOfColumns()
        print(f"num_cols={num_cols}")
        for c in range(1, num_cols):
            plot = self.chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, 0, c)
            plot.SetWidth(1.0)

           # --- Context menu ---

        try:
            self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor, self.active_signal.name, ch_name,self.meta.id,  parent=self.widget)

        except Exception as e:
            self.alerts.error(f"Error creating the context menu.\n {str(e)}")
     


        self.vtk_view.GetRenderWindow().Render()
