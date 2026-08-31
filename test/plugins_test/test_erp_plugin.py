import numpy as np
import pytest
from pathlib import Path

# --- Real pipeline imports (core app services & plugins) ---
from core.services.fileio import FileIOService
from core.filters import trials as tr
from core.services.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta

# Real ERP plugin
from plugins.analysis.time.erp.erp_plugin import Erp_plugin


# ============================================================
#                  GLOBAL CONFIG / TEST DATA
# ============================================================

# Base directory for test data files
BASE_DIR = Path(__file__).resolve().parents[2] / "test" / "data"

# Input ABF file
ABF_PATH = BASE_DIR / "17308005.abf"

# MATLAB reference CSV
MATLAB_CSV = BASE_DIR / "erp_data_matlab.csv"


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

# Expected number of columns (trials) in the ERP matrix
K_EXPECTED = 60

# Absolute tolerance for pointwise ERP comparison
TOL_ABS = 0.001

# Minimum acceptable Pearson correlation per column (trial)
MIN_CORR = 0.98


# ============================================================
#                    NUMPY HELPER FUNCTIONS
# ============================================================

def _detect_delimiter(path: Path) -> str | None:
    """
    Try to guess the delimiter of a CSV file by counting occurrences of
    ';', ',' and tab in a small sample of the file.
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        sample = f.read(8192)

    counts = {
        ";": sample.count(";"),
        ",": sample.count(","),
        "\t": sample.count("\t"),
    }
    delim, n = max(counts.items(), key=lambda kv: kv[1])
    return delim if n > 0 else None


def load_csv_auto(path: Path) -> np.ndarray:
    """
    Load a CSV file automatically detecting its delimiter.

    Returns:
        np.ndarray:
            2D array of float64. If the data is 1D, it is reshaped to (N, 1).
    """
    delim = _detect_delimiter(path)
    if delim is None:
        arr = np.genfromtxt(path, dtype=np.float64, filling_values=np.nan)
    else:
        arr = np.genfromtxt(path, delimiter=delim, dtype=np.float64, filling_values=np.nan)

    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)

    return arr


def crop_rows_to_min(A: np.ndarray, B: np.ndarray):
    """
    Crop A and B to the same number of rows (the minimum of both),
    keeping all columns. A and B are treated as 2D matrices (N, K).

    This is useful when APP and MATLAB matrices have slightly different
    lengths but we only want to compare the common overlapping part.
    """
    A = np.asarray(A, dtype=float)
    B = np.asarray(B, dtype=float)

    assert A.ndim == 2 and B.ndim == 2, "Input arrays must be 2D."
    assert A.shape[1] == B.shape[1], f"Different number of columns: {A.shape[1]} vs {B.shape[1]}"

    n = min(A.shape[0], B.shape[0])
    return A[:n, :], B[:n, :]


def corr_by_col(A, B):
    """
    Compute Pearson correlation per column between A and B.

    Here each column represents a trial in the ERP butterfly matrix.
    """
    A, B = crop_rows_to_min(A, B)
    K = A.shape[1]
    C = np.full(K, np.nan, float)

    for j in range(K):
        a, b = A[:, j], B[:, j]
        m = np.isfinite(a) & np.isfinite(b)
        if m.sum() > 2:
            C[j] = np.corrcoef(a[m], b[m])[0, 1]

    return C


def assert_points_within_tolerance_fraction(
    A,
    B,
    *,
    min_pass_ratio=0.95,
    atol=TOL_ABS,
    rtol=0.0,
    ref="B",
    label_a="APP",
    label_b="MATLAB",
    topk_cols=10,
    msg="",
):
    """
    Require that at least `min_pass_ratio` of the valid points satisfy:

        |A - B| <= atol + rtol * |ref|

    With the default parameters in this file:
        rtol = 0.0
        atol = TOL_ABS
    the condition simplifies to:

        |A - B| <= TOL_ABS

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
    over_mask = valid & (~within)
    excess = np.full_like(diffs, np.nan, dtype=float)
    excess[over_mask] = diffs[over_mask] - tol_mat[over_mask]

    flat_idx = np.nanargmax(excess)
    r, c = np.unravel_index(flat_idx, excess.shape)
    worst_excess = float(excess[r, c])
    worst_diff = float(diffs[r, c])
    worst_tol = float(tol_mat[r, c])
    va, vb = float(A[r, c]), float(B[r, c])

    by_col_counts = np.nansum(over_mask, axis=0)
    by_col_maxexc = np.nanmax(excess, axis=0)
    order = np.lexsort((-by_col_maxexc, -by_col_counts))[::-1]
    topk = [
        (int(cidx), int(by_col_counts[cidx]), float(by_col_maxexc[cidx]))
        for cidx in order[:topk_cols]
    ]

    lines = []
    lines.append(msg or "Fractional tolerance check failed")
    lines.append(f"[frac] shape {label_a}={A.shape}, {label_b}={B.shape}")
    lines.append(
        f"[frac] params: min_pass_ratio={min_pass_ratio:.3f}, "
        f"atol={atol}, rtol={rtol} (ref={ref})"
    )
    lines.append(f"[frac] passed={passed}/{total} -> ratio={ratio:.5f}")
    lines.append(
        f"[frac] worst @ (row={r}, col={c}) -> diff={worst_diff:.6f}, "
        f"tol_local={worst_tol:.6f}, excess={worst_excess:.6f} ; "
        f"{label_a}={va:.6f} ; {label_b}={vb:.6f}"
    )
    if topk:
        lines.append("[frac] top columns by violations (col, count, max_excess):")
        for col_id, cnt, mx in topk:
            lines.append(
                f"  - col={col_id:02d}  count={cnt}  max_excess={mx:.6f}"
            )

    raise AssertionError("\n".join(lines))


