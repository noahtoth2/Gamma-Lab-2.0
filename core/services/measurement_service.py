from datetime import datetime
import vtk
import bisect

from core.filters.measurements import amplitude_in_window, two_point_metrics
from core.utils.plugin_alerts import PluginAlerts


class MeasurementService:
    """
    2-point measurements with per-trial persistence and rebuildable overlays.
    - Persist p1/p2 in data coordinates + context (view_id, trial_id, channel_name).
    - When navigating: set_context(...) + rebuild_overlays_for_current_context().
    - Overlays: dashed line + points; show/hide without recreating when possible.
    """

    def __init__(self, parent, vtk_widget, get_active_chart, datastore_get, datastore_set,
                 pick_radius_px=10, debug=True):
        self.alerts = PluginAlerts()
        self.alerts.parent = parent
        self.parent = parent
        self.vtk_widget = vtk_widget
        self.get_active_chart = get_active_chart
        self.ds_get = datastore_get
        self.ds_set = datastore_set

        self._debug = False
        self._PICK_RADIUS_PX = pick_radius_px

        # ---- interaction state ----
        self._state = 'idle'
        self._current = None        # {'type','p1','p2'}
        self._down_pos = None

        # ---- axes/ranges (frozen when choosing P1) ----
        self._ref_axes = None       # {'x': axis, 'y': axis}
        self._saved_ranges = None   # {'x': (min,max), 'y': (min,max)}
        self._invert_y = False

        # ---- data for snapping ----
        self._ref_data = None       # {'xs': [...], 'ys': [...]}

        # ---- left-button actions (temporary suspension) ----
        self._saved_actions = {}

        # ---- currently visible overlays ----
        self._overlay_enabled = True
        # each item: {'id','chart','table','line_plot','points_plot'}
        self._overlays = []

        # ---- current context (for filtering/repainting) ----
        self._context = {
            "view_id": None,      # e.g., "trials", "erp", "fft", "psd", "average", "loader"
            "graph_id": None,     # XY chart UID (if several in the view)
            "trial_id": None,     # int or None
            "channel_name": None, # "CA1", "Fp1", ...
            "plugin": None,       # "trials", "erp", "fft", "psd", "open_signal", ...
            "domain": None,       # "time" | "frequency" | "other"
        }

        # line color palette
        self._palette = [
            (30, 144, 255), (220, 20, 60), (50, 205, 50), (255, 140, 0),
            (148, 0, 211), (0, 191, 255), (255, 99, 71), (0, 128, 128),
        ]
        self._palette_i = 0

    # ====================== Context & navigation ======================

    def set_context(self, *, view_id=None, graph_id=None, trial_id=None, channel_name=None, plugin=None, domain=None):
        if view_id is not None:      self._context["view_id"] = view_id
        if graph_id is not None:     self._context["graph_id"] = graph_id
        if trial_id is not None:     self._context["trial_id"] = trial_id
        if channel_name is not None: self._context["channel_name"] = channel_name
        if plugin is not None:       self._context["plugin"] = plugin
        if domain is not None:       self._context["domain"] = domain

    def _context_matches(self, curr, other) -> bool:
        for key in ("view_id", "graph_id", "trial_id", "channel_name", "plugin", "domain"):
            a = curr.get(key); b = other.get(key)
            if a is None or b is None:    # compare only if both have it
                continue
            if a != b:
                return False
        return True
    
    def clear_visual_overlays(self):
        """
        Clear ONLY visuals (overlays), without touching the datastore.
        Useful before switching trials.
        """
        while self._overlays:
            ov = self._overlays.pop()
            self._detach_overlay(ov)
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

    def rebuild_overlays_for_current_context(self):
        """
        Rebuild overlays for ALL measurements whose ctx metadata matches
        the current context.
        """
        # clear current visuals
        self.clear_visual_overlays()

        ctx = self._context.copy()
        lst = self.ds_get("measurements", None) or []
        for m in lst:
            mctx = m.get("ctx") or {}
            if self._context_matches(ctx, mctx):
                try:
                    p1 = m.get("p1"); p2 = m.get("p2"); mid = m.get("id")
                    self._add_overlay_for_points(mid, p1, p2, axes_snapshot=None)
                except Exception:
                    pass

    # ====================== Public API (measurement) ======================

    def _dbg(self, *a):
        if self._debug:
            try:
                print("[MEAS]", *a)
            except Exception:
                pass
        
    @property
    def state(self):
        return self._state

    def start(self, measure_type: str):
        allowed = {"slope", "slope_all_trials", "amplitude"}
        if measure_type not in allowed:
            measure_type = "slope"
        
        if measure_type == "slope_all_trials" and self._context.get("plugin") != "trials":
            try:
                self.alerts.info("This measurement is only available in the Trials plugin.")
            except Exception:
                pass
            return False
    
        if self._state != 'idle':
            try:
                self.alerts.info("A measurement is already in progress. Complete it or cancel (Esc).")
            except Exception:
                pass
            return False
        
        self._state = 'waiting_p1'
        self._current = {'type': measure_type, 'p1': None, 'p2': None}
        self.alerts.info("Select the FIRST point with left click.")

    def cancel(self):
        self._state = 'idle'
        self._current = None
        self._ref_axes = None
        self._saved_ranges = None
        self._ref_data = None
        self._down_pos = None
        self._suspend_left_actions(False)
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

    def on_left_press(self, sx, sy):
        if self._state != 'idle':
            self._down_pos = (sx, sy)

    def on_left_release(self, sx, sy, click_eps=8):
        if self._state == 'idle':
            return

        # click vs drag
        if self._down_pos is not None:
            dx = abs(sx - self._down_pos[0]); dy = abs(sy - self._down_pos[1])
            self._down_pos = None
            if dx > click_eps or dy > click_eps:
                return

        ch = self.get_active_chart()
        if not ch:
            self.alerts.warning("There is no active chart.")
            self.cancel(); return

        if self._state == 'waiting_p1':
            
            self._ref_axes = {'x': ch.GetAxis(vtk.vtkAxis.BOTTOM),
                            'y': ch.GetAxis(vtk.vtkAxis.LEFT)}
            self._save_axes_ranges()
            self._load_reference_data_for_pick(ch)

            # --- DEBUG ---
            rect = self._plot_rect_pixels()
            self._dbg("waiting_p1:",
                    "rect=", rect,
                    "ranges=", self._saved_ranges,
                    "xs_len=", (len(self._ref_data['xs']) if self._ref_data else 0))

            if not self._ref_data or not self._ref_data.get('xs'):
                self.alerts.warning("There is no series data to select points.")
                self.cancel(); return

        picked = self._pick_nearest_data_point(sx, sy)
        if picked is None:
            self.alerts.warning(f"No nearby point (≤ {self._PICK_RADIUS_PX}px). Try again.")
            return

        if self._state == 'waiting_p1':
            self._current['p1'] = picked
            self._state = 'waiting_p2'
            self._suspend_left_actions(True)
            self.alerts.info("Now select the SECOND point with left click.")
            return

        if self._state == 'waiting_p2':
            curr = self._get_current_ranges()
            if curr is not None:
                self._saved_ranges = curr
                self._dbg("waiting_p2: ranges REFRESHED ->", self._saved_ranges)

            self._current['p2'] = picked
            self._suspend_left_actions(False)
            self._finalize()
            return

    # ====================== axes/ranges & transforms ======================

    def _get_current_ranges(self):
        """Always read current chart ranges (after zoom/pan)."""
        ch = self.get_active_chart()
        if not ch:
            return None
        try:
            ax_x = ch.GetAxis(vtk.vtkAxis.BOTTOM)
            ax_y = ch.GetAxis(vtk.vtkAxis.LEFT)
            return {
                'x': (ax_x.GetMinimum(), ax_x.GetMaximum()),
                'y': (ax_y.GetMinimum(), ax_y.GetMaximum()),
            }
        except Exception:
            return None


    def _vec2_to_xy(self, v):
        if isinstance(v, (tuple, list)) and len(v) == 2:
            return float(v[0]), float(v[1])
        if hasattr(v, "GetX") and hasattr(v, "GetY"):
            return float(v.GetX()), float(v.GetY())
        if hasattr(v, "x") and hasattr(v, "y"):
            return float(v.x), float(v.y)
        return None, None

    def _save_axes_ranges(self):
        ch = self.get_active_chart()
        if not ch: return
        ax_x = self._ref_axes['x'] if self._ref_axes else ch.GetAxis(0)
        ax_y = self._ref_axes['y'] if self._ref_axes else ch.GetAxis(1)
        self._saved_ranges = {
            'x': (ax_x.GetMinimum(), ax_x.GetMaximum()),
            'y': (ax_y.GetMinimum(), ax_y.GetMaximum())
        }

    def _plot_rect_pixels(self):
        ch = self.get_active_chart()
        if not ch: return None
        try:
            p1 = ch.GetPoint1(); p2 = ch.GetPoint2()
        except Exception:
            return None
        x1, y1 = self._vec2_to_xy(p1)
        x2, y2 = self._vec2_to_xy(p2)
        if x1 is None or x2 is None or y1 is None or y2 is None:
            return None
        return x1, x2, y1, y2

    def _plot_to_screen(self, x_val, y_val):
        rect = self._plot_rect_pixels()
        if rect is None:
            return None
        x_min_px, x_max_px, y_min_px, y_max_px = rect

        # Prefer live chart ranges; use saved as fallback
        rng = self._get_current_ranges() or self._saved_ranges
        if rng is None:
            return None

        x_min, x_max = rng['x']
        y_min, y_max = rng['y']

        dxp = (x_max_px - x_min_px)
        dyp = (y_max_px - y_min_px)
        if dxp <= 0 or dyp <= 0 or (x_max - x_min) == 0 or (y_max - y_min) == 0:
            return None

        sx = x_min_px + (x_val - x_min) * dxp / (x_max - x_min)
        if not self._invert_y:
            sy = y_min_px + (y_val - y_min) * dyp / (y_max - y_min)
        else:
            sy = y_min_px + (y_max - y_val) * dyp / (y_max - y_min)
        return float(sx), float(sy)


    def _screen_to_plot(self, sx, sy):
        ch = self.get_active_chart()
        if not ch:
            return None

        rect = self._plot_rect_pixels()
        if rect is None:
            return None
        x_min_px, x_max_px, y_min_px, y_max_px = rect

        if sx < x_min_px or sx > x_max_px or sy < y_min_px or sy > y_max_px:
            return None

        # Prefer live chart ranges; use saved as fallback
        rng = self._get_current_ranges() or self._saved_ranges
        if rng is None:
            return None

        x_min, x_max = rng['x']
        y_min, y_max = rng['y']

        dxp = (x_max_px - x_min_px)
        dyp = (y_max_px - y_min_px)
        if dxp <= 0 or dyp <= 0 or (x_max - x_min) == 0 or (y_max - y_min) == 0:
            return None

        x_val = x_min + (sx - x_min_px) * (x_max - x_min) / dxp
        if not self._invert_y:
            y_val = y_min + (sy - y_min_px) * (y_max - y_min) / dyp
        else:
            y_val = y_min + (y_max - sy) * (y_max - y_min) / dyp
        return float(x_val), float(y_val)

    # ====================== data for snapping ======================

    def _load_reference_data_for_pick(self, chart):
        print("\n[MEAS][_load_reference_data_for_pick] >>>")

        # 1) Reference plot
        ref_plot = None
        try:
            n = chart.GetNumberOfPlots()
        except Exception:
            self._ref_data = None
            return

        for i in range(n):
            pl = chart.GetPlot(i)
            if pl is not None:
                ref_plot = pl
                break
        if ref_plot is None:
            self._ref_data = None
            return

        # 2) Table
        try:
            table = ref_plot.GetInput()
        except Exception:
            table = None
        if table is None:
            self._ref_data = None
            return

        # Utilities
        def _col_by_name(tbl, name: str):
            if not name:
                return None
            try:
                return tbl.GetColumnByName(name)
            except Exception:
                return None

        # Columns dump (debug)
        try:
            ncols = table.GetNumberOfColumns()
        except Exception:
            ncols = 0
        cols = []
        for c in range(ncols):
            try:
                arr = table.GetColumn(c)
                cols.append(arr.GetName() if arr else f"col{c}")
            except Exception:
                cols.append(f"col{c}?")
        print(f"[MEAS] columns={cols}")

        # Plot label & context
        try:
            lbl = ref_plot.GetLabel() or ""
        except Exception:
            lbl = ""
        ctx = self._context or {}
        ctx_tid = ctx.get("trial_id", None)
        print(f"[MEAS] ctx.trial_id={ctx_tid}  plot.label='{lbl}'")

        # 3) X selection: common time names, else column 0
        x_candidates = ["time", "Time (s)", "Time", "t", "x"]
        x_arr = None
        x_src = None
        for nm in x_candidates:
            x_arr = _col_by_name(table, nm)
            if x_arr is not None:
                x_src = nm
                break
        if x_arr is None:
            if ncols >= 1:
                try:
                    x_arr = table.GetColumn(0)
                    x_src = "col0"
                except Exception as e:
                    print(f"[MEAS] ERROR: no X column found: {e}")
                    self._ref_data = None
                    return
            else:
                print("[MEAS] ERROR: table has no columns.")
                self._ref_data = None
                return
        print(f"[MEAS] X picked -> name='{x_arr.GetName() if hasattr(x_arr,'GetName') else '?'}' src={x_src}")

        # 4) Y selection
        y_arr = None
        y_reason = None

        # (A) Trials path: use trial_{tid+1} when trial_id is provided
        if ctx_tid is not None and isinstance(ctx_tid, int) and ctx_tid >= 0:
            guess = f"trial_{ctx_tid+1}"
            try:
                arr = table.GetColumnByName(guess)
                if arr is not None:
                    y_arr = arr
                    y_reason = f"context:{guess}"
            except Exception:
                pass
            print(f"[MEAS] Y(A) context guess -> {y_reason or 'no-match'}")

        # (B) Non-trials (or if (A) failed): pick **second column** (index 1)
        if y_arr is None:
            if ncols < 2:
                print("[MEAS] ERROR: expected at least 2 columns (time + series).")
                self._ref_data = None
                return
            try:
                y_arr = table.GetColumn(1)
                y_reason = "second-column"
            except Exception as e:
                print(f"[MEAS] ERROR: could not read second column: {e}")
                self._ref_data = None
                return
        print(f"[MEAS] Y picked -> name='{y_arr.GetName() if hasattr(y_arr,'GetName') else '?'}' reason={y_reason}")

        # 5) Build ref_data using min length
        try:
            nrows = min(x_arr.GetNumberOfTuples(), y_arr.GetNumberOfTuples())
        except Exception as e:
            print(f"[MEAS] ERROR get tuples: {e}")
            self._ref_data = None
            return
        print(f"[MEAS] tuples -> X={x_arr.GetNumberOfTuples()} Y={y_arr.GetNumberOfTuples()}  used={nrows}")

        xs, ys = [], []
        for i in range(nrows):
            try:
                xs.append(float(x_arr.GetValue(i)))
                ys.append(float(y_arr.GetValue(i)))
            except Exception:
                # skip non-convertible rows
                continue

        # Sort by X and minimally de-duplicate
        pairs = sorted(zip(xs, ys), key=lambda t: t[0])
        xs2, ys2, last = [], [], None
        for x, y in pairs:
            if last is not None and x <= last:
                x = last + 1e-12
            xs2.append(x); ys2.append(y); last = x

        self._ref_data = {'xs': xs2, 'ys': ys2}
        print(f"[MEAS] ref_data: xs={len(xs2)} ys={len(ys2)}")
        if xs2 and ys2:
            print(f"[MEAS] ref_data head: {list(zip(xs2[:3], ys2[:3]))}")
            print(f"[MEAS] ref_data tail: {list(zip(xs2[-3:], ys2[-3:]))}")
        print("[MEAS][_load_reference_data_for_pick] <<<\n")


    def _pick_nearest_data_point(self, sx_click, sy_click):
        if not self._ref_data or not self._ref_data.get('xs'):
            self._dbg("pick: missing ref_data")  # DEBUG
            return None

        rect = self._plot_rect_pixels()
        if rect is None:
            self._dbg("pick: rect=None")  # DEBUG
            return None
        x_min_px, x_max_px, y_min_px, y_max_px = rect
        if not (x_min_px <= sx_click <= x_max_px and y_min_px <= sy_click <= y_max_px):
            self._dbg(f"pick: click outside rect {sx_click,sy_click} vs {rect}")  # DEBUG
            return None

        guess = self._screen_to_plot(sx_click, sy_click)
        if guess is None:
            self._dbg("pick: screen_to_plot=None")  # DEBUG
            return None
        xg, yg = guess
        self._dbg(f"pick: guess plot=({xg:.6f},{yg:.6f})")  # DEBUG

        xs = self._ref_data['xs']; ys = self._ref_data['ys']
        import bisect
        i = bisect.bisect_left(xs, xg)
        cand_idx = [max(0, i-2), max(0, i-1), min(len(xs)-1, i), min(len(xs)-1, i+1)]
        seen=set(); cand_idx=[c for c in cand_idx if not (c in seen or seen.add(c))]
        self._dbg("pick: cand_idx=", cand_idx)  # DEBUG

        best = None; best_d2 = None
        for idx in cand_idx:
            sp = self._plot_to_screen(xs[idx], ys[idx])
            if sp is None:
                self._dbg(f"pick: idx={idx} sp=None")  # DEBUG
                continue
            sx, sy = sp
            d2 = (sx - sx_click)**2 + (sy - sy_click)**2
            self._dbg(f"pick: idx={idx} data=({xs[idx]:.6f},{ys[idx]:.6f}) -> screen=({sx:.1f},{sy:.1f}) d2={d2:.1f}")  # DEBUG
            if best_d2 is None or d2 < best_d2:
                best_d2 = d2; best = (xs[idx], ys[idx])

        thr = self._PICK_RADIUS_PX * self._PICK_RADIUS_PX
        self._dbg(f"pick: best_d2={best_d2} thr={thr}")  # DEBUG
        if best is not None and best_d2 <= thr:
            return best
        return None


    # ====================== persistence ======================

    def _save_measurement(self, result, p1, p2, override_ctx=None):
        t = str(result.get("type", "measure"))
        lst = self.ds_get("measurements", None)
        if not isinstance(lst, list):
            lst = []

        prefix, seq = f"{t}-", 0
        for it in lst:
            if isinstance(it, dict) and it.get("type") == t:
                mid = str(it.get("id", ""))
                if mid.startswith(prefix):
                    try:
                        n = int(mid[len(prefix):]); seq = max(seq, n)
                    except Exception:
                        pass
        seq += 1
        meas_id = f"{t}-{seq:03d}"

        ctx = {
            "view_id": self._context.get("view_id"),
            "graph_id": self._context.get("graph_id"),
            "trial_id": self._context.get("trial_id"),
            "channel_name": self._context.get("channel_name"),
            "plugin": self._context.get("plugin"),
            "domain": self._context.get("domain"),
        }
        if isinstance(override_ctx, dict):
            ctx.update({k: v for k, v in override_ctx.items() if v is not None})

        p1x, p1y = float(p1[0]), float(p1[1])
        p2x, p2y = float(p2[0]), float(p2[1])
        base = {
            "id": meas_id,
            "type": t,
            "p1": (p1x, p1y),
            "p2": (p2x, p2y),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ctx": ctx,
        }

        dx = p2x - p1x
        dy = p2y - p1y
        rec = {**base, **{k: v for k, v in (result or {}).items() if k != "type"}}

        if t == "slope":
            rec.setdefault("dx", float(dx))
            rec.setdefault("dy", float(dy))
            if "slope" not in rec:
                rec["slope"] = float(dy / dx) if dx != 0 else float("inf")
            if "dist" not in rec:
                rec["dist"] = float((dx*dx + dy*dy) ** 0.5)

        lst.append(rec)
        self.ds_set("measurements", lst)
        return meas_id



    # ====================== measurement finalization ======================

    def _finalize(self):
        cur = self._current or {}
        if not (cur.get('p1') and cur.get('p2')):
            self.cancel(); return

        x1, y1 = cur['p1']; 
        x2, y2 = cur['p2']
        kind = cur.get('type', 'slope')

        if kind == 'slope':
            result = two_point_metrics((x1, y1), (x2, y2), kind='slope')
            meas_id = self._save_measurement(result, (x1, y1), (x2, y2))
            try:
                self._add_overlay_for_points(meas_id, (x1, y1), (x2, y2))
            except Exception:
                pass
            try:
                self.alerts.info(
                    f"Result '{result['type']}' saved (ID: {meas_id}).\n Slope = {result['slope']:.6f}\n\nFor more information go to 'Measure / Slope'."
                )
            except Exception:
                pass
            
            self._state = 'idle'
            self._current = None

        elif kind == 'amplitude':
            result = self._compute_amplitude_window(x1, x2)
            if not result:
                try:
                    self.alerts.info("The amplitude could not be calculated in the selected window.", "Amplitude")
                except Exception:
                    pass
                self._state = 'idle'
                self._current = None
                return

            # Save measurement with amplitude fields
            meas_id = self._save_measurement(result, (x1, y1), (x2, y2))

            # Simple overlay: draw a line between (x1,y1) and (x2,y2) to mark window
            try:
                self._add_overlay_for_points(meas_id, (x1, y1), (x2, y2))
            except Exception:
                pass

            try:
                self.alerts.info(
                    (f"Peak-to-peak amplitude = {result['amp_pp']:.6f}\n"
                     f"Ymax={result['y_max']:.6f} @ x={result['x_at_max']:.6f}\n"
                     f"Ymin={result['y_min']:.6f} @ x={result['x_at_min']:.6f}\n"
                     f"ID: {meas_id}"),
                    "Saved amplitude"
                )
            except Exception:
                pass
            self._state = 'idle'
            self._current = None
        
        elif kind == 'slope_all_trials':
            if not self._ref_data or not self._ref_data.get('xs'):
                ch = self.get_active_chart()
                if not ch:
                    self.cancel(); return
                self._load_reference_data_for_pick(ch)
                if not self._ref_data or not self._ref_data.get('xs'):
                    try:
                        self.alerts.info("No data to estimate X indices.")
                    except Exception:
                        pass
                    self.cancel(); return

            i1 = self._nearest_index(x1)
            i2 = self._nearest_index(x2)
            if i1 is None or i2 is None:
                try:
                    self.alerts.info("Could not determine the indices of the points.")
                except Exception:
                    pass
                self.cancel(); return

            if i1 == i2:
                try:
                    self.alerts.info("Both points fall at the same index; dx=0.")
                except Exception:
                    pass
                # seguimos adelante para que no deje rastro de estado
                self.cancel(); return

            ids = self._compute_and_save_slopes_each_trial_by_index(
                min(i1, i2), max(i1, i2),
                make_overlays_for_current=False  # pon True si quieres overlay solo del trial visible
            )

            try:
                self.alerts.info(f"Generated {len(ids)} measurements (one per trial).", "Slopes per trial")
            except Exception:
                pass

            self._state = 'idle'
            self._current = None

        else:
            # unsupported type (in case of leftover 'derivative')
            try:
                self.alerts.info(f"Unsupported measurement type: {kind}", "Measurement")
            except Exception:
                pass


    # ====================== left-button blocking ======================

    def _suspend_left_actions(self, suspend: bool):
        ch = self.get_active_chart()
        if not ch: return
        maybe = []
        for name in ("PAN", "ZOOM", "SELECT", "ZOOM_RECT", "ZOOM_BOX"):
            if hasattr(vtk.vtkChart, name):
                maybe.append(getattr(vtk.vtkChart, name))
        if suspend:
            self._saved_actions = {}
            for act in maybe:
                try:
                    btn = ch.GetActionToButton(act)
                    self._saved_actions[act] = btn
                    if btn == 1:
                        ch.SetActionToButton(act, -1)
                except Exception:
                    pass
        else:
            for act, btn in self._saved_actions.items():
                try:
                    ch.SetActionToButton(act, btn)
                except Exception:
                    pass
            self._saved_actions = {}

    # ====================== OVERLAYS ======================

    def _vtk_has_set_visible(self, plot) -> bool:
        return hasattr(plot, "SetVisible")

    def _set_plot_visible(self, chart, plot, visible: bool):
        if plot is None:
            return
        if self._vtk_has_set_visible(plot):
            try:
                plot.SetVisible(bool(visible)); return
            except Exception:
                pass
        # fallback
        if visible:
            try: chart.AddPlotInstance(plot)
            except Exception: pass
        else:
            try: chart.RemovePlotInstance(plot)
            except Exception: pass

    def set_overlay_visible(self, visible: bool):
        self._overlay_enabled = bool(visible)
        for ov in self._overlays:
            ch = ov.get("chart")
            if not ch: continue
            self._set_plot_visible(ch, ov.get("line_plot"), visible)
            self._set_plot_visible(ch, ov.get("points_plot"), visible)
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

    def toggle_overlay(self):
        self.set_overlay_visible(not self._overlay_enabled)

    def _next_color(self):
        c = self._palette[self._palette_i % len(self._palette)]
        self._palette_i += 1
        return c

    def _make_table_2pts(self, p1, p2):
        tbl = vtk.vtkTable()
        ax = vtk.vtkFloatArray(); ax.SetName("X")
        ay = vtk.vtkFloatArray(); ay.SetName("Y")
        tbl.AddColumn(ax); tbl.AddColumn(ay)
        tbl.InsertNextBlankRow(); tbl.SetValue(0, 0, float(p1[0])); tbl.SetValue(0, 1, float(p1[1]))
        tbl.InsertNextBlankRow(); tbl.SetValue(1, 0, float(p2[0])); tbl.SetValue(1, 1, float(p2[1]))
        return tbl

    def _add_overlay_for_points(self, meas_id: str, p1, p2, axes_snapshot=None):
        ch = self.get_active_chart()
        if not ch: return
        tbl = self._make_table_2pts(p1, p2)

        # dashed line
        line_plot = ch.AddPlot(vtk.vtkChart.LINE)
        try:
            pen = line_plot.GetPen()
            pen.SetWidth(2)
            pen.SetLineType(vtk.vtkPen.DASH_LINE)
            r, g, b = self._next_color(); pen.SetColor(r, g, b)
        except Exception:
            pass
        line_plot.SetInputData(tbl, 0, 1)
        line_plot.SetUseIndexForXSeries(False)

        # points
        points_plot = ch.AddPlot(vtk.vtkChart.POINTS)
        try:
            if hasattr(points_plot, "SetMarkerStyle"): points_plot.SetMarkerStyle(2)
            if hasattr(points_plot, "SetMarkerSize"): points_plot.SetMarkerSize(7.0)
            penp = points_plot.GetPen(); penp.SetWidth(2); penp.SetColor(0, 0, 0)
        except Exception:
            pass
        points_plot.SetInputData(tbl, 0, 1)
        points_plot.SetUseIndexForXSeries(False)

        self._overlays.append({
            "id": meas_id,
            "chart": ch,
            "table": tbl,
            "line_plot": line_plot,
            "points_plot": points_plot,
        })

        if not self._overlay_enabled:
            self._set_plot_visible(ch, line_plot, False)
            self._set_plot_visible(ch, points_plot, False)

        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

    def _detach_overlay(self, ov):
        ch = ov.get("chart")
        if not ch: return
        for key in ("line_plot", "points_plot"):
            self._set_plot_visible(ch, ov.get(key), False)

    def _remove_overlay_by_id(self, meas_id: str):
        idx = next((i for i, o in enumerate(self._overlays) if o.get("id") == meas_id), None)
        if idx is None: return False
        ov = self._overlays.pop(idx)
        self._detach_overlay(ov)
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass
        return True

    # ====================== Public deletions ======================

    def remove_last_measurement(self):
        if not self._overlays:
            return False
        last = self._overlays[-1]
        meas_id = last.get("id")
        ok = self._remove_overlay_by_id(meas_id)
        lst = self.ds_get("measurements", None) or []
        lst = [m for m in lst if str(m.get("id")) != str(meas_id)]
        self.ds_set("measurements", lst)
        return ok

    def remove_measurement_by_id(self, meas_id: str):
        ok = self._remove_overlay_by_id(meas_id)
        lst = self.ds_get("measurements", None) or []
        lst = [m for m in lst if str(m.get("id")) != str(meas_id)]
        self.ds_set("measurements", lst)
        return ok

    def clear_all_measurements(self):
        # limpia visual
        self.clear_visual_overlays()
        # limpia datastore
        self.ds_set("measurements", [])
        return True

    def on_chart_changed(self):
        """Invoked by the menu when the chart is replaced (new trial/view)."""
        self._ref_axes = None
        self._saved_ranges = None
        self._ref_data = None
        self._down_pos = None
        
        self._dump_chart_state("on_chart_changed(before render)")
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass
        self._dump_chart_state("on_chart_changed(after render)")
        
        if self._state != 'idle':
            self.cancel() 
            
    def _dump_chart_state(self, tag=""):  # REMOVE WHEN LOGGING NO LONGER NEEDED
        ch = self.get_active_chart()
        if not ch:
            print(f"[MEAS] {tag} chart=None"); return
        try:
            nplots = ch.GetNumberOfPlots()
        except Exception:
            nplots = -1
        # axes
        try:
            ax_x = ch.GetAxis(vtk.vtkAxis.BOTTOM)
            ax_y = ch.GetAxis(vtk.vtkAxis.LEFT)
            xr = (ax_x.GetMinimum(), ax_x.GetMaximum())
            yr = (ax_y.GetMinimum(), ax_y.GetMaximum())
        except Exception:
            xr = yr = None
        # chart rect in pixels
        try:
            p1 = ch.GetPoint1(); p2 = ch.GetPoint2()
            rect = (p1.GetX(), p2.GetX(), p1.GetY(), p2.GetY())
        except Exception:
            rect = None

        print(f"[MEAS] {tag} plots={nplots} xr={xr} yr={yr} rect={rect}")

        # Quick list of labels/rows to see which plots exist
        try:
            for i in range(nplots):
                pl = ch.GetPlot(i)
                if pl is None: 
                    print(f"   [plot {i}] None")
                    continue
                try:
                    lbl = pl.GetLabel()
                except Exception:
                    lbl = None
                rows = None
                try:
                    tbl = pl.GetInput()
                    rows = tbl.GetNumberOfRows() if tbl else None
                except Exception:
                    pass
                # type (LINE/POINTS) if available
                ptype = None
                try:
                    ptype = pl.GetPlotType()
                except Exception:
                    pass
                print(f"   [plot {i}] label={lbl!r} rows={rows} type={ptype}")
        except Exception:
            pass


    def _compute_amplitude_window(self, x1, x2):
        """Use self._ref_data (xs/ys) to compute amplitude in window [x1,x2]."""
        if not self._ref_data or not self._ref_data.get('xs'):
            ch = self.get_active_chart()
            if not ch:
                return None
            self._load_reference_data_for_pick(ch)
            if not self._ref_data or not self._ref_data.get('xs'):
                return None

        xs = self._ref_data['xs']; ys = self._ref_data['ys']
        return amplitude_in_window(xs, ys, x1, x2)
    
    def _nearest_index(self, x_target):
        # requires self._ref_data loaded (sorted xs)
        xs = self._ref_data.get('xs') if self._ref_data else None
        if not xs:
            return None
        i = bisect.bisect_left(xs, x_target)
        cand = []
        if i > 0: cand.append(i-1)
        if i < len(xs): cand.append(i)
        # choose the closest in X
        best_i, best_d = None, None
        for j in cand:
            d = abs(xs[j] - x_target)
            if best_d is None or d < best_d:
                best_d, best_i = d, j
        return best_i

    def _compute_and_save_slopes_each_trial_by_index(self, i1, i2, make_overlays_for_current=False):
        ch = self.get_active_chart()
        if not ch or ch.GetNumberOfPlots() == 0:
            return []

        ref_plot = ch.GetPlot(0)
        table = ref_plot.GetInput()
        if table is None:
            return []

        x_arr = table.GetColumnByName("time") or table.GetColumn(0)
        if x_arr is None:
            return []

        t1 = float(x_arr.GetValue(i1))
        t2 = float(x_arr.GetValue(i2))
        dx = float(t2 - t1)
        if dx == 0:
            return []

        ncols = table.GetNumberOfColumns()
        meas_ids = []

        for c in range(1, ncols):
            col = table.GetColumn(c)
            if not col:
                continue
            name = col.GetName() if hasattr(col, "GetName") else f"col{c}"
            if not name or not name.startswith("trial_"):
                continue

            y1 = float(col.GetValue(i1))
            y2 = float(col.GetValue(i2))

            # standard "slope" metric using utilities
            res = two_point_metrics((t1, y1), (t2, y2), kind='slope')
            # add useful metadata
            res["trial_name"] = name
            # map trial_k (1-based) to trial_id (0-based)
            try:
                k = int(name.split("_")[1])
                trial_id_zero_based = k - 1
            except Exception:
                trial_id_zero_based = None

            mid = self._save_measurement(
                res,
                (t1, y1),
                (t2, y2),
                override_ctx={"trial_id": trial_id_zero_based}
            )
            meas_ids.append(mid)

            if make_overlays_for_current and self._context.get("trial_id") == trial_id_zero_based:
                try:
                    self._add_overlay_for_points(mid, (t1, y1), (t2, y2))
                except Exception:
                    pass

        return meas_ids

