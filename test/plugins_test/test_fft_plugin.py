import numpy as np
import pytest
from pathlib import Path

# --- Real pipeline imports (core app services & plugins) ---
from core.services.fileio import FileIOService
from core.filters import trials as tr
from core.services.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from plugins.analysis.frequency.fft.fft_plugin import Fft_plugin


# ============================================================
#                  GLOBAL CONFIG / TEST DATA
# ============================================================

# Base directory for test data files
BASE_DIR = Path(__file__).resolve().parents[2] / "test" / "data"

# Input ABF file
ABF_PATH = BASE_DIR / "17308005.abf"

# MATLAB reference CSV
MATLAB_CSV = BASE_DIR / "fft_data_matlab.csv"


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
PAD_VALUE = 0.0


# ============================================================
#                 FFT UI / SAMPLING PARAMETERS
# ============================================================

# UI parameters that the test double enforces
UI_TARGET_FS = 1000    # 0 -> no resample
UI_F_LO = 0.0
UI_F_HI = 500.0        # High upper limit to avoid cropping


# ============================================================
#                 NUMERICAL COMPARISON PARAMETERS
# ============================================================

# Expected number of columns (trials) in the FFT matrix
K_EXPECTED = 60

# Minimum acceptable Pearson correlation per column (trial)
MIN_CORR = 0.98

# Fractional test parameters (allowing outliers)
FRAC_MIN_PASS = 0.95    # At least 95% of points must be within tolerance
FRAC_ATOL = 0.75        # Absolute tolerance: |APP - MATLAB| <= 0.75
FRAC_RTOL = 0.0         # No relative part


# ============================================================
#                 MATLAB CSV LOADING HELPER
# ============================================================

def load_csv_matlab(path: Path) -> np.ndarray:
    """
    Load the CSV exported from MATLAB for the FFT figure.

    Adjust the 'delimiter' according to how the CSV was exported.
    The result is always a 2D float64 array. If the data is 1D,
    it is reshaped to (Nf, 1).
    """
    arr = np.genfromtxt(
        path,
        delimiter=";",     # <-- If your CSV uses ',', change this to ','
        dtype=np.float64,
        filling_values=np.nan,
    )
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    return arr


# ============================================================
#                    NUMPY HELPER FUNCTIONS
# ============================================================

def crop_rows_to_min(A: np.ndarray, B: np.ndarray):
    """
    Crop A and B to the same number of rows (the minimum of both),
    keeping all columns. A and B are treated as 2D matrices (N, K).
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    assert A.ndim == 2 and B.ndim == 2, "Input arrays must be 2D."
    assert A.shape[1] == B.shape[1], f"Different number of columns: {A.shape[1]} vs {B.shape[1]}"

    n = min(A.shape[0], B.shape[0])
    return A[:n, :], B[:n, :]


def diff_debug_report_fraction(A, B, within, tol_mat, label_a="APP", label_b="MATLAB", topk_cols=10):
    """
    Build a detailed debug report for the fractional tolerance test.

    The report includes:
      - The worst point (row, col) where tolerance is violated,
      - The difference, local tolerance, and excess at that point,
      - The total number of violating columns,
      - The top columns ranked by number of violations and max excess.

    Columns that are entirely NaN are handled without warnings.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    A, B = crop_rows_to_min(A, B)

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

    # Aggregated statistics by column (avoid all-NaN warnings).
    by_col_counts = np.nansum(over_mask, axis=0)
    with np.errstate(all="ignore", invalid="ignore"):
        by_col_maxexc = np.nanmax(excess, axis=0)

    # Filter columns that actually have violations.
    cols = np.where(by_col_counts > 0)[0]
    topk = []
    if cols.size > 0:
        # Sort by (#violations desc, max_excess desc).
        order = np.lexsort((-by_col_maxexc[cols], -by_col_counts[cols]))[::-1]
        for idx in order[:topk_cols]:
            cidx = int(cols[idx])
            topk.append((cidx, int(by_col_counts[cidx]), float(by_col_maxexc[cidx])))

    lines = []
    lines.append(
        f"[frac] worst @ (row={r}, col={c}) -> diff={worst_diff:.6f}, "
        f"tol_local={worst_tol:.6f}, excess={worst_excess:.6f} ; "
        f"{label_a}={va:.6f} ; {label_b}={vb:.6f}"
    )
    lines.append(f"[frac] total columns with violations: {len(cols)}")
    if topk:
        lines.append("[frac] top columns by violations (col, count, max_excess):")
        for col_id, cnt, mx in topk:
            lines.append(f"  - col={col_id:02d}  count={cnt}  max_excess={mx:.6f}")
    return "\n".join(lines)


