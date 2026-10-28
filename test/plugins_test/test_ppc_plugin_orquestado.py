"""PPC contra el orquestador: la Fase 5b.

No se prueba el cálculo —eso es `test_ppc_core.py`— sino que el plugin se porte
bien con la cola: que encole en vez de bloquear, que el cálculo salga del hilo
de la interfaz, que las cuatro guardas descarten lo que llega tarde, y que lo
que no se puede calcular se diga **antes** de encolar nada.

Se usa el `TaskService` de verdad, no un doble: lo que se quiere comprobar es
justamente el contrato con él.

**La interfaz sí es un doble, y no por comodidad.** Todas las pruebas del
proyecto levantan una `QCoreApplication`, con la que crear widgets de Qt aborta
el proceso. Si esta prueba levantara una `QApplication` y otra hubiera creado
antes la `QCoreApplication` —hay cuatro que lo hacen—, se caería la suite
entera, sin mensaje. El doble ofrece la misma API que el plugin usa, y el
contrato de nombres se comprueba aparte, leyendo los dos archivos.
"""
import threading
import time

import numpy as np
import pytest
from PyQt5.QtCore import QCoreApplication

from core.model.signal_dataset import SignalDataset
from core.model.trial_dataset import TrialDataset
from core.plugins.meta import PluginMeta
from core.services.task_service import TaskService
from plugins.analysis.connectivity.ppc import compute as cp
from plugins.analysis.connectivity.ppc.ppc_plugin import Ppc_plugin

ARCHIVO = "17308005.abf"
FS = 500.0
NS, T = 1000, 4


@pytest.fixture(scope="module")
def qt_app():
    return QCoreApplication.instance() or QCoreApplication([])


def esperar(condicion, ms=30000):
    app = QCoreApplication.instance()
    limite = time.monotonic() + ms / 1000.0
    while time.monotonic() < limite:
        app.processEvents()
        if condicion():
            return True
        time.sleep(0.005)
    app.processEvents()
    return condicion()


# ------------------------------------------- el doble de la interfaz
class _Senal:
    """Lo que el plugin le pide a un `clicked`."""
    def __init__(self):
        self._conectados = []

    def connect(self, fn):
        self._conectados.append(fn)

    def emit(self):
        for fn in self._conectados:
            fn()


class _Spin:
    def __init__(self, valor=0):
        self._v = valor

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = v


class _Combo:
    def __init__(self):
        self._items, self._i = [], -1

    def blockSignals(self, _):
        pass

    def clear(self):
        self._items, self._i = [], -1

    def addItems(self, items):
        self._items.extend(items)
        if self._i < 0 and self._items:
            self._i = 0

    def count(self):
        return len(self._items)

    def itemText(self, i):
        return self._items[i]

    def currentText(self):
        return self._items[self._i] if 0 <= self._i < len(self._items) else ""

    def setCurrentText(self, t):
        if t in self._items:
            self._i = self._items.index(t)

    def setCurrentIndex(self, i):
        self._i = i


class _Boton:
    def __init__(self):
        self.clicked = _Senal()
        self._texto, self._activo = "Generate", True

    def setEnabled(self, v):
        self._activo = bool(v)

    def isEnabled(self):
        return self._activo

    def setText(self, t):
        self._texto = t

    def text(self):
        return self._texto


class _UiFalsa:
    def __init__(self):
        self.channel1ComboBox = _Combo()
        self.channel2ComboBox = _Combo()
        self.sampleDensitySpinBox = _Spin(2000)
        self.lowFrequencySpinBox = _Spin(0.1)
        self.highFrequencySpinBox = _Spin(500.0)
        self.windowSpinBox = _Spin(0.05)
        self.cyclesSpinBox = _Spin(3.0)
        self.clearButton = _Boton()
        self.createPpcButton = _Boton()
        self.plotArea = None


# ------------------------------------------------------------------ montaje
def trials_de(canal, indice, semilla, ns=NS, t=T, onsets=None):
    rng = np.random.default_rng(semilla)
    return TrialDataset(
        source=f"C:/datos/{ARCHIVO}", sampling_rate=FS,
        channel_index=indice, channel_name=canal, unit="mV",
        t0=0.0, t1=ns / FS, time_rel=np.arange(ns) / FS,
        trials=rng.normal(size=(ns, t)),
        onsets_s=list(onsets if onsets is not None else range(t)))


def señal_con(*juegos):
    ds = SignalDataset(
        name=ARCHIVO, format="abf", source_path=f"C:/datos/{ARCHIVO}",
        sampling_rate=FS, time=np.arange(NS) / FS,
        signals=np.random.default_rng(0).normal(size=(2, NS)),
        channel_names=["CA1", "IN 7"], units=["mV", "mV"], metadata={})
    for td in juegos:
        ds.add_trial_dataset(td)
    return ds


