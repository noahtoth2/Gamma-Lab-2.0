"""PAC Psel entre canales: los ciclos y la fase de un canal, la amplitud de otro.

Réplica de `f_Phase_PAC_Pdetect_inter`. Lo que se comprueba aquí no es que el
cálculo sea nuevo —no lo es, es el mismo `pac_psel`— sino que **cada cosa venga
del canal que le toca**, que es justo lo que el original tiene mal resuelto.

El reparto que se verifica:

| Qué | De qué canal |
|---|---|
| los ciclos, la fase y `ciclos_theta` | el de **fase** |
| `ciclos_full`, `ciclos_gamma` y el mapa | el de **amplitud** |

Y la garantía que lo hace seguro: pasándole la misma señal como los dos canales,
el resultado es **idéntico bit a bit** al de un canal. Las 124 pruebas de
`test_pac_core` no se tocan porque el camino que recorren no cambió.
"""
import numpy as np
import pytest

from plugins.analysis.time_frequency.pac import compute as cp

FS = 2000.0
FL = 5.0        # el ritmo lento, dentro de la banda de fase 3-8
FR = 45.0       # la portadora rapida, dentro de la banda de amplitud 25-60
P1, P2, A1, A2 = 3.0, 8.0, 25.0, 60.0


class Ctx:
    cancelled = False

    def __init__(self):
        self.avances = []

    def progress(self, pct, msg=""):
        self.avances.append((pct, msg))


def canal(con_gamma, semilla, n_trials=6, dur=3.0):
    """Un canal con el ritmo lento y, si se pide, el gamma enganchado al valle.

    El ritmo lento es **idéntico** en todos los canales que fabrica esta función:
    solo cambian el ruido y la presencia del gamma. Así, cuando dos pruebas
    comparten el canal de fase, comparten también los valles, y cualquier
    diferencia en el resultado viene de dónde está el gamma y no de qué ciclos
    se eligieron.
    """
    t = np.arange(int(FS * dur)) / FS
    lento = np.sin(2 * np.pi * FL * t)
    env = (1 - lento) / 2                      # maximo en el valle
    extra = 0.6 * env * np.sin(2 * np.pi * FR * t) if con_gamma else 0.0
    rng = np.random.default_rng(semilla)
    return np.column_stack([lento + extra + 0.05 * rng.standard_normal(t.size)
                            for _ in range(n_trials)])


def correr(fase, amplitud=None, **extra):
    return cp.pac_psel(Ctx(), fase, FS, FS, P1, P2, A1, A2,
                       data_amplitud=amplitud, **extra)


# Las dos pilas caras, una vez para todo el módulo.
@pytest.fixture(scope="module")
def inter():
    """El gamma está en el canal de amplitud: el caso que este modo existe para ver."""
    return correr(canal(False, 0), canal(True, 1),
                  canal_fase="CA1", canal_amplitud="IN 7")


@pytest.fixture(scope="module")
def inter_control():
    """El gamma está en el canal de fase. El modo entre canales no debe verlo."""
    return correr(canal(True, 0), canal(False, 1))


# ============================================================
#   Lo que mide: el acoplamiento del canal de amplitud
# ============================================================
def test_ve_el_gamma_del_canal_de_amplitud_y_no_el_del_otro(inter, inter_control):
    """**La prueba que discrimina.**

    Mismo ritmo lento en los cuatro canales, mismas bandas, mismos ciclos. Lo
    único que cambia es en cuál de los dos está el gamma. Si el análisis mirara
    el canal equivocado, los dos casos saldrían al revés.
    """
    assert abs(inter.vector) > 0.5, (
        f"con el gamma en el canal de amplitud salió {abs(inter.vector):.4f}")
    assert abs(inter_control.vector) < 0.1, (
        f"con el gamma en el canal de fase salió {abs(inter_control.vector):.4f}")
    assert abs(inter.vector) > 10 * abs(inter_control.vector)


