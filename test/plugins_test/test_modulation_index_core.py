"""El comodulograma del índice de modulación, portado de `f_PAC_sing`.

Hasta ahora `compute.py` del índice de modulación solo se probaba desde la
interfaz, con un barrido chico para que corriera rápido. Eso dejó sin cubrir el
caso más importante de todos: **los valores con los que el panel arranca**. Una
guarda de Nyquist mal planteada los rechazaba enteros y ninguna prueba se
enteró. De ahí este archivo.
"""
import numpy as np
import pytest

from core.filters.iir import filtro_iir, tope_banda_alta

from plugins.analysis.time_frequency.modulation_index.compute import (
    ANCHO_BANDA_AMPLITUD, CICLOS_MINIMOS_FASE, LIMITE_BANDAS_AMPLITUD, comodulograma,
    eje_barrido)

FS = 1000.0

# Lo que trae el panel al abrirlo. Están aquí como constantes y no sueltos en
# cada prueba para que se vea de un vistazo qué es lo que se está defendiendo.
POR_DEFECTO = dict(p_ini=0.1, p_fin=10.0, pstep=0.1,
                   a_ini=10.0, a_fin=500.0, astep=0.5)


class Ctx:
    """El contexto que inyecta el orquestador, reducido a lo que se usa aquí."""
    cancelled = False

    def __init__(self):
        self.avances = []

    def progress(self, pct, msg=""):
        self.avances.append((pct, msg))


def senal(dur=2.0, fs=FS, f_lenta=3.5, f_rapida=75.0):
    """Un acoplamiento fase-amplitud construido a mano: la envolvente del ritmo
    rápido sigue al lento, así que el máximo del comodulograma tiene que caer
    donde se puso."""
    t = np.arange(int(fs * dur)) / fs
    lento = np.cos(2 * np.pi * f_lenta * t)
    return lento + 0.5 * ((1 + lento) / 2) * np.sin(2 * np.pi * f_rapida * t)


# ------------------------------------------------------------------ eje_barrido

def test_eje_barrido_incluye_el_extremo_cuando_cae_justo():
    """`a:paso:b` de MATLAB llega hasta `b` si la división es exacta."""
    assert eje_barrido(10.0, 12.0, 0.5).tolist() == [10.0, 10.5, 11.0, 11.5, 12.0]


def test_eje_barrido_corta_antes_cuando_no_cae_justo():
    assert eje_barrido(10.0, 11.2, 0.5).tolist() == [10.0, 10.5, 11.0]


def test_eje_barrido_por_defecto_da_981_frecuencias():
    """El número del que sale el 81,9 % de filas vacías con los valores de fábrica."""
    assert eje_barrido(10.0, 500.0, 0.5).size == 981


def test_eje_barrido_rechaza_paso_cero():
    with pytest.raises(ValueError, match="mayor que cero"):
        eje_barrido(10.0, 20.0, 0.0)


# ------------------------------------------- la guarda de Nyquist (regresión)

def test_los_valores_por_defecto_del_panel_calculan():
    """**La regresión.**

    El barrido por defecto termina en 500 Hz y la señal se muestrea a 1.000, así
    que la última frecuencia del barrido más los 10 Hz de ancho de banda daría
    510 Hz, por encima del Nyquist de 500. Pero esa banda **no se filtra nunca**:
    el límite de 178 corta en 98,5 Hz. MATLAB tampoco le diseña filtro.

    La guarda miraba `rango_amplitud[-1]` en vez de la última banda realmente
    calculada y tumbaba el caso por defecto con un error de Nyquist.
    """
    r = comodulograma(Ctx(), senal(), FS, FS, limite_matlab=True, **POR_DEFECTO)
    assert r is not None
    assert r.bandas_calculadas == LIMITE_BANDAS_AMPLITUD
    tope = r.frecuencias_amplitud[r.bandas_calculadas - 1] + ANCHO_BANDA_AMPLITUD
    assert tope == pytest.approx(108.5), "la banda 178 es la de 98,5-108,5 Hz"


def test_avisa_cuando_la_banda_178_si_se_pasa_de_nyquist():
    """La guarda sigue haciendo falta: con un paso grande la banda número 178
    sí llega por encima del Nyquist, y ahí el filtro reventaría."""
    with pytest.raises(ValueError, match="Nyquist"):
        comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                      a_ini=10.0, a_fin=1000.0, astep=3.0, limite_matlab=True)


