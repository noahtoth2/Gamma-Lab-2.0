import pytest
from unittest.mock import Mock, patch
from core.services.measurement_service import MeasurementService

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def create_basic_service():
    """Minimal MeasurementService with stubbed datastore and chart access."""
    parent = Mock()
    vtk_widget = Mock()
    vtk_widget.GetRenderWindow().Render = Mock()
    get_active_chart = Mock(return_value=None)
    ds_get = Mock(return_value=[])
    ds_set = Mock()

    svc = MeasurementService(parent, vtk_widget, get_active_chart, ds_get, ds_set)
    svc.alerts = Mock()
    return svc


def create_service_with_data():
    """Service with preloaded ref data (xs, ys)."""
    svc = create_basic_service()
    svc._ref_data = {
        "xs": [0.0, 1.0, 2.0, 3.0, 4.0, 5.0],
        "ys": [0.0, 2.0, -1.0, 3.0, -2.0, 1.0],
    }
    return svc


# =====================================================================
# 1) STATE MACHINE: start / cancel / reentry / guards
# =====================================================================

def test_start_slope_success():
    svc = create_basic_service()
    svc.start("slope")
    assert svc._state == "waiting_p1"
    assert svc._current == {"type": "slope", "p1": None, "p2": None}
    svc.alerts.info.assert_called_once()


def test_start_amplitude_success():
    svc = create_basic_service()
    svc.start("amplitude")
    assert svc._state == "waiting_p1"
    assert svc._current["type"] == "amplitude"


def test_start_slope_all_trials_wrong_plugin():
    svc = create_basic_service()
    svc.set_context(plugin="erp")
    result = svc.start("slope_all_trials")
    assert result is False
    assert svc._state == "idle"
    svc.alerts.info.assert_called_once()


def test_start_slope_all_trials_correct_plugin():
    svc = create_basic_service()
    svc.set_context(plugin="trials")
    result = svc.start("slope_all_trials")
    assert svc._state == "waiting_p1"
    assert result is not False


def test_start_when_measurement_already_in_progress():
    svc = create_basic_service()
    svc._state = "waiting_p2"
    result = svc.start("slope")
    assert result is False
    svc.alerts.info.assert_called()


def test_start_while_busy_different_type_is_blocked_and_does_not_mutate():
    svc = create_basic_service()
    svc._state = "waiting_p2"
    svc._current = {"type": "slope", "p1": (0, 0), "p2": None}
    result = svc.start("amplitude")
    assert result is False
    assert svc._state == "waiting_p2"
    assert svc._current["type"] == "slope"
    svc.alerts.info.assert_called()


# ---------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------

def test_cancel_resets_all_state():
    svc = create_basic_service()
    svc._state = "waiting_p2"
    svc._current = {"type": "slope", "p1": (1, 2), "p2": None}
    svc._ref_axes = {"x": Mock(), "y": Mock()}
    svc._saved_ranges = {"x": (0, 10), "y": (0, 5)}
    svc._ref_data = {"xs": [1, 2, 3], "ys": [4, 5, 6]}
    svc.cancel()
    assert svc._state == "idle"
    assert svc._current is None
    assert svc._ref_axes is None
    assert svc._saved_ranges is None
    assert svc._ref_data is None


def test_cancel_during_waiting_p1():
    svc = create_basic_service()
    svc.start("slope")
    svc.cancel()
    assert svc._state == "idle"
    assert svc._current is None


# =====================================================================
# 2) PERSISTENCE: save_measurement / IDs / context
# =====================================================================

def test_save_measurement_slope():
    svc = create_basic_service()
    result = {"type": "slope", "slope": 0.5, "dx": 2.0, "dy": 1.0, "dist": 2.236}
    meas_id = svc._save_measurement(result, (1.0, 1.0), (3.0, 2.0))
    assert meas_id == "slope-001"
    svc.ds_set.assert_called_once()
    saved_list = svc.ds_set.call_args[0][1]
    assert len(saved_list) == 1
    assert saved_list[0]["id"] == "slope-001"
    assert saved_list[0]["type"] == "slope"
    assert saved_list[0]["slope"] == 0.5
    assert saved_list[0]["p1"] == (1.0, 1.0)
    assert saved_list[0]["p2"] == (3.0, 2.0)


