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
from core.utils.trial_labels import trials_used
from core.utils.unidades import etiqueta_psd
from functools import partial
from core.utils.submuestreo import agregar_columna, agregar_linea


def calcular_psd(X, fs, target_fs, window, nperseg, noverlap, nfft, detrend, ctx=None, log=None):
    """Welch PSD of every trial: returns (freq, pxx, fs_eff). Pure, for the TaskService."""
    log = log or (lambda *a: None)
    srt = max(1, int(round(fs / float(target_fs)))) if (target_fs and target_fs > 0) else 1
    fs_eff = fs / srt
    Xds = X[::srt, :] if srt > 1 else X
    Xds = np.nan_to_num(Xds, copy=True, nan=0.0, posinf=0.0, neginf=0.0)

    Ns_eff = Xds.shape[0]
    if nperseg > Ns_eff:
        nperseg = Ns_eff
    if noverlap >= nperseg:
        noverlap = nperseg // 2
    if nfft < nperseg:
        nfft = nperseg
    detrend_arg = False if detrend == "none" else detrend
    log(f"Welch params: fs_eff={fs_eff}, window={window}, nperseg={nperseg}, "
        f"noverlap={noverlap}, nfft={nfft}, detrend={detrend_arg}, axis=0")

    freq, pxx = welch(Xds, fs=fs_eff, window=window, nperseg=nperseg, noverlap=noverlap,
                      nfft=nfft, detrend=detrend_arg, scaling='density', axis=0)
    pxx = np.nan_to_num(pxx, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float64)
    freq = freq.astype(np.float64)
    log(f"PSD: srt={srt}, fs_eff={fs_eff:.3f} Hz, Nf={freq.size}, T_calc={pxx.shape[1]}")
    return freq, pxx, fs_eff



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
        self._plot_enabled: bool = True
        self._ultimo: dict | None = None
        self.vtk_menu: VTKContextMenu | None = None
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

    def get_widget(self, parent=None):
        if self.widget is None:
            self.ui = Ui_Relative_psd()
            self.widget = QtWidgets.QWidget(parent)
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self._crear_area_de_grafica()
            self.crear_selector_de_trials()
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

    def _crear_area_de_grafica(self):
        """La gráfica a la izquierda y los parámetros a la derecha, como en la FFT."""
        self.ui.plotArea = QtWidgets.QFrame()
        self.ui.plotArea.setObjectName("plotArea")
        self.ui.plotArea.setFrameShape(QtWidgets.QFrame.StyledPanel)
        divisor = QtWidgets.QSplitter(QtCore.Qt.Horizontal, self.widget)
        self.ui.vbox.removeWidget(self.ui.rightContainer)
        divisor.addWidget(self.ui.plotArea)
        divisor.addWidget(self.ui.rightContainer)
        # Como FFT y PSD: el panel tiene un ancho máximo y el resto es de la
        # gráfica. Sin el tope, el panel se quedaba con casi toda la ventana y la
        # gráfica quedaba en una columna angosta a la izquierda.
        self.ui.rightContainer.setMaximumWidth(300)
        divisor.setStretchFactor(0, 1)
        divisor.setStretchFactor(1, 0)
        self.ui.vbox.insertWidget(0, divisor, 1)

    def _inject_optional_controls(self):
        """Inject optional controls without assuming a specific UI layout."""
        def _etiqueta(texto):
            # Mismo estilo que las demás filas del panel. Sin él, el tema dibuja la
            # etiqueta en letra grande y la fila se hace más ancha que el panel:
            # todo lo alineado a la derecha (Window, N-Per-Seg...) quedaba escondido.
            lab = QtWidgets.QLabel(texto)
            lab.setProperty("variant", "input")
            return lab

        def _add_form_row(label_text: str, w: QtWidgets.QWidget, apilada: bool = False):
            if hasattr(self.ui, "welchParameters") and isinstance(self.ui.welchParameters, QtWidgets.QVBoxLayout):
                # Apilada: la etiqueta arriba y el control debajo, a todo el ancho,
                # para una etiqueta larga que junto al control no cabe en 300 px.
                row_layout = QtWidgets.QVBoxLayout() if apilada else QtWidgets.QHBoxLayout()
                row_layout.addWidget(_etiqueta(label_text))
                if apilada:
                    # El tema limita todos los desplegables a 92 px de texto y
                    # "All Trials (GF=1)" necesita más: se corta. Este, que va solo
                    # en su línea, puede usar todo el ancho del panel.
                    w.setStyleSheet("QComboBox { max-width: 16777215px; }")
                    w.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                row_layout.addWidget(w)
                self.ui.welchParameters.addLayout(row_layout)

                return
            if hasattr(self.ui, "layoutWidget") and isinstance(self.ui.layoutWidget, QtWidgets.QWidget):
                lay = self.ui.layoutWidget.layout()
                if lay is not None:
                    hl = QtWidgets.QHBoxLayout()
                    hl.addWidget(QtWidgets.QLabel(label_text))
                    hl.addWidget(w)
                    lay.addLayout(hl)
                else:
                    lay = QtWidgets.QVBoxLayout(self.ui.layoutWidget)
                    hl = QtWidgets.QHBoxLayout()
                    hl.addWidget(QtWidgets.QLabel(label_text))
                    hl.addWidget(w)
                    lay.addLayout(hl)
                return

            if self.widget.layout() is None:
                self.widget.setLayout(QtWidgets.QVBoxLayout())
            hl = QtWidgets.QHBoxLayout()
            hl.addWidget(QtWidgets.QLabel(label_text))
            hl.addWidget(w)
            self.widget.layout().addLayout(hl)

        if not hasattr(self.ui, "detrendComboBox"):
            detrend_cb = QtWidgets.QComboBox()
            detrend_cb.addItems(["none", "constant", "linear"])
            self.ui.detrendComboBox = detrend_cb
            _add_form_row("Detrend", detrend_cb)

        if not hasattr(self.ui, "gainFactorComboBox"):
            gf_cb = QtWidgets.QComboBox()
            gf_cb.addItems(["Average (GF=0)", "All Trials (GF=1)"])
            self.ui.gainFactorComboBox = gf_cb
            _add_form_row("Calculation Mode (GF)", gf_cb, apilada=True)

    def _wire_ui(self):
        self.ui.calculateRelativePsd.clicked.connect(self._on_calculate_clicked)
        self.ui.clearButton.clicked.connect(self._init_defaults)
        self.ui.npersegSpinBox.valueChanged.connect(self._sync_noverlap)
        self.ui.lowFrequencySpinBox.valueChanged.connect(self._sync_range)
        self.ui.highFrequencySpinBox.valueChanged.connect(self._sync_range)
        self.ui.npersegSpinBox.setRange(1, 100_000_000)
        self.ui.npersegSpinBox.setKeyboardTracking(False)
        self.ui.npersegSpinBox.setValue(256)
        self.ui.noverlapSpinBox.setRange(0, 100_000_000)
        self.ui.noverlapSpinBox.setValue(128)
        self.ui.nfftSpinBox.setRange(1, 100_000_000)
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
        self.ui.lowFrequencySpinBox.setKeyboardTracking(False)
        self.ui.highFrequencySpinBox.setKeyboardTracking(False)
        self.ui.lowFrequencySpinBox.setSingleStep(1.0)
        self.ui.lowFrequencySpinBox.setValue(8.0)

    def _init_defaults(self):
        self.ui.sampleDensitySpinBox.setValue(1000)
        try:
            idx = self.ui.windowComboBox.findText("hamming", QtCore.Qt.MatchFixedString)
            if idx >= 0:
                self.ui.windowComboBox.setCurrentIndex(idx)
        except Exception:
            pass
        self.ui.npersegSpinBox.setValue(256)
        self._sync_noverlap()
        self.ui.nfftSpinBox.setValue(256)
        self.ui.lowFrequencySpinBox.setValue(8.0)
        self.ui.highFrequencySpinBox.setValue(12.0)
        if hasattr(self.ui, "detrendComboBox"):
            self.ui.detrendComboBox.setProperty("variant", "input")
            self.ui.detrendComboBox.setCurrentText("none")
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

    def _on_calculate_clicked(self):
        self._log("_on_calculate_clicked()")

        fs, X, ch_name = self._load_trials_from_store()
        if X is None or fs is None:
            self._notify("Relative PSD: no trials in active signal.")
            return
        X, posiciones, total = self.elegir_trials(X)
        if X is None:
            return

        if self.ui.sampleDensitySpinBox.value() <= 0:
            self.ui.sampleDensitySpinBox.setValue(min(fs, 1000.0))

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
            GF 	    = 1 if (gf_idx and gf_idx.currentIndex() == 1) else 0

            if f1 >= f2:
                raise ValueError("Low frequency must be lower than High frequency.")
        except Exception as e:
            self.alerts.warning(f"Parameter error: {str(e)}", "Invalid parameters")
            return

        p = dict(f1=f1, f2=f2, GF=GF, ch_name=ch_name, n_trials=total, posiciones=posiciones)
        self.run_task(calcular_psd, partial(self._on_psd_done, p),
                      on_failed=lambda m: self.alerts.error(f"Could not compute PSD: {m}"),
                      X=X, fs=fs, target_fs=target_fs, window=window, nperseg=nperseg,
                      noverlap=noverlap, nfft=nfft, detrend=detrend)

    def _on_psd_done(self, p, resultado):
        f1, f2, GF, ch_name = p["f1"], p["f2"], p["GF"], p["ch_name"]
        freq, pxx_all, fs_eff = resultado

        abs_power, rel_power = self._compute_relative_psd(freq, pxx_all, f1, f2, GF)

        self.ui.absPowerValue.setText(f"{abs_power:.4e}")
        self.ui.relPowerValue.setText(f"{rel_power:.4f}")

        nyq = float(fs_eff) / 2.0
        avisos = []
        if f1 >= nyq:
            avisos.append(f"The band [{f1}-{f2}] Hz is above Nyquist ({nyq:.1f} Hz): it has no power.")
        elif f2 > nyq:
            avisos.append(f"The band upper limit ({f2} Hz) is above Nyquist ({nyq:.1f} Hz); "
                          f"it was computed up to {nyq:.1f} Hz.")
        if nyq < 490.0:
            avisos.append(f"Total power is defined on 0.5-490 Hz, but with a sample density of "
                          f"{fs_eff:.0f} Hz it only reaches {nyq:.1f} Hz. Raise 'Sample density' "
                          f"to at least 980 Hz for MATLAB-comparable relative values.")
        if len(freq) > 1 and f1 < nyq:
            df = float(freq[1] - freq[0])
            nb = self._bins_in_band(freq, f1, f2)
            if nb < 4:
                necesario = int(2 ** np.ceil(np.log2(4.0 * fs_eff / max(f2 - f1, 1e-9))))
                avisos.append(f"Low frequency resolution: each PSD bin is {df:.2f} Hz wide, so the band "
                              f"[{f1}-{f2}] Hz only covers {nb} bin(s) and the result is not reliable. "
                              f"Raise 'nperseg' (and 'nfft') to at least {necesario}.")
        if avisos:
            self.alerts.warning("\n\n".join(avisos), "Relative PSD")

        self._trials_used = trials_used(p["posiciones"], p["n_trials"], "all" if GF == 1 else "average",
                                        channel=ch_name)
        for lbl in (self.ui.absPowerValue, self.ui.relPowerValue):
            lbl.setToolTip(f"Calculado con {self._trials_used['label']} — {ch_name}")
        self._notify(f"Relative PSD [{f1}-{f2} Hz] ready with {self._trials_used['label']}. "
                     f"fs_eff={fs_eff:.1f} Hz, df~{freq[1]-freq[0]:.2f} Hz")
        self.publish_current_trial()

        self._log_bands(freq, pxx_all, GF)

        self._ultimo = dict(freq=freq, pxx=pxx_all, fs_eff=fs_eff, f1=f1, f2=f2, GF=GF, ch_name=ch_name,
                            abs_power=abs_power, rel_power=rel_power, p=p)
        if self._plot_enabled:
            try:
                self._plot_psd(freq, pxx_all, ch_name, f1, f2)
            except Exception as e:
                self._log(f"Plot error: {e}")

        self.mark_project_dirty()

    def get_analysis_params(self) -> dict:
        return {
            "sample_density": self.ui.sampleDensitySpinBox.value(),
            "low_freq": self.ui.lowFrequencySpinBox.value(),
            "high_freq": self.ui.highFrequencySpinBox.value(),
            "window": self.ui.windowComboBox.currentText(),
            "nperseg": self.ui.npersegSpinBox.value(),
            "noverlap": self.ui.noverlapSpinBox.value(),
            "nfft": self.ui.nfftSpinBox.value(),
            "detrend": self.ui.detrendComboBox.currentText() if hasattr(self.ui, "detrendComboBox") else "none",
            "gain_factor_index": self.ui.gainFactorComboBox.currentIndex() if hasattr(self.ui, "gainFactorComboBox") else 1,
            "trials_used": self._trials_used,
        }

    def apply_analysis_params(self, params: dict):
        self.ui.sampleDensitySpinBox.setValue(params.get("sample_density", self.ui.sampleDensitySpinBox.value()))
        self.ui.lowFrequencySpinBox.setValue(params.get("low_freq", self.ui.lowFrequencySpinBox.value()))
        self.ui.highFrequencySpinBox.setValue(params.get("high_freq", self.ui.highFrequencySpinBox.value()))

        idx = self.ui.windowComboBox.findText(params.get("window", ""))
        if idx >= 0:
            self.ui.windowComboBox.setCurrentIndex(idx)

        self.ui.npersegSpinBox.setValue(params.get("nperseg", self.ui.npersegSpinBox.value()))
        self.ui.noverlapSpinBox.setValue(params.get("noverlap", self.ui.noverlapSpinBox.value()))
        self.ui.nfftSpinBox.setValue(params.get("nfft", self.ui.nfftSpinBox.value()))

        if hasattr(self.ui, "detrendComboBox"):
            didx = self.ui.detrendComboBox.findText(params.get("detrend", "none"))
            if didx >= 0:
                self.ui.detrendComboBox.setCurrentIndex(didx)
        if hasattr(self.ui, "gainFactorComboBox"):
            self.ui.gainFactorComboBox.setCurrentIndex(params.get("gain_factor_index", 1))

        self._on_calculate_clicked()


    def _band_sum(self, freq: np.ndarray, pxx: np.ndarray, lo: float, hi: float,
                  edges: str = "matlab") -> float:
        """
        Sum power in [lo, hi] with two edge policies:
          - edges='matlab'    -> inclusive upper edge (id2 = find(f>=hi); sum[i1:id2])
          - edges='exclusive' -> exclusive upper edge (sum[i1:id2]) without the 'hi' bin
        """
        i1 = int(np.searchsorted(freq, lo, side="left"))
        if edges == "matlab":
            i2 = int(np.searchsorted(freq, hi, side="left"))
            i1 = max(0, min(i1, len(freq) - 1))
            i2 = max(0, min(i2, len(freq) - 1))
            if i2 < i1: i1, i2 = i2, i1
            return float(np.nansum(pxx[i1:i2 + 1]))
        else:
            i2 = int(np.searchsorted(freq, hi, side="left"))
            i1 = max(0, min(i1, len(freq)))
            i2 = max(0, min(i2, len(freq)))
            if i2 < i1: i1, i2 = i2, i1
            return float(np.nansum(pxx[i1:i2]))


    def _compute_relative_psd(self, freq: np.ndarray, pxx_all: np.ndarray,
                              f1: float, f2: float, GF: int):
        """
        Reproduces f_PSD_Relative:
        - GF=1: pxx_av = pxx_all (all trials), then sum across trials
        - GF=0: pxx_av = mean(pxx_all, across trials)
        Ptot in [0.5, 490] Hz.
        Uses _band_sum to handle edges (inclusive/exclusive).
        """
        pxx_sum = np.nansum(pxx_all, axis=1) if GF == 1 else np.nanmean(pxx_all, axis=1)

        edges_mode = "matlab"

        df = freq[1]-freq[0]
        i1 = np.searchsorted(freq, f1, side="left")
        i2_matlab = np.searchsorted(freq, f2, side="left")
        self._log(f"df = {df:.4f} Hz")
        self._log(f"Band [{f1}-{f2}] Hz: bins [{i1}:{i2_matlab}] (MATLAB-style) -> f[{i1}]={freq[i1]:.4f}, f[{i2_matlab}]={freq[min(i2_matlab,len(freq)-1)]:.4f}")

        Ptot     = self._band_sum(freq, pxx_sum, 0.5, 490.0, edges=edges_mode)
        pow_band = self._band_sum(freq, pxx_sum, f1,  f2,    edges=edges_mode)
        rel      = (pow_band / Ptot) if Ptot > 0 else 0.0
        abs_power = pow_band * float(df)

        self._log(f"[GF={GF}, edges={edges_mode}] Band {f1}-{f2} Hz -> Abs={abs_power:.4e}, RelFrac={rel:.4f}")
        return abs_power, rel

    @staticmethod
    def _bins_in_band(freq, f1, f2) -> int:
        """Frequency bins summed for [f1, f2] with the MATLAB edge rule (first f>=f1 to first f>=f2)."""
        i1 = int(np.searchsorted(freq, f1, side="left"))
        i2 = int(np.searchsorted(freq, f2, side="left"))
        i1 = max(0, min(i1, len(freq) - 1)); i2 = max(0, min(i2, len(freq) - 1))
        return abs(i2 - i1) + 1


    def _log_bands(self, freq: np.ndarray, pxx_all: np.ndarray, GF: int):
        pxx_sum = np.nansum(pxx_all, axis=1) if GF == 1 else np.nanmean(pxx_all, axis=1)
        edges_mode = "matlab"

        def bsum(lo, hi): return self._band_sum(freq, pxx_sum, lo, hi, edges=edges_mode)

        Ptot = bsum(0.5, 490.0)
        if Ptot <= 0:
            self._log("Ptot <= 0; bands not logged."); return

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
        self._log("-" * 40)
        for name, lo, hi in bands:
            val = bsum(lo, hi) / Ptot
            parts.append(val)
            self._log(f"Band {name:6s} [{lo:>5.1f}-{hi:>6.1f}] -> {val:.4f}")

        total_parts = sum(parts)
        self._log(f"Sum of bands (delta+theta+alpha+beta+gamma1+gamma2+HFO1+HFO2) = {total_parts:.4f}")
        self._log("-" * 40)


    def _load_trials_from_store(self):
        if not self.mainwin:
            return None, None, None


        if self.get_active_signal() is None:
            return None, None, None

        td = self.get_active_trials()

        if td is None or td.trials.size == 0:
            return None, None, None

        fs = float(getattr(td, "sampling_rate", 0.0))
        X = np.asarray(getattr(td, "trials", None), dtype=np.float64)
        ch = getattr(td, "channel_name", "")
        self._unidad_psd = getattr(td, "unit", "") or ""
        if X is None or X.ndim != 2 or fs <= 0:
            self._log("Invalid TrialDataset (fs<=0 or trials not 2D).")
            return None, None, None

        self._log(f"Trials: Ns={X.shape[0]}, T={X.shape[1]}, fs={fs}")
        return fs, X, ch

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
        """Whole spectrum up to 490 Hz (the total-power range): every trial thin, their average
        in black on top, and the band [lo, hi] marked with two vertical lines. Before, only the
        band was drawn, which with the default resolution was a single point per trial."""
        if self.vtk_view is None:
            self._ensure_vtk()
        if self.vtk_view is None:
            return

        sel = (freq >= 0.5) & (freq <= 490.0)
        freq_v = freq[sel]
        pxx_v = pxx_all[sel, :]
        if freq_v.size == 0:
            return

        scene = self.vtk_view.GetScene()
        scene.ClearItems()
        self.chart = vtk.vtkChartXY()
        scene.AddItem(self.chart)

        ax_b = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_l = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_b.SetGridVisible(True); ax_l.SetGridVisible(True)
        ax_b.SetTitle("Frequency (Hz)")
        ax_l.SetTitle(etiqueta_psd(getattr(self, "_unidad_psd", "")))

        MAX_PLOTS = 200
        dibujar = pxx_v
        if pxx_v.shape[1] > MAX_PLOTS:
            self._log(f"There are {pxx_v.shape[1]} trials → showing {MAX_PLOTS}")
            dibujar = pxx_v[:, :MAX_PLOTS]
        for c in range(dibujar.shape[1]):
            plot = agregar_linea(self.chart, freq_v, dibujar[:, c], "frequency", f"trial_{c + 1}")
            plot.SetWidth(0.5)
            plot.SetColor(170, 170, 170, 255)
        if pxx_v.shape[1] > 1:
            prom = agregar_linea(self.chart, freq_v, np.nanmean(pxx_v, axis=1), "frequency", "average")
            prom.SetColor(0, 0, 0, 255)
            prom.SetWidth(2.5)
            prom.SetLabel("Average")

        y_max = float(np.nanmax(pxx_v)) if np.isfinite(pxx_v).any() else 1.0
        for x in (lo, hi):
            linea = agregar_linea(self.chart, [x, x], [0.0, y_max], "frequency", "band")
            linea.SetColor(220, 0, 0, 255)
            linea.SetWidth(1.5)
            try:
                linea.GetPen().SetLineType(vtk.vtkPen.DASH_LINE)
            except Exception:
                pass

        try:
            if ch_name:
                etiqueta = (self._trials_used or {}).get("label")
                txt = f"Relative PSD - {ch_name} — band {lo:g}-{hi:g} Hz"
                if etiqueta:
                    txt += f" — {etiqueta}"
                self.chart.SetTitle(txt)
        except Exception:
            pass

        try:
            if self.vtk_menu is None:
                self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor, self.active_signal.name, ch_name,
                                               self.meta.id, parent=self.widget)
                for fmt in ("csv", "xlsx", "json"):
                    self.vtk_menu.add_action(f"Export Relative PSD results ({fmt})", partial(self.exportar_resultados, fmt))
            else:
                self.vtk_menu.set_chart(self.chart)
                self.vtk_menu.set_signal_name(self.active_signal.name)
                self.vtk_menu.set_channel_name(ch_name)
        except Exception as e:
            self.alerts.error(f"Error creating the context menu.\n {str(e)}")

        self.vtk_view.GetRenderWindow().Render()

    BANDAS = [
        ("delta", 0.5, 3.9), ("theta", 4.0, 7.9), ("alpha", 8.0, 11.9), ("beta", 12.0, 24.9),
        ("gamma1", 25.0, 59.0), ("gamma2", 61.0, 120.0), ("HFO1", 121.0, 250.0), ("HFO2", 251.0, 490.0),
    ]

    def _fracciones_por_banda(self, freq, pxx_all, GF):
        pxx = np.nansum(pxx_all, axis=1) if GF == 1 else np.nanmean(pxx_all, axis=1)
        total = self._band_sum(freq, pxx, 0.5, 490.0)
        return [(n, lo, hi, (self._band_sum(freq, pxx, lo, hi) / total) if total > 0 else 0.0)
                for n, lo, hi in self.BANDAS]

    def _secciones_resultado(self) -> dict:
        u = self._ultimo
        usados = (self._trials_used or {}).get("label")
        parametros = [["canal", u["ch_name"]], ["trials_usados", usados],
                      ["modo", "todos los trials" if u["GF"] == 1 else "promedio"],
                      ["banda_baja_hz", u["f1"]], ["banda_alta_hz", u["f2"]], ["fs_efectiva_hz", float(u["fs_eff"])]]
        if self.ui is not None:
            parametros += [["ventana", self.ui.windowComboBox.currentText()], ["nperseg", self.ui.npersegSpinBox.value()],
                           ["noverlap", self.ui.noverlapSpinBox.value()], ["nfft", self.ui.nfftSpinBox.value()],
                           ["densidad_de_muestra_hz", self.ui.sampleDensitySpinBox.value()]]
        potencia = [["potencia_absoluta", float(u["abs_power"])], ["potencia_relativa", float(u["rel_power"])]]
        bandas = [[n, lo, hi, float(v)] for n, lo, hi, v in self._fracciones_por_banda(u["freq"], u["pxx"], u["GF"])]
        return {
            "Parametros": (["parametro", "valor"], parametros),
            "Potencia": (["medida", "valor"], potencia),
            "Bandas": (["banda", "desde_hz", "hasta_hz", "fraccion_de_la_potencia_total"], bandas),
        }

    def exportar_resultados(self, fmt: str):
        if not self._ultimo or self.vtk_menu is None:
            self.alerts.warning("Primero calcula la PSD relativa para poder exportar sus resultados.")
            return
        self.vtk_menu.export_service.export_sections(self._secciones_resultado(), fmt)

    def _compute_psd(self, X: np.ndarray, fs: float, target_fs: float,
                     window: str, nperseg: int, noverlap: int, nfft: int, detrend: str):
        return calcular_psd(X, fs, target_fs, window, nperseg, noverlap, nfft, detrend, log=self._log)