class _Store:
    def __init__(self, ds):
        self._ds = ds

    def get_active_signal(self):
        return self._ds

    def get(self, _clave, default=None):
        return default


class _Kernel:
    def __init__(self, servicios):
        self._s = servicios

    def get_service(self, clave):
        return self._s.get(clave)


class _MainWin:
    def __init__(self, kernel):
        self.kernel = kernel


def plugin_con(ds, tareas):
    meta = PluginMeta(id="ppc", name="PPC", category="Analysis",
                      subcategory="Connectivity", version="1.0",
                      icon="icn_ppc.png", logic_class="Ppc_plugin")
    p = Ppc_plugin(meta)
    kernel = _Kernel({"DataStore": _Store(ds), "TaskService": tareas})
    p.kernel = kernel
    p.mainwin = _MainWin(kernel)
    p.ui = _UiFalsa()
    # El dibujo no se prueba aquí: no hay ventana ni OpenGL en el doble. Se
    # sustituye por un registro de lo que se habría dibujado.
    p.dibujados = []
    p.ensure_vtk = lambda: None
    p.render_resultado = p.dibujados.append
    p._llenar_canales()
    return p


@pytest.fixture
def listo(qt_app):
    tareas = TaskService()
    ds = señal_con(trials_de("CA1", 0, 1), trials_de("IN 7", 1, 2))
    p = plugin_con(ds, tareas)
    # una banda chica, para que la prueba no tarde
    p.ui.lowFrequencySpinBox.setValue(20.0)
    p.ui.highFrequencySpinBox.setValue(120.0)
    p.ui.sampleDensitySpinBox.setValue(int(FS))
    yield p, tareas, ds
    tareas.cancel_all_from("ppc")


# ============================================================
#   El panel
# ============================================================
def test_los_dos_combos_arrancan_en_canales_distintos(listo):
    """El PPC de un canal consigo mismo vale 1 y no mide nada, así que el valor
    por omisión no puede ser el mismo en los dos."""
    p, _, _ = listo
    assert p.ui.channel1ComboBox.currentText() == "CA1"
    assert p.ui.channel2ComboBox.currentText() == "IN 7"


def test_ofrece_todos_los_canales_de_la_señal(qt_app):
    """Aunque solo uno tenga trials: los del otro se generan al calcular."""
    ds = señal_con(trials_de("CA1", 0, 1))
    p = plugin_con(ds, TaskService())
    assert [p.ui.channel1ComboBox.itemText(i)
            for i in range(p.ui.channel1ComboBox.count())] == ["CA1", "IN 7"]


def test_genera_los_trials_del_otro_canal_con_la_misma_receta(qt_app):
    """Con un solo canal cortado, el segundo se corta solo con los mismos
    parámetros: es lo que habría que hacer a mano en Trials."""
    from core.filters.trials import cut_trials_single_channel

    n = int(FS * 12)
    t = np.arange(n) / FS
    estimulo = np.zeros(n)
    for k in range(6):
        estimulo[int((1 + 1.5 * k) * FS): int((1 + 1.5 * k) * FS) + 10] = 1.0
    ds = SignalDataset(
        name=ARCHIVO, format="abf", source_path=f"C:/datos/{ARCHIVO}", sampling_rate=FS,
        time=t, signals=np.vstack([np.sin(2 * np.pi * 10 * t), np.cos(2 * np.pi * 10 * t), estimulo]),
        channel_names=["CA1", "IN 7", "STIM"], units=["mV", "mV", "V"], metadata={})
    receta = dict(channel=0, stim_channel=2, threshold=0.5, t0=0.0, t1=1.0,
                  end_mode="fixed", stim_expected=None, inter_stim_time=None)
    td = cut_trials_single_channel(ds=ds, **receta, debug=False)
    td.metadata["generation_params"] = receta
    ds.add_trial_dataset(td)

    p = plugin_con(ds, TaskService())
    p.ui.channel2ComboBox.setCurrentText("IN 7")
    nuevo = p._asegurar_trials(ds, "IN 7")
    assert nuevo is not None and nuevo.channel_name == "IN 7"
    assert np.asarray(nuevo.trials).shape == np.asarray(td.trials).shape
    assert ds.get_active_trials(ds.name, "IN 7") is not None
    cp.validar_alineacion(td, nuevo)   # mismo corte: no lanza


def test_los_valores_por_omision_son_los_del_matlab(listo):
    p, _, _ = listo
    p._valores_por_defecto()
    assert p.ui.sampleDensitySpinBox.value() == 2000
    assert p.ui.lowFrequencySpinBox.value() == pytest.approx(0.1)
    assert p.ui.highFrequencySpinBox.value() == pytest.approx(500.0)
    assert p.ui.windowSpinBox.value() == pytest.approx(0.05)
    assert p.ui.cyclesSpinBox.value() == pytest.approx(3.0)