def test_save_measurement_increments_id_correctly():
    svc = create_basic_service()
    svc.ds_get.return_value = [
        {"id": "slope-001", "type": "slope"},
        {"id": "slope-002", "type": "slope"},
    ]
    result = {"type": "slope", "slope": 1.0}
    meas_id = svc._save_measurement(result, (0, 0), (1, 1))
    assert meas_id == "slope-003"


def test_save_measurement_includes_context():
    svc = create_basic_service()
    svc.set_context(
        view_id="trials", trial_id=5, channel_name="CA1", plugin="trials", domain="time"
    )
    result = {"type": "slope", "slope": 1.5}
    svc._save_measurement(result, (1, 2), (3, 4))
    saved_list = svc.ds_set.call_args[0][1]
    ctx = saved_list[0]["ctx"]
    assert ctx["view_id"] == "trials"
    assert ctx["trial_id"] == 5
    assert ctx["channel_name"] == "CA1"
    assert ctx["plugin"] == "trials"
    assert ctx["domain"] == "time"


def test_save_measurement_override_context():
    svc = create_basic_service()
    svc.set_context(trial_id=5)
    override = {"trial_id": 10, "channel_name": "Fp1"}
    result = {"type": "slope", "slope": 1.0}
    svc._save_measurement(result, (0, 0), (1, 1), override_ctx=override)
    saved_list = svc.ds_set.call_args[0][1]
    assert saved_list[0]["ctx"]["trial_id"] == 10
    assert saved_list[0]["ctx"]["channel_name"] == "Fp1"



def test_measurement_id_sequence_beyond_999():
    svc = create_basic_service()
    svc.ds_get.return_value = [{"id": f"slope-{i:03d}", "type": "slope"} for i in range(1, 1000)]
    meas_id = svc._save_measurement({"type": "slope", "slope": 1.0}, (0, 0), (1, 1))
    assert meas_id == "slope-1000"



# =====================================================================
# 4) TRIALS: slopes by trial and helpers
# =====================================================================

@patch("core.services.measurement_service.two_point_metrics")
def test_compute_slopes_each_trial_basic(mock_metrics):
    # Return different slopes to distinguish calls
    mock_metrics.side_effect = [
        {"type": "slope", "slope": 0.5},  # for trial_1
        {"type": "slope", "slope": 0.7},  # for trial_2
    ]

    svc = create_basic_service()
    svc.set_context(view_id="trials", plugin="trials", domain="time", trial_id=1)

    # x + trial_1 + trial_2 (3 samples)
    x_vals  = [0.0, 1.0, 2.0]
    t1_vals = [1.0, 1.5, 2.0]
    t2_vals = [2.0, 3.0, 4.0]

    x_arr = Mock()
    x_arr.GetName.return_value = "time"
    x_arr.GetNumberOfValues.return_value = len(x_vals)
    x_arr.GetValue.side_effect = lambda i: x_vals[i]

    t1_arr = Mock()
    t1_arr.GetName.return_value = "trial_1"
    t1_arr.GetNumberOfValues.return_value = len(t1_vals)
    t1_arr.GetValue.side_effect = lambda i: t1_vals[i]

    t2_arr = Mock()
    t2_arr.GetName.return_value = "trial_2"
    t2_arr.GetNumberOfValues.return_value = len(t2_vals)
    t2_arr.GetValue.side_effect = lambda i: t2_vals[i]

    table = Mock()
    table.GetNumberOfColumns.return_value = 3
    table.GetNumberOfRows.return_value = 3
    table.GetColumn.side_effect = lambda i: [x_arr, t1_arr, t2_arr][i]
    table.GetColumnByName.return_value = x_arr

    plot = Mock(); plot.GetInput.return_value = table
    chart = Mock(); chart.GetNumberOfPlots.return_value = 1; chart.GetPlot.return_value = plot
    svc.get_active_chart.return_value = chart

    with patch.object(svc, "_save_measurement", side_effect=["slope-001", "slope-002"]) as mock_save, \
         patch.object(svc, "_add_overlay_for_points") as mock_overlay:

        ids = svc._compute_and_save_slopes_each_trial_by_index(
            0, 2, make_overlays_for_current=True
        )

    # IDs collected for both trials
    assert ids == ["slope-001", "slope-002"]

    # two_point_metrics called with exact (t,y) pairs and kind
    assert mock_metrics.call_count == 2
    (a1, a2), kw1 = mock_metrics.call_args_list[0]
    (b1, b2), kw2 = mock_metrics.call_args_list[1]
    assert a1 == (0.0, t1_vals[0]) and a2 == (2.0, t1_vals[2]) and kw1["kind"] == "slope"
    assert b1 == (0.0, t2_vals[0]) and b2 == (2.0, t2_vals[2]) and kw2["kind"] == "slope"

    # _save_measurement called with correct enriched results and endpoints
    assert mock_save.call_count == 2

    # First call (trial_1)
    save_args1, save_kwargs1 = mock_save.call_args_list[0]
    res1, p1_1, p2_1 = save_args1  # (result_dict, (t1,y1), (t2,y2))
    assert res1["type"] == "slope"
    assert res1["slope"] == 0.5
    assert res1["trial_name"] == "trial_1"
    assert p1_1 == (0.0, t1_vals[0])
    assert p2_1 == (2.0, t1_vals[2])
    assert save_kwargs1["override_ctx"]["trial_id"] == 0  # "trial_1" -> 0-based

    # Second call (trial_2)
    save_args2, save_kwargs2 = mock_save.call_args_list[1]
    res2, p1_2, p2_2 = save_args2
    assert res2["type"] == "slope"
    assert res2["slope"] == 0.7
    assert res2["trial_name"] == "trial_2"
    assert p1_2 == (0.0, t2_vals[0])
    assert p2_2 == (2.0, t2_vals[2])
    assert save_kwargs2["override_ctx"]["trial_id"] == 1  # "trial_2" -> 0-based

    # Overlays only for current trial_id=1 -> only for trial_2
    assert mock_overlay.call_count == 1
    ov_args, _ = mock_overlay.call_args
    assert ov_args[0] == "slope-002"
    assert ov_args[1] == (0.0, t2_vals[0])
    assert ov_args[2] == (2.0, t2_vals[2])



