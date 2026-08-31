import numpy as np
from pathlib import Path
import pytest

# --- Real pipeline imports (core app services & plugins) ---
from core.services.fileio_service import FileIOService
from core.filters import trials as tr
from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from plugins.analysis.time_frequency.wavelet_average.wavelet_average_plugin import (
    Wavelet_average_plugin,
)


# ============================================================
#                  GLOBAL CONFIG / TEST DATA
# ============================================================

# Base directory for test data files
BASE_DIR = Path(__file__).resolve().parents[2] / "test" / "data"

# Input ABF file
ABF_PATH = BASE_DIR / "17308005.abf"

# MATLAB reference CSV
MATLAB_SCALO_AVG = BASE_DIR / "wavelet_average_data_matlab.csv"


# ============================================================
#                 TRIALS DIVISION PARAMETERS
# ============================================================

# Channel where the signal of interest is stored
TARGET_CHANNEL = 0

# Channel used to detect stimulus onsets
STIM_CHANNEL = 1

# Threshold to detect a stimulus event
THRESHOLD = 0.7

# Time window around each stimulus (in seconds)
T0 = -0.05     # Start time relative to stimulus
T1 = 4.00      # End time relative to stimulus

# How to decide the end of a trial
END_MODE = "until_next_onset"

# Expected number of stimuli per trial (sanity check inside filter)
STIM_EXPECTED = 1

# Inter-stimulus interval (used by the cutting logic)
ISI = 0.0

# Value used to pad trials if needed
# We keep it at 0.0 to avoid contaminating the scalogram with NaNs.
PAD_VALUE = 0.0


# ============================================================
#            WAVELET / TIME-FREQUENCY PARAMETERS
# ============================================================

# Default plugin parameters (as in the UI)
TARGET_FS = 1000.0   # sampleDensitySpinBox
F_LO = 1.0           # lowFrequencySpinBox
F_HI = 500.0         # highFrequencySpinBox
CYCLES = 2.0         # cyclesSpinBox
NORMALIZE = False    # normalizeCheckBox
SCALE_LOG = True     # scaleCheckBox


# ============================================================
#                 NUMERICAL COMPARISON PARAMETERS
# ============================================================

# Minimum acceptable Pearson correlation per row (frequency)
MIN_CORR = 0.8

# Fractional test parameters
FRAC_MIN_PASS = 0.95   # At least 95% of points must be within tolerance
FRAC_ATOL = 0.0001        # Absolute tolerance
FRAC_RTOL = 0.0        # Relative tolerance


# ============================================================
#       MATLAB CSV LOADING HELPER (AVERAGE SCALOGRAM 2D)
# ============================================================

def load_csv_matlab_scalogram_avg(path: Path) -> np.ndarray:
    """
    Load the (nF, nT) matrix exported from MATLAB for the average scalogram.

    The returned array is always a 2D float64 matrix.
    """
    M = np.loadtxt(path, delimiter=";")
    return np.asarray(M, dtype=np.float64)


# ============================================================
#                    NUMPY HELPER FUNCTIONS
# ============================================================

def crop_to_min(A: np.ndarray, B: np.ndarray):
    """
    Crop A and B to the same number of rows and columns (minimum of both).

    Both A and B are treated as 2D matrices (nF, nT).
    1D arrays are promoted to a single-row matrix.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    if A.ndim == 1:
        A = A.reshape(1, -1)
    if B.ndim == 1:
        B = B.reshape(1, -1)

    assert A.ndim == 2 and B.ndim == 2, "Input arrays must be 2D."
    nF = min(A.shape[0], B.shape[0])
    nT = min(A.shape[1], B.shape[1])
    return A[:nF, :nT], B[:nF, :nT]


def diff_debug_report_fraction(
    A,
    B,
    within,
    tol_mat,
    label_a="APP",
    label_b="MATLAB",
    topk_rows=10,
):
    """
    Build a detailed debug report for the fractional tolerance test.

    The report includes:
      - The worst point (row, col) where tolerance is violated,
      - The difference, local tolerance, and excess at that point,
      - The total number of rows with violations,
      - The top rows ranked by number of violations and max excess.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    A, B = crop_to_min(A, B)

    valid = np.isfinite(A) & np.isfinite(B)
    over_mask = valid & (~within)

    if not np.any(over_mask):
        return "[frac] no violations"

    diffs = np.abs(A - B)
    excess = np.full_like(diffs, np.nan, dtype=float)
    excess[over_mask] = diffs[over_mask] - tol_mat[over_mask]

    # Worst violating point (ignoring NaNs).
    flat_idx = np.nanargmax(excess)
    r, c = np.unravel_index(flat_idx, excess.shape)
    worst_excess = float(excess[r, c])
    worst_diff = float(diffs[r, c])
    worst_tol = float(tol_mat[r, c])
    va, vb = float(A[r, c]), float(B[r, c])

    # Aggregated statistics by row (frequencies).
    by_row_counts = np.nansum(over_mask, axis=1)
    with np.errstate(all="ignore", invalid="ignore"):
        by_row_maxexc = np.nanmax(excess, axis=1)

    rows = np.where(by_row_counts > 0)[0]
    topk = []
    if rows.size > 0:
        # Sort by (#violations desc, max_excess desc).
        order = np.lexsort((-by_row_maxexc[rows], -by_row_counts[rows]))[::-1]
        for idx in order[:topk_rows]:
            ridx = int(rows[idx])
            topk.append((ridx, int(by_row_counts[ridx]), float(by_row_maxexc[ridx])))

    lines = []
    lines.append(
        f"[frac] worst @ (row={r}, col={c}) -> diff={worst_diff:.6f}, "
        f"tol_local={worst_tol:.6f}, excess={worst_excess:.6f} ; "
        f"{label_a}={va:.6f} ; {label_b}={vb:.6f}"
    )
    lines.append(f"[frac] total rows with violations: {len(rows)}")
    if topk:
        lines.append("[frac] top rows by violations (row, count, max_excess):")
        for row_id, cnt, mx in topk:
            lines.append(f"  - row={row_id:03d}  count={cnt}  max_excess={mx:.6f}")
    return "\n".join(lines)


