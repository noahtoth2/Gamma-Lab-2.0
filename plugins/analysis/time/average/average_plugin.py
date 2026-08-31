from core import kernel
from core.plugins.interfaces import IPlugin
from core.plugins.meta import PluginMeta
from core.utils.vtk_context_menu import VTKContextMenu


from plugins.analysis.time.average.average_plugin_ui import Ui_Average
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
import numpy as np



class Average_plugin(IPlugin):
    def __init__(self, meta:PluginMeta):
        super().__init__(meta)
        self.vtk_widget = None
        self.renwin = None
        self.ui = None
        self.vtk_menu: VTKContextMenu | None = None


    def process(self, data: any):
        if self.vtk_widget:
            self.vtk_widget.Enable()

    def stop(self):
        print("Stopping Average")

        if self.vtk_widget:
            self.vtk_widget.Disable()   


    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_Average()
            self.ui.setupUi(self.widget)
            # Assign the widget to alerts
            self.alerts.parent = self.widget

            self.ensure_vtk()

            # Connect "Calculate Average" button
            self.ui.calculateAverageButton.clicked.connect(self._on_calculate_average)

        else:
            self.widget.setParent(parent)

        return self.widget


    def _on_calculate_average(self):
        """Load the active SignalDataset from the DataStore and use its associated TrialDataset."""

        if self.get_active_signal() is None:
            return
        
        
        trials = self.get_active_trials()
        if trials is None:
            return

        # Compute per-sample average across trials
        av_data = np.mean(trials.trials, axis=1)
        t = trials.time_rel

        self._notify(f"Average computed -> shape: {av_data.shape} with {trials.trials.shape[1]} trials used")

        
        # Render in VTK
        self.render_average(t, av_data, trials.channel_name, trials.unit)

    def render_average(self, t, av_data, channel_name=None, unit=None):
        """
        Render the average using vtkContextView + vtkChartXY
        t: 1D array of times
        av_data: 1D array of average values
        """
        if self.view is None:
            self.ensure_vtk()

        # Basic validations
        t = np.asarray(t, dtype=float)
        av = np.asarray(av_data, dtype=float)
        if t.ndim != 1 or av.ndim != 1 or t.size != av.size:
            self.alerts.error( "Time and signal vectors must have the same 1D length.", "Render error")
            return

        # Downsample if there are many points (to keep UI responsive)
        MAX_SAMPLES = 2000
        N = t.size
        if N > MAX_SAMPLES:
            factor = int(np.ceil(N / MAX_SAMPLES))
            t_plot = t[::factor]
            av_plot = av[::factor]
        else:
            t_plot = t
            av_plot = av

        # Clear scene and create VTK table
        scene = self.view.GetScene()
        scene.ClearItems()

        table = vtk.vtkTable()
        arr_time = vtk.vtkFloatArray(); arr_time.SetName("Time (s)")
        arr_sig  = vtk.vtkFloatArray();  arr_sig.SetName(f"{channel_name or 'Signal'} [{unit or ''}]")

        for ti, si in zip(t_plot, av_plot):
            arr_time.InsertNextValue(float(ti))
            arr_sig.InsertNextValue(float(si))

        table.AddColumn(arr_time)
        table.AddColumn(arr_sig)

        # Chart + actor 
        chart = vtk.vtkChartXY()
        scene.AddItem(chart)


        # Draw line
        plot = chart.AddPlot(vtk.vtkChart.LINE)
        plot.SetInputData(table, 0, 1)
        # Optional: width and color
        try:
            plot.SetWidth(1.5)
            # SetColor expects RGBA (0..255) in some versions
            plot.SetColor(0, 0, 0, 255)
        except Exception:
            pass

        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Time (s)")
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle(unit or "Amplitude")
        chart.SetTitle(f"Average - {channel_name or ''}")

        # --- Context menu ---

        signal_name = self.active_signal.name
        ch_name = channel_name or "channel"
        graph_uid = f"average"
        
        if self.vtk_menu is not None:
            self.vtk_menu.on_view_rebuilt(
                chart,
                view_id="average",
                trial_id=None,
                channel_name=f"{signal_name}:{ch_name}",
                plugin=self.meta.id,
                domain=self.meta.subcategory,
                graph_id=graph_uid
            )
        # --- End context menu ---

        # Force render
        try:
            self.view.GetRenderWindow().Render()
        except Exception:
            # Fallback: if view lacks a RenderWindow use vtk_widget
            try:
                self.vtk_widget.GetRenderWindow().Render()
            except Exception:
                pass


    def ensure_vtk(self):
        """Create and initialize VTK widgets and the context view."""
        # Create QVTK inside the container defined in the .ui
        if not self.vtk_widget:
            self.vtk_widget = QVTKRenderWindowInteractor(self.ui.plotArea)
            
            layout = QVBoxLayout(self.ui.plotArea)
            layout.setContentsMargins(0, 0, 0, 0)
            self.ui.plotArea.setLayout(layout)
            layout.addWidget(self.vtk_widget)

        # ContextView (facilitates charting)
        self.view = vtk.vtkContextView()
        self.view.SetRenderWindow(self.vtk_widget.GetRenderWindow())
        self.view.GetRenderer().SetBackground(0.98, 0.98, 0.98)
        self.vtk_widget.Initialize()
        
        # Menu
        if self.vtk_menu is None:
            base_scope = {
                "view_id": "average",
                "graph_id": "average:blank",
                "trial_id": None,           
                "channel_name": None,       
                "plugin": "average",
                "domain": "time",
            }
            try:
                self.vtk_menu = VTKContextMenu(
                    chart=None,
                    vtk_widget=self.vtk_widget,
                    plugin_name="average",
                    measurements_enabled=True,
                    measure_scope=base_scope,
                    parent=self.widget
                )
                self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))
            except Exception as e:            
                self.alerts.info(f"Error creating contextual menu\n {str(e)}", "Contextual menu")



   
