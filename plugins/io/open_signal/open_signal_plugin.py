# plugins/io/open_signal/open_signal_plugin.py
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox
import traceback

from PyQt5 import QtCore, QtWidgets
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk

from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu
from core.services.data_store import DataStore
from core.services.fileio_service import FileIOService
from core.services.settings_service import SettingsService
from core.model.signal_dataset import SignalDataset
from core.utils.adapters import dataset_to_vtk_table

from plugins.io.open_signal.open_signal_ui import Ui_OpenSignal


class OpenSignalPlugin(IPlugin):
    MAX_CHANNELS_VISIBLE = 3

    def __init__(self, meta: PluginMeta):
        super().__init__(meta)

        self.settings = SettingsService()

        

        self.ui: Ui_OpenSignal | None = None
        self.vtk_interactor: QVTKRenderWindowInteractor | None = None
        self.vtk_view: vtk.vtkContextView | None = None

        self.current_ds: SignalDataset | None = None
        self._block_item_changed = False

        self._charts: list[vtk.vtkChartXY] = []
        self._vtk_table = None
        
        self._sync_callback = None
        self._is_syncing = False



    def stop(self):
        if self.vtk_interactor:
            self.vtk_interactor.Disable()

    def process(self, data: any):
        """Restore rendering and re-enable interaction."""
        if self.vtk_interactor:
            self.vtk_interactor.Enable()

    def get_widget(self, parent=None):
        if self.ui is None:
            self.ui = Ui_OpenSignal(parent)
            self.alerts.parent = self.ui
            self._ensure_vtk()

            self.ui.Btn_abrir_senal.clicked.connect(self._on_open_clicked)
            self.ui.listChannels.itemChanged.connect(self._on_channel_item_changed)

            if hasattr(self.ui, "splitter"):
                self.ui.splitter.splitterMoved.connect(lambda *_: self._relayout_charts())

            store: DataStore | None = self.kernel.get_service("DataStore")
            if store and store.get_active_signal() is not None:
                self._set_dataset(store.get_active_signal())
        else:
            self.ui.setParent(parent)
        return self.ui

    def _ensure_vtk(self):
        """Embed a QVTKRenderWindowInteractor and use vtkContextView (charts)."""
        self._log("ensure_vtk(): enter")

        container = self.ui.vtkContainer
        if container.layout() is None:
            lay = QtWidgets.QVBoxLayout(container)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

        self.vtk_interactor = QVTKRenderWindowInteractor(container)
        container.layout().addWidget(self.vtk_interactor)
        self._log("ensure_vtk(): embedded interactor")

        _orig_resize = self.vtk_interactor.resizeEvent
        def _resize_wrapper(ev):
            _orig_resize(ev)              
            self._relayout_charts()        
        self.vtk_interactor.resizeEvent = _resize_wrapper  

        self.vtk_view = vtk.vtkContextView()
        self.vtk_view.SetRenderWindow(self.vtk_interactor.GetRenderWindow())
        self.vtk_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)

        try:
            self.vtk_menu = VTKContextMenu(
                chart=[],                              
                vtk_widget=self.vtk_interactor,       
                plugin_name="open_signal",
                measurements_enabled=False,             
                measure_scope={                         
                    "view_id": "signal_loader",         
                    "trial_id": None,
                    "channel_name": None,          
                    "plugin": "open_signal",
                    "domain": "time",
                    "graph_id": "open_signal:blank" 
                },
                parent=self.ui
            )
            self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))
        except Exception as e:
            self.vtk_menu = None
            self.alerts.error("Error creating the context menu.\n" + str(e))

        # synchronization callback
        self._setup_sync_callback()

        try:
            self.vtk_interactor.Initialize()
        except Exception:
            pass
        self._log("ensure_vtk(): scheduled init")

    def _setup_sync_callback(self):
        """Configure callback to synchronize X axes across all charts."""
        if not self.vtk_interactor:
            return

        def sync_axes(caller, event):
            if self._is_syncing or not self._charts:
                return
            self._is_syncing = True
            try:
                # 1) Where is the cursor?
                try:
                    mx, my = self.vtk_interactor.GetEventPosition()
                except Exception:
                    mx, my = -1, -1

                ref_chart = self._chart_at_pixel(mx, my) or self._charts[0]

                ref_axis = ref_chart.GetAxis(vtk.vtkAxis.BOTTOM)
                ref_range = [0.0, 0.0]
                ref_axis.GetRange(ref_range)
                x0, x1 = ref_range

                ref_axis.SetBehavior(vtk.vtkAxis.AUTO)

                for chart in self._charts:
                    if chart is ref_chart:
                        continue
                    axis = chart.GetAxis(vtk.vtkAxis.BOTTOM)

                    cur_range = [0.0, 0.0]
                    axis.GetRange(cur_range)
                    cx0, cx1 = cur_range

                    if abs(cx0 - x0) > 1e-6 or abs(cx1 - x1) > 1e-6:
                        axis.SetRange(x0, x1)
                        axis.SetBehavior(vtk.vtkAxis.FIXED)

                self.vtk_view.GetRenderWindow().Render()
            finally:
                self._is_syncing = False
 
        self._sync_callback = sync_axes
        
        # Add observers for different interaction events
        self.vtk_interactor.AddObserver(vtk.vtkCommand.InteractionEvent, self._sync_callback)
        self.vtk_interactor.AddObserver(vtk.vtkCommand.MouseWheelForwardEvent, self._sync_callback)
        self.vtk_interactor.AddObserver(vtk.vtkCommand.MouseWheelBackwardEvent, self._sync_callback)
        self.vtk_interactor.AddObserver(vtk.vtkCommand.LeftButtonPressEvent, self._sync_callback)
        self.vtk_interactor.AddObserver(vtk.vtkCommand.LeftButtonReleaseEvent, self._sync_callback)
        self.vtk_interactor.AddObserver(vtk.vtkCommand.MouseMoveEvent, self._sync_callback)

    # ---------------- file / data ----------------
    def _on_open_clicked(self):
        # Get last opened folder from settings
        last_dir = self.settings.get("last_open_dir", str(Path.cwd()))

        fname, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.ui,
            "Select signal file",
            last_dir,
            # "Signals (*.abf *.edf *.ebf *.mat);;ABF Files (*.abf);;EDF Files (*.edf);;EBF Files (*.ebf);;MAT Files (*.mat)"
            "Signals (*.abf *.edf);;ABF Files (*.abf);;EDF Files (*.edf)"

        )
        if not fname:
            return
        
        # Save the selected folder as last used
        self.settings.set("last_open_dir", str(Path(fname).parent))

        fileio: FileIOService | None = self.kernel.get_service("FileIO")
        if fileio is None:
            fileio = FileIOService()
            self.kernel.register_service("FileIO", fileio)
        
        
        store: DataStore | None = self.kernel.get_service("DataStore")
        if store is None:
            store = DataStore()
            self.kernel.register_service("DataStore", store)

        name_aux = Path(fname).name
        if store.has(name_aux):
            reply = QMessageBox.warning(
                self.ui,
                "Warning",
                f"A signal named '{name_aux}' already exists.\n\n"
                "If you continue, the existing signal will be overwritten and previous work will be lost.\n\n"
                "Do you want to continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                if self.mainwin:
                    self.mainwin.statusBar().showMessage("Load canceled by user.", 4000)
                return
            

        ext = Path(fname).suffix.lower()
        try:
            if ext == ".abf":
                ds = fileio.load_abf(fname)
            elif ext == ".edf":
                ds = fileio.load_edf(fname)
            # elif ext == ".mat":
            #     ds = fileio.load_mat(fname)
            else:
                if self.mainwin:
                    self.mainwin.statusBar().showMessage(f"Unsupported format: {ext}", 4000)
                return
        except Exception as e:
            QMessageBox.warning(self.ui, "Error", f"Error opening file {fname}\n{e}.")
            self._log("_on_open_clicked error:", e)
            traceback.print_exc()
            return


        key = store.add_signal(ds, ds.name)
        self._log("Saved in DataStore:", key)
        store.set_active_signal(key)
        self.kernel.emit_event("signal_added", {"key": key})

        self._set_dataset(ds)

        self.vtk_menu.set_signal_name(ds.name)

        if self.mainwin:
            self.mainwin.statusBar().showMessage(f"Loaded: {fname}", 4000)

    def _set_dataset(self, ds: SignalDataset):
        self.current_ds = ds
        self._populate_channel_list(ds)
        self._vtk_table = dataset_to_vtk_table(ds)
        self._render_selected()

    def _populate_channel_list(self, ds: SignalDataset):
        lw = self.ui.listChannels
        self._block_item_changed = True
        lw.clear()

        names = list(ds.channel_names) if getattr(ds, "channel_names", None) else [
            f"ch-{i+1}" for i in range(ds.signals.shape[0])
        ]
        for i, name in enumerate(names):
            it = QtWidgets.QListWidgetItem(name)
            it.setFlags(it.flags() | QtCore.Qt.ItemIsUserCheckable)
            it.setCheckState(QtCore.Qt.Checked if i < self.MAX_CHANNELS_VISIBLE else QtCore.Qt.Unchecked)
            it.setData(QtCore.Qt.UserRole, i)
            lw.addItem(it)

        self._block_item_changed = False

    def _checked_indices(self):
        out = []
        lw = self.ui.listChannels
        for i in range(lw.count()):
            it = lw.item(i)
            if it.checkState() == QtCore.Qt.Checked:
                out.append(int(it.data(QtCore.Qt.UserRole)))
        return out

    def _on_channel_item_changed(self, item: QtWidgets.QListWidgetItem):
        if self._block_item_changed:
            return
        checked = self._checked_indices()
        if len(checked) > self.MAX_CHANNELS_VISIBLE:
            self._block_item_changed = True
            item.setCheckState(QtCore.Qt.Unchecked)
            self._block_item_changed = False
            if self.mainwin:
                self.mainwin.statusBar().showMessage(f"Maximum {self.MAX_CHANNELS_VISIBLE} visible channels.", 2500)
            return
        self._render_selected()

    # ---------------- layout helpers ----------------
    def _relayout_charts(self):
        """Reposition charts with enough spacing so axes are visible."""
        if not self.vtk_view or not self._charts:
            return

        rw = self.vtk_view.GetRenderWindow()
        w, h = rw.GetSize()
        if w <= 0 or h <= 0:
            return

        left_margin, right_margin = 8, 8
        top_margin, bottom_margin = 10, 12
        gap = 40            # space between charts
        min_row_h = 150

        rows = len(self._charts)
        inner_h = max(1, h - top_margin - bottom_margin - gap * (rows - 1))
        row_h = max(min_row_h, inner_h // rows)

        y = float(h - top_margin - row_h)
        for chart in self._charts:
            chart.SetAutoSize(False)
            chart.SetSize(vtk.vtkRectf(
                float(left_margin),
                float(y),
                float(w - left_margin - right_margin),
                float(row_h)
            ))
            y -= (row_h + gap)

        for chart in self._charts:
            ax_b = chart.GetAxis(vtk.vtkAxis.BOTTOM)
            ax_b.SetLabelsVisible(True)
            ax_b.SetTitle("Time (s)")

        # Synchronize ranges after re-layout
        self._sync_all_x_axes()

        rw.Render()

    def _sync_all_x_axes(self):
        """Synchronize all X axes to the same range."""
        if not self._charts or self._is_syncing:
            return

        self._is_syncing = True
        try:
            # Reference chart range
            ref_axis = self._charts[0].GetAxis(vtk.vtkAxis.BOTTOM)

            ref_range = [0.0, 0.0]
            ref_axis.GetRange(ref_range)
            x0, x1 = ref_range

            # Apply to all charts
            for chart in self._charts:
                axis = chart.GetAxis(vtk.vtkAxis.BOTTOM)
                axis.SetRange(x0, x1)
                axis.SetBehavior(vtk.vtkAxis.AUTO)
        finally:
            self._is_syncing = False


    def _render_selected(self):
        if self.current_ds is None or self.vtk_view is None:
            return

        ds = self.current_ds
        scene = self.vtk_view.GetScene()
        scene.ClearItems()
        self._charts.clear()

        sel = self._checked_indices()
        if not sel:
            self.vtk_view.GetRenderWindow().Render()
            return

        table = self._vtk_table if self._vtk_table is not None else dataset_to_vtk_table(ds)

        for ch in sel:
            chart = vtk.vtkChartXY()
            scene.AddItem(chart)
            self._charts.append(chart)

            plot = chart.AddPlot(vtk.vtkChart.LINE)
            plot.SetInputData(table, 0, ch + 1)
            plot.SetWidth(0.8)

            name = ds.channel_names[ch] if ch < len(ds.channel_names) else f"ch{ch}"
            chart.SetTitle(name)

            ax_b = chart.GetAxis(vtk.vtkAxis.BOTTOM)
            ax_l = chart.GetAxis(vtk.vtkAxis.LEFT)
            ax_b.SetGridVisible(True)
            ax_l.SetGridVisible(True)

            # Show labels and X title on all charts
            ax_b.SetLabelsVisible(True)
            ax_b.SetTitle("Time (s)")

            ax_b.SetBehavior(vtk.vtkAxis.AUTO)

            unit = "Amplitude"
            if ch < len(ds.units) and ds.units[ch]:
                unit = ds.units[ch]
            ax_l.SetTitle(unit)

        self._relayout_charts()

        if self.vtk_menu and self._charts:
            self.vtk_menu.set_chart(self._charts)
            
    def _chart_at_pixel(self, x: int, y: int):
        """Return the chart whose rectangle contains point (x, y) in VTK coords."""
        for ch in self._charts:
            r = ch.GetSize()  # vtkRectf: x, y, width, height
            if (r.GetX() <= x <= r.GetX() + r.GetWidth()
                    and r.GetY() <= y <= r.GetY() + r.GetHeight()):
                return ch
        return None
