import numpy as np
import pytest
from pathlib import Path

# --- Real pipeline imports (core app services & plugins) ---
from core.services.fileio import FileIOService
from core.filters import trials as tr
from core.services.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from plugins.analysis.frequency.psd.psd_plugin import Psd_plugin


# ============================================================
#                  GLOBAL CONFIG / TEST DATA
# ============================================================

# Base directory for test data files
BASE_DIR = Path(__file__).resolve().parents[2] / "test" / "data"

# Input ABF file
ABF_PATH = BASE_DIR / "17308005.abf"

# MATLAB reference CSV
MATLAB_CSV = BASE_DIR / "psd_data_matlab.csv"


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
#                 PSD / WELCH PARAMETERS
# ============================================================

# Default PSD parameters
TARGET_FS = 1000.0
WIN = "hamming"
NPERSEG = 1024
NOVERLAP = 128
NFFT = 1024
DETREND = "none"
F_LO = 0.0
F_HI = 500.0


# ============================================================
#                 NUMERICAL COMPARISON PARAMETERS
# ============================================================

# Expected number of columns (trials) in the PSD matrix
K_EXPECTED = 60          # 60 trials → 60 columns

# Minimum acceptable Pearson correlation per column (trial)
MIN_CORR = 0.88

# Fractional test parameters
FRAC_MIN_PASS = 0.95     # At least 95% of points must be within tolerance
FRAC_ATOL = 0.0001         # Absolute tolerance (adjust if too strict)
FRAC_RTOL = 0.0         # Relative tolerance


# ============================================================
#           MATLAB CSV LOADING HELPER (PER-TRIAL PSD)
# ============================================================

def load_csv_matlab_psd(path: Path) -> np.ndarray:
    """
    Load the CSV exported from MATLAB for per-trial PSD.

    We assume shape (Nf, K) or (K, Nf) with K=60 trials.
    No averaging is done here; we return the full 2D matrix.
    """
    M = np.loadtxt(path, delimiter=";")
    M = np.asarray(M, dtype=np.float64)

    if M.ndim == 1:
        # If for some reason it is 1D, treat as a single curve.
        M = M.reshape(-1, 1)

    return M


# ============================================================
#                    NUMPY HELPER FUNCTIONS
# ============================================================

