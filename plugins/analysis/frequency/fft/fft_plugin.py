# plugins/analysis/frequency/fft/fft_plugin.py
from PyQt5 import QtWidgets, QtCore
import vtk
import numpy as np
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
from plugins.analysis.frequency.fft.fft_plugin_ui import Ui_Fft
from core.utils.adapters import trials_matrix_to_vtk_table

class Fft_plugin(IPlugin):
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.ui: Ui_Fft | None = None

        # VTK
        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None
        self.chart: vtk.vtkChartXY | None = None


    def stop(self):
        self._log("stop() - cleanup VTK")
        #self._cleanup_vtk()
        if self.vtk_interactor:
            self.vtk_interactor.Disable()
        
    def process(self, data):
        if self.vtk_interactor:
            self.vtk_interactor.Enable()

        self._log(f"[FFT] Process: enable {data}")

    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget(): creating UI")
            self.ui = Ui_Fft()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget

            # UI structure log
            self._log("UI created. plotArea:", bool(self.ui.plotArea),
                      "panel:", bool(self.ui.layoutWidget),
                      "splitter:", bool(self.ui.splitter))
            #self._ensure_vtk()
            self._wire_ui()

            # post-show logs (actual dimensions)
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
        self.ui.calculateFftButton.clicked.connect(self._on_calculate_clicked)
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


    # ------- actions (placeholder) -------
    def _on_calculate_clicked(self):
            self._log("_on_calculate_clicked()")

            # 1) Load trials from the active signal
            fs, X, ch_name = self._load_trials_from_store()
            if X is None or fs is None:
                self._notify("FFT: no trials in the active signal.")
                return

            # 2) UI parameters
            target_fs = float(self.ui.sampleDensitySpinBox.value())  # 0 = no resampling
            lo = float(self.ui.lowFrequencySpinBox.value())
            hi = float(self.ui.highFrequencySpinBox.value())
            if lo > hi:
                lo, hi = hi, lo

            # 3) FFT
            freq, mag, fs_eff = self._compute_fft(X, fs, target_fs)

            # 4) Plot
            self._plot_fft(freq, mag, ch_name, lo, hi)
            self._notify(f"FFT ready: fs_eff={fs_eff:.2f} Hz, {freq.size} bins, trials={mag.shape[1]}")

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

    # ====== DATA ======
    def _load_trials_from_store(self):
        """
        Find the active signal in the DataStore and return:
          fs: float (TrialDataset sampling_rate)
          X:  np.ndarray (Ns, T)  trials matrix (columns = trials)
          ch_name: channel name (optional for title)
        """
        if not self.mainwin:
            return None, None, None

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

    # ====== FFT ======
    def _compute_fft(self, X: np.ndarray, fs: float, target_fs: float):
        """
        Returns (freq:(Nf,), mag:(Nf,T), fs_eff:float)
        """
        Ns, T = X.shape
        if target_fs and target_fs > 0:
            srt = max(1, int(round(fs / float(target_fs))))
        else:
            srt = 1

        fs_eff = fs / srt
        Xds = X[::srt, :] if srt > 1 else X
        Ns_eff = Xds.shape[0]

        mFourier = np.fft.rfft(Xds, axis=0)             # (Nf, T)
        mag = np.abs(mFourier).astype(np.float64)       # (Nf, T)
        freq = np.fft.rfftfreq(Ns_eff, d=1.0/fs_eff)    # (Nf,)

        self._log(f"FFT: srt={srt}, fs_eff={fs_eff:.3f} Hz, Nf={freq.size}, T={mag.shape[1]}")
        return freq, mag, fs_eff

    # ====== Plot in VTK using the adapter ======
    def _plot_fft(self, freq: np.ndarray, mag: np.ndarray, ch_name: str, lo: float, hi: float):
        """
        Build a vtkTable using trials_matrix_to_vtk_table(freq, mag)
        and draw one line per trial. Apply [lo, hi] filter.
        """
        if self.vtk_view is None:
            self._ensure_vtk()

        # Frequency range filter
        sel = (freq >= lo) & (freq <= hi)
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
            plot.SetWidth(0.5)

         # --- Context menu ---

        try:
            self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor, self.active_signal.name, ch_name, self.meta.id, parent=self.widget)

        except Exception as e:
            self.alerts.error(f"Error creating the context menu.\n {str(e)}")
     

        self.vtk_view.GetRenderWindow().Render()
