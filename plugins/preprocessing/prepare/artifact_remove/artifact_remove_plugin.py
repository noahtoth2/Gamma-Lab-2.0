from vtk.util import numpy_support as nps  # Safe import for VTK/NumPy
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
import numpy as np
import vtk
from typing import Optional, List, Set
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from types import SimpleNamespace  # Helper for trials

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset

from plugins.preprocessing.prepare.artifact_remove.artifact_remove_ui import Ui_ArtifactRemove
# Import logic entry point
from plugins.preprocessing.prepare.artifact_remove.artifact_logic import apply_modification_to_all_valid

# Optional import for custom context menu
try:
    from core.utils.vtk_context_menu import VTKContextMenu
except ImportError:
    VTKContextMenu = None

LOGP = "[ArtifactRemovePlugin]"
# --- Worker to run heavy logic in a background thread ---
class _ApplyWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(int)
    finished = QtCore.pyqtSignal(object)   
    error = QtCore.pyqtSignal(str)

    def __init__(self, kernel, mode, point_a, point_b):
        super().__init__()
        self.kernel = kernel
        self.mode = mode
        self.point_a = point_a
        self.point_b = point_b

    @QtCore.pyqtSlot()
    def run(self):
        try:
            from plugins.preprocessing.prepare.artifact_remove.artifact_logic import apply_modification_to_all_valid
            td = apply_modification_to_all_valid(
                kernel=self.kernel,
                mode=self.mode,
                point_a=self.point_a,
                point_b=self.point_b
            )
            self.finished.emit(td)
        except Exception as e:
            self.error.emit(f"{type(e).__name__}: {e}")

class _WidgetVisibilityFilter(QtCore.QObject):
    """Listens to show/hide events on the plugin widget to keep the plot in sync."""
    def __init__(self, plugin):
        super().__init__(plugin.widget)
        self._plugin = plugin

    def eventFilter(self, obj, event):
        if obj is self._plugin.widget:
            if event.type() == QtCore.QEvent.Show:
                self._plugin._on_widget_shown()
            elif event.type() == QtCore.QEvent.Hide:
                self._plugin._on_widget_hidden()
        return super().eventFilter(obj, event)

