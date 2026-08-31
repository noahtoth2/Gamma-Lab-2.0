import sys
import numpy as np
from PyQt5 import QtWidgets, QtCore
from scipy.signal import welch
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.model.signal_dataset import SignalDataset
from plugins.analysis.frequency.relative_psd.relative_psd_plugin_ui import Ui_Relative_psd
from core.utils.adapters import trials_matrix_to_vtk_table


class Relative_psd_plugin(IPlugin):
    """
    Relative (and absolute) PSD mirroring MATLAB's f_PSD_Relative.
    - Welch per column (trials)
    - Total power Ptot in [0.5, 490] Hz
    - Bin selection like MATLAB: id1 = find(f>=lo), id2 = find(f>=hi), sum inclusive id1:id2
    - GF mode:
        GF=1 -> All Trials (sum power across trials, no averaging)
        GF=0 -> Average (average PSD across trials)
    """

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.ui: Ui_Relative_psd | None = None
        # Plot toggle (disable chart rendering as requested)
        self._plot_enabled: bool = False
        # VTK
        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None
        self.chart: vtk.vtkChartXY | None = None


    def stop(self):
        self._log("stop()")
        if self._plot_enabled and self.vtk_interactor:
            self.vtk_interactor.Disable()

    def process(self, data):
        if self._plot_enabled and self.vtk_interactor:
            self.vtk_interactor.Enable()

        self._log(f"[Relative PSD] Process: enable {data}")

    # ---------- UI ----------
    def get_widget(self, parent=None):
        if self.widget is None:
            self.ui = Ui_Relative_psd()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            # Chart disabled: do not create a plot area unless enabled
            if self._plot_enabled:
                try:
                    if not hasattr(self.ui, "plotArea"):
                        self.ui.plotArea = QtWidgets.QWidget(self.widget)
                        self.ui.plotArea.setObjectName("plotArea")
                        if self.widget.layout() is None:
                            self.widget.setLayout(QtWidgets.QVBoxLayout())
                        self.widget.layout().insertWidget(0, self.ui.plotArea, stretch=1)
                except Exception:
                    pass
            self._inject_optional_controls()
            self._wire_ui()
            self._init_defaults()
            if self._plot_enabled and hasattr(self.ui, "plotArea"):
                if self.ui.plotArea.layout() is None:
                    self.ui.plotArea.setLayout(QtWidgets.QVBoxLayout())
                    self.ui.plotArea.layout().setContentsMargins(0, 0, 0, 0)
        else:
            self.widget.setParent(parent)
        return self.widget

    def _inject_optional_controls(self):
        """Inject optional controls without assuming a specific UI layout."""
        def _add_form_row(label_text: str, w: QtWidgets.QWidget):
            # 1) Add to form layout if present
            if hasattr(self.ui, "welchParameters") and isinstance(self.ui.welchParameters, QtWidgets.QVBoxLayout):
                row_layout = QtWidgets.QHBoxLayout()
                row_layout.addWidget(QtWidgets.QLabel(label_text))
                row_layout.addWidget(w)
                self.ui.welchParameters.addLayout(row_layout)

                return
            # 2) Add to widget layout if present
            if hasattr(self.ui, "layoutWidget") and isinstance(self.ui.layoutWidget, QtWidgets.QWidget):
                lay = self.ui.layoutWidget.layout()
                if lay is not None:
                    hl = QtWidgets.QHBoxLayout()
                    hl.addWidget(QtWidgets.QLabel(label_text))
                    hl.addWidget(w)
                    lay.addLayout(hl)
                else:
                    # Create a layout if missing
                    lay = QtWidgets.QVBoxLayout(self.ui.layoutWidget)
                    hl = QtWidgets.QHBoxLayout()
                    hl.addWidget(QtWidgets.QLabel(label_text))
                    hl.addWidget(w)
                    lay.addLayout(hl)
                return

            # 3) Fallback: root plugin widget layout
            if self.widget.layout() is None:
                self.widget.setLayout(QtWidgets.QVBoxLayout())
            hl = QtWidgets.QHBoxLayout()
            hl.addWidget(QtWidgets.QLabel(label_text))
            hl.addWidget(w)
            self.widget.layout().addLayout(hl)

        # --- Detrend ---
        if not hasattr(self.ui, "detrendComboBox"):
            detrend_cb = QtWidgets.QComboBox()
            detrend_cb.addItems(["none", "constant", "linear"])
            self.ui.detrendComboBox = detrend_cb
            _add_form_row("Detrend", detrend_cb)

        # --- GF (calculation mode) ---
        if not hasattr(self.ui, "gainFactorComboBox"):
            gf_cb = QtWidgets.QComboBox()
            gf_cb.addItems(["Average (GF=0)", "All Trials (GF=1)"])
            self.ui.gainFactorComboBox = gf_cb
            _add_form_row("Calculation Mode (GF)", gf_cb)

    def _wire_ui(self):
        self.ui.calculateRelativePsd.clicked.connect(self._on_calculate_clicked)
        self.ui.npersegSpinBox.valueChanged.connect(self._sync_noverlap)
        # keep lo/hi consistent
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
        self.ui.highFrequencySpinBox.setValue(12.0)
        self.ui.lowFrequencySpinBox.setDecimals(2)
        self.ui.lowFrequencySpinBox.setRange(0.0, 10000)
        self.ui.lowFrequencySpinBox.setSingleStep(1.0)
        self.ui.lowFrequencySpinBox.setValue(8.0)

    def _init_defaults(self):
        # Hamming window (like MATLAB)
        try:
            idx = self.ui.windowComboBox.findText("hamming", QtCore.Qt.MatchFixedString)
            if idx >= 0:
                self.ui.windowComboBox.setCurrentIndex(idx)
        except Exception:
            pass
        # Welch
        self.ui.npersegSpinBox.setValue(256)
        self._sync_noverlap()
        self.ui.nfftSpinBox.setValue(256)
        # Default band
        self.ui.lowFrequencySpinBox.setValue(8.0)
        self.ui.highFrequencySpinBox.setValue(12.0)
        # Detrend
        if hasattr(self.ui, "detrendComboBox"):
            self.ui.detrendComboBox.setProperty("variant", "input")
            self.ui.detrendComboBox.setCurrentText("none")
        # Default GF = 1 (All Trials) to emulate MATLAB if untouched
        if hasattr(self.ui, "gainFactorComboBox"):
            self.ui.gainFactorComboBox.setProperty("variant", "input")
            self.ui.gainFactorComboBox.setCurrentIndex(1)

    def _sync_noverlap(self):
        nperseg = self.ui.npersegSpinBox.value()
        self.ui.noverlapSpinBox.setValue(nperseg // 2)
        self.ui.nfftSpinBox.setValue(nperseg)

    def _sync_range(self):
        lo = float(self.ui.lowFrequencySpinBox.value())
        hi = float(self.ui.highFrequencySpinBox.value())
        if lo > hi:
            sender = self.widget.sender() if self.widget else None
            if sender is self.ui.lowFrequencySpinBox:
                self.ui.highFrequencySpinBox.setValue(lo)
            else:
                self.ui.lowFrequencySpinBox.setValue(hi)
        self._log(f"range sync: low={lo}, high={hi}")

    # ---------- actions ----------
    def _on_calculate_clicked(self):
        self._log("_on_calculate_clicked()")

        fs, X, ch_name = self._load_trials_from_store()
        if X is None or fs is None:
            self._notify("Relative PSD: no trials in active signal.")
            return

        # Default target Fs (sufficient resolution)
        if self.ui.sampleDensitySpinBox.value() <= 0:
            self.ui.sampleDensitySpinBox.setValue(min(fs, 1000.0))

        # Parameters
        try:
            target_fs = float(self.ui.sampleDensitySpinBox.value())
            window 	  = self.ui.windowComboBox.currentText()
            nperseg 	= self.ui.npersegSpinBox.value()
            noverlap 	= self.ui.noverlapSpinBox.value()
            nfft 	  = self.ui.nfftSpinBox.value()
            f1 	    = float(self.ui.lowFrequencySpinBox.value())
            f2 	    = float(self.ui.highFrequencySpinBox.value())
            detrend 	= getattr(self.ui, "detrendComboBox", None)
            detrend 	= detrend.currentText() if detrend else "none"
            gf_idx 	= getattr(self.ui, "gainFactorComboBox", None)
            GF 	    = 1 if (gf_idx and gf_idx.currentIndex() == 1) else 0 	# 1=All Trials, 0=Average

            if f1 >= f2:
                raise ValueError("Low frequency must be lower than High frequency.")
        except Exception as e:
            self.alerts.error(f"Parameter error: {str(e)}")
            return

        try:
            freq, pxx_all, fs_eff = self._compute_psd(
                X, fs, target_fs, window, nperseg, noverlap, nfft, detrend
            )
        except Exception as e:
            self._log("Error in _compute_psd:", e)
            self.alerts.error(f"Could not compute PSD: {e}")
            return

        # --- Relative PSD (GF) ---
        abs_power, rel_power = self._compute_relative_psd(freq, pxx_all, f1, f2, GF)

        # UI
        self.ui.absPowerValue.setText(f"{abs_power: .4e}")
        self.ui.relPowerValue.setText(f"{rel_power: .4f}")

        self._notify(f"Relative PSD [{f1}-{f2} Hz] ready. fs_eff={fs_eff:.1f} Hz, df≈{freq[1]-freq[0]:.2f} Hz")

        # Log standard bands (like MATLAB)
        self._log_bands(freq, pxx_all, GF)

        # Plot disabled
        if self._plot_enabled:
            try:
                self._plot_psd(freq, pxx_all, ch_name, f1, f2)
            except Exception as e:
                self._log(f"Plot error: {e}")

    # ---------- Relative PSD ----------

    # 1) Replace _band_sum(...) with edge handling
    def _band_sum(self, freq: np.ndarray, pxx: np.ndarray, lo: float, hi: float,
                  edges: str = "matlab") -> float:
        """
        Sum power in [lo, hi] with two edge policies:
          - edges='matlab'    -> inclusive upper edge (id2 = find(f>=hi); sum[i1:id2])
          - edges='exclusive' -> exclusive upper edge (sum[i1:id2]) without the 'hi' bin
        """
        i1 = int(np.searchsorted(freq, lo, side="left"))
        if edges == "matlab":
            i2 = int(np.searchsorted(freq, hi, side="left"))  # include hi bin
            i1 = max(0, min(i1, len(freq) - 1))
            i2 = max(0, min(i2, len(freq) - 1))
            if i2 < i1: i1, i2 = i2, i1
            return float(np.nansum(pxx[i1:i2 + 1]))
        else:
            i2 = int(np.searchsorted(freq, hi, side="left"))  # exclusive
            i1 = max(0, min(i1, len(freq)))
            i2 = max(0, min(i2, len(freq)))
            if i2 < i1: i1, i2 = i2, i1
            return float(np.nansum(pxx[i1:i2]))


    # 2) Main computation using that edge policy
    def _compute_relative_psd(self, freq: np.ndarray, pxx_all: np.ndarray,
                              f1: float, f2: float, GF: int):
        """
        Reproduces f_PSD_Relative:
        - GF=1: pxx_av = pxx_all (all trials), then sum across trials
        - GF=0: pxx_av = mean(pxx_all, across trials)
        Ptot in [0.5, 490] Hz.
        Uses _band_sum to handle edges (inclusive/exclusive).
        """
        # sum (GF=1) or average (GF=0)
        pxx_sum = np.nansum(pxx_all, axis=1) if GF == 1 else np.nanmean(pxx_all, axis=1)

        edges_mode = "matlab"     # or "exclusive" if you want bands to sum ≈1

        # Quick debug tip:
        df = freq[1]-freq[0]
        i1 = np.searchsorted(freq, f1, side="left")
        i2_matlab = np.searchsorted(freq, f2, side="left")
        self._log(f"df = {df:.4f} Hz")
        self._log(f"Band [{f1}-{f2}] Hz: bins [{i1}:{i2_matlab}] (MATLAB-style) -> f[{i1}]={freq[i1]:.4f}, f[{i2_matlab}]={freq[min(i2_matlab,len(freq)-1)]:.4f}")
        # End quick tip

        Ptot     = self._band_sum(freq, pxx_sum, 0.5, 490.0, edges=edges_mode)
        pow_band = self._band_sum(freq, pxx_sum, f1,  f2,    edges=edges_mode)
        rel      = (pow_band / Ptot) if Ptot > 0 else 0.0

        self._log(f"[GF={GF}, edges={edges_mode}] Band {f1}-{f2} Hz -> Abs={pow_band:.4e}, RelFrac={rel:.4f}")
        return pow_band, rel


    # 3) Log band parts similar to MATLAB
    def _log_bands(self, freq: np.ndarray, pxx_all: np.ndarray, GF: int):
        # sum (GF=1) or average (GF=0)
        pxx_sum = np.nansum(pxx_all, axis=1) if GF == 1 else np.nanmean(pxx_all, axis=1)
        edges_mode = "matlab"  # same as used above

        def bsum(lo, hi): return self._band_sum(freq, pxx_sum, lo, hi, edges=edges_mode)

        Ptot = bsum(0.5, 490.0)
        if Ptot <= 0:
            self._log("Ptot <= 0; bands not logged."); return

        # MATLAB band edges used by the original function
        bands = [
            ("delta",   0.5,   3.9),
            ("theta",   4.0,   7.9),
            ("alpha",   8.0,  11.9),
            ("beta",   12.0,  24.9),
            ("gamma1", 25.0,  59.0),
            ("gamma2", 61.0, 120.0),
            ("HFO1",  121.0, 250.0),
            ("HFO2",  251.0, 490.0),
        ]
        parts = []
        self._log("-" * 40) # Separator for band logs
        for name, lo, hi in bands:
            val = bsum(lo, hi) / Ptot
            parts.append(val)
            self._log(f"Band {name:6s} [{lo:>5.1f}-{hi:>6.1f}] -> {val:.4f}")

        total_parts = sum(parts)
        self._log(f"Sum of bands (δ+θ+α+β+γ1+γ2+HFO1+HFO2) = {total_parts:.4f}")
        self._log("-" * 40)


    # ---------- DATA ----------
    def _load_trials_from_store(self):
        if not self.mainwin:
            return None, None, None


        if self.get_active_signal() is None:
            return None, None, None

        td = self.get_active_trials()

        if td is None or td.trials.size == 0:
            return None, None, None

        fs = float(getattr(td, "sampling_rate", 0.0))
        X = np.asarray(getattr(td, "trials", None), dtype=np.float64) 	# (Ns, T)
        ch = getattr(td, "channel_name", "")
        if X is None or X.ndim != 2 or fs <= 0:
            self._log("Invalid TrialDataset (fs<=0 or trials not 2D).")
            return None, None, None

        self._log(f"Trials: Ns={X.shape[0]}, T={X.shape[1]}, fs={fs}")
        return fs, X, ch

    # ------- VTK -------
    def _ensure_vtk(self):
        self._log("ensure_vtk(): enter")
        if not hasattr(self.ui, "plotArea") or self.ui.plotArea is None:
            return
        if self.vtk_interactor is not None:
            return
        self.vtk_interactor = QVTKRenderWindowInteractor(self.ui.plotArea)
        self.ui.plotArea.layout().addWidget(self.vtk_interactor)

        self.vtk_view = vtk.vtkContextView()
        self.vtk_view.SetRenderWindow(self.vtk_interactor.GetRenderWindow())
        self.vtk_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        try:
            self.vtk_interactor.Initialize()
        except Exception:
            pass
        self._log("ensure_vtk(): scheduled init")

    def _plot_psd(self, freq: np.ndarray, pxx_all: np.ndarray, ch_name: str, lo: float, hi: float):
        if self.vtk_view is None:
            self._ensure_vtk()
        if self.vtk_view is None:
            return

        sel = (freq >= lo) & (freq <= hi)
        freq_v = freq[sel]
        pxx_v = pxx_all[sel, :]

        MAX_PLOTS = 200
        if pxx_v.shape[1] > MAX_PLOTS:
            self._log(f"There are {pxx_v.shape[1]} trials → showing {MAX_PLOTS}")
            pxx_v = pxx_v[:, :MAX_PLOTS]

        table = trials_matrix_to_vtk_table(freq_v, pxx_v)

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
            if ch_name:
                self.chart.SetTitle(f"Relative PSD - {ch_name}")
        except Exception:
            pass

        num_cols = table.GetNumberOfColumns()
        for c in range(1, num_cols):
            plot = self.chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, 0, c)
            plot.SetWidth(0.5)

        try:
            self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor, self.active_signal.name, ch_name, self.meta.id, parent=self.widget)
        except Exception as e:
            self.alerts.error(f"Error creating the context menu.\n {str(e)}")

        self.vtk_view.GetRenderWindow().Render()

    # ---------- Welch ----------
    def _compute_psd(self, X: np.ndarray, fs: float, target_fs: float,
                     window: str, nperseg: int, noverlap: int, nfft: int, detrend: str):
        # Integer downsample like MATLAB
        srt = max(1, int(round(fs / float(target_fs)))) if (target_fs and target_fs > 0) else 1
        fs_eff = fs / srt
        Xds = X[::srt, :] if srt > 1 else X

        # Clean NaN/Inf
        np.nan_to_num(Xds, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

        Ns_eff = Xds.shape[0]
        if nperseg > Ns_eff:
            nperseg = Ns_eff
        if noverlap >= nperseg:
            noverlap = nperseg // 2
        if nfft < nperseg:
            nfft = nperseg
        detrend_arg = False if detrend == "none" else detrend

        self._log(f"Welch params: fs_eff={fs_eff}, window={window}, nperseg={nperseg}, "
                  f"noverlap={noverlap}, nfft={nfft}, detrend={detrend_arg}, axis=0")

        freq, pxx = welch(
            Xds, fs=fs_eff, window=window, nperseg=nperseg, noverlap=noverlap,
            nfft=nfft, detrend=detrend_arg, scaling='density', axis=0
        )

        pxx = np.nan_to_num(pxx, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float64) 	# (Nf, T)
        freq = freq.astype(np.float64)
        self._log(f"PSD: srt={srt}, fs_eff={fs_eff:.3f} Hz, Nf={freq.size}, T_calc={pxx.shape[1]}")
        return freq, pxx, fs_eff