def test_apunta_al_valle_donde_se_construyo(inter):
    """El gamma se metió en el valle del ritmo lento, que es la fase ±pi."""
    ang = abs(float(np.angle(inter.vector)))
    assert ang > 2.5, f"el vector medio apunta a {np.rad2deg(ang):.1f}°, no al valle"


def test_intercambiar_los_canales_cambia_el_resultado():
    """No es simétrico, y no debe serlo: fase y amplitud no son intercambiables."""
    a, b = canal(False, 0), canal(True, 1)
    assert not np.allclose(correr(a, b).mapa, correr(b, a).mapa)


# ============================================================
#   La garantía: con un canal, nada cambió
# ============================================================
NUMERICOS = ("mapa", "frecuencias", "fases", "histograma", "mapa_tf", "tiempo_tf",
             "ciclos_full", "ciclos_theta", "ciclos_gamma", "promedio_theta",
             "promedio_full", "vectores_por_grupo", "senal", "senal_filtrada", "tiempo")


def test_la_misma_senal_como_los_dos_canales_da_lo_mismo_que_un_canal():
    """**La red de seguridad.**

    El camino de dos canales con la misma señal en los dos tiene que reducirse,
    bit a bit, al de un canal. Si esto se rompe, el modo nuevo le cambió el
    resultado a los análisis que ya existían.
    """
    d = canal(True, 0)
    uno = correr(d)
    dos = correr(d, d, permisivo=False)   # permisivo aparte: eso sí cambia a propósito

    for campo in NUMERICOS:
        assert np.array_equal(getattr(uno, campo), getattr(dos, campo)), \
            f"'{campo}' dejó de coincidir con el modo de un canal"
    assert uno.vector == dos.vector
    assert uno.n_ciclos == dos.n_ciclos
    assert uno.ciclos_descartados == dos.ciclos_descartados
    assert (uno.vpp, uno.vpp_full, uno.vrms) == (dos.vpp, dos.vpp_full, dos.vrms)


def test_un_canal_no_llena_los_campos_nuevos():
    r = correr(canal(True, 0))
    assert r.inter_canal is False
    assert r.senal_amplitud is None
    assert r.canal_fase is None and r.canal_amplitud is None
    assert r.permisivo is False


# ============================================================
#   Cada pila, de su canal
# ============================================================
def test_los_ciclos_en_gamma_salen_del_canal_de_amplitud(inter, inter_control):
    """Decisión nuestra, no del original: la `_window` lo saca del canal de fase.

    Con el gamma en el canal de amplitud la pila tiene energía; con el gamma en
    el de fase, la misma pila queda casi plana. Si saliera del canal de fase
    —como en el MATLAB— las dos medidas estarían intercambiadas.
    """
    con = float(np.sqrt(np.mean(inter.ciclos_gamma ** 2)))
    sin = float(np.sqrt(np.mean(inter_control.ciclos_gamma ** 2)))
    assert con > 5 * sin, f"con gamma {con:.4f} y sin gamma {sin:.4f}"


def test_la_onda_lenta_y_los_ciclos_solo_dependen_del_canal_de_fase():
    """Mismo canal de fase y canales de amplitud distintos: los valles, la pila
    de la onda lenta y su promedio tienen que salir idénticos."""
    fase = canal(False, 0)
    a = correr(fase, canal(True, 1))
    b = correr(fase, canal(False, 2))

    assert a.n_ciclos == b.n_ciclos
    assert np.array_equal(a.ciclos_theta, b.ciclos_theta)
    assert np.array_equal(a.promedio_theta, b.promedio_theta)
    assert np.array_equal(a.senal_filtrada, b.senal_filtrada)
    # y, a la vez, lo que sí depende del canal de amplitud cambió
    assert not np.array_equal(a.ciclos_full, b.ciclos_full)