# Main Plugin Class
class ArtifactRemovePlugin(IPlugin):
    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.meta = meta
        print(f"{LOGP} __init__")

        self.ui: Optional[Ui_ArtifactRemove] = None
        self.vtk_interactor: Optional[QVTKRenderWindowInteractor] = None
        self.vtk_view: Optional[vtk.vtkContextView] = None
        self.chart: Optional[vtk.vtkChartXY] = None
        self.vtk_menu: Optional[VTKContextMenu] = None

        self._apply_thread = None
        self._apply_worker = None

        self._refresh_timer = QtCore.QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(120) # ms
        self._refresh_timer.timeout.connect(self._refresh_view_coalesced)

        self.current_display_index: int = -1  # -1 = Average
        self.valid_indices: List[int] = []
        self.total_original_trials: int = 0
        self.discarded_indices: Set[int] = set()
        self.modified_indices: Set[int] = set()

        self._visibility_filter: Optional[_WidgetVisibilityFilter] = None

    def process(self, data): 
        pass

    def _refresh_view_coalesced(self):
        """Coalesced refresh: only refresh once for bursty events."""
        try:
            self._reset_state()
            if self.vtk_interactor and not self.vtk_interactor.isEnabled():
                try:
                    self.vtk_interactor.Enable()
                except Exception:
                    pass
            self._load_and_display_trials()
            QtCore.QTimer.singleShot(50, self._force_render)
        except Exception as e:
            print(f"{LOGP} _refresh_view_coalesced error: {e}")


    def start(self, kernel):
        """Called when the plugin is first loaded."""
        print(f"{LOGP} start()")
        self.kernel = kernel
        self.mainwin = kernel.get_service("MainWindow")
        try:
            self.kernel.event.connect(self._on_data_updated)
            print(f"{LOGP} Connected to kernel events.")
        except Exception as e:
            print(f"{LOGP} Error connecting to events: {e}")

    def stop(self):
        """Called when the plugin closes or is disabled."""
        print(f"{LOGP} stop() - Disabling VTK interactor.")
        if self.vtk_interactor and self.vtk_interactor.isEnabled():
            try:
                self.vtk_interactor.Disable()
            except Exception as e: 
                print(f"{LOGP} Error disabling interactor: {e}")

    def get_widget(self, parent=None):
        """Return the plugin's main widget to the main window."""
        
        if self.widget is None:
            print(f"{LOGP} get_widget(): Creating UI for the first time...")
            
            self.widget = QWidget(parent)
            self.alerts.parent = self.widget
            
            try:
                self.ui = Ui_ArtifactRemove()
                self.ui.setupUi(self.widget)
                self._wire_controls()

                if self.kernel is None:
                    if hasattr(parent, 'kernel'): 
                        self.kernel = parent.kernel
                    if self.kernel:
                        print(f"{LOGP} Kernel obtained in get_widget.")
                        self.mainwin = self.kernel.get_service("MainWindow")
                        try: 
                            self.kernel.event.connect(self._on_data_updated)
                            print(f"{LOGP} Connected events in get_widget.")
                        except Exception as e: 
                            print(f"{LOGP} Error connecting events: {e}")
                    else: 
                        raise RuntimeError("Kernel not available.")

                print(f"{LOGP} get_widget(): Loading initial data...")
                self._load_and_display_trials()
                if self.ui and self.ui.paramsLayout:
                    self._on_mode_changed(self.ui.mode_combo.currentText())

                # Show watermark until something is plotted
                try:
                    if self.mainwin:
                        self.mainwin.show_watermark()
                except Exception:
                    pass
                self._ensure_visibility_filter()

            except Exception as e: 
                error_message = f"Failed to initialize Remove Artifact plugin:\n{type(e).__name__}: {e}"
                print(f"{LOGP} CRITICAL ERROR during initial setup: {e}")
                self.alerts.error(error_message, "Plugin Initialization Error")
                self._cleanup_vtk_references()
                self.widget.deleteLater() 
                self.widget = None
                self.ui = None
                return None 

        else:
            print(f"{LOGP} get_widget(): Reusing existing UI.")
            self.widget.setParent(parent)
            self._ensure_visibility_filter()
            
            try:
                if self.vtk_interactor and not self.vtk_interactor.isEnabled():
                    self.vtk_interactor.Enable()
                
                print(f"{LOGP} get_widget(): Reloading data...")
                self._load_and_display_trials()
                QtCore.QTimer.singleShot(50, self._force_render) 
                
            except Exception as e:
                print(f"{LOGP} Error re-ensuring VTK or reloading data: {e}")
                self._clear_render(f"Error reloading view:\n{e}")

        return self.widget

    def _force_render(self):
        """Force a render if the widget is visible."""
        if self.vtk_interactor and self.vtk_view and self.widget and self.widget.isVisible():
            try: 
                print(f"{LOGP} DEBUG: Forcing Render.")
                self.vtk_view.GetRenderWindow().Render()
                print(f"{LOGP} DEBUG: Render successful.")
            except Exception as e: 
                print(f"{LOGP} Error during forced render: {e}")

    def _wire_controls(self):
        """Connect UI signals to slots (no optional guards)."""
        if not self.ui:
            print(f"{LOGP} Error: UI not initialized in _wire_controls.")
            return

        self.ui.apply_button.clicked.connect(self._on_apply_changes)
        self.ui.prev_button.clicked.connect(self._go_to_previous_trial)
        self.ui.next_button.clicked.connect(self._go_to_next_trial)
        self.ui.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        # Ensure correct initial visibility/state
        try:
            self._on_mode_changed(self.ui.mode_combo.currentText())
        except Exception:
            pass

        print(f"{LOGP} UI controls connected.")

    def _on_mode_changed(self, mode_text: str):
        """Update Point B visibility depending on mode."""
        if not self.ui or not hasattr(self.ui, 'artifact_panel'): 
            return
            
        show_point_b = (mode_text == "Interpolate Interval" or mode_text == "Blank Interval")

        # Toggle visibility directly on UI widgets
        if hasattr(self.ui, 'label_b'):
            self.ui.label_b.setVisible(show_point_b)
        if hasattr(self.ui, 'point_b'):
            self.ui.point_b.setVisible(show_point_b)

        # Update label A text
        if hasattr(self.ui, 'label_a'):
            if mode_text == "Cut From Start":
                self.ui.label_a.setText("Cut until (s):")
            else:
                self.ui.label_a.setText("Point A (s):")

    def _on_apply_changes(self):
        """Run modification in a thread to avoid blocking the UI."""
        if not self.ui or not self.widget:
            return

        panel = self.ui.paramsLayout

        if self.current_display_index != -1:
            self.alerts.warning("Apply changes only from the 'Average' view (Index -1).", "Invalid Action")
            return

        try:
            mode_text = self.ui.mode_combo.currentText()
            # Adjust mode based on modification logic
            mode = 'blank' if mode_text in ("Cut From Start", "Blank Interval") else 'interpolate'

            point_a_str = self.ui.point_a.text().strip()
            if not point_a_str:
                raise ValueError("Point A cannot be empty.")
            point_a = float(point_a_str)

            point_b = 0.0
            if mode == 'interpolate' or mode_text == "Blank Interval":  # interval operations require B
                point_b_str = self.ui.point_b.text().strip()
                if not point_b_str:
                    # In "Cut From Start" B is optional; do not raise here
                    if mode_text != "Cut From Start":
                         raise ValueError("Point B cannot be empty for interval modification.")
                else:
                    point_b = float(point_b_str)
                    if point_a == point_b and mode_text != "Cut From Start":
                        raise ValueError("Points A and B cannot be the same.")

            # --- Feedback and reentrancy guard
            self.ui.apply_button.setEnabled(False)
            self.ui.mode_combo.setEnabled(False)
            self.ui.prev_button.setEnabled(False)
            self.ui.next_button.setEnabled(False)
            if self.vtk_interactor:
                try:
                    self.vtk_interactor.Disable()
                except Exception:
                    pass
            self._clear_render("")

            # --- Create and start worker in a QThread
            self._apply_thread = QtCore.QThread(self.widget)
            self._apply_worker = _ApplyWorker(self.kernel, mode, point_a, point_b)
            self._apply_worker.moveToThread(self._apply_thread)

            # Connections
            self._apply_thread.started.connect(self._apply_worker.run)
            self._apply_worker.finished.connect(self._on_apply_finished) 
            self._apply_worker.error.connect(self._on_apply_error)

            # Auto cleanup
            self._apply_worker.finished.connect(self._apply_thread.quit)
            self._apply_worker.finished.connect(self._apply_worker.deleteLater)
            self._apply_thread.finished.connect(self._apply_thread.deleteLater)
            self._apply_worker.error.connect(self._apply_thread.quit)
            self._apply_worker.error.connect(self._apply_worker.deleteLater)

            self._apply_thread.start()

        except ValueError as ve:
            self.alerts.error(str(ve), "Parameter Error")
        except RuntimeError as re:
            self.alerts.error(str(re), "Data Error")
        except Exception as e:
            self.alerts.error(f"An unexpected error occurred: {e}")
            print(f"{LOGP} Error on apply: {e}")

    def _go_to_previous_trial(self):
        num_valid = len(self.valid_indices)
        if num_valid <= 0: 
            return
        idx_before = self.current_display_index
        if self.current_display_index == 0:
            self.current_display_index = -1 
        elif self.current_display_index == -1:
            self.current_display_index = num_valid - 1 
        else:
            self.current_display_index -= 1
            
        print(f"{LOGP} Nav Prev: {idx_before} -> {self.current_display_index}")
        self._load_and_display_trials()
        QtCore.QTimer.singleShot(50, self._force_render)

    def _go_to_next_trial(self):
        num_valid = len(self.valid_indices)
        if num_valid <= 0: 
            return
        idx_before = self.current_display_index
        if self.current_display_index == num_valid - 1:
            self.current_display_index = -1 
        elif self.current_display_index == -1:
            self.current_display_index = 0 
        else:
            self.current_display_index += 1
            
        print(f"{LOGP} Nav Next: {idx_before} -> {self.current_display_index}")
        self._load_and_display_trials()
        QtCore.QTimer.singleShot(50, self._force_render)

    # --- HELPERS TO FETCH ACTIVE TRIALS ---
    def _get_active_signal_and_name(self):
        store = self.kernel.get_service("DataStore")
        if not store:
            raise RuntimeError("DataStore missing.")
        sd = store.get_active_signal()
        if not isinstance(sd, SignalDataset):
            raise RuntimeError("No active signal selected.")
        sig_name = getattr(sd, "name", None) or getattr(sd, "signal_name", None) or getattr(sd, "id", None)
        if not sig_name and hasattr(sd, "get_name"):
            sig_name = sd.get_name()
        if not sig_name:
            raise RuntimeError("Active Signal has no name.")
        return sd, sig_name
        
    def _get_current_channel_name(self, sd: SignalDataset) -> str:
        """Return channel name to use with get_active_trials."""
        # 1) last TrialDataset
        try:
            tds = getattr(sd, "trials_dataset", None)
            if tds and len(tds) > 0:
                last_td = tds[-1]
                ch = getattr(last_td, "channel_name", None)
                if ch:
                    return str(ch)
        except Exception:
            pass

        # 2) known names list
        try:
            names = getattr(sd, "channel_names", None)
            if names and len(names) > 0:
                return str(names[0])
        except Exception:
            pass

        # 3) fallback if there are signals
        sig = getattr(sd, "signals", None)
        if sig is not None and getattr(sig, "shape", None) and sig.shape[0] > 0:
            # assume "ch-1" if names are missing
            return "ch-1"

        raise RuntimeError("No channel selected/found. Generate Trials first or select a channel.")


    def _fetch_active_trials(self):
        sd, sig_name = self._get_active_signal_and_name()
        if not hasattr(sd, "get_active_trials"):
            raise RuntimeError("SignalDataset.get_active_trials(...) not available.")

        # Resolve channel
        channel_name = self._get_current_channel_name(sd)

        # Call with channel
        result = sd.get_active_trials(sig_name, channel_name)

        td = None; meta = {}
        if isinstance(result, TrialDataset):
            td = result
        elif isinstance(result, (list, tuple)):
            for it in result:
                if isinstance(it, TrialDataset):
                    td = it
                elif isinstance(it, dict):
                    meta.update(it)
        elif isinstance(result, dict):
            meta.update(result)
            trials = meta.get("trials"); time_rel = meta.get("time_rel")
            if trials is not None and time_rel is not None:
                td = SimpleNamespace(
                    trials=np.asarray(trials),
                    time_rel=np.asarray(time_rel),
                    channel_name=meta.get("channel_name", "Unknown"),
                    metadata=meta,
                )
        if td is None:
            raise RuntimeError("get_active_trials() returned an unsupported format.")

        trials = np.asarray(td.trials)
        time_rel = np.asarray(getattr(td, "time_rel", meta.get("time_rel", None)))
        if time_rel is None:
            raise RuntimeError("Active trials missing time_rel.")
        if trials.ndim != 2:
            raise RuntimeError(f"Active trials must be 2D. Got {trials.shape}.")

        n_total = int(meta.get("total_trials", getattr(td, "total_trials", trials.shape[1])))
        orig_idx = meta.get("orig_indices", getattr(td, "orig_indices", None))
        if orig_idx is None:
            orig_idx = list(range(trials.shape[1]))
        else:
            orig_idx = list(map(int, orig_idx))
            
        # Use resolved channel_name if the result does not provide it
        chan = getattr(td, "channel_name", meta.get("channel_name", channel_name))

        return SimpleNamespace(
            time_rel=time_rel,
            trials=trials,
            orig_indices=orig_idx,
            channel_name=chan,
            total_trials=n_total,
        )

    # --- Data loading and plotting ---
    def _load_and_display_trials(self):
        """Load active trials via get_active_trials and show average or individual."""
        print(f"{LOGP} _load_and_display_trials(). Index: {self.current_display_index}")
        if not self.kernel:
            return self._clear_render("Kernel missing.")
        try:
            active = self._fetch_active_trials()
        except Exception as e:
            msg = str(e)
            print(f"{LOGP} fetch active trials error: {msg}")
            self._reset_state()
            # Clear message when there are no trials yet (show hint in status label instead of overlay)
            if "unsupported format" in msg or "get_active_trials" in msg:
                msg = "Generate Trials first"
            if "No channel selected" in msg or "Generate Trials" in msg or "not available" in msg:
                if self.ui and hasattr(self.ui, "trial_status_label"):
                    self.ui.trial_status_label.setText("Status: No trial data. Generate Trials first.")
                return self._clear_render("", show_message=False)
            return self._clear_render(msg)


        t = np.asarray(active.time_rel)
        trials = np.asarray(active.trials)          # (Ns, Tact)
        orig_indices = list(active.orig_indices)    # map to original indices
        total_trials = int(active.total_trials)
        channel_name = active.channel_name

        Tact = trials.shape[1]
        if Tact == 0:
            self._reset_state()
            if self.ui and hasattr(self.ui, "trial_status_label"):
                self.ui.trial_status_label.setText("Status: No active trials for this signal.")
            return self._clear_render("", show_message=False)
        if not (-1 <= self.current_display_index < Tact):
            self.current_display_index = -1

        # Populate valid_indices for navigation
        self.valid_indices = list(range(Tact))
        self.total_original_trials = int(total_trials) 

        if self.ui:
            self.ui.apply_button.setEnabled(self.current_display_index == -1 and Tact > 0)

        if self.current_display_index == -1:
            y = np.nanmean(trials, axis=1)
            title = f"Average ({Tact} Valid) - {channel_name}"
            status = f"Viewing Average / {Tact} Valid ({total_trials} Total)"
        else:
            idx = self.current_display_index
            y = trials[:, idx]
            orig_idx = orig_indices[idx] if idx < len(orig_indices) else idx
            title = f"Trial {orig_idx + 1} - {channel_name}"
            status = f"Viewing Valid {idx + 1}/{Tact} (Orig. {orig_idx + 1}) / {total_trials} Total"

        if self.ui:
            self.ui.trial_status_label.setText(status)

        if t.ndim != 1 or y.ndim != 1:
            return self._clear_render(f"Invalid shapes: time={t.shape}, data={y.shape}")
        if t.shape[0] != y.shape[0]:
            return self._clear_render(f"Length mismatch: time={t.shape[0]}, data={y.shape[0]}")

        self._plot_curve(t, y, title, channel_name)

    # --- VTK display logic ---
    def _ensure_vtk(self):
        """Ensure the interactor and view exist and are added to the layout."""
        
        if (self.vtk_interactor and self.vtk_view and 
            self.ui.plotArea.layout() and 
            self.ui.plotArea.layout().indexOf(self.vtk_interactor) != -1):
            
            if not self.vtk_interactor.isEnabled():
                try: 
                    self.vtk_interactor.Enable()
                except Exception as e:
                    print(f"{LOGP} Error re-enabling VTK: {e}")
            return  # already set

        print(f"{LOGP} _ensure_vtk(): Setting up VTK...")
        
        try:
            self.vtk_interactor = QVTKRenderWindowInteractor(self.ui.plotArea)
            self.ui.plotArea.setLayout(QtWidgets.QVBoxLayout())
            self.ui.plotArea.layout().setContentsMargins(0, 0, 0, 0)
            self.ui.plotArea.layout().addWidget(self.vtk_interactor)
            print(f"{LOGP} VTK Interactor embedded.")

            self.vtk_view = vtk.vtkContextView()
            
            print(f"{LOGP} DEBUG: Setting RenderWindow on vtkContextView.")
            self.vtk_view.SetRenderWindow(self.vtk_interactor.GetRenderWindow())
            print(f"{LOGP} DEBUG: RenderWindow set. Setting background.")
            
            self.vtk_view.GetRenderer().SetBackground(vtk.vtkNamedColors().GetColor3d("WhiteSmoke"))

            print(f"{LOGP} Using QVTKRenderWindowInteractor directly.")
            
            print(f"{LOGP} DEBUG: Attempting to get VTK Interactor.")
            interactor = self.vtk_interactor.GetRenderWindow().GetInteractor()
            print(f"{LOGP} DEBUG: VTK Interactor object retrieved: {interactor is not None}")
            
            if interactor and not interactor.GetInteractorStyle():
                print(f"{LOGP} DEBUG: Setting vtkContextInteractorStyle.")
                interactor.SetInteractorStyle(vtk.vtkContextInteractorStyle())
                print(f"{LOGP} Explicitly set vtkContextInteractorStyle to fix zoom deformation and crash.")
            
            print(f"{LOGP} MouseMove observer is DISABLED to prevent interaction crash.")
            
            print(f"{LOGP} DEBUG: Calling Initialize.")
            self.vtk_interactor.Initialize()
            print(f"{LOGP} DEBUG: Initialize finished.")
            
            print(f"{LOGP} VTK Initialized.")
            
        except Exception as e:
            print(f"{LOGP} CRITICAL VTK Setup Error: {e}")
            self._cleanup_vtk_references()
            if self.ui and self.ui.plotArea:
                lbl = QLabel(f"VTK Error:\n{e}", self.ui.plotArea)
                lbl.setAlignment(QtCore.Qt.AlignCenter)
                if self.ui.plotArea.layout():
                    self.ui.plotArea.layout().addWidget(lbl)

    def _cleanup_vtk_references(self):
        """Clean VTK references to avoid memory leaks."""
        self.vtk_interactor = None
        self.vtk_view = None
        self.chart = None
        self.vtk_menu = None
        print(f"{LOGP} VTK references cleaned.")


    def _plot_curve(self, t: np.ndarray, y: np.ndarray, title: str = "", ch_name: str = ""):
        """Draw arrays 't' and 'y' in the VTK chart."""
        
        if self.vtk_view is None:
            self._ensure_vtk()

        if not self.vtk_view or not self.vtk_interactor:
            if self.widget: 
                self.alerts.error("Failed to initialize VTK view.", "VTK Error")
            return

        try:
            scene = self.vtk_view.GetScene()
            scene.ClearItems()
            renderer = self.vtk_view.GetRenderer()
            
            renderer.GetActors2D().RemoveAllItems() 
            
            # Fix stale message: force render after clearing 2D actors
            self.vtk_view.GetRenderWindow().Render() 
            
            renderer.SetBackground(vtk.vtkNamedColors().GetColor3d("WhiteSmoke"))

            # --- clean data and convert to VTK safely (nps.numpy_to_vtk) ---
            finite_mask = np.isfinite(t) & np.isfinite(y)
            valid_mask = finite_mask.copy()
            
            t_valid = t[valid_mask]
            y_valid = y[valid_mask]
            
            n_points = t_valid.shape[0]

            if n_points == 0:
                raise RuntimeError("No valid points to plot (NaN/Inf).")
            
            vtk_t = nps.numpy_to_vtk(t_valid.astype(np.float64), deep=True)
            vtk_t.SetName("Time (s)")
            vtk_y = nps.numpy_to_vtk(y_valid.astype(np.float64), deep=True)
            vtk_y.SetName("Amplitude")

            table = vtk.vtkTable()
            table.AddColumn(vtk_t)
            table.AddColumn(vtk_y)

            self.chart = vtk.vtkChartXY()
            scene.AddItem(self.chart)
            plot = self.chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, "Time (s)", "Amplitude")
            plot.SetWidth(1.5)

            color = "Crimson" if self.current_display_index == -1 else "SteelBlue"
            plot.GetPen().SetColor(vtk.vtkNamedColors().GetColor4ub(color))

            self.chart.SetTitle(title)
            axis_b = self.chart.GetAxis(vtk.vtkAxis.BOTTOM); axis_b.SetTitle("Time (s)")
            axis_l = self.chart.GetAxis(vtk.vtkAxis.LEFT);   axis_l.SetTitle("Amplitude")
            axis_b.SetGridVisible(True); axis_l.SetGridVisible(True)

            max_abs = float(np.nanmax(np.abs(y_valid)))
            if not np.isfinite(max_abs) or max_abs > 1e12:
                print(f"{LOGP} WARNING: very large amplitude (|y| max ≈ {max_abs:.3e}). Check signal units/scale.")

            self.chart.RecalculateBounds()
            # Context menu consistent with other plugins
            try:
                if VTKContextMenu is not None and self.vtk_interactor is not None and self.active_signal is not None:
                    self.vtk_menu = VTKContextMenu(self.chart, self.vtk_interactor,
                                                   self.active_signal.name, ch_name,
                                                   self.meta.id, parent=self.widget)
            except Exception as e:
                if self.alerts:
                    self.alerts.error(f"Error creating the context menu.\n {str(e)}")

            print(f"{LOGP} _plot_curve: Plot '{title}' with {n_points} valid points.")
            # Hide watermark once a plot is shown
            try:
                if self.mainwin:
                    self.mainwin.hide_watermark()
            except Exception:
                pass

        except RuntimeError as re:
            print(f"{LOGP} _plot_curve: runtime plot error: {re}")
            self.chart = None
            txt = vtk.vtkTextActor()
            txt.SetInput(f"No data to display for:\n{title}\nError: {re}")
            prop = txt.GetTextProperty()
            prop.SetColor(0.2, 0.2, 0.2); prop.SetJustificationToCentered()
            prop.SetVerticalJustificationToCentered(); prop.SetFontSize(16)
            
            size = renderer.GetSize()
            txt.SetPosition(size[0] / 2, size[1] / 2)
            renderer.AddActor2D(txt)
            
        except Exception as e:
            print(f"{LOGP} Error during _plot_curve: {e}")
            self._clear_render(f"Error plotting:\n{e}")

    # --- Utility functions ---

    def _reset_state(self):
        """Reset internal plugin state."""
        print(f"{LOGP} Resetting state...")
        self.current_display_index = -1
        self.valid_indices = []
        self.total_original_trials = 0
        self.discarded_indices = set()
        self.modified_indices = set()
        
        if self.ui:
            try:
                self.ui.trial_status_label.setText("Status: N/A")
                self.ui.point_a.setText("0.0")
                self.ui.point_b.setText("0.0")
                self.ui.apply_button.setEnabled(False)
            except Exception as e:
                print(f"{LOGP} Error resetting UI state: {e}")

    def _clear_render(self, message="", show_message=True):
        """Clear the VTK view and optionally show a message."""
        
        if self.vtk_view is None:
            self._ensure_vtk()
        
        if not self.vtk_view or not self.vtk_interactor:
            print(f"{LOGP} VTK not available to clear.")
            return
            
        print(f"{LOGP} Clearing render. Msg: '{message}'")
        try:
            scene = self.vtk_view.GetScene()
            scene.ClearItems()
            renderer = self.vtk_view.GetRenderer()
            
            renderer.GetActors2D().RemoveAllItems()
            
            renderer.SetBackground(vtk.vtkNamedColors().GetColor3d("WhiteSmoke"))
            
            if message and show_message:
                txt = vtk.vtkTextActor()
                txt.SetInput(message)
                prop = txt.GetTextProperty()
                prop.SetColor(0.2, 0.2, 0.2)
                prop.SetJustificationToCentered()
                prop.SetVerticalJustificationToCentered()
                prop.SetFontSize(16)
                
                size = renderer.GetSize()
                if size[0] > 0 and size[1] > 0:
                   txt.SetPosition(size[0] / 2, size[1] / 2)
                else:
                   txt.SetPosition(200, 200) 
                    
                renderer.AddActor2D(txt)
                
            self.vtk_view.GetRenderWindow().Render()
        except Exception as e:
            print(f"{LOGP} Error during _clear_render: {e}")

    def _ensure_visibility_filter(self):
        """Install an event filter so we refresh whenever the widget is shown again."""
        if not self.widget or self._visibility_filter is not None:
            return
        self._visibility_filter = _WidgetVisibilityFilter(self)
        self.widget.installEventFilter(self._visibility_filter)

    def _on_widget_shown(self):
        """Triggered when the stacked widget makes this plugin visible again."""
        if not self.widget:
            return
        print(f"{LOGP} Widget shown -> refreshing view.")
        if self._refresh_timer.isActive():
            self._refresh_timer.stop()
        try:
            if self.vtk_interactor and not self.vtk_interactor.isEnabled():
                self.vtk_interactor.Enable()
            if self.vtk_interactor:
                render_window = self.vtk_interactor.GetRenderWindow()
                if render_window:
                    interactor = render_window.GetInteractor()
                    if interactor and not interactor.GetEnabled():
                        interactor.Enable()
        except Exception:
            pass
        self._refresh_view_coalesced()

    def _on_widget_hidden(self):
        """Triggered when the plugin is hidden; stop pending refresh."""
        if self._refresh_timer.isActive():
            self._refresh_timer.stop()

    def _on_data_updated(self, topic: str, payload: object):
        """Listen to kernel events and coalesce refreshes to avoid UI lag."""
        try:
            if topic in ["signal_added", "active_signal_changed", "trials_generated", "trial_discard_updated"]:
                if self.widget and self.widget.isVisible():
                    print(f"{LOGP} Event '{topic}' received. Coalescing update...")

                    if hasattr(self, "_refresh_timer"):
                        self._refresh_timer.start()
                    else:
                        self._reset_state()
                        if self.vtk_interactor and not self.vtk_interactor.isEnabled():
                            try:
                                self.vtk_interactor.Enable()
                            except Exception:
                                pass
                        self._load_and_display_trials()
                        QtCore.QTimer.singleShot(50, self._force_render)
        except Exception as e:
            print(f"{LOGP} Error in _on_data_updated: {e}")

    def _on_apply_finished(self, modified_td):
        """Signal: worker finished successfully."""
        print(f"{LOGP} finished received, type={type(modified_td)}")
        try:
            if modified_td:
                self.alerts.info("Changes applied to all valid trials.")
            else:
                self.alerts.info("No modifications were applied.")
        finally:
            # Re-enable UI and refresh
            try:
                if self.vtk_interactor:
                    try:
                        self.vtk_interactor.Enable()
                    except Exception:
                        pass
                panel = self.ui.paramsLayout
                self.ui.apply_button.setEnabled(True)
                self.ui.mode_combo.setEnabled(True)
                self.ui.prev_button.setEnabled(True)
                self.ui.next_button.setEnabled(True)

                # Recarga y render forzado
                self._reset_state()
                self._load_and_display_trials()
                QtCore.QTimer.singleShot(50, self._force_render)
            except Exception as e:
                print(f"{LOGP} _on_apply_finished UI restore error: {e}")

    def _on_apply_error(self, msg):
        """Signal: worker reported an error."""
        try:
            self.alerts.error(msg, "Apply Error")
        finally:
            try:
                if self.vtk_interactor:
                    try:
                        self.vtk_interactor.Enable()
                    except Exception:
                        pass
                panel = self.ui.paramsLayout
                self.ui.apply_button.setEnabled(True)
                self.ui.mode_combo.setEnabled(True)
                self.ui.prev_button.setEnabled(True)
                self.ui.next_button.setEnabled(True)
                QtCore.QTimer.singleShot(50, self._force_render)
            except Exception as e:
                print(f"{LOGP} _on_apply_error UI restore error: {e}")
