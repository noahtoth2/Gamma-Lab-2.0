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
from core.filters.trials import cut_trials_single_channel, mv_to_unit
from core.utils.adapters import trials_matrix_to_vtk_table
from plugins.preprocessing.trials.trial_plugin_ui import Ui_Trials
from functools import partial
<<<<<<< HEAD
=======
from core.utils.submuestreo import agregar_columna
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238


def cortar_trials(ds, ctx=None, **params):
    """Cuts the trials of one channel. Reads `ds`, never writes it, so it can run in the TaskService."""
    return cut_trials_single_channel(ds=ds, **params)


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
            self.ui.Btn_clear_params.clicked.connect(self._on_clear_params_clicked)
            self._init_controls()

            self._populate_channels_once()
            self._restore_existing_trials_if_any()

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

        self.ui.stimChannelComboBox.currentIndexChanged.connect(lambda _: self._update_threshold_unit())
        self._update_threshold_unit()

    # -------------- Threshold units -----------------
    def _stim_unit(self) -> str:
        """Unit of the selected stimulus channel ("" if unknown)."""
        ds = self.get_active_signal(silent=True) if self.mainwin else None
        idx = self.ui.stimChannelComboBox.currentData()
        if ds is None or idx is None:
            return ""
        units = list(getattr(ds, "units", []) or [])
        return str(units[idx]) if 0 <= idx < len(units) else ""

    def _update_threshold_unit(self):
        """The threshold is shown in mV and converted to the stimulus channel's
        unit before detecting. A channel without a voltage unit (a.u., pA...)
        cannot be expressed in mV, so its own unit is shown instead."""
        spin = self.ui.thresholdDoubleSpinBox
        unit = self._stim_unit()
        ch_name = self.ui.stimChannelComboBox.currentText()
        if not unit or mv_to_unit(1.0, unit) is not None:
            spin.setSuffix(" mV")
            extra = (f"\nThe stimulus channel '{ch_name}' is in {unit}; the value is converted."
                     if unit and unit.strip().lower() != "mv" else "")
            spin.setToolTip("Stimulus detection threshold in mV (absolute value)." + extra)
        else:
            spin.setSuffix(f" {unit}")
            spin.setToolTip(f"The stimulus channel '{ch_name}' is in {unit}, which is not a "
                            f"voltage: the threshold is applied in {unit}, not in mV.")

    def _show_recipe_threshold(self, td: TrialDataset):
        """Show the stimulus channel and threshold the trials were cut with,
        back in mV (the recipe stores it in the stimulus channel's unit)."""
        params = (td.metadata or {}).get("generation_params") or {}
        if "threshold" not in params:
            return
        stim = params.get("stim_channel")
        if stim is not None:
            i = self.ui.stimChannelComboBox.findData(int(stim))
            if i >= 0:
                self.ui.stimChannelComboBox.setCurrentIndex(i)
        factor = mv_to_unit(1.0, self._stim_unit())
        value = float(params["threshold"])
        self.ui.thresholdDoubleSpinBox.setValue(value / factor if factor else value)
        self._update_threshold_unit()

    def _on_clear_params_clicked(self):
        self.ui.thresholdDoubleSpinBox.setValue(self.params["threshold"])
        self.ui.initialTimeDoubleSpinBox.setValue(self.params["t0"])
        self.ui.finalTimeDoubleSpinBox.setValue(self.params["t1"])
        self.ui.stimNumberSpinBox.setValue(self.params["stim_count"] or 0)
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
            self._update_threshold_unit()


    def _populate_channels_once(self):
        """Try to load the active signal and populate the combo (silent if none)."""
        ds = self.get_active_signal(silent=True)
        if ds:
            self._populate_channel_combos(ds)
        else:
            self._log("_populate_channels_once: no active signal (yet)")

    def _restore_existing_trials_if_any(self):
        """Show the active signal's most recent TrialDataset, if it already has
        one (e.g. just restored from an opened project), instead of a blank view."""
        ds = self.get_active_signal(silent=True)
        if not ds or ds.number_of_trials_dataset() == 0:
            return
        td = ds.get_all_trials_datasets()[-1]
        idx = self.ui.channelComboBox.findText(td.channel_name)
        if idx >= 0:
            self.ui.channelComboBox.setCurrentIndex(idx)
        self._show_recipe_threshold(td)
        self.last_td = td
        self.visible_trials = [0]
        self._render_trials(td)
        self._update_trial_ui(ds, 0, td.trials.shape[1], None)

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

        # The threshold is entered in mV; detection compares it against the raw
        # stimulus channel, so it goes in that channel's unit. A channel without
        # a voltage unit has no mV equivalent and keeps the value as entered.
        th_shown = float(self.ui.thresholdDoubleSpinBox.value())
        stim_unit = self._stim_unit()
        th_native = mv_to_unit(th_shown, stim_unit) if stim_unit else th_shown
        if th_native is None:
            th_native = th_shown
            th_text = f"{th_shown:g} {stim_unit}"
        else:
            th_text = f"{th_shown:g} mV"
        th = th_native
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