def corr_by_col(A, B):
    """
    Compute Pearson correlation per column (trial).

    Returns a vector (K,) with NaN for columns that do not
    have enough valid data.
    """
    A, B = crop_rows_to_min(A, B)
    K = A.shape[1]
    C = np.full(K, np.nan, float)

    for j in range(K):
        a = A[:, j]
        b = B[:, j]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() > 2:
            C[j] = np.corrcoef(a[m], b[m])[0, 1]

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
    topk_cols=10,
):
    """
    Require that at least `min_pass_ratio` of the valid points satisfy:

        |A - B| <= atol + rtol * |ref|

    With the default parameters in this file:
        rtol = FRAC_RTOL (0.0)
        atol = FRAC_ATOL (0.75)
    the condition simplifies to:

        |A - B| <= FRAC_ATOL

    If the check fails, a detailed debug report is attached to the
    AssertionError to make it easier to inspect the worst violations.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)
    A, B = crop_rows_to_min(A, B)

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
    lines.append(
        diff_debug_report_fraction(
            A, B, within, tol_mat, label_a, label_b, topk_cols
        )
    )
    raise AssertionError("\n".join(lines))


# ============================================================
#            MINIMAL STUBS FOR FFT PLUGIN (TEST DOUBLE)
# ============================================================

class _Spin:
    """
    Minimal spin-box-like stub with a fixed numeric value.

    It mimics the Qt spin box API used by the plugin (value()).
    """
    def __init__(self, v: float):
        self._v = float(v)

    def value(self):
        return self._v


class _FftUiStub:
    """
    Minimal UI stub providing the attributes accessed by the FFT plugin.

    It exposes:
      - sampleDensitySpinBox
      - lowFrequencySpinBox
      - highFrequencySpinBox
    plus placeholders for plot-related attributes that we do not use.
    """
    def __init__(self, target_fs: float, f_lo: float, f_hi: float):
        self.sampleDensitySpinBox = _Spin(target_fs)
        self.lowFrequencySpinBox = _Spin(f_lo)
        self.highFrequencySpinBox = _Spin(f_hi)
        self.plotArea = None
        self.layoutWidget = None
        self.splitter = None


class FftDouble(Fft_plugin):
    """
    Headless version of the FFT plugin for tests.

    This test double:
      - Avoids any UI/VTK initialization,
      - Injects TrialDataset and signal dataset directly,
      - Exposes _load_trials_from_store and _compute_fft() so we can
        compute the FFT magnitudes and compare them with MATLAB.
    """

    def __init__(self, target_fs=UI_TARGET_FS, f_lo=UI_F_LO, f_hi=UI_F_HI):
        meta = PluginMeta(
            id="fft",
            name="FFT",
            category="analysis",
            subcategory="frequency",
            version="0.0.0",
            icon="",
            logic_class="Fft_plugin",
        )
        super().__init__(meta)

        self._active_td: TrialDataset | None = None
        self._active_sd = None

        # Headless UI stub used by the plugin.
        self.ui = _FftUiStub(target_fs, f_lo, f_hi)

    # --- UI / VTK handling overrides ---

    def _ensure_vtk(self):
        """
        Override VTK initialization to keep the test completely headless.
        """
        self.vtk_interactor = None
        self.vtk_view = None
        self.chart = None

    # --- Injection helpers used by the tests ---

    def set_active_trials(self, td: TrialDataset):
        """
        Inject the TrialDataset (trials cut from the original signal).
        """
        self._active_td = td

    def set_active_signal(self, sd):
        """
        Inject the signal dataset used by the plugin.
        """
        self._active_sd = sd

    # --- Bridges required by the original plugin API ---

    def get_active_signal(self):
        """
        Return the signal dataset that the plugin should use.
        """
        return self._active_sd

    def _load_trials_from_store(self):
        """
        Load trials from the injected TrialDataset and return:

            fs, X, channel_name

        where:
          - fs: sampling rate (float),
          - X: trials array (Ns, T),
          - channel_name: optional channel name string.
        """
        td = self._active_td
        if td is None or not hasattr(td, "trials") or td.trials.size == 0:
            return None, None, None

        fs = float(getattr(td, "sampling_rate", 0.0))
        X = np.asarray(td.trials, dtype=np.float64)  # (Ns, T)
        ch = getattr(td, "channel_name", "")

        return fs, X, ch


# ============================================================
#                        FIXTURES
# ============================================================

@pytest.fixture(scope="session")
def ds():
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


@pytest.fixture(scope="session")
def td(ds):
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


@pytest.fixture(scope="session")
def app_fft(ds, td):
    """
    Use the plugin's _compute_fft(X, fs, target_fs) method directly.

    This is the same method where you previously saw:
        freq = (1526,)
        mag  = (1526, 60)
        fs_eff = 1000
    """
    plug = FftDouble(target_fs=UI_TARGET_FS, f_lo=UI_F_LO, f_hi=UI_F_HI)
    plug.set_active_signal(ds)
    plug.set_active_trials(td)

    fs, X, _ = plug._load_trials_from_store()
    assert fs is not None and X is not None

    freq, mag, fs_eff = plug._compute_fft(X, fs, UI_TARGET_FS)

    # Simple logs for inspection.
    print("APP FFT mag:\n", mag, mag.shape)
    print("APP FFT freq shape:", freq.shape, "fs_eff:", fs_eff)

    return np.asarray(freq, float), np.asarray(mag, float)  # (Nf,), (Nf, K)


@pytest.fixture(scope="session")
def matlab_fft_matrix():
    """
    Load the MATLAB FFT matrix from CSV using the dedicated helper.

    Expected shapes are (Nf, K) or (K, Nf). Orientation is adapted
    when comparing.
    """
    M = load_csv_matlab(MATLAB_CSV)
    M = np.asarray(M, dtype=np.float64)

    # Simple log for debugging.
    print("MATLAB FFT mag:\n", M, M.shape)

    return M


# ============================================================
#                   TEST FOR FFT
# ============================================================

@pytest.mark.skipif(not ABF_PATH.exists(), reason="ABF file not found")
@pytest.mark.skipif(not MATLAB_CSV.exists(), reason="MATLAB CSV not found")
class TestFFTABFVsMatlab:
    """
    Integration tests that compare the full FFT magnitude matrix
    produced by the Gamma Lab FFT plugin against a MATLAB reference.

    The tests check:
      1) Shape / columns consistency (60 trials).
      2) High Pearson correlation per trial (column).
      3) Pointwise agreement for ≥ 95% of the points within a given
         absolute tolerance.
    """

    # --------------------------------------------------------
    # Helper to match MATLAB orientation to the APP matrix
    # --------------------------------------------------------
    def _orient_matlab_like_app(self, mag_app, M):
        """
        Return M with the same orientation (Nf, K) as mag_app.
        """
        Nf_app, _ = mag_app.shape

        if M.shape[0] == Nf_app:
            return M
        if M.shape[1] == Nf_app:
            return M.T

        # Fallback: choose the orientation with larger number of rows
        # as a best guess for frequency dimension.
        return M if M.shape[0] >= M.shape[1] else M.T

    # --------------------------------------------------------
    # 1. Structure / columns checks
    # --------------------------------------------------------
    def test_shape_and_columns(self, app_fft, matlab_fft_matrix):
        """
        Both matrices must have K=60 columns (one per trial).

        If MATLAB comes transposed, we adapt it to match the
        APP orientation.
        """
        _, mag_app = app_fft  # (Nf,), (Nf, K_app)
        M_use = self._orient_matlab_like_app(mag_app, matlab_fft_matrix)

        assert mag_app.ndim == 2 and M_use.ndim == 2
        assert mag_app.shape[1] == K_EXPECTED, (
            f"APP columns={mag_app.shape[1]} != {K_EXPECTED}"
        )
        assert M_use.shape[1] == K_EXPECTED, (
            f"MATLAB columns={M_use.shape[1]} != {K_EXPECTED}"
        )
        assert mag_app.shape[0] >= 1 and M_use.shape[0] >= 1

    # --------------------------------------------------------
    # 2. Correlation per column (trial)
    # --------------------------------------------------------
    def test_correlation_by_column(self, app_fft, matlab_fft_matrix):
        """
        Check Pearson correlation per trial (column) with threshold
        MIN_CORR.

        This is particularly useful when there are offsets or scaling
        differences but the shape of the spectra is correct.
        """
        _, mag_app = app_fft
        M_use = self._orient_matlab_like_app(mag_app, matlab_fft_matrix)

        # We expect exactly 60 columns (trials).
        assert mag_app.shape[1] == K_EXPECTED and M_use.shape[1] == K_EXPECTED

        C = corr_by_col(mag_app, M_use)
        finite_mask = np.isfinite(C)
        assert np.any(finite_mask), "No columns with valid data for correlation."

        low = np.where(finite_mask & (C < MIN_CORR))[0]
        if low.size > 0:
            order = np.argsort(C[finite_mask])
            worst_idx = np.where(finite_mask)[0][order[:5]]
            msg = (
                f"Low correlation in columns {low.tolist()} "
                f"(min={np.nanmin(C):.4f}, threshold={MIN_CORR})"
            )
            msg += "\nWorst correlations: " + ", ".join(
                f"col {int(i)}: {C[int(i)]:.4f}" for i in worst_idx
            )
            pytest.fail(msg)

    # --------------------------------------------------------
    # 3. Pointwise comparison with tolerance (allows outliers)
    # --------------------------------------------------------
    def test_pointwise_fraction_allowing_outliers(self, app_fft, matlab_fft_matrix):
        """
        Require that at least 95% of the points (Nf x K) satisfy:

            |APP - MATLAB| <= FRAC_ATOL  (0.75 by default)

        A small fraction of outliers is allowed, but detailed information
        is reported if the requirement is not met.
        """
        _, mag_app = app_fft
        M_use = self._orient_matlab_like_app(mag_app, matlab_fft_matrix)

        # We expect exactly 60 columns (trials).
        assert mag_app.shape[1] == K_EXPECTED and M_use.shape[1] == K_EXPECTED

        A, B = crop_rows_to_min(mag_app, M_use)
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
                f"FFT magnitudes: at least {FRAC_MIN_PASS*100:.1f}% of the points "
                f"must be within the absolute tolerance ({FRAC_ATOL})"
            ),
        )