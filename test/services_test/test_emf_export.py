"""EMF y tablas de mapas de calor.

No levantan Qt ni una ventana de VTK: las gráficas se construyen en memoria. Lo
que se comprueba es que el archivo sea un EMF bien formado (cabecera, tamaño,
número de registros y cierre), que lleve el texto de los ejes y que la tabla de
Excel de un mapa grande se recorte avisándolo.
"""
import struct

import numpy as np
import pytest
import vtk
from vtkmodules.util import numpy_support

from core.utils.emf_writer import EmfWriter, anotar_mapa, chart_a_emf
from core.utils.heatmap_export import MAX_CELDAS_XLSX, secciones_de_mapa


def _registros(datos):
    """Recorre los registros de un EMF y devuelve (tipo, tamaño)."""
    out, pos = [], 0
    while pos < len(datos):
        tipo, tam = struct.unpack_from("<II", datos, pos)
        assert tam >= 8 and tam % 4 == 0, (pos, tipo, tam)
        out.append((tipo, tam))
        pos += tam
    assert pos == len(datos)
    return out


def _mapa(nx=40, ny=30):
    img = vtk.vtkImageData()
    img.SetDimensions(nx, ny, 1)
    img.SetSpacing(0.025, 1.0, 1.0)
    img.SetOrigin(0.0, 1.0, 0.0)
    z = np.add.outer(np.arange(ny), np.arange(nx)).astype(np.float32)
    z[0, :5] = np.nan
    img.GetPointData().SetScalars(numpy_support.numpy_to_vtk(z.ravel(), deep=True, array_type=vtk.VTK_FLOAT))
    lut = vtk.vtkColorTransferFunction()
    for f, c in zip((0, 0.5, 1), ((0, 0, 1), (1, 1, 0), (1, 0, 0))):
        lut.AddRGBPoint(f * float(np.nanmax(z)), *c)
    lut.SetNanOpacity(0.0)
    chart = vtk.vtkChartHistogram2D()
    chart.SetInputData(img, 0)
    chart.SetTransferFunction(lut)
    anotar_mapa(chart, img, lut)
    chart.SetTitle("Scalogram")
    chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Time (s)")
    chart.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(0.0, 1.0)
    chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle("Frequency (Hz)")
    chart.GetAxis(vtk.vtkAxis.LEFT).SetRange(1.0, 31.0)
    return chart


def test_el_emf_de_un_mapa_esta_bien_formado(tmp_path):
    ruta = tmp_path / "mapa.emf"
    chart_a_emf(_mapa(), str(ruta))
    datos = ruta.read_bytes()

    tipo, tam, *_ = struct.unpack_from("<IIiiiiiiii", datos, 0)
    assert (tipo, tam) == (1, 88)
    firma, version, nbytes, nregs = struct.unpack_from("<IIII", datos, 40)
    assert firma == 0x464D4520 and version == 0x10000
    assert nbytes == len(datos), "el tamaño de la cabecera debe ser el del archivo"

    regs = _registros(datos)
    assert regs[0][0] == 1 and regs[-1][0] == 14, "empieza con la cabecera y cierra con EMR_EOF"
    assert nregs == len(regs)


def test_el_emf_lleva_los_rotulos_como_texto_y_el_mapa_como_imagen(tmp_path):
    ruta = tmp_path / "mapa.emf"
    chart_a_emf(_mapa(), str(ruta))
    datos = ruta.read_bytes()
    tipos = [t for t, _ in _registros(datos)]
    assert 81 in tipos, "el mapa va como bitmap (EMR_STRETCHDIBITS)"
    assert tipos.count(84) >= 6, "marcas, título y ejes son texto (EMR_EXTTEXTOUTW)"
    for rotulo in ("Scalogram", "Time (s)", "Frequency (Hz)"):
        assert rotulo.encode("utf-16-le") in datos, rotulo


def test_el_emf_de_lineas_es_todo_vectorial(tmp_path):
    t = np.linspace(0, 1, 500)
    tabla = vtk.vtkTable()
    for nombre, v in (("x", t), ("y", np.sin(2 * np.pi * 5 * t))):
        col = numpy_support.numpy_to_vtk(v, deep=True)
        col.SetName(nombre)
        tabla.AddColumn(col)
    chart = vtk.vtkChartXY()
    plot = chart.AddPlot(vtk.vtkChart.LINE)
    plot.SetInputData(tabla, 0, 1)
    chart.SetTitle("FFT")
    chart.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(0, 1)
    chart.GetAxis(vtk.vtkAxis.LEFT).SetRange(-1, 1)
    ruta = tmp_path / "linea.emf"
    chart_a_emf(chart, str(ruta))
    tipos = [t_ for t_, _ in _registros(ruta.read_bytes())]
    assert 87 in tipos, "la serie es una polilínea (EMR_POLYLINE16)"
    assert 81 not in tipos, "sin bitmaps"


def test_una_grafica_de_otro_tipo_se_rechaza(tmp_path):
    with pytest.raises(ValueError):
        chart_a_emf(vtk.vtkChartPie(), str(tmp_path / "x.emf"))


def test_un_mapa_sin_anotar_avisa_en_vez_de_escribir_basura(tmp_path):
    chart = vtk.vtkChartHistogram2D()
    with pytest.raises(ValueError, match="mapa de calor"):
        chart_a_emf(chart, str(tmp_path / "x.emf"))


def test_el_escritor_alinea_cada_registro_a_cuatro_bytes(tmp_path):
    e = EmfWriter(200, 100)
    e.texto(10, 10, "abc")          # 3 caracteres: el relleno importa
    e.texto(10, 30, "abcde")
    e.guardar(str(tmp_path / "t.emf"))
    _registros((tmp_path / "t.emf").read_bytes())


# ---------------------------------------------------------------- tablas
def test_excel_recorta_un_mapa_grande_y_lo_dice():
    ny, nx = 800, 3000                       # 2,4 millones de celdas
    m = np.random.default_rng(0).random((ny, nx))
    sec = secciones_de_mapa({"canal": "a"}, [["n", 1]], np.linspace(500, 1, ny),
                            np.arange(nx) / 1000, m, "xlsx", nombre="Escalograma")
    encabezado, filas = sec["Escalograma"]
    assert len(filas) * (len(encabezado) - 1) <= MAX_CELDAS_XLSX
    assert any(r[0] == "excel_columnas_recortadas" for r in sec["Resumen"][1])


def test_csv_y_json_llevan_la_matriz_completa():
    ny, nx = 800, 3000
    m = np.zeros((ny, nx))
    for fmt in ("csv", "json"):
        sec = secciones_de_mapa({}, [], np.linspace(500, 1, ny), np.arange(nx) / 1000, m, fmt)
        assert len(sec["Mapa"][0]) == nx + 1
        assert not any(r[0] == "excel_columnas_recortadas" for r in sec["Resumen"][1])


def test_los_nan_salen_vacios():
    m = np.array([[1.0, np.nan], [2.0, 3.0]])
    sec = secciones_de_mapa({}, [], [10, 5], [0.0, 0.1], m, "json")
    assert sec["Mapa"][1][0][2] is None
