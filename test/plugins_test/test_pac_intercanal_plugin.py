"""El cableado del modo «PAC Psel inter-canal» en el plugin.

No se prueba el cálculo —eso es `test_pac_intercanal.py`— sino que la interfaz
ofrezca el modo y el selector de canal se comporte: que aparezca solo cuando
toca, que se llene con los canales de la señal, que **no ofrezca el canal
activo** (ese es el de fase, y el acoplamiento de un canal consigo mismo ya es
el modo «PAC Psel» de siempre) y que respete lo que el usuario había elegido.

**La interfaz es un doble, y no por comodidad.** Casi toda la suite levanta una
`QCoreApplication`, bajo la cual crear widgets de Qt aborta el proceso sin
mensaje. El doble ofrece la misma API que el plugin usa y el contrato de
nombres se comprueba aparte, leyendo los dos archivos.
"""
from pathlib import Path

import pytest

from plugins.analysis.time_frequency.pac.pac_plugin import Pac_plugin

RAIZ = Path(__file__).resolve().parents[2] / "plugins/analysis/time_frequency/pac"
WIDGETS = ("ampChannelLabel", "ampChannelLine", "ampChannelComboBox")


# ------------------------------------------- el doble de la interfaz
class _Combo:
    def __init__(self, texto=""):
        self.items, self._texto, self.visible, self.mudo = [], texto, True, False

    def currentText(self):
        return self._texto

    def clear(self):
        self.items, self._texto = [], ""

    def addItems(self, xs):
        self.items.extend(xs)
        if not self._texto and self.items:      # Qt elige el primero al llenar
            self._texto = self.items[0]

    def setCurrentText(self, t):
        self._texto = t

    def findText(self, t):
        return self.items.index(t) if t in self.items else -1

    def blockSignals(self, v):
        self.mudo = bool(v)

    def setVisible(self, v):
        self.visible = bool(v)

    def isVisible(self):
        return self.visible


class _Widget:
    def __init__(self):
        self.visible, self.texto, self.habilitado = True, "", True

    def setVisible(self, v):
        self.visible = bool(v)

    def isVisible(self):
        return self.visible

    def setText(self, t):
        self.texto = t

    def setEnabled(self, v):
        self.habilitado = bool(v)


class _Spin(_Widget):
    def __init__(self):
        super().__init__()
        self._v, self._max = 1, 1

    def value(self):
        return self._v

    def setValue(self, v):
        self._v = v

    def setMaximum(self, v):
        self._max = v


class _Ui:
    def __init__(self, tipo=Pac_plugin.PSEL_INTER):
        self.pacTypeComboBox = _Combo(tipo)
        self.ampChannelComboBox = _Combo()
        self.ampChannelLabel = _Widget()
        self.ampChannelLine = _Widget()
        self.trialSpinBox = _Spin()
        self.prevTrialButton = _Widget()
        self.nextTrialButton = _Widget()
        self.trialTotalLabel = _Widget()


class _Trials:
    def __init__(self, canal):
        self.channel_name = canal


class _Senal:
    def __init__(self, canales):
        self.channel_names = list(canales)


def plugin(tipo=Pac_plugin.PSEL_INTER, canales=("CA1", "IN 7", "IN 8"), activo="CA1"):
    p = object.__new__(Pac_plugin)
    p.ui = _Ui(tipo)
    sig = _Senal(canales) if canales is not None else None
    td = _Trials(activo) if activo is not None else None
    p._active_trials_quiet = lambda: (sig, td)
    p.get_active_trials = lambda: None          # para `_n_trials`
    return p


# ============================================================
#   El modo existe y comparte camino con Psel
# ============================================================
def test_el_modo_esta_en_la_lista_y_va_al_final():
    assert Pac_plugin.PSEL_INTER in Pac_plugin.PAC_TYPES
    assert Pac_plugin.PAC_TYPES[-1] == Pac_plugin.PSEL_INTER
    assert len(Pac_plugin.PAC_TYPES) == len(set(Pac_plugin.PAC_TYPES))


def test_los_dos_modos_psel_dibujan_los_mismos_paneles():
    """`_es_psel` es lo que manda el resultado a `render_psel`, los 13 paneles."""
    p = plugin()
    assert p._es_psel(Pac_plugin.PSEL)
    assert p._es_psel(Pac_plugin.PSEL_INTER)
    assert not p._es_psel("PAC")
    assert not p._es_psel("PAC Average")


