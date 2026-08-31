import numpy as np
import pytest
from pathlib import Path

# --- Real pipeline imports (core app services & plugins) ---
from core.services.fileio import FileIOService
from core.filters import trials as tr
from core.services.trial_dataset import TrialDataset
from plugins.analysis.time.average.average_plugin import Average_plugin
from core.plugins.meta import PluginMeta


# ============================================================
#                  GLOBAL CONFIG / TEST DATA
# ============================================================

# Base directory for test data files
BASE_DIR = Path(__file__).resolve().parents[2] / "test" / "data"

# Input ABF file
ABF_PATH = BASE_DIR / "17308005.abf"

# MATLAB reference CSV
MATLAB_CSV = BASE_DIR / "average_data_matlab.csv"


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

# Expected number of stimuli per trial
STIM_EXPECTED = 1

# Inter-stimulus interval (used by the cutting logic)
ISI = 0.0

# Value used to pad trials if needed
PAD_VALUE = 0.0


# ============================================================
#                 NUMERICAL COMPARISON PARAMETERS
# ============================================================

# Expected number of columns in the average vector (we use 1)
K_EXPECTED = 1          # Expected number of columns

# Minimum acceptable Pearson correlation between APP vs MATLAB curves
MIN_CORR = 0.98

# Minimum fraction of points that must be within tolerance
FRAC_MIN_PASS = 0.95    # ≥ 95% of points must pass

# Absolute tolerance for pointwise comparison: |APP - MATLAB| ≤ FRAC_ATOL
FRAC_ATOL = 0.001

# Relative tolerance (unused for now, but kept for completeness of the formula)
FRAC_RTOL = 0.0         # With rtol=0.0 we only use the absolute tolerance


# ============================================================
#                    NUMPY HELPER FUNCTIONS
# ============================================================