# ============================================================
#   Encola, no bloquea
# ============================================================
def test_el_calculo_corre_fuera_del_hilo_de_la_interfaz(listo):
    """Es el punto del orquestador. Si corriera aquí, la ventana se congelaría
    los 2 a 5 segundos que tarda con trials de verdad."""
    p, _, _ = listo
    hilos = []
    original = cp.ppc_mapa

    def espia(*a, **k):
        hilos.append(threading.current_thread().name)
        return original(*a, **k)

    cp.ppc_mapa = espia
    try:
        p.on_create_ppc()
        assert esperar(lambda: p._handle is None and bool(hilos))
    finally:
        cp.ppc_mapa = original

    assert hilos
    assert hilos[0] != threading.current_thread().name
    assert hilos[0] != "MainThread"


def test_el_boton_se_bloquea_mientras_calcula_y_vuelve_al_terminar(listo):
    p, _, _ = listo
    p.on_create_ppc()
    assert not p.ui.createPpcButton.isEnabled()
    assert p.ui.createPpcButton.text() == "Computing..."

    assert esperar(lambda: p._handle is None)
    assert p.ui.createPpcButton.isEnabled()
    assert p.ui.createPpcButton.text() == "Generate"


def test_el_resultado_llega_y_se_guarda(listo):
    p, _, _ = listo
    p.on_create_ppc()
    assert esperar(lambda: p._ultimo is not None)

    r = p._ultimo["resultado"]
    assert isinstance(r, cp.ResultadoPPC)
    assert r.canal_1 == "CA1" and r.canal_2 == "IN 7"
    assert r.n_trials == T
    assert p._ultimo["parametros"]["canal_1"] == "CA1"
    assert p._ultimo["parametros"]["n_trials"] == T


def test_los_parametros_del_panel_son_los_que_se_calculan(listo):
    p, _, _ = listo
    p.ui.windowSpinBox.setValue(0.08)
    p.ui.cyclesSpinBox.setValue(4.0)
    p.on_create_ppc()
    assert esperar(lambda: p._ultimo is not None)

    r = p._ultimo["resultado"]
    assert r.ventana_min_s == pytest.approx(0.08)
    assert r.ciclos == pytest.approx(4.0)
    assert r.fs_pedida == pytest.approx(FS)


def test_se_informa_del_avance(listo):
    p, _, _ = listo
    dichos = []
    p._notify = dichos.append
    p.on_create_ppc()
    assert esperar(lambda: p._ultimo is not None)
    assert any("Trial" in d for d in dichos), "sin avance la espera es ciega"


def test_los_avisos_se_registran_sin_abrir_dialogos(listo):
    """Los avisos van al log. Un modal abre un bucle de eventos anidado y el
    temporizador de VTK sigue disparando dentro (nº 24)."""
    p, _, _ = listo
    registrado, dialogos = [], []
    p._log = lambda *a: registrado.append(" ".join(str(x) for x in a))
    p.alerts.warning = lambda m: dialogos.append(m)
    p.alerts.error = lambda m: dialogos.append(m)

    p.ui.lowFrequencySpinBox.setValue(5.0)   # deja mucho mapa en blanco
    p.on_create_ppc()
    assert esperar(lambda: p._ultimo is not None)

    # Con el modo de bordes por omisión el mapa sale lleno, así que el aviso
    # que toca es el de que los extremos se calcularon con menos muestras.
    assert any("n_por_celda" in r for r in registrado)
    assert dialogos == []


# ============================================================
#   Las cuatro guardas
# ============================================================
def test_un_resultado_que_llega_tarde_se_descarta(listo):
    """Al cambiar un parámetro se encola otra tarea y la anterior puede seguir
    viva un instante. Sin la guarda, su resultado sobreescribe el nuevo."""
    p, _, _ = listo
    p.on_create_ppc()
    viejo = p._handle
    assert viejo is not None

    p._handle = object()           # como si ya hubiera otra en curso
    p._on_ppc_done(viejo, "basura")
    assert p._ultimo is None, "el resultado viejo no puede guardarse"

    p._on_ppc_failed(viejo, "error viejo")
    p._on_ppc_cancelled(viejo)
    assert p._handle is not None, "tampoco puede resetear el estado del nuevo"


def test_un_fallo_abre_dialogo_y_libera_el_boton(listo):
    """Un fallo de verdad **sí** avisa: es el único camino que abre diálogo."""
    p, _, _ = listo
    errores = []
    p.alerts.error = errores.append

    p.ui.highFrequencySpinBox.setValue(FS * 5)     # pasa del Nyquist
    p.on_create_ppc()
    assert esperar(lambda: bool(errores))
    assert "Nyquist" in errores[0]
    assert p.ui.createPpcButton.isEnabled()