def test_el_modo_entre_canales_no_usa_un_solo_trial():
    """Concatena todos, como Psel, así que el selector de trial no aplica."""
    assert plugin(tipo=Pac_plugin.PSEL_INTER)._usa_un_solo_trial() is False
    assert plugin(tipo="PAC")._usa_un_solo_trial() is True


# ============================================================
#   El selector de canal
# ============================================================
@pytest.mark.parametrize("tipo", ["PAC", "PAC Average", Pac_plugin.PSEL])
def test_el_selector_se_oculta_en_los_demas_modos(tipo):
    p = plugin(tipo=tipo)
    p._actualizar_selector_canal()
    for nombre in WIDGETS:
        assert getattr(p.ui, nombre).isVisible() is False, f"{nombre} quedó visible en {tipo}"


def test_el_selector_aparece_y_se_llena_entre_canales():
    p = plugin()
    p._actualizar_selector_canal()
    for nombre in WIDGETS:
        assert getattr(p.ui, nombre).isVisible() is True
    assert p.ui.ampChannelComboBox.items == ["IN 7", "IN 8"]


def test_no_ofrece_el_canal_activo():
    """El activo es el de fase. Ofrecerlo sería ofrecer «PAC Psel» con otro nombre."""
    p = plugin(canales=("CA1", "IN 7", "IN 8"), activo="IN 7")
    p._actualizar_selector_canal()
    assert "IN 7" not in p.ui.ampChannelComboBox.items
    assert p.ui.ampChannelComboBox.items == ["CA1", "IN 8"]


def test_respeta_el_canal_que_el_usuario_ya_habia_elegido():
    p = plugin()
    p._actualizar_selector_canal()
    p.ui.ampChannelComboBox.setCurrentText("IN 8")
    p._actualizar_selector_canal()          # un refresco cualquiera
    assert p.ui.ampChannelComboBox.currentText() == "IN 8"


def test_si_el_canal_elegido_desaparece_no_se_queda_colgado():
    p = plugin()
    p._actualizar_selector_canal()
    p.ui.ampChannelComboBox.setCurrentText("IN 8")
    p._active_trials_quiet = lambda: (_Senal(("CA1", "IN 7")), _Trials("CA1"))
    p._actualizar_selector_canal()
    assert p.ui.ampChannelComboBox.currentText() == "IN 7"


def test_sin_senal_cargada_no_revienta():
    p = plugin(canales=None, activo=None)
    p._actualizar_selector_canal()
    assert p.ui.ampChannelComboBox.items == []
    assert p.ui.ampChannelComboBox.isVisible() is True   # visible pero vacío


def test_sin_interfaz_montada_no_revienta():
    """Se llama durante la restauración de un proyecto, antes de que haya UI."""
    p = object.__new__(Pac_plugin)
    p.ui = None
    p._actualizar_selector_canal()      # no debe lanzar


def test_el_selector_de_trial_arrastra_al_de_canal():
    """`_actualizar_selector_trial` ya está conectado al cambio de tipo y de
    datos; el de canal cuelga de ahí para no duplicar conexiones."""
    p = plugin(tipo="PAC")
    p._actualizar_selector_trial()
    assert p.ui.ampChannelComboBox.isVisible() is False

    p.ui.pacTypeComboBox.setCurrentText(Pac_plugin.PSEL_INTER)
    p._actualizar_selector_trial()
    assert p.ui.ampChannelComboBox.isVisible() is True
    assert p.ui.ampChannelComboBox.items == ["IN 7", "IN 8"]


# ============================================================
#   El contrato de nombres con el archivo de la interfaz
# ============================================================
def test_la_interfaz_declara_los_widgets_que_el_plugin_usa():
    """El doble de arriba no puede detectar que la UI de verdad cambie de
    nombre, así que el contrato se comprueba leyendo los dos archivos."""
    ui = (RAIZ / "pac_plugin_ui.py").read_text(encoding="utf-8")
    plug = (RAIZ / "pac_plugin.py").read_text(encoding="utf-8")
    for nombre in WIDGETS:
        assert f"self.{nombre}" in ui, f"la interfaz no declara {nombre}"
        assert nombre in plug, f"el plugin no usa {nombre}"


def test_el_selector_lleva_ayuda_que_explica_de_donde_sale_cada_cosa():
    ui = (RAIZ / "pac_plugin_ui.py").read_text(encoding="utf-8")
    assert "ampChannelComboBox.setToolTip" in ui
    assert "cortados igual" in ui, "la ayuda no avisa de que los cortes deben coincidir"
