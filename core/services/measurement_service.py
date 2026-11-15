from datetime import datetime
import vtk
import bisect
import re
import weakref

import numpy as np

from core.filters.measurements import amplitude_in_window, two_point_metrics, derivative_in_window
from core.utils.plugin_alerts import PluginAlerts
from core.utils.submuestreo import tabla_de, datos_completos


class MeasurementService:
    """Servicio de medición del núcleo (R69): una sola instancia, registrada en el Kernel.

    Cada gráfico mide por su cuenta, con su medición en curso y sus líneas dibujadas, así que el servicio
    le entrega una `SesionDeMedicion`. Lo que comparten, el almacén donde se guardan las mediciones,
    lo guarda el servicio.
    """

    def __init__(self, datastore):
        self.datastore = datastore
        self._sesiones = weakref.WeakValueDictionary()

    def _leer(self, clave, defecto=None):
        try:
            return self.datastore.get(clave, defecto) if self.datastore else defecto
        except Exception:
            return defecto

    def _escribir(self, clave, valor):
        try:
            if self.datastore:
                self.datastore.set(clave, valor)
        except Exception:
            pass

    def sesion_para(self, parent, vtk_widget, get_active_chart, pick_radius_px=10, debug=False):
        """La sesión de medición de una ventana gráfica; reemplaza a la anterior de esa ventana."""
        sesion = SesionDeMedicion(parent, vtk_widget, get_active_chart, self._leer, self._escribir,
                                  pick_radius_px, debug)
        self._sesiones[id(vtk_widget)] = sesion
        return sesion

    def sesion_de(self, vtk_widget):
        return self._sesiones.get(id(vtk_widget))


