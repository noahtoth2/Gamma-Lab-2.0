"""La Gabor vive en `core/filters/` y PAC la sigue viendo por su nombre.

Fase 1 del plan de PPC. `gabor_tf` empezó dentro del `compute.py` de PAC y
subió a `core` cuando PPC pasó a necesitarla. Estas pruebas cuidan las dos
mitades del movimiento: que esté arriba, y que abajo no se haya roto nada.
"""
import numpy as np

from core.filters import gabor as nucleo
from plugins.analysis.time_frequency.pac import compute as pac


def test_la_funcion_vive_en_core():
    assert callable(nucleo.gabor_tf)
    assert nucleo.gabor_tf.__module__ == "core.filters.gabor"


def test_pac_la_reexporta_y_es_la_misma():
    """No una copia: el mismo objeto. Si se duplicara, una se arreglaría y la
    otra no."""
    assert pac.gabor_tf is nucleo.gabor_tf
    assert pac.CICLOS_GABOR is nucleo.CICLOS_GABOR


def test_la_constante_conserva_su_valor():
    """1, no 3. La cabecera del .m dice 3 pero `f_Phase_PAC_Pdetect` pasa 1."""
    assert nucleo.CICLOS_GABOR == 1.0


def test_no_quedo_una_copia_en_pac():
    """El `compute.py` de PAC no puede volver a definirla: tiene que importarla."""
    fuente = open(pac.__file__, encoding="utf-8").read()
    assert "def gabor_tf(" not in fuente
    assert "from core.filters.gabor import" in fuente


def test_core_no_importa_plugins():
    """La dirección de la dependencia: `core` no puede mirar hacia `plugins`.

    Se miran los `import`, no el texto: los comentarios sí nombran a `plugins`
    —para decir de dónde vino la función y dónde quedó la Morse— y eso es
    documentación, no un acoplamiento.
    """
    import ast
    arbol = ast.parse(open(nucleo.__file__, encoding="utf-8").read())
    modulos = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos += [a.name for a in nodo.names]
        elif isinstance(nodo, ast.ImportFrom):
            modulos.append(nodo.module or "")
    assert modulos, "se esperaba al menos un import"
    for m in modulos:
        assert not m.startswith("plugins"), f"core/filters/gabor.py importa {m}"


def test_sigue_calculando_lo_mismo():
    """Una corrida de referencia, para que el movimiento no tape un cambio."""
    fs = 1000.0
    t = np.arange(501) / fs
    x = np.sin(2 * np.pi * 60 * t) + 0.3 * np.sin(2 * np.pi * 110 * t)

    tf, eje_t, eje_f = nucleo.gabor_tf(x, fs, 25.0, 129.0, 40)

    assert tf.shape == (40, 501)
    assert eje_t.size == 501
    assert eje_f[0] > eje_f[-1], "el eje de frecuencias va descendente"
    # la fila de más energía tiene que caer sobre los 60 Hz de la señal
    fila = int(np.argmax(tf.mean(axis=1)))
    assert abs(eje_f[fila] - 60.0) < 5.0