def test_salir_de_la_pestana_cancela_lo_que_este_en_vuelo(listo):
    p, _, _ = listo
    p.on_create_ppc()
    p.stop()
    assert p._handle is None
    assert p.ui.createPpcButton.isEnabled()


# ============================================================
#   Lo que se dice antes de encolar
# ============================================================
def test_sin_receta_para_el_otro_canal_avisa_y_no_encola(qt_app):
    """CA1 tiene trials pero sin parámetros de corte guardados: no hay de dónde
    copiar la receta para IN 7."""
    ds = señal_con(trials_de("CA1", 0, 1))
    p = plugin_con(ds, TaskService())
    avisos = []
    p.alerts.warning = avisos.append

    p.on_create_ppc()
    assert avisos and "no tiene trials" in avisos[0]
    assert p._handle is None, "no puede haber encolado nada"


def test_el_mismo_canal_dos_veces_se_rechaza_antes_de_calcular(listo):
    """Calcularlo son varios segundos de espera para acabar enseñando un mapa
    entero de unos. Mejor decirlo antes."""
    p, _, _ = listo
    avisos = []
    p.alerts.warning = avisos.append

    p.ui.channel2ComboBox.setCurrentText("CA1")
    p.on_create_ppc()
    assert avisos and "distintos" in avisos[0]
    assert p._handle is None


def test_canales_desalineados_se_rechazan_antes_de_calcular(qt_app):
    """Cortados con onsets distintos: restar sus fases no significa nada."""
    ds = señal_con(trials_de("CA1", 0, 1),
                   trials_de("IN 7", 1, 2, onsets=[9, 9, 9, 9]))
    p = plugin_con(ds, TaskService())
    errores = []
    p.alerts.error = errores.append

    p.on_create_ppc()
    assert errores and "instantes distintos" in errores[0]
    assert p._handle is None


def test_sin_servicio_de_tareas_lo_dice(qt_app):
    ds = señal_con(trials_de("CA1", 0, 1), trials_de("IN 7", 1, 2))
    p = plugin_con(ds, None)
    errores = []
    p.alerts.error = errores.append
    p.on_create_ppc()
    assert errores and "tareas" in errores[0]


# ============================================================
#   El contrato de nombres con la interfaz
# ============================================================
# Se comprueba leyendo los dos archivos, sin levantar Qt. Es lo que más
# probablemente se rompa cuando se reemplace el andamio por la interfaz de
# verdad: si allí un widget se llama distinto, esto falla y dice cuál.

# `setupUi` no es un widget sino el metodo que los crea; es lo unico que el
# plugin le pide a `self.ui` que no sea un control.
NO_SON_WIDGETS = {"setupUi"}


def _fuente(modulo):
    return open(modulo.__file__, encoding="utf-8").read()


def _widgets_que_usa_el_plugin():
    import re

    from plugins.analysis.connectivity.ppc import ppc_plugin

    usados = set(re.findall(r"self\.ui\.(\w+)", _fuente(ppc_plugin)))
    return usados - NO_SON_WIDGETS


def test_cada_widget_que_el_plugin_lee_existe_en_la_interfaz():
    from plugins.analysis.connectivity.ppc import ppc_plugin_ui

    usados = _widgets_que_usa_el_plugin()
    assert usados, "se esperaba que el plugin leyera algún widget"

    fuente_ui = _fuente(ppc_plugin_ui)
    faltan = [n for n in sorted(usados) if f"self.{n}" not in fuente_ui]
    assert not faltan, (
        f"el plugin lee widgets que la interfaz no define: {faltan}. "
        f"Si se renombraron, hay que cambiar las dos puntas.")


def test_el_doble_de_la_prueba_ofrece_lo_mismo_que_el_plugin_usa():
    """Para que el doble no se quede atrás del plugin y lo tape."""
    usados = _widgets_que_usa_el_plugin()
    falso = _UiFalsa()
    faltan = [n for n in sorted(usados) if not hasattr(falso, n)]
    assert not faltan, f"al doble de la interfaz le faltan: {faltan}"


# ============================================================
#   El dibujo
# ============================================================
def test_el_resultado_se_manda_a_dibujar(listo):
    """`_on_ppc_done` llama a `render_resultado` con el resultado del cálculo."""
    p, _, _ = listo
    p.on_create_ppc()
    assert esperar(lambda: p._ultimo is not None)
    assert p.dibujados == [p._ultimo["resultado"]]


def test_el_plugin_declara_el_dibujo_y_la_exportacion():
    for nombre in ("render_resultado", "ensure_vtk", "exportar_resultados",
                   "get_analysis_params", "apply_analysis_params"):
        assert callable(getattr(Ppc_plugin, nombre, None)), nombre