class SesionDeMedicion:
    """
    2-point measurements for one view, with per-trial persistence and rebuildable overlays.
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

        # Optional callback invoked whenever the measurement list changes
        # (save/delete/clear), so the UI (e.g. the Results panel) can refresh live.
        self.on_change = None

        # ---- interaction state ----
        self._state = 'idle'
        self._current = None        # {'type','p1','p2'}
        # Curve chosen with P1 when the chart has several (butterfly): extra ctx for the record
        self._picked_ctx = None
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

        # ---- every trial of the view (for the "all trials" measurements) ----
        # Callable returning (time (Ns,), trials (Ns, T), trial_ids [0-based, len T]) or None.
        # Each plot of a chart only keeps its own column, so the chart alone cannot
        # give the other trials: the plugin that owns the view provides them here.
        self.trials_source = None
        # 0-based trial ids drawn right now (None = no filter). Overlays of trials
        # that are not on screen (another group of the butterfly) are not drawn.
        self.visible_trial_ids = None

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
        batches = {}
        for m in lst:
            mctx = m.get("ctx") or {}
            if not self._context_matches(ctx, mctx):
                continue
            if m.get("batch"):
                batches.setdefault(m["batch"], []).append(m)
                continue
            if not self._trial_on_screen(mctx.get("trial_id")):
                continue
            try:
                self._add_overlay_for_record(m, render=False)
            except Exception:
                pass
        for recs in batches.values():
            try:
                self._draw_batch(recs)
            except Exception:
                pass
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

    def _trial_on_screen(self, trial_id) -> bool:
        vis = self.visible_trial_ids
        if vis is None or not isinstance(trial_id, int):
            return True
        return trial_id in vis

    def _add_overlay_for_record(self, m, render=True):
        """Draw the overlay of a saved measurement: its curve if it has one, else P1–P2."""
        mid = m.get("id")
        pts = m.get("overlay_pts")
        if isinstance(pts, (list, tuple)) and len(pts) >= 2:
            self._add_overlay_for_points(mid, pts[0], pts[-1], points=pts,
                                         right_axis=bool(m.get("overlay_right_axis")), render=render)
        else:
            self._add_overlay_for_points(mid, m.get("p1"), m.get("p2"), render=render,
                                         color=self.SLOPE_COLOR if m.get("type") == "slope" else None)

    # ====================== Public API (measurement) ======================

    def _dbg(self, *a):
        if self._debug:
            try:
                print("[MEAS]", *a)
            except Exception:
                pass

    def _notify_change(self):
        if self.on_change:
            try:
                self.on_change()
            except Exception:
                pass
        
    @property
    def state(self):
        return self._state

    ALLOWED_TYPES = {"slope", "slope_all_trials", "amplitude", "amplitude_all_trials",
                     "difference", "difference_all_trials"}

    def supports_all_trials(self) -> bool:
        """True when the view gave its trials (Trials, ERP butterfly)."""
        return callable(self.trials_source) or self._context.get("plugin") == "trials"

    def start(self, measure_type: str):
        if measure_type not in self.ALLOWED_TYPES:
            measure_type = "slope"

        if measure_type.endswith("_all_trials") and not self.supports_all_trials():
            try:
                self.alerts.warning("This measurement is only available in views with trials "
                                    "(Trials or Event Related Potential).")
            except Exception:
                pass
            return False
    
        if self._state != 'idle':
            try:
                self.alerts.warning("A measurement is already in progress. Complete it or cancel (Esc).")
            except Exception:
                pass
            return False
        
        self._state = 'waiting_p1'
        self._current = {'type': measure_type, 'p1': None, 'p2': None}
        self.alerts.info("Select the FIRST point with left click.")

    def cancel(self):
        self._state = 'idle'
        self._current = None
        self._picked_ctx = None
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

            # Several curves (butterfly, trials of a PSD...): take the one clicked, and keep it for P2
            self._picked_ctx = None
            series = self._series_of_chart(ch)
            if len(series) > 1:
                hit = self._pick_nearest_among_series(series, sx, sy)
                if hit is None:
                    self.alerts.warning(f"No nearby point (≤ {self._PICK_RADIUS_PX}px). Try again.")
                    return
                serie, picked = hit
                self._ref_data = {'xs': serie['x'].tolist(), 'ys': serie['y'].tolist()}
                self._picked_ctx = serie['ctx']
                self._current['p1'] = picked
                self._state = 'waiting_p2'
                self._suspend_left_actions(True)
                cual = f" on '{serie['label']}'" if serie['label'] else ""
                self.alerts.info(f"First point taken{cual}. Now select the SECOND point with left click.")
                return

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

    # ====================== several curves (butterfly) ======================

    def _overlay_plot_keys(self):
        keys = set()
        for ov in self._overlays:
            for k in ("line_plot", "points_plot"):
                pl = ov.get(k)
                if pl is not None:
                    keys.add(getattr(pl, "__this__", id(pl)))
        return keys

    def _series_of_chart(self, chart):
        """Data curves of the chart (measurement overlays left out), with full data and sorted X.

        Each item: {'x','y' (numpy), 'label', 'ctx'}; 'ctx' says which trial the curve is
        ('Trial k' -> trial_id k-1) or that it is the average, for the saved measurement.
        """
        out = []
        try:
            n = chart.GetNumberOfPlots()
        except Exception:
            return out
        skip = self._overlay_plot_keys()
        for i in range(n):
            pl = chart.GetPlot(i)
            if pl is None or getattr(pl, "__this__", id(pl)) in skip:
                continue
            try:
                if hasattr(pl, "GetVisible") and not pl.GetVisible():
                    continue
            except Exception:
                pass
            d = datos_completos(pl)
            if d is None:
                continue
            x = np.asarray(d[0], dtype=np.float64)
            y = np.asarray(d[1], dtype=np.float64)
            if x.size < 1 or x.shape != y.shape:
                continue
            if x.size > 1 and np.any(np.diff(x) < 0):
                orden = np.argsort(x, kind="stable")
                x, y = x[orden], y[orden]
            try:
                label = pl.GetLabel() or ""
            except Exception:
                label = ""
            ctx = None
            m = re.match(r"^\s*trial[ _-]?(\d+)\s*$", label, re.IGNORECASE)
            if m:
                ctx = {"trial_id": int(m.group(1)) - 1}
            elif label.lower() == "average":
                ctx = {"graph_id": "average"}
            out.append({"x": x, "y": y, "label": label, "ctx": ctx})
        return out

    def _pick_nearest_among_series(self, series, sx_click, sy_click):
        """(serie, (x, y)) of the data point closest to the click on screen, within the pick radius."""
        rect = self._plot_rect_pixels()
        if rect is None:
            return None
        x_min_px, x_max_px, y_min_px, y_max_px = rect
        if not (x_min_px <= sx_click <= x_max_px and y_min_px <= sy_click <= y_max_px):
            return None
        guess = self._screen_to_plot(sx_click, sy_click)
        if guess is None:
            return None
        xg = guess[0]
        best = None; best_d2 = None
        for s in series:
            xs, ys = s["x"], s["y"]
            i = int(np.searchsorted(xs, xg))
            for idx in (i - 2, i - 1, i, i + 1):
                if not (0 <= idx < xs.size) or not np.isfinite(ys[idx]):
                    continue
                sp = self._plot_to_screen(float(xs[idx]), float(ys[idx]))
                if sp is None:
                    continue
                d2 = (sp[0] - sx_click) ** 2 + (sp[1] - sy_click) ** 2
                # On a tie the later curve wins: it is the one drawn on top (the average)
                if best_d2 is None or d2 <= best_d2:
                    best_d2 = d2; best = (s, (float(xs[idx]), float(ys[idx])))
        if best is not None and best_d2 <= self._PICK_RADIUS_PX ** 2:
            return best
        return None

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
        # On a butterfly, the 2-point measurements are taken on the average curve
        for i in range(n):
            pl = chart.GetPlot(i)
            try:
                if pl is not None and pl.GetLabel() == "Average":
                    ref_plot = pl
                    break
            except Exception:
                pass
        if ref_plot is None:
            self._ref_data = None
            return

        # 2) Table
        try:
            table = tabla_de(ref_plot)
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

        x1, y1 = cur['p1']
        x2, y2 = cur['p2']
        kind = cur.get('type', 'slope')

        try:
            if kind == 'slope':
                self._finalize_slope_single(x1, y1, x2, y2)
            elif kind == 'amplitude':
                self._finalize_amplitude_single(x1, y1, x2, y2)
            elif kind == 'difference':
                self._finalize_difference_single(x1, y1, x2, y2)
            elif kind.endswith('_all_trials'):
                self._finalize_all_trials(kind[:-len('_all_trials')], x1, x2)
            else:
                try:
                    self.alerts.error(f"Unsupported measurement type: {kind}", "Measurement")
                except Exception:
                    pass
        finally:
            self._state = 'idle'
            self._current = None
            self._picked_ctx = None
            self._notify_change()

    # ---- one trace ----

    def _finalize_slope_single(self, x1, y1, x2, y2):
        result = two_point_metrics((x1, y1), (x2, y2), kind='slope')
        meas_id = self._save_measurement(result, (x1, y1), (x2, y2), override_ctx=self._picked_ctx)
        try:
            self._add_overlay_for_points(meas_id, (x1, y1), (x2, y2), color=self.SLOPE_COLOR)
        except Exception:
            pass
        try:
            self.alerts.info(
                f"Result '{result['type']}' saved (ID: {meas_id}).\n Slope = {result['slope']:.6f}\n\n"
                f"For more information go to 'Measure / Slope'."
            )
        except Exception:
            pass

    def _finalize_amplitude_single(self, x1, y1, x2, y2):
        result = self._compute_amplitude_window(x1, x2)
        if not result:
            try:
                self.alerts.warning("The amplitude could not be calculated in the selected window.", "Amplitude")
            except Exception:
                pass
            return
        meas_id = self._save_measurement(result, (x1, y1), (x2, y2), override_ctx=self._picked_ctx)
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

    def _finalize_difference_single(self, x1, y1, x2, y2):
        if not self._ensure_ref_data():
            try:
                self.alerts.warning("There is no series data to differentiate.", "Difference")
            except Exception:
                pass
            return
        result = derivative_in_window(self._ref_data['xs'], self._ref_data['ys'], x1, x2)
        if not result:
            try:
                self.alerts.warning("The window needs at least two samples to compute the derivative.",
                                    "Difference")
            except Exception:
                pass
            return
        result.update(self._difference_overlay_fields(result))
        meas_id = self._save_measurement(result, (x1, y1), (x2, y2), override_ctx=self._picked_ctx)
        try:
            self._add_overlay_for_points(meas_id, (x1, y1), (x2, y2), points=result["overlay_pts"],
                                         right_axis=True)
        except Exception:
            pass
        try:
            self.alerts.info(
                (f"Derivative dy/dx in [{result['x1']:.6g}, {result['x2']:.6g}]\n"
                 f"Mean = {result['d_mean']:.6g}\n"
                 f"Max = {result['d_max']:.6g} @ x={result['x_at_dmax']:.6g}\n"
                 f"Min = {result['d_min']:.6g} @ x={result['x_at_dmin']:.6g}\n"
                 f"ID: {meas_id}\n\nThe derivative is drawn on the right axis."),
                "Saved difference"
            )
        except Exception:
            pass

    @staticmethod
    def _difference_overlay_fields(result):
        """The derivative curve goes to the record as overlay (right axis), not as a result column."""
        curve = result.pop("curve", None) or []
        return {"overlay_pts": [tuple(p) for p in curve], "overlay_right_axis": True}

    def _ensure_ref_data(self) -> bool:
        if self._ref_data and self._ref_data.get('xs'):
            return True
        ch = self.get_active_chart()
        if not ch:
            return False
        self._load_reference_data_for_pick(ch)
        return bool(self._ref_data and self._ref_data.get('xs'))

    # ---- every trial ----

    def _all_trials_data(self):
        """(t, M (Ns, T), ids 0-based) from the view, or from the chart columns as fallback."""
        src = self.trials_source
        if callable(src):
            try:
                got = src()
            except Exception as e:
                self._dbg("trials_source error:", e)
                got = None
            if got is not None:
                t, M, ids = got
                t = np.asarray(t, dtype=np.float64).ravel()
                M = np.asarray(M, dtype=np.float64)
                if M.ndim == 2 and M.shape[0] == t.size and M.shape[1] == len(ids):
                    return t, M, [int(i) for i in ids]
        # Fallback: whatever trial_k columns the chart's plots hold
        ch = self.get_active_chart()
        if not ch:
            return None
        t = None; cols = []; ids = []
        for i in range(ch.GetNumberOfPlots()):
            tbl = tabla_de(ch.GetPlot(i))
            if tbl is None:
                continue
            for c in range(1, tbl.GetNumberOfColumns()):
                col = tbl.GetColumn(c)
                name = col.GetName() if col is not None else ""
                if not name or not name.startswith("trial_"):
                    continue
                try:
                    k = int(name.split("_")[1]) - 1
                except Exception:
                    continue
                if k in ids:
                    continue
                xcol = tbl.GetColumn(0)
                xs = np.array([xcol.GetValue(j) for j in range(xcol.GetNumberOfTuples())], dtype=np.float64)
                ys = np.array([col.GetValue(j) for j in range(col.GetNumberOfTuples())], dtype=np.float64)
                if t is None:
                    t = xs
                if ys.size != t.size:
                    continue
                cols.append(ys); ids.append(k)
        if t is None or not cols:
            return None
        return t, np.column_stack(cols), ids

    def _finalize_all_trials(self, base, x1, x2):
        data = self._all_trials_data()
        if data is None:
            try:
                self.alerts.warning("No trials available for this view.")
            except Exception:
                pass
            return
        t, M, ids = data
        if x2 < x1:
            x1, x2 = x2, x1
        i1 = int(np.argmin(np.abs(t - x1)))
        i2 = int(np.argmin(np.abs(t - x2)))
        if i1 == i2:
            try:
                self.alerts.warning("Both points fall at the same sample; dx=0.")
            except Exception:
                pass
            return

        batch = datetime.now().strftime("%Y%m%d%H%M%S%f")
        made = 0
        drawn_on_graph = self._context.get("plugin") == "trials"
        cur_tid = self._context.get("trial_id")
        for col, k in enumerate(ids):
            y = M[:, col]
            p1 = (float(t[i1]), float(y[i1]))
            p2 = (float(t[i2]), float(y[i2]))
            if base == "slope":
                res = two_point_metrics(p1, p2, kind="slope")
            elif base == "amplitude":
                res = amplitude_in_window(t, y, x1, x2)
            elif base == "difference":
                res = derivative_in_window(t, y, x1, x2)
                if res:
                    res.update(self._difference_overlay_fields(res))
            else:
                return
            if not res:
                continue
            res["trial_name"] = f"trial_{k + 1}"
            res["batch"] = batch
            res["all_trials"] = True
            ctx_over = {"trial_id": k}
            if drawn_on_graph:
                ctx_over["graph_id"] = f"trial {k}"
            self._save_measurement(res, p1, p2, override_ctx=ctx_over)
            made += 1

        recs = [m for m in (self.ds_get("measurements", None) or []) if m.get("batch") == batch]
        lines_drawn = True
        try:
            lines_drawn = self._draw_batch(recs)
        except Exception:
            pass
        try:
            self.vtk_widget.GetRenderWindow().Render()
        except Exception:
            pass

        titles = {"slope": "Slopes per trial", "amplitude": "Amplitudes per trial",
                  "difference": "Derivatives per trial"}
        extra = ""
        if not lines_drawn:
            extra = (f"\n\nThere are more than {self.MAX_TRIAL_LINES} trials on screen, so only the two "
                     f"points (grey vertical lines) are drawn. Choose groups of 6 (or fewer) in "
                     f"'Butterfly display' to see the line of each trial.")
        try:
            self.alerts.info(
                f"Generated {made} measurements (one per trial) between x={t[i1]:.6g} and x={t[i2]:.6g}.\n"
                f"All of them are in the Results panel and in its CSV/Excel export." + extra,
                titles.get(base, "All trials"))
        except Exception:
            pass

    # ---- drawing of an "all trials" batch ----

    MAX_TRIAL_LINES = 12      # more lines than this on one chart cannot be read
    SLOPE_COLOR = (220, 0, 0)  # slope lines are red; the butterfly average is black

    def _trial_colors(self, chart):
        """trial_id (0-based) -> (r, g, b) of the curve labelled 'Trial k' on the chart."""
        colors = {}
        try:
            n = chart.GetNumberOfPlots()
        except Exception:
            return colors
        for i in range(n):
            pl = chart.GetPlot(i)
            try:
                m = re.match(r"^\s*trial[ _-]?(\d+)\s*$", pl.GetLabel() or "", re.IGNORECASE)
                if not m:
                    continue
                c = vtk.vtkColor4ub()
                pl.GetColorRGBA(c)
                colors[int(m.group(1)) - 1] = (c[0], c[1], c[2])
            except Exception:
                pass
        return colors

    def _y_span(self, chart, recs):
        ys = []
        for s in self._series_of_chart(chart):
            y = s["y"][np.isfinite(s["y"])]
            if y.size:
                ys += [float(y.min()), float(y.max())]
        if not ys:
            for m in recs:
                ys += [float(m["p1"][1]), float(m["p2"][1])]
        lo, hi = min(ys), max(ys)
        if hi == lo:
            hi, lo = hi + 1.0, lo - 1.0
        return lo, hi

    def _draw_batch(self, recs):
        """Draw one 'all trials' measurement: the two points as grey vertical lines, and a thin
        line per trial in that trial's color when at most MAX_TRIAL_LINES trials are on screen.
        Returns False when the per-trial lines were left out because there were too many."""
        ch = self.get_active_chart()
        if not ch or not recs:
            return True
        cur_tid = self._context.get("trial_id")
        visibles = [m for m in recs
                    if self._trial_on_screen((m.get("ctx") or {}).get("trial_id"))
                    and (cur_tid is None or cur_tid == (m.get("ctx") or {}).get("trial_id"))]
        batch = recs[0].get("batch")
        draw_lines = len(visibles) <= self.MAX_TRIAL_LINES
        if draw_lines and visibles:
            colors = self._trial_colors(ch)
            for m in visibles:
                tid = (m.get("ctx") or {}).get("trial_id")
                color = self.SLOPE_COLOR if m.get("type") == "slope" else colors.get(tid)
                pts = m.get("overlay_pts")
                if isinstance(pts, (list, tuple)) and len(pts) >= 2:
                    self._add_overlay_for_points(m.get("id"), pts[0], pts[-1], points=pts,
                                                 right_axis=bool(m.get("overlay_right_axis")),
                                                 color=color, width=1.5, markers=False,
                                                 batch=batch, render=False)
                else:
                    self._add_overlay_for_points(m.get("id"), m.get("p1"), m.get("p2"),
                                                 color=color, width=2.0, dashed=False, markers=False,
                                                 batch=batch, render=False)
        # P1 / P2 once for the whole batch
        lo, hi = self._y_span(ch, recs)
        for tag, x in (("x1", recs[0]["p1"][0]), ("x2", recs[0]["p2"][0])):
            self._add_overlay_for_points(f"batch:{batch}:{tag}", (x, lo), (x, hi),
                                         color=(90, 90, 90), width=1.5, dashed=True, markers=False,
                                         batch=batch, render=False)
        return draw_lines


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
        return self._make_table_pts([p1, p2])

    def _make_table_pts(self, pts):
        tbl = vtk.vtkTable()
        ax = vtk.vtkFloatArray(); ax.SetName("X")
        ay = vtk.vtkFloatArray(); ay.SetName("Y")
        tbl.AddColumn(ax); tbl.AddColumn(ay)
        for i, p in enumerate(pts):
            tbl.InsertNextBlankRow()
            tbl.SetValue(i, 0, float(p[0])); tbl.SetValue(i, 1, float(p[1]))
        return tbl

    def _add_overlay_for_points(self, meas_id: str, p1, p2, axes_snapshot=None, *,
                                points=None, right_axis=False, markers=True, render=True,
                                color=None, width=2.0, dashed=None, batch=None):
        """Draw a measurement on the active chart.

        Without `points`: dashed line P1-P2 with its two points marked (slope, amplitude).
        With `points`: solid curve through them (the derivative of 'difference'); with
        `right_axis` it uses the chart's right Y axis, since its units (y/x) are not the signal's.
        """
        ch = self.get_active_chart()
        if not ch: return
        curve = points is not None and len(points) >= 2
        tbl = self._make_table_pts(points if curve else [p1, p2])
        tbl_markers = self._make_table_2pts(p1, p2) if curve else tbl

        line_plot = ch.AddPlot(vtk.vtkChart.LINE)
        try:
            pen = line_plot.GetPen()
            pen.SetWidth(float(width))
            if dashed is None:
                dashed = not curve
            pen.SetLineType(vtk.vtkPen.DASH_LINE if dashed else vtk.vtkPen.SOLID_LINE)
            r, g, b = color if color is not None else self._next_color()
            pen.SetColor(int(r), int(g), int(b))
        except Exception:
            pass
        line_plot.SetInputData(tbl, 0, 1)
        line_plot.SetUseIndexForXSeries(False)
        if right_axis:
            try:
                ch.SetPlotCorner(line_plot, 1)          # bottom X + right Y
                ax_r = ch.GetAxis(vtk.vtkAxis.RIGHT)
                ax_r.SetVisible(True)
                ax_r.SetTitle("dy/dx")
            except Exception:
                pass
        try:
            line_plot.SetLabel(str(meas_id))
        except Exception:
            pass

        # P1 / P2 markers, always on the signal axes
        points_plot = None
        if markers:
            points_plot = ch.AddPlot(vtk.vtkChart.POINTS)
            try:
                if hasattr(points_plot, "SetMarkerStyle"): points_plot.SetMarkerStyle(2)
                if hasattr(points_plot, "SetMarkerSize"): points_plot.SetMarkerSize(7.0)
                penp = points_plot.GetPen(); penp.SetWidth(2); penp.SetColor(0, 0, 0)
            except Exception:
                pass
            points_plot.SetInputData(tbl_markers, 0, 1)
            points_plot.SetUseIndexForXSeries(False)

        self._overlays.append({
            "id": meas_id,
            "chart": ch,
            "table": tbl,
            "line_plot": line_plot,
            "points_plot": points_plot,
            "batch": batch,
        })

        if not self._overlay_enabled:
            self._set_plot_visible(ch, line_plot, False)
            self._set_plot_visible(ch, points_plot, False)

        if render:
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
        batch = last.get("batch")
        if batch:
            # an "all trials" measurement is deleted as a whole (every trial + its two lines)
            for ov in [o for o in self._overlays if o.get("batch") == batch]:
                self._overlays.remove(ov)
                self._detach_overlay(ov)
            lst = self.ds_get("measurements", None) or []
            self.ds_set("measurements", [m for m in lst if m.get("batch") != batch])
            try:
                self.vtk_widget.GetRenderWindow().Render()
            except Exception:
                pass
            self._notify_change()
            return True
        meas_id = last.get("id")
        ok = self._remove_overlay_by_id(meas_id)
        lst = self.ds_get("measurements", None) or []
        lst = [m for m in lst if str(m.get("id")) != str(meas_id)]
        self.ds_set("measurements", lst)
        self._notify_change()
        return ok

    def remove_measurement_by_id(self, meas_id: str):
        ok = self._remove_overlay_by_id(meas_id)
        lst = self.ds_get("measurements", None) or []
        lst = [m for m in lst if str(m.get("id")) != str(meas_id)]
        self.ds_set("measurements", lst)
        self._notify_change()
        return ok

    def clear_all_measurements(self):
        # limpia visual
        self.clear_visual_overlays()
        # limpia datastore
        self.ds_set("measurements", [])
        self._notify_change()
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
        table = tabla_de(ref_plot)
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

