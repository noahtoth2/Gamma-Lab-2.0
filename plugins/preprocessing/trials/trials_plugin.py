import sys
from PyQt5 import QtWidgets, QtCore
from PyQt5.QtWidgets import QWidget
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.services.data_store import DataStore
from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from core.filters.trials import cut_trials_single_channel
from core.utils.adapters import trials_matrix_to_vtk_table
from plugins.preprocessing.trials.trial_plugin_ui import Ui_Trials

class TrialsPlugin(IPlugin):

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)
        self.ui = None

        self.params = {
            "channel": 0,
            "threshold": 0.7,
            "t0": -0.05,
            "t1": 4.0,
            "stim_count": 1,
            "inter_stim_time": 0.1
        }




        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None
        self.chart: vtk.vtkChartXY | None = None

        self.visible_trials = []
        self.last_td: TrialDataset | None = None
        self._active_ds: SignalDataset | None = None
        
        self.vtk_menu: VTKContextMenu | None = None



    def stop(self):
        self._log("stop() – tearing down VTK")
        self.vtk_view.GetRenderWindow().GetInteractor().Disable()

    def process(self, data: any):
        self._log(f"process{data}")
        if self.vtk_interactor:
            self.vtk_interactor.Enable()

        #self._populate_channels_once()

    # -------------- UI ---------------------
    def get_widget(self, parent=None):
        if self.widget is None:
            self._log("get_widget: creating UI")
            self.ui = Ui_Trials(parent)
            self.widget = self.ui
            self.alerts.parent = self.widget

            self._ensure_vtk()
            self.ui.Btn_generate_trials.clicked.connect(self._on_generate_clicked)
            self._init_controls()

            self._populate_channels_once()

            # Buttons to navigate between trials
            self.ui.Btn_prev_trial.clicked.connect(lambda: self.navigate_trial(-1))
            self.ui.Btn_next_trial.clicked.connect(lambda: self.navigate_trial(1))
        else:
            self.widget.setParent(parent)

        return self.widget

    def _ensure_vtk(self):
        self._log("ensure_vtk(): enter")
        
        self.vtk_interactor = QVTKRenderWindowInteractor(self.ui.plotArea)
        self.vtk_interactor.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.vtk_interactor.destroyed.connect(self._on_vtk_widget_destroyed)
        self.ui.plotArea.setLayout(QtWidgets.QVBoxLayout())
        self.ui.plotArea.layout().setContentsMargins(0, 0, 0, 0)
        self.ui.plotArea.layout().addWidget(self.vtk_interactor)
        self._log("ensure_vtk(): embedded interactor")

        self.vtk_view = vtk.vtkContextView()
        self.vtk_view.SetRenderWindow(self.vtk_interactor.GetRenderWindow())
        self.vtk_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        try:
            self.vtk_interactor.Initialize()
        except Exception:
            pass
        
        if self.vtk_menu is None:
            base_scope = {
                "view_id": "trials",
                "trial_id": None,
                "channel_name": None,
                "plugin": "trials",
                "domain": "time",
                "graph_id": "trials:blank"
            }
            self.vtk_menu = VTKContextMenu(
                chart=None,
                vtk_widget=self.vtk_interactor,
                plugin_name="trials",
                measurements_enabled=True,
                measure_scope=base_scope,
                parent=self.widget
            )
            self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))
        self._log("ensure_vtk(): scheduled init")

    def _on_vtk_widget_destroyed(self, *args):
        # extra safety if Qt destroys the widget
        try:
            if self.vtk_view is not None:
                rw = self.vtk_view.GetRenderWindow()
                if rw is not None:
                    try:
                        rw.AbortRenderOn()
                    except Exception:
                        pass
                    try:
                        rw.Finalize()
                    except Exception:
                        pass
        except Exception as e:
            self._log("_on_vtk_widget_destroyed:", e)
        finally:
            self.vtk_view = None
            self.vtk_interactor = None
            self.chart = None
    def _init_controls(self):
        self._log("_init_controls: set defaults")
        self.ui.thresholdDoubleSpinBox.setRange(0.0, 1e12)
        self.ui.thresholdDoubleSpinBox.setValue(self.params["threshold"])

        self.ui.initialTimeDoubleSpinBox.setRange(-3600.0, 0.0)
        self.ui.initialTimeDoubleSpinBox.setValue(self.params["t0"])

        self.ui.finalTimeDoubleSpinBox.setRange(0.001, 3600.0)
        self.ui.finalTimeDoubleSpinBox.setValue(self.params["t1"])

        self.ui.stimNumberSpinBox.setRange(0, 1_000_000)
        self.ui.stimNumberSpinBox.setValue(self.params["stim_count"] or 0)

        self.ui.interStimTimeDoubleSpinBox.setDecimals(6)
        self.ui.interStimTimeDoubleSpinBox.setSingleStep(0.01)
        self.ui.interStimTimeDoubleSpinBox.setValue(self.params["inter_stim_time"] or 0.0)
        
        self.ui.stimNumberSpinBox.valueChanged.connect(self._on_stim_count_changed)
        self._apply_interstim_ui_rules(self.ui.stimNumberSpinBox.value())

    
    def on_kernel_event(self, topic: str, payload: object):
        """
        Listen to events emitted by the Kernel.
        """
        if topic == "signal_active_changed" or topic =="signal_added":
            print(f"New signal changed: {payload}")
            self._populate_channels_once()



    def _on_stim_count_changed(self, val: int):
        """Callback when the number of stimuli changes: apply rules to the ISI field."""
        try:
            self._apply_interstim_ui_rules(int(val))
        except Exception as e:
            self._log("_on_stim_count_changed error:", e)
        
    def _apply_interstim_ui_rules(self, stim_count: int):
        """
        - stim_count <= 1: disable ISI and set it to 0.0
        - stim_count >= 2: enable ISI, require > 0 (suggested minimum 1 ms)
        """
        isi = self.ui.interStimTimeDoubleSpinBox

        if stim_count is None or stim_count <= 1:
            isi.blockSignals(True)
            isi.setEnabled(False)
            isi.setMinimum(0.0)
            isi.setValue(0.0)
            isi.setToolTip("Inter-stim time does not apply when there are 0 or 1 stimuli per trial.")
            isi.blockSignals(False)
            return

        # stim_count >= 2
        isi.blockSignals(True)
        isi.setEnabled(True)
        isi.setMinimum(0.001)
        if isi.value() <= 0.0:
            isi.setValue(0.1)
        isi.setToolTip("Inter-stimulus time (s). Must be > 0 when there are ≥2 stimuli per trial.")
        isi.blockSignals(False)
        

    def _populate_channel_combos(self, ds: SignalDataset):
        """
        Fill channelComboBox and stimChannelComboBox with the same names (userData = index).
        - Channel → default index 0
        - Stim Channel → default last channel
        """
        # Get references (tolerant if UI does not yet have the stim combo)
        cb_main = getattr(self.ui, "channelComboBox", None)
        cb_stim = getattr(self.ui, "stimChannelComboBox", None)

        if cb_main is None:
            return  # nothing to do

        # Build list of names
        names = []
        try:
            if getattr(ds, "channel_names", None):
                names = [str(n) for n in ds.channel_names]
        except Exception as e:
            self._log("channel_names error:", e)

        if not names:
            # Fallback by shape
            C = 0
            try:
                sig = getattr(ds, "signals", None)
                C = int(sig.shape[0]) if sig is not None else 0
            except Exception:
                C = 0
            names = [f"ch-{i+1}" for i in range(C)]
            self._log("fallback names by shape:", len(names))

        # Populate main combo
        cb_main.blockSignals(True)
        cb_main.clear()
        for i, name in enumerate(names):
            cb_main.addItem(name, i)
        cb_main.setCurrentIndex(0 if names else -1)
        cb_main.blockSignals(False)

        # Populate stim combo (if present in UI)
        if cb_stim is not None:
            cb_stim.blockSignals(True)
            cb_stim.clear()
            for i, name in enumerate(names):
                cb_stim.addItem(name, i)
            # default to the LAST channel
            default_idx = (len(names) - 1) if names else -1
            cb_stim.setCurrentIndex(default_idx)
            cb_stim.setToolTip("Channel used to detect onsets/stimuli")
            cb_stim.blockSignals(False)


    def _populate_channels_once(self):
        """Try to load the active signal and populate the combo (silent if none)."""
        ds = self.get_active_signal()
        if ds:
            self._populate_channel_combos(ds)
        else:
            self._log("_populate_channels_once: no active signal (yet)")
    
    # -------------- Acciones UI -----------------
    def _on_generate_clicked(self):
        #self._log("_on_generate_clicked")

        ds = self.get_active_signal()
        if ds is None:
            return
        
        if self.ui.channelComboBox.count() == 0:
            self._populate_channel_combos(ds)
            if self.ui.channelComboBox.count() == 0:
                self.alerts.warning("The active signal has no available channels.")
                return

        ch = self.ui.channelComboBox.currentData()
        if ch is None:
            ch = self.ui.channelComboBox.currentIndex()
        if ch is None or ch < 0:
            self.alerts.warning("Select a channel.")
            return
        
        stim_ch = self.ui.stimChannelComboBox.currentData()
        if stim_ch is None:
            stim_ch = self.ui.stimChannelComboBox.currentIndex()
        if stim_ch is None or stim_ch < 0:
            self.alerts.warning("Select a stimulus channel.")

            return

        th   = float(self.ui.thresholdDoubleSpinBox.value())
        t0   = float(self.ui.initialTimeDoubleSpinBox.value())
        t1   = float(self.ui.finalTimeDoubleSpinBox.value())
        mode = self.ui.endModeCombo.currentData() or "fixed"
        stim = int(self.ui.stimNumberSpinBox.value())
        stim = None if stim < 0 else stim
        inter_stim_time  = float(self.ui.interStimTimeDoubleSpinBox.value())
        inter_stim_time  = None if inter_stim_time <= 0 else inter_stim_time

        if mode == "fixed" and not (t1 > t0):
            self.alerts.warning("t1 must be greater than t0.")
            return

        self._log("params →", dict(channel=int(ch), threshold=th, t0=t0, t1=t1,
                                end_mode=mode, stim_expected=stim, inter_stim_time=inter_stim_time))

        try:
            td = cut_trials_single_channel(
            ds=ds,
            channel=int(ch),                  # target channel to cut
            stim_channel=None if stim_ch is None else int(stim_ch),  # stimulus channel to detect onsets
            threshold=th,
            t0=t0, t1=t1,
            end_mode=mode,
            stim_expected=stim,
            inter_stim_time=inter_stim_time
        )
        except Exception as e:
            self._log("cut_trials_single_channel error:", e)
            self.alerts.error(f"Error generating trials: {e}")
            return

        #self._log("TD listo:", td.trials.shape, td.time_rel.shape, "onsets:", len(td.onsets_s))

        try:
            ds.add_trial_dataset(td)
            ds.clear_discarded_trials()
            
        except Exception as e:
            self._log("add_trial_dataset warning:", e)

        # Show only the first trial
        self.last_td = td
        self.navigate_trial(0)

        self._notify(f"Trials: T={td.trials.shape[1]}, Ns={td.trials.shape[0]}, channel='{td.channel_name}'")
   

    # -------------- Navigation between trials ----------------------
    def navigate_trial(self, direction: int):
        """
        Show next or previous trial according to 'direction'.
        direction = +1 → next
        direction = -1 → previous
        """
        if not self.last_td:
            self.alerts.info("No trials loaded.", "Navigation")
            return

        td = self.last_td
        sd = self.get_active_signal()
        
        _, T = td.trials.shape
        if T == 0:
            self.alerts.info("No trials available.", "Navigation")
            return

        if not self.visible_trials:
            self.visible_trials = [0]

        current = self.visible_trials[0]
        new_idx = (current + direction) % T  # circular navigation
        self.visible_trials = [new_idx]

        #self._log(f"Navigating trial {new_idx + 1}/{T}")
        self._render_trials(td)

        self._update_trial_ui(sd, new_idx, T, None)

        # Connect the button
        try:
            self.ui.Btn_discard_trial.clicked.disconnect()
        except Exception:
            pass
        self.ui.Btn_discard_trial.clicked.connect(lambda _, idx=new_idx: self._on_discard_trial(idx, T))

        self._notify(f"Trial {new_idx + 1} of {T}")
   


    def _on_discard_trial(self, index: int, T: int):

        ds = self.get_active_signal()
        ch = self.ui.channelComboBox.currentText()

        if not ds:
            return

        """Toggle discard state of the current trial (add or remove from SignalDataset list)."""
        if not self.last_td:
            self.alerts.warning("No trials loaded.", "Discard trial")
            return
    
      
        if not self.visible_trials:
            self.alerts.warning("No trial selected.", "Discard trial")
            return

        estado = ds.is_trial_discarded(ds.name, ch, index)
        print(f"Trial {index + 1} discarded: {estado}")

        if estado:
            # Include again
            ds.include_trial(ds.name, ch, index)
            self._update_trial_ui(ds, index, T, False)
            self.alerts.info(f"Trial {index + 1} included.", "Include trial")
        else:
            # Mark as discarded
            ds.discard_trial(ds.name, ch, index)
            self._update_trial_ui(ds, index, T, True)
            self.alerts.info(f"Trial {index + 1} discarded.", "Discard trial")

    def _update_trial_ui(self, ds: SignalDataset, index: int, total: int = None, estado_descartado: bool = None):
        """Update current trial label/button depending on discard state."""
        total_text = f"/{total}" if total else ""
        ch = self.ui.channelComboBox.currentText()

        if estado_descartado is None:
            estado_descartado = ds.is_trial_discarded(ds.name, ch, index)

        if estado_descartado:
            self.ui.currentTrialLabel.setText(f"Current trial: {index + 1} (discarded){total_text}")
            self.ui.currentTrialLabel.setStyleSheet("color: red; font-weight: bold;")
            self.ui.Btn_discard_trial.setText("Include")
        else:
            self.ui.currentTrialLabel.setText(f"Current trial: {index + 1}{total_text}")
            self.ui.currentTrialLabel.setStyleSheet("color: black; font-weight: bold;")
            self.ui.Btn_discard_trial.setText("Discard")

    # -------------- Render ----------------------
    def _render_trials(self, td: TrialDataset):
        self._log("_render_trials: enter")
        
        if self.vtk_view is None:
            self._log("  vtk_view not initialized → ensure_vtk()")
            self._ensure_vtk()
        if self.vtk_view is None:
            self._log("  no VTK view, abort")
            return

        table = trials_matrix_to_vtk_table(td.time_rel, td.trials)
        
        scene = self.vtk_view.GetScene()
        scene.ClearItems()
        self.chart = vtk.vtkChartXY()
        scene.AddItem(self.chart)

        Ns, T = td.trials.shape
        sel = sorted({i for i in self.visible_trials if 0 <= i < T})
        if not sel:
            sel = [1] if T > 1 else ([0] if T == 1 else [])

        for idx in sel:
            plot = self.chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, 0, idx + 1)
            plot.SetWidth(1.0)
            plot.SetLabel(f"Trial {idx+1}")

        ax_b = self.chart.GetAxis(vtk.vtkAxis.BOTTOM)
        ax_l = self.chart.GetAxis(vtk.vtkAxis.LEFT)
        ax_b.SetGridVisible(True); ax_l.SetGridVisible(True)
        ax_b.SetTitle("Time (s)")
        ax_l.SetTitle(td.unit or "Amplitude")
        
        ch_name = getattr(td, "channel_name", "") or "channel"
        trials_txt = ", ".join(str(i+1) for i in sel)
        self.chart.SetTitle(f"Trial {trials_txt} — {ch_name}")


        try:
            self.vtk_view.GetRenderWindow().Render()
            self._log("  render OK (interactive ContextView)")
        except Exception as e:
            self._log("Render error:", e)
            
        if self.vtk_menu is not None:
            self.vtk_menu.set_chart(self.chart)
            ds = self.get_active_signal()
            signal_name = getattr(ds, "name", "signal")
            trial_idx = (self.visible_trials[0] if self.visible_trials else 0)

            curr_channel_name = getattr(td, "channel_name", "") or "channel"

            graph_uid = f"trial {trial_idx}"
            print(f"trial idx={trial_idx}")
            self.vtk_menu.on_view_rebuilt(
                self.chart,
                view_id="trials",
                trial_id=trial_idx,
                channel_name=f"{signal_name}:{curr_channel_name}",
                plugin="trials",
                domain="time",
                graph_id=graph_uid
            )