<<<<<<< HEAD
<<<<<<< HEAD
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

        # The recipe keeps the threshold in the stimulus channel's unit: it is
        # passed straight back to cut_trials_single_channel on project open.
        td.metadata["threshold_display"] = th_text
        td.metadata["generation_params"] = {
            "channel": int(ch),
            "stim_channel": None if stim_ch is None else int(stim_ch),
=======
        params = {
            "channel": int(ch),                  # target channel to cut
            "stim_channel": None if stim_ch is None else int(stim_ch),   # stimulus channel to detect onsets
>>>>>>> 999eeb239d85a9390180f810f24343c2c1c29382
=======
        params = {
            "channel": int(ch),                  # target channel to cut
            "stim_channel": None if stim_ch is None else int(stim_ch),   # stimulus channel to detect onsets
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238
            "threshold": th,
            "t0": t0, "t1": t1,
            "end_mode": mode,
            "stim_expected": stim,
            "inter_stim_time": inter_stim_time,
        }

        # The cut runs in the TaskService (R71); the dataset is updated when it finishes
        def al_fallar(m):
            self._log("cut_trials_single_channel error:", m)
            self.alerts.error(f"Error generating trials: {m}")

<<<<<<< HEAD
        self.run_task(cortar_trials, partial(self._on_trials_cut, ds, params), on_failed=al_fallar,
                      ds=ds, **params)

    def _on_trials_cut(self, ds, params, td):
=======
        self.run_task(cortar_trials, partial(self._on_trials_cut, ds, params, th_text), on_failed=al_fallar,
                      ds=ds, **params)

    def _on_trials_cut(self, ds, params, th_text, td):
        # The recipe keeps the threshold in the stimulus channel's unit: it is
        # passed straight back to cut_trials_single_channel on project open.
        td.metadata["threshold_display"] = th_text
>>>>>>> f19cc48027c8d0790d3a1557c7f2977055e15238
        td.metadata["generation_params"] = dict(params)

        try:
            ds.add_trial_dataset(td)
            ds.clear_discarded_trials()
            self.mark_project_dirty()

        except Exception as e:
            self._log("add_trial_dataset warning:", e)

        # Show only the first trial
        self.last_td = td
        self.visible_trials = [0]
        self.navigate_trial(0)

        # Avisar a la ventana principal y a los demas plugins (indicador de
        # trial, Remove Artifact...). Antes este evento solo lo emitia Open Signal.
        self.kernel.emit_event("trials_generated", {"signal": ds.name, "channel": td.channel_name})

        self._notify(f"Trials: {td.trials.shape[1]} trials generados en '{td.channel_name}' "
                     f"con umbral {th_text} (Ns={td.trials.shape[0]}); descartes reiniciados")
   

    # -------------- Navigation between trials ----------------------
    def navigate_trial(self, direction: int):
        """
        Show next or previous trial according to 'direction'.
        direction = +1 → next
        direction = -1 → previous
        """
        if not self.last_td:
            self.alerts.warning("No trials loaded.", "Navigation")
            return

        td = self.last_td
        sd = self.get_active_signal()
        
        _, T = td.trials.shape
        if T == 0:
            self.alerts.warning("No trials available.", "Navigation")
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

        state = self.current_trial_state() or {}
        if state.get("discarded"):
            self._notify(f"Trial {new_idx + 1} of {T} (discarded)")
        elif state.get("note"):
            self._notify(f"Trial {new_idx + 1} of {T} (valid {state['position']}/{state['total']})")
        else:
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
        self.mark_project_dirty()
        self.kernel.emit_event("trial_discard_updated",
                               {"signal": ds.name, "channel": ch, "index": index})

    def _update_trial_ui(self, ds: SignalDataset, index: int, total: int = None, estado_descartado: bool = None):
        """Update current trial label/button depending on discard state."""
        total_text = f"/{total}" if total else ""
        ch = self.ui.channelComboBox.currentText()

        if estado_descartado is None:
            estado_descartado = ds.is_trial_discarded(ds.name, ch, index)

        # Este plugin navega por el indice original (incluye descartados); el
        # resto de la aplicacion numera por posicion entre los validos. Si hay
        # descartes se muestran las dos para que se puedan relacionar.
        state = self.current_trial_state()
        valid_text = ""
        if state and state.get("note") and not estado_descartado:
            valid_text = f"  (valid {state['position']}/{state['total']})"

        if estado_descartado:
            self.ui.currentTrialLabel.setText(f"Current trial: {index + 1} (discarded){total_text}")
            self.ui.currentTrialLabel.setStyleSheet("color: red; font-weight: bold;")
            self.ui.Btn_discard_trial.setText("Include")
        else:
            self.ui.currentTrialLabel.setText(f"Current trial: {index + 1}{total_text}{valid_text}")
            self.ui.currentTrialLabel.setStyleSheet("color: black; font-weight: bold;")
            self.ui.Btn_discard_trial.setText("Discard")

        if total is not None:
            self.ui.totalTrialsValueBox.setText(str(total))
        self.ui.currentTrialValueBox.setText(str(index + 1))

        self.publish_current_trial()

    def current_trial_state(self):
        """Trial visible, traducido a la numeracion de la aplicacion (posicion
        entre los validos). Si esta descartado no tiene posicion valida."""
        td = self.last_td
        ds = self.get_active_signal(silent=True) if self.mainwin else None
        if td is None or ds is None or not self.visible_trials:
            return super().current_trial_state()
        idx = self.visible_trials[0]
        T = int(td.trials.shape[1])
        valid = ds.get_active_trial_indices(ds.name, td.channel_name) or list(range(T))
        discarded = idx not in valid
        return self.build_trial_state(
            "single",
            position=None if discarded else valid.index(idx) + 1,
            total=len(valid),
            channel=td.channel_name,
            discarded=discarded,
            original_index=idx,
            note=(f"original {idx + 1} de {T}" if len(valid) != T and not discarded else None),
        )

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
            plot = agregar_columna(self.chart, table, idx + 1)
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