def test_el_mensaje_de_nyquist_nombra_la_banda_que_se_calcula():
    """Si dijera 'la última banda del barrido' mandaría al usuario a cambiar un
    número que no es el que manda."""
    with pytest.raises(ValueError) as e:
        comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                      a_ini=10.0, a_fin=1000.0, astep=3.0, limite_matlab=True)
    assert "551" in str(e.value), "10 + 177*3 + 10 = 551 Hz, la banda 178"


# ------------------------------------------------ el límite de 178 de MATLAB

def test_solo_calcula_178_bandas_y_el_resto_queda_en_nan():
    r = comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                      a_ini=30.0, a_fin=120.0, astep=0.5, limite_matlab=True)
    assert r.frecuencias_amplitud.size == 181
    assert r.bandas_calculadas == 178
    filas_vacias = np.all(np.isnan(r.mi_norm), axis=1)
    assert filas_vacias.sum() == 3
    assert filas_vacias[-3:].all(), "las que faltan son las tres de arriba"


def test_un_barrido_con_menos_de_178_bandas_avisa_en_vez_de_reventar():
    """Solo al reproducir MATLAB, donde es un error de índice fuera de rango."""
    with pytest.raises(ValueError, match="178"):
        comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                      a_ini=30.0, a_fin=50.0, astep=0.5, limite_matlab=True)


# ----------------------------------------------------------------- validación

@pytest.mark.parametrize("campos,trozo", [
    (dict(p_ini=0.0), "inicial de fase"),
    (dict(p_ini=8.0, p_fin=2.0), "final de fase"),
    (dict(a_ini=0.0), "inicial de amplitud"),
    (dict(a_ini=120.0, a_fin=30.0), "final de amplitud"),
])
def test_los_rangos_al_reves_o_en_cero_avisan_en_espanol(campos, trozo):
    args = dict(p_ini=2.0, p_fin=8.0, pstep=1.0, a_ini=30.0, a_fin=120.0, astep=0.5)
    args.update(campos)
    with pytest.raises(ValueError, match=trozo):
        comodulograma(Ctx(), senal(), FS, FS, **args)


# ------------------------------------------------------------- el orquestador

def test_cancelar_antes_de_empezar_devuelve_none():
    ctx = Ctx()
    ctx.cancelled = True
    assert comodulograma(ctx, senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                         a_ini=30.0, a_fin=120.0, astep=0.5) is None


def test_informa_el_avance_en_dos_tramos():
    """Primero las bandas de fase, después las de amplitud: el usuario tiene que
    ver que algo se mueve durante los 178 filtros."""
    ctx = Ctx()
    comodulograma(ctx, senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                  a_ini=30.0, a_fin=120.0, astep=0.5)
    mensajes = [m for _, m in ctx.avances]
    assert any(m.startswith("Fase") for m in mensajes)
    assert any(m.startswith("Amplitud") for m in mensajes)
    pcts = [p for p, _ in ctx.avances]
    assert pcts == sorted(pcts), "el avance no puede ir hacia atrás"
    assert pcts[-1] == 100


# ------------------------------------------- ciclos de la banda de fase lenta

def test_cuenta_los_ciclos_de_la_banda_de_fase_mas_lenta():
    """`duracion x p_ini`: cuantos ciclos del ritmo mas lento caben en el trial."""
    r = comodulograma(Ctx(), senal(dur=2.0), FS, FS, p_ini=2.0, p_fin=8.0, pstep=1.0,
                      a_ini=30.0, a_fin=120.0, astep=0.5)
    assert r.duracion_s == pytest.approx(2.0)
    assert r.ciclos_banda_lenta == pytest.approx(4.0)


def test_los_ciclos_se_miden_sobre_la_senal_ya_submuestreada():
    """Si se submuestrea, la duración no cambia; el conteo tampoco debe hacerlo."""
    sig = senal(dur=2.0, fs=2000.0)
    r = comodulograma(Ctx(), sig, 2000.0, FS, p_ini=3.0, p_fin=8.0, pstep=1.0,
                      a_ini=30.0, a_fin=120.0, astep=0.5)
    assert r.fs_efectiva == pytest.approx(1000.0)
    assert r.duracion_s == pytest.approx(2.0)
    assert r.ciclos_banda_lenta == pytest.approx(6.0)


def test_los_valores_por_defecto_caen_muy_por_debajo_del_minimo():
    """Con `Fq P1 = 0,1` haría falta un trial de un minuto para llegar a 6 ciclos.

    Es justo lo que hacía que el máximo del comodulograma apareciera pegado al
    borde izquierdo, donde no puede haber nada medible.
    """
    r = comodulograma(Ctx(), senal(dur=3.05), FS, FS, **POR_DEFECTO)
    assert r.ciclos_banda_lenta == pytest.approx(0.305)
    assert r.ciclos_banda_lenta < CICLOS_MINIMOS_FASE