def test_compute_slopes_each_trial_no_chart():
    svc = create_basic_service()
    svc.get_active_chart.return_value = None
    ids = svc._compute_and_save_slopes_each_trial_by_index(0, 10)
    assert ids == []


def test_compute_slopes_each_trial_same_index():
    svc = create_basic_service()

    x_arr = Mock(); x_arr.GetValue.side_effect = [1.0, 1.0]
    table = Mock(); table.GetNumberOfColumns.return_value = 1
    table.GetColumn.return_value = x_arr
    table.GetColumnByName.return_value = x_arr

    plot = Mock(); plot.GetInput.return_value = table
    chart = Mock(); chart.GetNumberOfPlots.return_value = 1; chart.GetPlot.return_value = plot
    svc.get_active_chart.return_value = chart

    ids = svc._compute_and_save_slopes_each_trial_by_index(0, 0)
    assert ids == []


# =====================================================================
# 5) REMOVAL: last / by id / clear / out-of-sync
# =====================================================================

def test_remove_last_measurement_success():
    svc = create_basic_service()
    svc._overlays = [{"id": "slope-001", "chart": Mock()},
                     {"id": "slope-002", "chart": Mock()}]
    svc.ds_get.return_value = [{"id": "slope-001"}, {"id": "slope-002"}]
    result = svc.remove_last_measurement()
    assert result is True
    assert len(svc._overlays) == 1
    saved_list = svc.ds_set.call_args[0][1]
    assert len(saved_list) == 1
    assert saved_list[0]["id"] == "slope-001"


def test_remove_last_measurement_empty():
    svc = create_basic_service()
    svc._overlays = []
    result = svc.remove_last_measurement()
    assert result is False
    svc.ds_set.assert_not_called()

def test_clear_all_measurements():
    svc = create_basic_service()
    svc._overlays = [{"id": "slope-001", "chart": Mock()},
                     {"id": "slope-002", "chart": Mock()},
                     {"id": "amplitude-001", "chart": Mock()}]
    result = svc.clear_all_measurements()
    assert result is True
    assert len(svc._overlays) == 0
    svc.ds_set.assert_called_once_with("measurements", [])




# =====================================================================
# 6) HELPERS: nearest index + extremes + math edge cases
# =====================================================================

def test_nearest_index_exact_match():
    svc = create_service_with_data()
    idx = svc._nearest_index(3.0)
    assert idx == 3
    assert svc._ref_data["xs"][idx] == 3.0