# ============================================================
#                 TEST FOR ERP BUTTERFLY
# ============================================================

class ErpButterflyDouble(Erp_plugin):
    """
    Headless version of the ERP plugin (test double).

    This class:
      - Avoids any UI/VTK initialization.
      - Captures the ERP butterfly matrix in memory (time vector + trials)
        so it can be compared directly with the MATLAB reference.
    """

    def __init__(self):
        meta = PluginMeta(
            id="erp-butterfly",
            name="ERP Butterfly (Double)",
            category="analysis",
            subcategory="time",
            version="0.0.0",
            icon="",
            logic_class="Erp_plugin",
        )
        super().__init__(meta)

        # References to active signal and trials set by the test.
        self._active_signal = None
        self._active_trials: TrialDataset | None = None

        # Captured outputs (time and ERP lines).
        self.captured_t = None
        self.captured_lines = None

    # --- UI / VTK handling overrides ---

    def ensure_vtk(self):
        """
        Override the VTK initialization to keep the test completely headless.
        """
        # No-op: do not create any view or VTK widget.
        return

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

    # --- Main execution used by the tests ---

    def run_all(self):
        """
        Build the ERP butterfly matrix from the active TrialDataset and
        capture it in memory instead of rendering it.

        The resulting matrix has shape (N_time, N_trials).
        """
        td = self.get_active_trials()
        if td is None:
            raise RuntimeError("TrialDataset not injected into ErpButterflyDouble.")

        t = np.asarray(td.time_rel, dtype=float)
        M = np.asarray(td.trials, dtype=float)

        # Trials shape adjustments:
        #   - We expect M to end up as (N_time, N_trials).
        if M.shape[0] == t.size:
            # Already (N_time, N_trials)
            pass
        elif M.shape[1] == t.size:
            # Currently (N_trials, N_time), transpose to match expected shape.
            M = M.T
        else:
            raise ValueError("time_rel length does not match trials shape.")

        self.captured_t = t
        self.captured_lines = M


# ============================================================
#                   TEST FOR Erp_plugin
# ============================================================