def crop_rows_to_min(A: np.ndarray, B: np.ndarray):
    """
    Crop A and B to the same number of rows (the minimum of both),
    keeping all columns. A and B are treated as 2D matrices (N, K).

    This is useful when APP and MATLAB vectors have slightly different
    lengths but we only want to compare the common overlapping part.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    # Promote 1D vectors to (N, 1) matrices.
    if A.ndim == 1:
        A = A.reshape(-1, 1)
    if B.ndim == 1:
        B = B.reshape(-1, 1)

    # Basic sanity checks for matrix shapes.
    assert A.ndim == 2 and B.ndim == 2, "Input arrays must be 2D."
    assert A.shape[1] == B.shape[1], f"Different number of columns: {A.shape[1]} vs {B.shape[1]}"

    n = min(A.shape[0], B.shape[0])
    return A[:n, :], B[:n, :]


def diff_debug_report_fraction(A, B, within, tol_mat, label_a="APP", label_b="MATLAB", topk_cols=10):
    """
    Build a detailed debug report for the fractional tolerance test.

    The report includes:
      - The worst point (row, col) where the tolerance is violated,
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

    # Find worst violating point (ignoring NaNs).
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
        # Sort by (# violations desc, max_excess desc).
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
    Compute Pearson correlation per column between A and B.

    In this test suite, we mostly work with a single column (K=1),
    but the helper is generic and works for any (N, K) matrices.
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
    min_pass_ratio=0.95,
    atol=FRAC_ATOL,
    rtol=FRAC_RTOL,
    ref="B",
    label_a="APP",
    label_b="MATLAB",
    msg="",
    topk_cols=10,
):
    """
    Assert that at least `min_pass_ratio` of the valid points satisfy:

        |A - B| <= atol + rtol * |ref|

    With the default parameters in this file:
        rtol = 0.0
        atol = FRAC_ATOL
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
    lines.append(f"[frac] passed={passed}/{total} -> ratio={ratio:.5f}")
    lines.append(
        diff_debug_report_fraction(
            A, B, within, tol_mat, label_a, label_b, topk_cols
        )
    )
    raise AssertionError("\n".join(lines))


# ============================================================
#                 TEST FOR Average_plugin
# ============================================================

class AverageDouble(Average_plugin):
    """
    Test double for Average_plugin that:
      - Avoids UI/VTK initialization, and
      - Captures (t, avg_data) from _on_calculate_average instead of rendering.

    This allows us to exercise the real plugin logic while keeping
    the test headless and stable.
    """

    def __init__(self):
        # Minimal plugin metadata required by the core plugin system.
        meta = PluginMeta(
            id="average",
            name="Average",
            category="analysis",
            subcategory="time",
            version="0.0.0",
            icon="",
            logic_class="Average_plugin",
        )
        super().__init__(meta)

        # Captured outputs from render_average().
        self._captured_t = None
        self._captured_avg = None

        # References to active signal and trials set by the test.
        self._active_signal = None
        self._active_trials: TrialDataset | None = None

    # --- UI / VTK handling overrides ---

    def ensure_vtk(self):
        """
        Override the VTK initialization to keep the test completely headless.
        """
        self.view = None
        self.vtk_widget = None

    def render_average(self, t, av_data, channel_name=None, unit=None):
        """
        Capture the average data instead of rendering it in a VTK widget.
        This method is called by _on_calculate_average in the real plugin.
        """
        self._captured_t = np.asarray(t, dtype=float)
        self._captured_avg = np.asarray(av_data, dtype=float)

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

    The resulting TrialDataset is what Average_plugin expects.
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
def app_avg(ds, td):
    """
    Run the Average plugin (headless test double) and capture its
    average vector.

    We use _on_calculate_average(), which builds the average and
    calls render_average(), but in this test double render_average()
    only stores the data in memory.
    """
    plug = AverageDouble()
    plug.set_active_signal(ds)
    plug.set_active_trials(td)
    plug._on_calculate_average()

    assert plug._captured_avg is not None, "AverageDouble did not capture av_data."
    avg = plug._captured_avg

    # Simple logging to help debug shape issues.
    print("APP Average shape:", avg.shape)

    # Return as (N, 1) so we can reuse the 2D helper functions.
    avg = np.asarray(avg, dtype=np.float64).reshape(-1, 1)
    return avg


@pytest.fixture(scope="class")
def matlab_avg():
    """
    Load the MATLAB CSV average:

      - If the CSV has shape (N, 1) or (N, k), the last column is
        interpreted as the average curve (e.g., [t, avg] -> avg).
      - If the CSV is 1D, it is used as-is.

    The result is always returned as a (N, 1) matrix.
    """
    M = np.loadtxt(MATLAB_CSV, delimiter=",")
    M = np.asarray(M, dtype=np.float64)

    if M.ndim == 2 and M.shape[1] >= 1:
        # Example: [t, avg] -> use the last column as average.
        M = M[:, -1]
    elif M.ndim != 1:
        # Fallback: flatten to 1D.
        M = M.reshape(-1)

    print("MATLAB Average shape (raw 1D):", M.shape)
    M = M.reshape(-1, 1)
    return M


# ============================================================
#                   INTEGRATION TEST SUITE
#          APP Average vs MATLAB Reference Average
# ============================================================

@pytest.mark.skipif(not ABF_PATH.exists(), reason="ABF file not found")
@pytest.mark.skipif(not MATLAB_CSV.exists(), reason="MATLAB CSV not found")
class TestAverageABFVsMatlab:
    """
    Integration tests that compare the average curve produced by the
    Gamma Lab Average plugin against a MATLAB reference implementation.

    The tests check:
      1) Shape / length consistency.
      2) High Pearson correlation between APP and MATLAB averages.
      3) Pointwise agreement for ≥ 95% of the points within a given
         absolute tolerance.
    """

    # --------------------------------------------------------
    # 1. Shape and basic structural checks
    # --------------------------------------------------------
    def test_shape_and_length(self, app_avg, matlab_avg):
        """
        Ensure that both APP and MATLAB averages:
          - Are 2D arrays,
          - Have the expected number of columns,
          - Have at least one row.
        """
        assert app_avg.ndim == 2 and matlab_avg.ndim == 2

        assert app_avg.shape[1] == K_EXPECTED, (
            f"APP columns={app_avg.shape[1]} != {K_EXPECTED}"
        )
        assert matlab_avg.shape[1] == K_EXPECTED, (
            f"MATLAB columns={matlab_avg.shape[1]} != {K_EXPECTED}"
        )

        assert app_avg.shape[0] >= 1 and matlab_avg.shape[0] >= 1

    # --------------------------------------------------------
    # 2. Correlation: APP vs MATLAB average curve
    # --------------------------------------------------------
    def test_correlation_with_matlab(self, app_avg, matlab_avg):
        """
        Check that each column of the APP average has Pearson correlation
        above MIN_CORR when compared to the MATLAB reference.
        """
        A, B = crop_rows_to_min(app_avg, matlab_avg)
        C = corr_by_col(A, B)

        finite_mask = np.isfinite(C)
        assert np.any(finite_mask), "No columns with valid data for correlation."

        low = np.where(finite_mask & (C < MIN_CORR))[0]
        if low.size > 0:
            msg = (
                f"Low correlation in columns {low.tolist()} "
                f"(min={np.nanmin(C):.4f}, threshold={MIN_CORR})"
            )
            pytest.fail(msg)

    # --------------------------------------------------------
    # 3. Pointwise comparison with tolerance (allows outliers)
    # --------------------------------------------------------
    def test_pointwise_fraction_allowing_outliers(self, app_avg, matlab_avg):
        """
        Require that at least FRAC_MIN_PASS of the valid points between
        APP and MATLAB are within the absolute tolerance FRAC_ATOL.

        A small fraction of outliers is allowed, but detailed information
        is reported if the requirement is not met.
        """
        A, B = crop_rows_to_min(app_avg, matlab_avg)
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
                f"Average: at least {FRAC_MIN_PASS*100:.1f}% of the points "
                f"must be within the absolute tolerance ({FRAC_ATOL})."
            ),
        )
