"""Wavelet con la densidad completa del archivo: cálculo, dibujo y zoom.

Al acercar en Wavelet se veían bloques: la wavelet se calculaba a 1000 Hz y cada
columna era 1 ms. Ahora la densidad por defecto es la del archivo. Eso exigía
tres cosas, que se prueban aquí:

1. Calcular: 998 frecuencias x 45.454 muestras tardaba 11,7 s y ocupaba 1 GB.
   Las frecuencias se reparten entre hilos y el resultado es idéntico bit a bit.
2. Dibujar: VTK no puede pintar una imagen de 45.454 columnas (supera el tamaño
   de textura y sale de un solo color). `MapaConZoom` dibuja la zona visible a
   la resolución de la pantalla y, al acercar, cada celda calculada.
3. La densidad por defecto: la del archivo, salvo que el usuario elija otra.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
import pywt
import vtk
from vtkmodules.util import numpy_support

from core.filters import wavelet as cw
from core.model.trial_dataset import TrialDataset
from core.utils.mapa_zoom import MAX_COLUMNAS, MapaConZoom, celdas_visibles, piramide

FS = 10101.0101


def _senal(n=6000, semilla=0):
    rng = np.random.default_rng(semilla)
    t = np.arange(n) / FS
    return np.sin(2 * np.pi * 40 * t) + 0.3 * rng.standard_normal(n)


# ============================================================
#   1. El cálculo en bloques
# ============================================================
def test_repartir_las_frecuencias_da_el_mismo_resultado_bit_a_bit():
    sig = _senal()
    Z, t, f = cw.compute_wavelet(sig, FS, round(FS), 1, 200, 2.0)
    wav = "cmor2.0-1.0"
    escalas = pywt.central_frequency(wav) * FS / f
    ref = np.abs(pywt.cwt(sig, escalas, wav, sampling_period=1 / FS, method="fft")[0])
    assert Z.shape == ref.shape == (f.size, sig.size)
    assert np.array_equal(Z, ref)


class _Ctx:
    def __init__(self, cancelar=False):
        self.cancelled = cancelar
        self.avances = []

    def progress(self, porcentaje, mensaje):
        self.avances.append((porcentaje, mensaje))


def test_el_calculo_informa_el_avance_y_se_puede_cancelar():
    ctx = _Ctx()
    cw.compute_wavelet(_senal(2000), FS, round(FS), 1, 100, 2.0, ctx=ctx)
    assert ctx.avances and ctx.avances[-1][0] == 100
    assert cw.compute_wavelet(_senal(2000), FS, round(FS), 1, 100, 2.0, ctx=_Ctx(cancelar=True)) is None


# ============================================================
#   2. El dibujo y el zoom
# ============================================================
def test_sin_zoom_se_dibuja_a_la_resolucion_de_la_pantalla():
    Z = np.random.default_rng(1).random((50, 45454), dtype=np.float32)
    bloque, x0, dx, _, _ = celdas_visibles(piramide(Z), 0.0, 1.0, 0.0, 1.0, (0, 45454), (0, 50))
    assert bloque.shape[1] <= MAX_COLUMNAS and bloque.shape[0] == 50
    # cada celda dibujada es el promedio de las columnas que cubre
    escala = int(round(dx))
    assert np.allclose(bloque[:, 3], Z[:, 3 * escala:4 * escala].mean(axis=1), rtol=1e-5)


def test_al_acercar_se_dibuja_cada_celda_calculada():
    Z = np.random.default_rng(2).random((50, 45454), dtype=np.float32)
    bloque, x0, dx, y0, dy = celdas_visibles(piramide(Z), 0.0, 1.0, 0.0, 1.0, (20000, 21500), (10, 30))
    assert dx == 1.0 and dy == 1.0, "una celda dibujada = una celda calculada"
    c0, f0 = int(x0), int(y0)
    assert c0 <= 20000 and c0 + bloque.shape[1] >= 21500
    assert np.array_equal(bloque, Z[f0:f0 + bloque.shape[0], c0:c0 + bloque.shape[1]])


def _pintar(chart, rango_x, rango_y):
    vista = vtk.vtkContextView()
    rw = vista.GetRenderWindow()
    rw.SetOffScreenRendering(1)
    rw.SetSize(800, 400)
    vista.GetScene().AddItem(chart)
    for eje, (a, b) in ((vtk.vtkAxis.BOTTOM, rango_x), (vtk.vtkAxis.LEFT, rango_y)):
        chart.GetAxis(eje).SetRange(a, b)
    rw.Render()
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    px = numpy_support.vtk_to_numpy(w2i.GetOutput().GetPointData().GetScalars()).reshape(400, 800, -1)
    return len(np.unique(px[60:340, 80:640, :3].reshape(-1, 3), axis=0))


def test_un_mapa_de_45454_columnas_se_ve_y_no_sale_de_un_solo_color():
    """Antes la imagen entera iba a VTK: salía de un solo color y tardaba 10 s."""
    nx, ny = 45454, 60
    Z = np.tile(((np.arange(nx) // 1000) % 2).astype(np.float32), (ny, 1))      # franjas
    lut = vtk.vtkColorTransferFunction()
    lut.AddRGBPoint(0.0, 0.1, 0.1, 0.5)
    lut.AddRGBPoint(1.0, 0.9, 0.9, 0.1)
    chart = vtk.vtkChartHistogram2D()
    chart.SetTransferFunction(lut)
    for eje, (a, b) in ((vtk.vtkAxis.BOTTOM, (0, nx)), (vtk.vtkAxis.LEFT, (0, ny))):
        ax = chart.GetAxis(eje)
        ax.SetBehavior(vtk.vtkAxis.FIXED)
        ax.SetRange(a, b)
    mapa = MapaConZoom(chart, Z, 0.0, 1.0, 0.0, 1.0)
    assert _pintar(chart, (0, nx), (0, ny)) > 1
    assert mapa.celdas_dibujadas[1] <= MAX_COLUMNAS
    # acercar: el eje avisa y el mapa recorta, ahora con cada celda
    chart.GetAxis(vtk.vtkAxis.BOTTOM).SetRange(20500, 21500)
    assert mapa.imagen.GetSpacing()[0] == 1.0
    assert mapa.celdas_dibujadas[1] <= 1004


# ============================================================
#   3. La densidad por defecto
# ============================================================
def _plugin_wavelet():
    from core.plugins.meta import PluginMeta
    from plugins.analysis.time_frequency.wavelet.wavelet_plugin import Wavelet_plugin
    return Wavelet_plugin(PluginMeta(id="w", name="Wavelet", category="Analysis", subcategory="Time-Frequency",
                                     version="1.0", icon="x.png", logic_class="Wavelet_plugin"))


def _trials(n=4000):
    return TrialDataset(source="C:/datos/x.abf", sampling_rate=FS, channel_index=0, channel_name="vM1",
                        unit="mV", t0=0.0, t1=n / FS, time_rel=np.arange(n) / FS,
                        trials=np.column_stack([_senal(n, s) for s in range(3)]), onsets_s=[0, 1, 2])


class _Spin:
    """QSpinBox mínimo: setValue avisa como valueChanged."""

    def __init__(self, al_cambiar):
        self.valor = 1000
        self.al_cambiar = al_cambiar

    def setValue(self, v):
        self.valor = int(v)
        self.al_cambiar(self.valor)

    def value(self):
        return self.valor


def _preparar(p, td):
    tareas = MagicMock()
    p.kernel = SimpleNamespace(get_service=lambda clave: tareas if clave == "TaskService" else None)
    p.alerts = MagicMock()
    p.get_active_signal = lambda *a, **k: SimpleNamespace(name="x.abf")
    p.get_active_trials = lambda *a, **k: td
    p._active_trials_quiet = lambda: (SimpleNamespace(name="x.abf"), td)
    p.selector_trials = MagicMock(posiciones=MagicMock(return_value=[1]))
    p.ui = MagicMock()
    p.ui.sampleDensitySpinBox = _Spin(p._al_cambiar_densidad)
    p.ui.lowFrequencySpinBox.value.return_value = 1.0
    p.ui.highFrequencySpinBox.value.return_value = 100.0
    p.ui.cyclesSpinBox.value.return_value = 2
    p.ui.normalizeCheckBox.isChecked.return_value = False
    p.ui.scaleCheckBox.isChecked.return_value = False
    return tareas


def test_la_densidad_por_defecto_es_la_del_archivo():
    p = _plugin_wavelet()
    assert p._densidad_por_defecto() == p.DENSIDAD_SIN_SENAL, "sin señal todavía"
    td = _trials()
    p._active_trials_quiet = lambda: (SimpleNamespace(name="x.abf"), td)
    assert p._densidad_por_defecto() == 10101


def test_al_generar_usa_la_densidad_del_archivo_sin_avisos():
    p = _plugin_wavelet()
    tareas = _preparar(p, _trials())
    p.on_create_wavelet()
    assert tareas.submit.call_args.kwargs["fs"] == 10101
    p.alerts.info.assert_not_called()       # 10.101 frente a 10.101,01 Hz no merece aviso
    p.alerts.warning.assert_not_called()


def test_si_el_usuario_elige_otra_densidad_se_respeta():
    p = _plugin_wavelet()
    tareas = _preparar(p, _trials())
    p.ui.sampleDensitySpinBox.setValue(2000)          # cambio del usuario
    p.on_create_wavelet()
    assert tareas.submit.call_args.kwargs["fs"] == 2000