@pytest.mark.skipif(not ABF_PATH.exists(), reason="ABF file not found")
@pytest.mark.skipif(not MATLAB_CSV.exists(), reason="MATLAB CSV not found")
class TestErpButterflyABFVsMatlab:
    """
    Integration tests that compare the ERP butterfly produced by
    the Gamma Lab ERP plugin against a MATLAB reference implementation.

    The tests check:
      1) Shape / columns consistency.
      2) High Pearson correlation per trial (column).
      3) Pointwise agreement for ≥ 95% of the points within a given
         absolute tolerance.
    """

    # --------------------------------------------------------
    # Fixtures: dataset, trials and matrices
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
    def app_matrix(self, ds, td):
        """
        Run the ERP butterfly plugin (headless test double) and capture
        the resulting ERP matrix as a (N_time, N_trials) float64 array.
        """
        plug = ErpButterflyDouble()
        plug.set_active_signal(ds)
        plug.set_active_trials(td)
        plug.run_all()

        return np.asarray(plug.captured_lines, dtype=np.float64, copy=False)

    @pytest.fixture(scope="class")
    def matlab_matrix(self):
        """
        Load the MATLAB ERP butterfly matrix from CSV using the
        automatic delimiter detection helper.
        """
        M = load_csv_auto(MATLAB_CSV)
        return np.asarray(M, dtype=np.float64, copy=False)

    # --------------------------------------------------------
    # 1. Structure / columns checks
    # --------------------------------------------------------
    def test_shape_and_columns(self, app_matrix, matlab_matrix):
        """
        Ensure that both APP and MATLAB matrices:
          - Are 2D arrays,
          - Have the expected number of columns (trials),
          - Have at least one row (time samples).
        """
        assert app_matrix.ndim == 2 and matlab_matrix.ndim == 2

        assert app_matrix.shape[1] == K_EXPECTED, (
            f"APP columns={app_matrix.shape[1]} != {K_EXPECTED}"
        )
        assert matlab_matrix.shape[1] == K_EXPECTED, (
            f"MATLAB columns={matlab_matrix.shape[1]} != {K_EXPECTED}"
        )

        assert app_matrix.shape[0] >= 1 and matlab_matrix.shape[0] >= 1

    # --------------------------------------------------------
    # 2. Correlation per column (trial)
    # --------------------------------------------------------
    def test_correlation_by_column(self, app_matrix, matlab_matrix):
        """
        Check that each trial (column) in the APP ERP matrix has
        Pearson correlation above MIN_CORR when compared to the
        corresponding MATLAB trial.
        """
        C = corr_by_col(app_matrix, matlab_matrix)

        finite_mask = np.isfinite(C)
        assert np.any(finite_mask), "No columns with valid data for correlation."

        low = np.where(finite_mask & (C < MIN_CORR))[0]
        if low.size > 0:
            msg = (
                f"Low correlation in columns {low.tolist()} "
                f"(min={np.nanmin(C):.4f}) with threshold={MIN_CORR}"
            )
            order = np.argsort(C[finite_mask])
            worst_idx = np.where(finite_mask)[0][order[:5]]
            msg += "\nWorst correlations: " + ", ".join(
                f"col {int(i)}: {C[int(i)]:.4f}" for i in worst_idx
            )
            pytest.fail(msg)

    # --------------------------------------------------------
    # 3. Pointwise comparison with tolerance (allows outliers)
    # --------------------------------------------------------
    def test_pointwise_fraction_allowing_outliers(self, app_matrix, matlab_matrix):
        """
        Require that at least 95% of valid points between APP and MATLAB
        ERP matrices are within the absolute tolerance TOL_ABS.

        A small fraction of outliers is allowed, but detailed information
        is reported if the requirement is not met.
        """
        A, B = crop_rows_to_min(app_matrix, matlab_matrix)
        assert_points_within_tolerance_fraction(
            A,
            B,
            min_pass_ratio=0.95,
            atol=TOL_ABS,
            rtol=0.0,
            ref="B",
            label_a="APP",
            label_b="MATLAB",
            msg="ERP butterfly: 95% of points must be within absolute tolerance",
        )