def test_nearest_index_between_values():
    svc = create_service_with_data()
    idx = svc._nearest_index(1.3)
    assert idx == 1

def test_nearest_index_no_ref_data():
    svc = create_basic_service()
    svc._ref_data = None
    assert svc._nearest_index(2.5) is None

def test_nearest_index_with_duplicates():
    svc = create_basic_service()
    svc._ref_data = {"xs": [0.0, 1.0, 1.0, 2.0, 3.0], "ys": [0.0, 1.0, 1.5, 2.0, 3.0]}
    idx = svc._nearest_index(1.0)
    assert idx in [1, 2]
    assert svc._ref_data["xs"][idx] == 1.0


# =====================================================================
# 7) CONTEXT + CLEAR/CLEANUP INTEGRATION
# =====================================================================


def test_cancel_cleans_up_all_internal_state():
    svc = create_basic_service()
    svc._state = "waiting_p2"
    svc._current = {"type": "slope", "p1": (1, 2), "p2": None}
    svc._down_pos = (100, 200)
    svc._ref_axes = {"x": Mock(), "y": Mock()}
    svc._saved_ranges = {"x": (0, 10), "y": (0, 5)}
    svc._ref_data = {"xs": [1], "ys": [2]}
    svc._saved_actions = {1: 2}
    svc.cancel()
    assert svc._state == "idle"
    assert svc._current is None
    assert svc._down_pos is None
    assert svc._ref_axes is None
    assert svc._saved_ranges is None
    assert svc._ref_data is None


def test_clear_all_preserves_context():
    svc = create_basic_service()
    svc.set_context(view_id="trials", trial_id=5)
    svc._overlays = [{"id": "test", "chart": Mock()}]
    svc.clear_all_measurements()
    assert svc._context["view_id"] == "trials"
    assert svc._context["trial_id"] == 5


# =====================================================================
# 8) INTEGRATION mini-workflows
# =====================================================================

@patch("core.services.measurement_service.two_point_metrics")
def test_complete_slope_workflow(mock_metrics):
    mock_metrics.return_value = {"type": "slope", "slope": 1.5, "dx": 2.0, "dy": 3.0, "dist": 3.606}
    svc = create_basic_service()
    svc.get_active_chart.return_value = Mock()
    svc.start("slope")
    assert svc.state == "waiting_p1"
    svc._current["p1"] = (1.0, 2.0)
    svc._current["p2"] = (3.0, 5.0)
    svc._finalize()
    assert svc.state == "idle"
    assert svc._current is None
    saved_list = svc.ds_set.call_args[0][1]
    assert len(saved_list) == 1
    assert saved_list[0]["type"] == "slope"
    assert saved_list[0]["slope"] == 1.5
    assert saved_list[0]["id"] == "slope-001"


@patch("core.services.measurement_service.amplitude_in_window")
def test_complete_amplitude_workflow(mock_amplitude):
    mock_amplitude.return_value = {
        "type": "amplitude",
        "amp_pp": 4.5,
        "y_max": 3.0,
        "y_min": -1.5,
        "x_at_max": 2.5,
        "x_at_min": 4.0,
    }
    svc = create_service_with_data()
    svc.get_active_chart.return_value = Mock()
    svc.start("amplitude")
    assert svc.state == "waiting_p1"
    svc._current["p1"] = (1.0, 0.0)
    svc._current["p2"] = (5.0, 0.0)
    svc._finalize()
    assert svc.state == "idle"
    saved_list = svc.ds_set.call_args[0][1]
    assert len(saved_list) == 1
    assert saved_list[0]["type"] == "amplitude"
    assert saved_list[0]["amp_pp"] == 4.5
    assert saved_list[0]["y_max"] == 3.0
    assert saved_list[0]["y_min"] == -1.5


def test_multiple_measurements_workflow():
    svc = create_basic_service()
    svc.get_active_chart.return_value = Mock()
    with patch("core.services.measurement_service.two_point_metrics") as mock_metrics:
        mock_metrics.return_value = {"type": "slope", "slope": 1.0}
        svc.start("slope"); svc._current["p1"] = (0, 0); svc._current["p2"] = (1, 1); svc._finalize()
        svc.start("slope"); svc._current["p1"] = (2, 2); svc._current["p2"] = (3, 3); svc._finalize()
        assert svc.ds_set.call_count == 2