def test_los_ciclos_crudos_son_los_del_canal_de_amplitud(inter):
    """`ciclos_full` son ventanas del canal de amplitud **sin filtrar**, así que
    cada columna tiene que aparecer tal cual dentro de su señal concatenada."""
    assert inter.senal_amplitud is not None
    columna = inter.ciclos_full[:, 0]
    senal = inter.senal_amplitud
    # la ventana sale de algun punto de la senal de amplitud, no de la de fase
    encaja = any(np.allclose(senal[i:i + columna.size], columna)
                 for i in range(0, senal.size - columna.size, 1)
                 if abs(senal[i] - columna[0]) < 1e-12)
    assert encaja, "ciclos_full no proviene de la señal del canal de amplitud"


# ============================================================
#   Los dos canales tienen que estar alineados
# ============================================================
def test_rechaza_canales_con_distinto_numero_de_muestras():
    with pytest.raises(ValueError) as e:
        correr(canal(False, 0, dur=3.0), canal(True, 1, dur=2.0))
    msg = str(e.value)
    assert "no están alineados" in msg
    assert "6000" in msg and "4000" in msg, f"el mensaje no dice las dos formas: {msg}"
    assert "cambiando solo el canal" in msg


def test_rechaza_canales_con_distinto_numero_de_trials():
    with pytest.raises(ValueError) as e:
        correr(canal(False, 0, n_trials=6), canal(True, 1, n_trials=4))
    assert "no están alineados" in str(e.value)


def test_el_canal_de_amplitud_puede_venir_en_una_dimension():
    """Un solo trial llega como vector; se trata como una columna, igual que `data`."""
    fase = canal(False, 0, n_trials=1)
    r = correr(fase[:, 0], canal(True, 1, n_trials=1)[:, 0])
    assert r.inter_canal is True
    assert r.n_ciclos > 0


# ============================================================
#   Los umbrales permisivos
# ============================================================
def test_permisivo_se_enciende_solo_entre_canales(inter):
    assert inter.permisivo is True
    assert correr(canal(True, 0)).permisivo is False


def test_permisivo_se_puede_forzar_en_los_dos_sentidos():
    d = canal(True, 0)
    assert correr(d, permisivo=True).permisivo is True
    assert correr(d, d, permisivo=False).permisivo is False


def test_los_umbrales_permisivos_aceptan_un_superconjunto_de_valles():
    """Relajar los dos umbrales solo puede **quitar** motivos de descarte, nunca
    añadirlos, así que los valles estrictos tienen que seguir estando todos."""
    senal = canal(True, 0)[:, 0]
    sos, _ = cp.filtro_iir(FS, P1, P2)
    lento = cp.bifiltro(sos, senal)
    tiempo = np.arange(lento.size) / FS
    picos, valles = cp.detectar_extremos(lento)
    ceros = cp.cruces_por_cero(lento)
    min_t, max_t = 0.5 / P2, 0.5 / P1

    estrictos = cp.seleccionar_valles(lento, tiempo, picos, valles, ceros,
                                      min_t, max_t, permisivo=False)
    sueltos = cp.seleccionar_valles(lento, tiempo, picos, valles, ceros,
                                    min_t, max_t, permisivo=True)

    assert set(estrictos.tolist()) <= set(sueltos.tolist())
    assert sueltos.size >= estrictos.size


def test_permisivo_no_reduce_el_numero_de_ciclos():
    d = canal(True, 0)
    assert correr(d, d, permisivo=True).n_ciclos >= correr(d, d, permisivo=False).n_ciclos


# ============================================================
#   Los nombres, que son los que rotulan los paneles
# ============================================================
def test_guarda_el_nombre_de_cada_canal(inter):
    """El panel de gamma no lleva rótulo en MATLAB, y es justo lo que hace falta
    para saber qué se está mirando. El resultado tiene que cargar los nombres."""
    assert inter.canal_fase == "CA1"
    assert inter.canal_amplitud == "IN 7"