def corr_by_row(A, B):
    """
    Compute Pearson correlation per row (each frequency is a curve over time).

    Returns a vector (nF,) of correlations.
    """
    A, B = crop_to_min(A, B)
    nF = A.shape[0]
    C = np.full(nF, np.nan, float)

    for i in range(nF):
        a = A[i, :]
        b = B[i, :]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() > 2:
            C[i] = np.corrcoef(a[m], b[m])[0, 1]

    return C


def assert_points_within_tolerance_fraction(
    A,
    B,
    *,
    min_pass_ratio=FRAC_MIN_PASS,
    atol=FRAC_ATOL,
    rtol=FRAC_RTOL,
    ref="B",
    label_a="APP",
    label_b="MATLAB",
    msg="",
    topk_rows=10,
):
    """
    Require that at least `min_pass_ratio` of valid points in the 2D matrix
    (nF, nT) satisfy:

        |A - B| <= atol + rtol * |ref|

    where `ref` indicates which matrix (A or B) is used in the
    relative term (rtol * |ref|).
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    A, B = crop_to_min(A, B)

    # Only evaluate points where both matrices are finite.
    valid = np.isfinite(A) & np.isfinite(B)
    total = int(np.sum(valid))
    if total == 0:
        # Nothing to compare: silently accept.
        return

    # Choose which matrix is used as "reference" in the tolerance formula.
    ref_mat = A if ref.upper() == "A" else B
    tol_mat = atol + rtol * np.abs(ref_mat)

    diffs = np.abs(A - B)
    within = (diffs <= tol_mat) & valid
    passed = int(np.sum(within))
    ratio = passed / float(total)

    if ratio >= min_pass_ratio:
        # Enough points are within tolerance → test passes.
        return

    # Build a detailed report to help debugging failures.
    lines = []
    lines.append(msg or "Fractional tolerance check failed")
    lines.append(f"[frac] shape {label_a}={A.shape}, {label_b}={B.shape}")
    lines.append(
        f"[frac] params: min_pass_ratio={min_pass_ratio:.3f}, "
        f"atol={atol}, rtol={rtol} (ref={ref})"
    )
    lines.append(f"[frac] passed={passed}/{total} -> ratio={ratio:.5f}")
    lines.append(
        diff_debug_report_fraction(
            A, B, within, tol_mat, label_a, label_b, topk_rows
        )
    )
    raise AssertionError("\n".join(lines))


# ============================================================
#            TEST FOR WAVELET AVERAGE PLUGIN
# ============================================================

class WaveletAverageDouble(Wavelet_average_plugin):
    """
    Test double for Wavelet_average:

      - Avoids real VTK/UI,
      - Allows injecting TrialDataset / signal dataset,
      - Uses the real WaveletWorker from the plugin, but calls run()
        directly (no real threads),
      - Captures (avg_scalogram, t, f) from the worker's finished signal.
    """

    def __init__(self):
        meta = PluginMeta(
            id="wavelet_average",
            name="Wavelet Average",
            category="analysis",
            subcategory="time_frequency",
            version="0.0.0",
            icon="",
            logic_class="Wavelet_average_plugin",
        )
        super().__init__(meta)

        self._active_signal = None
        self._active_trials: TrialDataset | None = None

        self.scalo = None
        self.t_axis = None
        self.f_axis = None
        self._last_error = None

    # --- Injection helpers used by the tests ---

    def set_active_signal(self, sd):
        """
        Inject the signal dataset used by the plugin.
        """
        self._active_signal = sd

    def set_active_trials(self, td: TrialDataset):
        """
        Inject the TrialDataset (trials cut from the original signal).
        """
        self._active_trials = td

    # --- Bridges required by the original plugin API ---

    def get_active_signal(self):
        """
        Return the signal dataset that the plugin should use.
        """
        return self._active_signal

    def get_active_trials(self):
        """
        Return the TrialDataset with the already cut trials.
        """
        return self._active_trials

    # --- UI / VTK handling overrides ---

    def _create_vtk_container(self):
        """
        Override the VTK container creation to keep the test headless.
        """
        self.vtk_widget = None
        self.renwin = None
        self._context_view = None
        self._vtk_renderer = None

    def ensure_vtk(self):
        """
        Override ensure_vtk to avoid creating any real VTK objects.
        """
        self.vtk_widget = None
        self.renwin = None
        self._context_view = None
        self._vtk_renderer = None

    def render_scalogram(self, *args, **kwargs):
        """
        No rendering in tests. The scalogram is captured numerically only.
        """
        pass

    # --- Synchronous "full pipeline" using the real WaveletWorker ---

    def run_average(
        self,
        *,
        fs_plot=TARGET_FS,
        fmin=F_LO,
        fmax=F_HI,
        cycles=CYCLES,
        normalize=NORMALIZE,
        scale_log=SCALE_LOG,
        norm_method="z-score",
    ):
        """
        Run the wavelet average using exactly the plugin's logic:

          - Build WaveletWorker with the same parameters,
          - Call worker.run() synchronously (no threads),
          - Capture the average scalogram and the associated time
            and frequency axes from the worker's 'finished' signal.

        Returns:
            scalo_avg, t_axis, f_axis
        """
        td = self.get_active_trials()
        assert td is not None, "TrialDataset not present in WaveletAverageDouble."

        t = np.asarray(td.time_rel, dtype=float)
        data = np.array(td.trials)

        # Ensure shape is (n_samples, n_trials)
        if data.ndim == 1:
            data = data[:, np.newaxis]
        if data.shape[0] < data.shape[1]:
            data = data.T  # (n_samples, n_trials)

        # Compute sampling rate from time axis
        fs_calculated = round(1.0 / (t[1] - t[0]), 3)

        # Build the REAL worker from the plugin
        worker = self.WaveletWorker(
            self,
            data,
            fs_calculated,
            fs_plot,
            fmin,
            fmax,
            cycles,
            normalize,
            scale_log,
            norm_method,
        )

        # Local callback to capture the worker output
        def _on_finished(times, freqs, avg_scalogram, scaled_flag, error):
            self._last_error = error
            if error is None and avg_scalogram is not None:
                self.scalo = np.asarray(avg_scalogram, dtype=float)
                self.t_axis = np.asarray(times, dtype=float)
                self.f_axis = np.asarray(freqs, dtype=float)

        worker.finished.connect(_on_finished)

        # IMPORTANT: call run() directly → synchronous, no threads
        worker.run()

        if self._last_error is not None:
            raise RuntimeError(
                f"WaveletAverageDouble.run_average error: {self._last_error}"
            )

        assert self.scalo is not None, "Average scalogram not obtained from plugin."
        return self.scalo, self.t_axis, self.f_axis


# ============================================================
#                   INTEGRATION TEST SUITE
#      APP Wavelet Average vs MATLAB Average Scalogram
# ============================================================

@pytest.mark.skipif(not ABF_PATH.exists(), reason="ABF file not found")
@pytest.mark.skipif(not MATLAB_SCALO_AVG.exists(), reason="MATLAB average scalogram CSV not found")
class TestWaveletAverageABFVsMatlab:
    """
    Integration tests that compare the average wavelet scalogram
    produced by the Gamma Lab Wavelet Average plugin against a
    MATLAB reference.

    The tests check:
      1) Basic shape / minimal size.
      2) Pearson correlation per frequency row.
      3) Pointwise agreement for ≥ 95% of the points within a given
         absolute and relative tolerance.
    """

    # --------------------------------------------------------
    # Fixtures
    # --------------------------------------------------------
    @pytest.fixture(scope="class")
    def ds(self):
        """
        Load the real ABF file using FileIOService and return
        a signal dataset with float64 time and signal arrays.
        """
        fio = FileIOService()
        sd = fio.load_abf(str(ABF_PATH))

        # Ensure we work with float64 for better numerical stability.
        sd.signals = sd.signals.astype(np.float64, copy=False)
        sd.time = sd.time.astype(np.float64, copy=False)

        return sd

    @pytest.fixture(scope="class")
    def td(self, ds):
        """
        Cut trials from the ABF signal using the real pipeline:
        core.filters.trials.cut_trials_single_channel.
        """
        return tr.cut_trials_single_channel(
            ds=ds,
            channel=TARGET_CHANNEL,
            stim_channel=STIM_CHANNEL,
            threshold=THRESHOLD,
            t0=T0,
            t1=T1,
            end_mode=END_MODE,
            stim_expected=STIM_EXPECTED,
            inter_stim_time=ISI,
            pad_value=PAD_VALUE,
            debug=False,
        )

    @pytest.fixture(scope="class")
    def app_scalogram_avg(self, ds, td):
        """
        Compute the average scalogram using EXACTLY the plugin logic:

          WaveletWorker.run() + internal averaging + normalization / log scale
          (depending on flags), but done synchronously and without VTK.

        Returns only the average scalogram matrix (nF, nT).
        """
        plug = WaveletAverageDouble()
        plug.set_active_signal(ds)
        plug.set_active_trials(td)

        scalo, t_axis, f_axis = plug.run_average(
            fs_plot=TARGET_FS,
            fmin=F_LO,
            fmax=F_HI,
            cycles=CYCLES,
            normalize=NORMALIZE,
            scale_log=SCALE_LOG,
            norm_method="z-score",
        )

        assert scalo.ndim == 2 and scalo.shape[0] > 0 and scalo.shape[1] > 0

        print(
            "APP WAVELET AVG: scalo.shape =",
            scalo.shape,
            ", t_axis.shape =",
            t_axis.shape,
            ", f_axis.shape =",
            f_axis.shape,
        )

        return scalo

    @pytest.fixture(scope="class")
    def matlab_scalogram_avg(self):
        """
        Load the (nF, nT) average matrix exported from MATLAB,
        e.g. the CData/ZData of the average wavelet surface.
        """
        M = load_csv_matlab_scalogram_avg(MATLAB_SCALO_AVG)
        print("MATLAB WAVELET AVG shape:", M.shape)
        return M

    # --------------------------------------------------------
    # 1. Basic structure / size checks
    # --------------------------------------------------------
    def test_shape_and_size(self, app_scalogram_avg, matlab_scalogram_avg):
        """
        Both scalograms (APP and MATLAB) must be 2D and have
        at least one frequency and one time point after cropping
        to a common shape.
        """
        A, B = crop_to_min(app_scalogram_avg, matlab_scalogram_avg)

        assert A.ndim == 2 and B.ndim == 2
        assert A.shape[0] >= 1 and A.shape[1] >= 1
        assert B.shape[0] >= 1 and B.shape[1] >= 1

    # --------------------------------------------------------
    # 2. Correlation per frequency row
    # --------------------------------------------------------
    def test_correlation_by_row(self, app_scalogram_avg, matlab_scalogram_avg):
        """
        Check Pearson correlation per row (frequency) between APP
        and MATLAB average scalograms.

        Each row is a curve over time, and we require correlation
        above MIN_CORR for all valid rows.
        """
        A, B = crop_to_min(app_scalogram_avg, matlab_scalogram_avg)
        C = corr_by_row(A, B)

        finite_mask = np.isfinite(C)
        assert np.any(finite_mask), "No rows with valid data for correlation."

        low = np.where(finite_mask & (C < MIN_CORR))[0]
        if low.size > 0:
            order = np.argsort(C[finite_mask])
            worst_idx = np.where(finite_mask)[0][order[:5]]
            msg = (
                f"Low correlation in rows {low.tolist()} "
                f"(min={np.nanmin(C):.4f}, threshold={MIN_CORR})"
            )
            msg += "\nWorst rows: " + ", ".join(
                f"row {int(i)}: {C[int(i)]:.4f}" for i in worst_idx
            )
            pytest.fail(msg)

    # --------------------------------------------------------
    # 3. Pointwise comparison with tolerance (allows outliers)
    # --------------------------------------------------------
    def test_pointwise_fraction_allowing_outliers(
        self,
        app_scalogram_avg,
        matlab_scalogram_avg,
    ):
        """
        Require that at least FRAC_MIN_PASS of valid points satisfy:

            |APP - MATLAB| <= FRAC_ATOL + FRAC_RTOL * |MATLAB|

        A small fraction of outliers is allowed, but detailed information
        is reported if the requirement is not met.
        """
        A, B = crop_to_min(app_scalogram_avg, matlab_scalogram_avg)

        assert_points_within_tolerance_fraction(
            A,
            B,
            min_pass_ratio=FRAC_MIN_PASS,
            atol=FRAC_ATOL,
            rtol=FRAC_RTOL,
            ref="B",
            label_a="APP",
            label_b="MATLAB",
            msg=(
                "Wavelet average scalogram: "
                f"{FRAC_MIN_PASS*100:.1f}% of the points must be within "
                f"tolerance (atol={FRAC_ATOL}, rtol={FRAC_RTOL})"
            ),
        )