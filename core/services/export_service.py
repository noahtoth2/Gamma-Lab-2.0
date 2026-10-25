from datetime import datetime
from PyQt5.QtWidgets import QFileDialog
import os
import vtk
import pandas as pd
import csv
import json
import numpy as np

from core.utils.plugin_alerts import PluginAlerts

class ExportService:
    """
    Image and table export service for VTK.
    - Does not depend on VTKContextMenu class.
    - Receives callbacks to get the active chart and names (signal/channel/plugin).
    """
    def __init__(self, parent, vtk_widget, get_active_chart, get_names, last_dir_getter, last_dir_setter):
        self.alerts = PluginAlerts()
        self.alerts.parent = parent
        self.parent = parent
        self.vtk_widget = vtk_widget
        self.get_active_chart = get_active_chart
        self.get_names = get_names
        self._get_last_dir = last_dir_getter
        self._set_last_dir = last_dir_setter

    # ---------- image ----------
    def export_image(self, format: str, filename: str = None):
        """
        Export the VTK window to an image (png/jpg/jpeg/bmp/tiff).
        If filename is None, open a dialog. Respects the 'last_export_dir'.
        """
        try:
            signal_name, channel_name, plugin_name = self.get_names()
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            if channel_name:
                base_name = f"{signal_name}_{channel_name}_{plugin_name}_{stamp}.{format}"
            else:
                base_name = f"{signal_name}_{plugin_name}_{stamp}.{format}"
            
            print(f"[Export] names -> signal='{signal_name}', channel='{channel_name}', plugin='{plugin_name}'")
            
            initial_path = os.path.join(self._get_last_dir(), base_name)

            if not filename:
                file_filter = f"Image (*.{format})"
                filename, _ = QFileDialog.getSaveFileName(
                    self.parent, "Save image as...", initial_path, file_filter
                )
                if not filename:
                    return

            self._set_last_dir(os.path.dirname(filename))

            window = self.vtk_widget.GetRenderWindow()
            w2i = vtk.vtkWindowToImageFilter()
            w2i.SetInput(window)
            w2i.Update()

            ext = format.lower()
            if ext == "png":
                writer = vtk.vtkPNGWriter()
            elif ext in ["jpg", "jpeg"]:
                writer = vtk.vtkJPEGWriter()
            elif ext == "bmp":
                writer = vtk.vtkBMPWriter()
            elif ext in ["tiff", "tif"]:
                writer = vtk.vtkTIFFWriter()
            else:
                self.alerts.error(f"Format '{format}' not supported.")
                return

            writer.SetFileName(filename)
            writer.SetInputConnection(w2i.GetOutputPort())
            writer.Write()

            self.alerts.info(f"Image exported successfully {base_name}", "Successful export")

        except Exception as e:
            self.alerts.error(f"Error exporting image:\n{e}", "Export error")

    # ---------- vector graphic (EMF) ----------
    def export_emf(self, filename: str = None):
        """
        Export the active chart as an Enhanced Metafile: axes, ticks, labels and
        colour bar are vector records and the heat map is an embedded bitmap.
        """
        try:
            from core.utils.emf_writer import chart_a_emf

            chart = self.get_active_chart()
            if chart is None:
                self.alerts.error("There is no chart to export.")
                return

            signal_name, channel_name, plugin_name = self.get_names()
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = (
                f"{signal_name}_{channel_name}_{plugin_name}_{stamp}.emf"
                if channel_name else f"{signal_name}_{plugin_name}_{stamp}.emf"
            )
            initial_path = os.path.join(self._get_last_dir(), base_name)

            if not filename:
                filename, _ = QFileDialog.getSaveFileName(
                    self.parent, "Save vector graphic as...", initial_path, "Enhanced Metafile (*.emf)"
                )
                if not filename:
                    return

            self._set_last_dir(os.path.dirname(filename))

            # Same proportions as the chart on screen
            w, h = max(1, self.vtk_widget.width()), max(1, self.vtk_widget.height())
            ancho = 1000
            alto = int(min(max(ancho * h / w, 400), 1400))
            chart_a_emf(chart, filename, ancho, alto)

            self.alerts.info(f"Graphic exported successfully {os.path.basename(filename)}", "Successful export")

        except OSError as e:
            self.alerts.error(f"The file could not be saved (protected folder or full disk).\n{e}")
        except Exception as e:
            self.alerts.error(f"Error exporting graphic \n{str(e)}")

    # ---------- sections (results made of several tables) ----------
    def export_sections(self, sections: dict, fmt: str, filename: str = None):
        """
        Export a result made of several tables (parameters, summary, matrices...).

        `sections` maps a section name to `(headers, rows)`. csv writes the
        sections one after another, each preceded by its name; xlsx writes one
        sheet per section; json writes one list of records per section.
        If filename is None, open a dialog. Respects the 'last_export_dir'.
        """
        try:
            if not sections:
                self.alerts.warning("There are no results to export.")
                return

            signal_name, channel_name, plugin_name = self.get_names()
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = (
                f"{signal_name}_{channel_name}_{plugin_name}_{stamp}.{fmt}"
                if channel_name else f"{signal_name}_{plugin_name}_{stamp}.{fmt}"
            )
            initial_path = os.path.join(self._get_last_dir(), base_name)

            if not filename:
                filters = {
                    "csv": "CSV file (*.csv)",
                    "xlsx": "Excel file (*.xlsx)",
                    "json": "JSON file (*.json)"
                }
                filename, _ = QFileDialog.getSaveFileName(
                    self.parent, f"Save results as {fmt.upper()}...", initial_path, filters[fmt]
                )
                if not filename:
                    return

            self._set_last_dir(os.path.dirname(filename))

            if fmt == "csv":
                with open(filename, mode="w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    for name, (headers, rows) in sections.items():
                        w.writerow([f"[{name}]"])
                        w.writerow(headers)
                        w.writerows(rows)
                        w.writerow([])
            elif fmt == "xlsx":
                with pd.ExcelWriter(filename) as writer:
                    for name, (headers, rows) in sections.items():
                        pd.DataFrame(rows, columns=headers).to_excel(
                            writer, sheet_name=str(name)[:31], index=False)
            elif fmt == "json":
                data = {name: [dict(zip(headers, row)) for row in rows]
                        for name, (headers, rows) in sections.items()}
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            else:
                self.alerts.error(f"Format '{fmt}' not supported.")
                return

            self.alerts.info(f"Results successfully exported to:\n{base_name}", "Successful export")

        except Exception as e:
            self.alerts.error(f"Error exporting results \n{str(e)}")

    # ---------- table ----------
    def _heatmap_sections(self, chart):
        """The matrix behind a heat map: one row per Y value, one column per X value."""
        from vtkmodules.util import numpy_support

        img = getattr(chart, "emf_imagen", None)
        if img is None:
            return None
        nx, ny, _ = img.GetDimensions()
        ox, oy, _ = img.GetOrigin()
        sx, sy, _ = img.GetSpacing()
        z = numpy_support.vtk_to_numpy(img.GetPointData().GetScalars()).reshape(ny, nx)
        x = ox + np.arange(nx) * sx
        y = oy + np.arange(ny) * sy
        y_title = chart.GetAxis(vtk.vtkAxis.LEFT).GetTitle() or "Y"
        if "log" in y_title.lower():
            # the axis is drawn in log10; the table carries the real frequency
            y = 10.0 ** y
            y_title = "Frequency (Hz)"
        x_title = chart.GetAxis(vtk.vtkAxis.BOTTOM).GetTitle() or "X"

        def num(v):
            v = float(v)
            return v if np.isfinite(v) else None

        rows = [[num(yy)] + [num(v) for v in fila] for yy, fila in zip(y, z)]
        return {"Map": ([y_title] + [f"{x_title}={num(xx):.6g}" for xx in x], rows)}

    def _export_heatmap_table(self, chart, fmt, filename=None):
        secciones = self._heatmap_sections(chart)
        if secciones is None:
            self.alerts.error("The chart does not contain data to export.")
            return
        self.export_sections(secciones, fmt, filename)

    def export_table(self, fmt: str, filename: str = None):
        """
        Export data (all series) from the active chart to csv/xlsx/json.
        If filename is None, open a dialog.
        """
        try:
            chart = self.get_active_chart()
            if not chart:
                self.alerts.warning("There is no chart to export.")
                return
            if isinstance(chart, vtk.vtkChartHistogram2D):
                self._export_heatmap_table(chart, fmt, filename)
                return
            if chart.GetNumberOfPlots() == 0:
                self.alerts.warning("The chart does not contain data to export.")
                return

            signal_name, channel_name, plugin_name = self.get_names()
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = (
                f"{signal_name}_{channel_name}_{plugin_name}_{stamp}.{fmt}"
                if channel_name else f"{signal_name}_{plugin_name}_{stamp}.{fmt}"
            )
            print(f"[Export] names -> signal='{signal_name}', channel='{channel_name}', plugin='{plugin_name}'")
            initial_path = os.path.join(self._get_last_dir(), base_name)

            if not filename:
                filters = {
                    "csv": "CSV file (*.csv)",
                    "xlsx": "Excel file (*.xlsx)",
                    "json": "JSON file (*.json)"
                }
                filename, _ = QFileDialog.getSaveFileName(
                    self.parent, f"Save table as {fmt.upper()}...", initial_path, filters[fmt]
                )
                if not filename:
                    return

            self._set_last_dir(os.path.dirname(filename))

            data_rows, headers = [], []
            for i in range(chart.GetNumberOfPlots()):
                plot = chart.GetPlot(i)
                table = plot.GetInput()
                if table is None:
                    continue
                x_col = table.GetColumn(0)
                y_col = table.GetColumn(1)
                num_points = table.GetNumberOfRows()
                series_name = plot.GetLabel() or f"Series_{i + 1}"
                headers.extend([f"{series_name}_X", f"{series_name}_Y"])
                for r in range(num_points):
                    x_val = x_col.GetValue(r)
                    y_val = y_col.GetValue(r)
                    if len(data_rows) <= r:
                        data_rows.append([])
                    data_rows[r].extend([x_val, y_val])

            if fmt == "csv":
                import io
                with open(filename, mode="w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(headers)
                    w.writerows(data_rows)
            elif fmt == "xlsx":
                import pandas as pd
                df = pd.DataFrame(data_rows, columns=headers)
                df.to_excel(filename, index=False)
            elif fmt == "json":
                data_dict = [dict(zip(headers, row)) for row in data_rows]
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(data_dict, f, ensure_ascii=False, indent=4)

            self.alerts.info(f"Data successfully exported to:\n{base_name}", "Successful export")

        except Exception as e:
            self.alerts.error(f"Error exporting table \n{str(e)}")