def crop_rows_to_min(A: np.ndarray, B: np.ndarray):
    """
    Crop A and B to the same number of rows (the minimum of both),
    keeping all columns. A and B are treated as 2D matrices (N, K).

    1D arrays are promoted to (N, 1) matrices.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    if A.ndim == 1:
        A = A.reshape(-1, 1)
    if B.ndim == 1:
        B = B.reshape(-1, 1)

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
    Compute Pearson correlation per column (trial/curve).
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

    where `ref` indicates which matrix (A or B) is used in the
    relative term (rtol * |ref|).
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
    lines.append(f"[frac] passed={passed}/{total} -> ratio={ratio:.5f}")
    lines.append(
        diff_debug_report_fraction(
            A, B, within, tol_mat, label_a, label_b, topk_cols
        )
    )
    raise AssertionError("\n".join(lines))


# ============================================================
#                TEST FOR PSD PLUGIN
# ============================================================

class PsdDouble(Psd_plugin):
    """
    Minimal test double for the PSD plugin.

    This class:
      - Creates the real plugin to reuse _compute_psd(),
      - Avoids VTK initialization,
      - Lets the tests call _compute_psd() directly and compare
        its output against MATLAB.
    """

    def __init__(self):
        meta = PluginMeta(
            id="psd",
            name="PSD",
            category="analysis",
            subcategory="frequency",
            version="0.0.0",
            icon="",
            logic_class="Psd_plugin",
        )
        super().__init__(meta)

    def _ensure_vtk(self, *args, **kwargs):
        """
        Override VTK initialization to keep the test completely headless.
        """
        self.vtk_interactor = None
        self.vtk_view = None


# ============================================================
#                        FIXTURES
# ============================================================

@pytest.fixture(scope="class")
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


@pytest.fixture(scope="class")
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


@pytest.fixture(scope="class")
def app_psd(td):
    """
    Compute PSD for all trials using _compute_psd() and return
    the full power matrix (Nf, K) without averaging.
    """
    plug = PsdDouble()

    X = np.asarray(td.trials, dtype=np.float64)   # (Ns, T)
    fs = float(td.sampling_rate)

    freq, power_all, fs_eff = plug._compute_psd(
        X,
        fs,
        TARGET_FS,
        WIN,
        int(NPERSEG),
        int(NOVERLAP),
        int(NFFT),
        DETREND,
    )
    # power_all: (Nf, K_trials)

    print(
        "APP PSD: freq.shape =",
        freq.shape,
        ", power_all.shape =",
        power_all.shape,
        ", fs_eff =",
        fs_eff,
    )

    return freq, power_all


@pytest.fixture(scope="class")
def matlab_psd_matrix():
    """
    Load per-trial PSD from MATLAB as a 2D matrix.

    It may come as (Nf, K) or (K, Nf); orientation is adapted later.
    """
    M = load_csv_matlab_psd(MATLAB_CSV)
    print("MATLAB PSD shape:", M.shape)
    return M


# ============================================================
#                   INTEGRATION TEST SUITE
#          APP PSD per trial vs MATLAB Reference
# ============================================================

@pytest.mark.skipif(not ABF_PATH.exists(), reason="ABF file not found")
@pytest.mark.skipif(not MATLAB_CSV.exists(), reason="MATLAB CSV not found")
class TestPsdABFVsMatlab:
    """
    Integration tests that compare the per-trial PSD matrix produced
    by the Gamma Lab PSD plugin against a MATLAB reference.

    The tests check:
      1) Shape / columns consistency (60 trials).
      2) High Pearson correlation per trial (column).
      3) Pointwise agreement for ≥ 95% of the points within a given
         absolute and relative tolerance.
    """

    # --------------------------------------------------------
    # Helper to match MATLAB orientation to the APP matrix
    # --------------------------------------------------------
    def _orient_matlab_like_app(self, power_app, M):
        """
        Return M with the same orientation (Nf, K) as power_app.

        We assume K_EXPECTED = 60 columns (trials).
        """
        Nf_app, _ = power_app.shape

        if M.shape[0] == Nf_app:
            return M
        if M.shape[1] == Nf_app:
            return M.T

        # Fallback: choose the orientation with larger number of rows
        # as a best guess for the frequency dimension.
        return M if M.shape[0] >= M.shape[1] else M.T

    # --------------------------------------------------------
    # 1. Structure / length checks
    # --------------------------------------------------------
    def test_shape_and_columns(self, app_psd, matlab_psd_matrix):
        """
        Both matrices must have K=60 columns (one per trial) and
        at least one frequency row.
        """
        _, power_app = app_psd          # (Nf_app, K_app)
        M_use = self._orient_matlab_like_app(power_app, matlab_psd_matrix)

        assert power_app.ndim == 2 and M_use.ndim == 2
        assert power_app.shape[1] == K_EXPECTED, (
            f"APP columns={power_app.shape[1]} != {K_EXPECTED}"
        )
        assert M_use.shape[1] == K_EXPECTED, (
            f"MATLAB columns={M_use.shape[1]} != {K_EXPECTED}"
        )
        assert power_app.shape[0] >= 1 and M_use.shape[0] >= 1

    # --------------------------------------------------------
    # 2. Correlation per column (trial)
    # --------------------------------------------------------
    def test_correlation_by_column(self, app_psd, matlab_psd_matrix):
        """
        Check Pearson correlation per trial (column) with threshold
        MIN_CORR. This allows for small scale/offset differences while
        still enforcing a similar spectral shape.
        """
        _, power_app = app_psd
        M_use = self._orient_matlab_like_app(power_app, matlab_psd_matrix)

        # We expect exactly 60 columns (trials).
        assert power_app.shape[1] == K_EXPECTED and M_use.shape[1] == K_EXPECTED

        C = corr_by_col(power_app, M_use)
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
    def test_pointwise_fraction_allowing_outliers(self, app_psd, matlab_psd_matrix):
        """
        Require that at least FRAC_MIN_PASS of valid points satisfy:

            |APP - MATLAB| <= FRAC_ATOL + FRAC_RTOL * |MATLAB|

        A small fraction of outliers is allowed, but detailed information
        is reported if the requirement is not met.
        """
        _, power_app = app_psd
        M_use = self._orient_matlab_like_app(power_app, matlab_psd_matrix)

        # We expect exactly 60 columns (trials).
        assert power_app.shape[1] == K_EXPECTED and M_use.shape[1] == K_EXPECTED

        A, B = crop_rows_to_min(power_app, M_use)

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
                f"PSD per-trial: {FRAC_MIN_PASS*100:.1f}% of the points must be "
                f"within tolerance (atol={FRAC_ATOL}, rtol={FRAC_RTOL})"
            ),
        )