def test_el_umbral_de_ciclos_es_el_que_se_midio():
    """Si alguien lo cambia sin medir de nuevo, que al menos falle una prueba."""
    assert CICLOS_MINIMOS_FASE == 6.0


# ------------------------------------------------- calcular todas las bandas

def test_el_comodulograma_sale_lleno():
    """Si todas las bandas caben, no queda ni una fila vacía."""
    r = comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=2.0,
                      a_ini=30.0, a_fin=120.0, astep=0.5, limite_matlab=False)
    assert r.bandas_calculadas == r.frecuencias_amplitud.size == 181
    assert not np.isnan(r.mi_norm).any()
    assert r.limite_matlab is False


def test_por_omision_se_calcula_todo_y_no_el_tope_de_matlab():
    """El tope de 178 dejó de ser el comportamiento normal: hay que pedirlo."""
    r = comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=2.0,
                      a_ini=30.0, a_fin=120.0, astep=0.5)
    assert r.bandas_calculadas == r.frecuencias_amplitud.size == 181
    assert r.limite_matlab is False


def test_se_puede_pedir_el_tope_de_matlab_para_comparar():
    r = comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=2.0,
                      a_ini=30.0, a_fin=120.0, astep=0.5, limite_matlab=True)
    assert r.bandas_calculadas == LIMITE_BANDAS_AMPLITUD
    assert r.limite_matlab is True


def test_calcular_de_mas_no_cambia_las_primeras_178_filas():
    """Lo que hacía innecesaria la casilla que llegó a existir.

    Cada fila del comodulograma sale de **su** banda de amplitud y de ninguna
    otra: `S[ca, cp] = Σ m_amp[n, ca]·e^{i·m_fase[n, cp]}`. Así que reproducir
    la referencia de MATLAB no exige recortar el barrido — basta con mirar las
    primeras 178 filas del comodulograma completo.
    """
    args = dict(p_ini=2.0, p_fin=8.0, pstep=2.0, a_ini=30.0, a_fin=120.0, astep=0.5)
    sig = senal()
    recortado = comodulograma(Ctx(), sig, FS, FS, limite_matlab=True, **args)
    completo = comodulograma(Ctx(), sig, FS, FS, **args)
    n = LIMITE_BANDAS_AMPLITUD
    assert np.array_equal(recortado.mi_norm[:n], completo.mi_norm[:n])
    assert np.array_equal(recortado.mi[:n], completo.mi[:n])


def test_admite_barridos_de_menos_de_178():
    """Un barrido corto ya no es un error: se calcula entero."""
    r = comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=2.0,
                      a_ini=30.0, a_fin=50.0, astep=0.5, limite_matlab=False)
    assert r.bandas_calculadas == 41
    assert not np.isnan(r.mi_norm).any()


def test_recorta_en_nyquist_en_vez_de_abortar():
    """Las bandas que no admiten filtro se quedan en NaN; el resto se calcula.

    Abortar el barrido entero por las de arriba sería tirar trabajo útil.
    """
    r = comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=2.0,
                      a_ini=10.0, a_fin=600.0, astep=1.0, limite_matlab=False)
    assert r.frecuencias_amplitud.size == 591
    assert r.bandas_calculadas == 480, "la 480 llega a 499 Hz; la 481 ya tocaría 500"
    assert np.all(np.isnan(r.mi_norm[480:]))
    assert not np.isnan(r.mi_norm[:480]).any()


def test_avisa_si_ni_la_primera_banda_cabe():
    with pytest.raises(ValueError, match="Ninguna banda"):
        comodulograma(Ctx(), senal(), FS, FS, p_ini=2.0, p_fin=8.0, pstep=2.0,
                      a_ini=495.0, a_fin=600.0, astep=1.0, limite_matlab=False)


def test_el_tope_de_filtro_coincide_con_lo_que_acepta_filtro_iir():
    """`tope_banda_alta` no puede ser una estimación: si se separa de lo que
    `filtro_iir` admite de verdad, el recorte deja bandas sin calcular o revienta."""
    tope = tope_banda_alta(FS)
    for f2, cabe in ((tope - 0.5, True), (tope - 0.01, True), (tope, False), (tope + 1, False)):
        try:
            filtro_iir(FS, f2 - 10.0, f2)
            pudo = True
        except ValueError:
            pudo = False
        assert pudo is cabe, f"f2={f2:g}: filtro_iir dice {pudo}, el tope decía {cabe}"
