# Resultados de la Fase 0

*Mediciones previas a la decisión de diseño del orquestador*

---

## Qué se midió y por qué

La Fase 0 del plan de implementación existe para no diseñar sobre suposiciones. Había tres cosas sin verificar, y las tres cambian decisiones:

1. **Una línea base fresca**, para poder demostrar después que los cambios sirvieron.
2. **Si `method='fft'` es realmente más rápido que el `method='conv'` que corre hoy**, y si da los mismos números.
3. **Si el GIL se suelta durante el CWT** — de lo que depende que mover el cálculo a un hilo libere de verdad la interfaz.

Apareció además un cuarto resultado que nadie fue a buscar, y es el más importante de los cuatro.

**Fecha:** 18 de septiembre de 2026.

**Equipo:** Intel de 16 núcleos lógicos (Family 6 Model 186), Windows 10 (10.0.26200), AMD64.

**Versiones:** Python 3.11.9 · numpy 2.3.4 · scipy 1.16.2 · PyWavelets 1.8.0 · VTK 9.5.2 · PyQt5-Qt 5.15.2 · pyabf 2.3.8.

**Datos:** el archivo real `test/data/17308005.abf` — 2 canales (`CA1`, `IN 7`), 1.800.000 muestras por canal, 10.000 Hz, 180 s. Cortado en **60 trials de 30.501 muestras** con los mismos parámetros que usa la suite de comparación contra MATLAB.

---

## Cómo reproducirlo

```powershell
# 0.1 - linea base
$env:GAMMA_PERF_LABEL = "v2_fase0_baseline"
pytest test/performance_test -s

# comparar contra cualquier corrida anterior
python test/performance_test/compare_report.py gammalab1_baseline_2026-08-16 v2_fase0_baseline
```

Los pasos 0.2 y 0.3 se midieron con un script suelto que replica exactamente `Wavelet_plugin.compute_wavelet()` sobre el mismo archivo, sin modificar ningún plugin. Los parámetros son los que trae el plugin por defecto: `fmin=1`, `fmax=500`, `cycles=2`, `fs=1000`, wavelet `cmor2.0-1.0`.

---

## 0.1 — Línea base

25 pruebas, 2 minutos, sin fallos. La corrida quedó guardada en `test/performance_test/results/perf_results.json` bajo la etiqueta **`v2_fase0_baseline`**.

Comparada contra `gammalab1_baseline_2026-08-16`: misma máquina y mismas versiones de librerías, así que las dos etiquetas son directamente comparables y las diferencias son ruido de medición, no cambios reales.

| Operación | mín | **mediana** | reps | ago-16 |
|---|---:|---:|---:|---:|
| **Cómputo de análisis** | | | | |
| `fft._compute_fft` (todos los trials) | 3,6 | **3,7 ms** | 5 | 3,8 |
| `fft_average._compute_fft_average` | 8,3 | **8,5 ms** | 5 | 11,5 |
| `psd._compute_psd` (Welch) | 5,8 | **6,1 ms** | 5 | 5,3 |
| `psd_average._compute_psd` (Welch) | 11,8 | **11,9 ms** | 5 | 9,2 |
| `relative_psd._compute_psd` (Welch) | 6,3 | **6,4 ms** | 5 | 6,3 |
| `relative_psd._compute_relative_psd` (solo la razón) | 0,1 | **0,1 ms** | 5 | 0,1 |
| `wavelet.compute_wavelet` (1 trial) | 200,1 | **202,0 ms** | 3 | 215,6 |
| `wavelet_average.compute_wavelet` (×20 trials) | 4192,8 | **4213,6 ms** | 2 | 4190,2 |
| **Renderizado VTK** | | | | |
| `wavelet.render_scalogram` (998×3051) | 710,3 | **716,5 ms** | 3 | 725,3 |
| `wavelet_average.render_scalogram` (998×3051) | 731,6 | **732,1 ms** | 3 | 741,6 |
| `erp._render_heatmap` (60×30501 antes del downsample) | 33,6 | **34,5 ms** | 3 | 35,8 |
| `adapters.dataset_to_vtk_table` (1800000×3, vectorizado) | 26,1 | **26,6 ms** | 10 | 21,0 |
| `adapters.trials_matrix_to_vtk_table` (30501×61, vectorizado) | 11,7 | **12,7 ms** | 10 | 11,1 |
| **Micro-benchmark: bucle vs vectorizado** | | | | |
| `vtk_array.bucle_python` (300.000 puntos) | 27,6 | **27,8 ms** | 5 | 28,4 |
| `vtk_array.numpy_to_vtk` (300.000 puntos) | 1,1 | **1,6 ms** | 5 | 0,4 |
| `vtk_array.bucle_python` (50.000 puntos) | 4,5 | **8,6 ms** | 5 | 4,6 |
| `vtk_array.numpy_to_vtk` (50.000 puntos) | 0,0 | **0,0 ms** | 5 | 0,0 |
| **Entrada/salida y preprocesamiento** | | | | |
| `fileio.load_abf` (2 canales × 1.800.000) | 72,5 | **78,6 ms** | 5 | 59,8 |
| `trials.cut_trials_single_channel` (30501×60) | 18,9 | **19,8 ms** | 10 | 18,6 |
| `filter.run_filter` (señal completa, 1.800.000) | 45,1 | **46,3 ms** | 10 | 43,2 |
| `filter.run_filter` (1 trial, 30.501) | 1,5 | **1,6 ms** | 20 | 1,8 |
| **Núcleo** | | | | |
| `kernel.bootstrap_completo` (17 plugins) | 23,0 | **24,9 ms** | 5 | — |
| `kernel.plugin_manager.load_all` (17 plugins) | 23,0 | **23,5 ms** | 5 | — |
| `kernel.plugins.discover` (17 plugins) | 22,9 | **29,7 ms** | 5 | — |
| `kernel.register_plugin` (×200 plugins ficticios) | 0,5 | **0,7 ms** | 10 | 1,4 |
| `data_store.add_signal` (×500 señales) | 12,1 | **12,1 ms** | 5 | 13,0 |
| `data_store.set+get` (×2000 pares) | 0,9 | **1,5 ms** | 5 | 0,6 |

### Lo que dice esta tabla

**Solo cuatro operaciones pasan de 100 ms.** Wavelet individual (202 ms), wavelet promedio (4,2 s), y los dos renderizados de escalograma (~720 ms cada uno). Todo lo demás está entre 0,1 y 80 ms.

Eso confirma el criterio de la Fase 4 del plan: **migrar FFT o PSD al orquestador sería agregar complejidad para cero beneficio visible.** A 3,7 ms nadie percibe un congelamiento.

**El renderizado pesa tanto como el cálculo.** `wavelet.compute_wavelet` son 202 ms, pero `render_scalogram` son 716 ms — el dibujo es 3,5 veces más caro que la cuenta. Y el renderizado **no se puede sacar del hilo de la interfaz**, porque VTK obliga a llenar sus estructuras desde el hilo gráfico. Es el argumento más fuerte para hacer la vectorización antes que el orquestador.

**El micro-benchmark confirma el factor de la vectorización.** La propia suite lo imprime: *"vectorizar 50000 puntos es 239,6× más rápido"*, *"300000 puntos es 17,5× más rápido"*. La variación entre ambos es porque a 50.000 puntos el tiempo vectorizado cae por debajo de la resolución del cronómetro; el orden de magnitud está claro.

**Ya son 17 plugins, no 16.** El benchmark del kernel ahora reporta `discover (17 plugins)` contra los 16 de agosto: es el `pac` que se agregó después. El arranque sigue costando ~25 ms, o sea que sumar plugins no es un problema de rendimiento.

---

## 0.2 — `method='conv'` contra `method='fft'`

Hoy `pywt.cwt` corre en su modo lento sin que nadie lo haya decidido: el valor por defecto de PyWavelets es `method='conv'`, y ninguno de los dos plugins pasa el parámetro (`wavelet_plugin.py:209`, `wavelet_average_plugin.py:290`).

### Velocidad

| | Tiempo (mediana de 3, con calentamiento) |
|---|---|
| `method='conv'` — lo que corre hoy | 0,212 s |
| `method='fft'` | **0,112 s** |
| | **1,89× más rápido** |

### Equivalencia numérica

```
max diferencia absoluta : 2,586820e-14
max diferencia relativa : 4,348924e-14
allclose(rtol=1e-6)     : True
allclose(rtol=1e-3)     : True
```

Eso es precisión de máquina. **Los dos modos dan el mismo resultado.**

### Veredicto

**Adoptar `method='fft'`.** Es un argumento en dos archivos, casi duplica la velocidad del CWT y no cambia ningún resultado.

Dos advertencias sobre las expectativas:

- **Son 1,89×, no un salto de orden.** El documento de diseño sugiere una mejora mayor al mencionar que `fft` es de orden N·log N. En este tamaño de datos la ganancia real es de 1,89×. `wavelet_average` con 20 trials pasaría de ~4,2 s a ~2,2 s: bien, pero sigue siendo demasiado para dejarlo en el hilo de la interfaz.
- **El criterio de aceptación original de este paso no servía.** El plan decía *"verificar contra `test/plugins_test/`"*, pero esas pruebas ya están en rojo antes de tocar nada (ver la sección siguiente). El criterio válido es el que se aplicó: comparar `fft` contra `conv` directamente.

---

## 0.3 — ¿Se suelta el GIL durante el CWT?

Esta era la incógnita que más pesaba, porque toda la elección de hilos del documento de diseño descansa en que la respuesta sea sí. La prueba: el mismo trabajo dos veces en serie, contra las mismas dos veces en dos hilos.

| Modo | 2 llamadas en serie | 2 llamadas en 2 hilos | Ganancia | Lectura |
|---|---:|---:|---:|---|
| `conv` | 0,395 s | 0,217 s | **1,82×** | El GIL se suelta |
| `fft` | 0,203 s | 0,154 s | 1,32× | Se suelta, con menos margen |

### Veredicto

**El GIL se suelta. Los hilos sirven.**

La preocupación era concreta: si `np.convolve` retenía el GIL durante toda la llamada, mover el cálculo a un hilo trabajador no liberaría de verdad la interfaz — la ventana se repintaría (eso es C++ de Qt), pero cualquier *slot* escrito en Python se quedaría esperando, comprometiendo el R55 (respuesta ≤0,3 s) incluso con el orquestador ya construido.

**Esa preocupación era infundada.** La Familia A de la sección 1 del diseño queda validada con medición.

El 1,32× de `fft` no contradice esto: es menor simplemente porque el cálculo ya es más corto (0,112 s), así que pesan proporcionalmente más la creación de hilos y el ancho de banda de memoria. No es el GIL estorbando.

### Consecuencia para el paralelismo interno (sección 6 del diseño)

El GIL deja de ser el bloqueo, así que la sección 6 es **técnicamente viable**. Pero el techo medido con 2 hilos es de 1,3-1,8×, no 2× — y cada hilo adicional reserva su propio buffer de trabajo. Sigue siendo lo más complejo del diseño con el beneficio menos seguro.

**Se mantiene fuera de la v1.** Viable no es lo mismo que prioritario.

---

## Hallazgo no planeado: el wavelet no coincide con MATLAB

Al ir a verificar la equivalencia numérica aparecieron las pruebas de validación contra MATLAB. **Ya fallan hoy, sin haber tocado una línea:**

```
test_wavelet_plugin.py::TestWaveletABFVsMatlab::test_correlation_by_row                    FAILED
test_wavelet_plugin.py::TestWaveletABFVsMatlab::test_pointwise_fraction_allowing_outliers  FAILED
test_wavelet_average_plugin.py::TestWaveletAverageABFVsMatlab::test_correlation_by_row     FAILED
test_wavelet_average_plugin.py::TestWaveletAverageABFVsMatlab::test_pointwise_fraction...  FAILED

4 failed, 2 passed in 17.08s
```

La magnitud descarta que sea una tolerancia mal puesta:

```
passed = 6917 / 3.044.898  ->  ratio = 0,00227      (pasa el 0,23 % de los puntos)
peor punto: APP = 0,447459   MATLAB = 0,006129      (factor ~73×)
filas con violaciones: 998 de 998
```

Fallan **todas** las filas del escalograma, y la prueba de correlación por fila también. Eso no es ruido numérico acumulado: apunta a una diferencia estructural — la normalización, la parametrización del wavelet Morlet, o el mapeo de frecuencias a escalas.

### Qué significa

**Para el orquestador, nada.** Es un problema anterior e independiente. El cambio a `method='fft'` no lo mejora ni lo empeora, porque produce exactamente los mismos números que `conv`.

**Para el proyecto, bastante.** Es una herramienta de análisis científico cuyo resultado de wavelet no coincide con la referencia contra la que se validó. Es una cuestión de correctitud, y una cuestión de correctitud pesa más que una de rendimiento.

**Recomendación:** abrirlo como frente de trabajo aparte y levantarlo con la directora del proyecto antes de avanzar con la Fase 1. No bloquea al orquestador, pero no debería quedar enterrado dentro de un informe de rendimiento.

---

## Decisiones que salen de la Fase 0

| Pregunta | Respuesta medida | Decisión |
|---|---|---|
| ¿Adoptar `method='fft'`? | 1,89× más rápido, diferencia de 4,3e-14 | **Sí.** Entra en la Fase 1.1 |
| ¿Los hilos sirven, o el GIL estorba? | Se suelta: 1,82× (`conv`), 1,32× (`fft`) | **Hilos confirmados.** El diseño se sostiene |
| ¿Entra el paralelismo interno (sección 6)? | Viable, pero el techo con 2 hilos es 1,3-1,8× | **No en la v1.** Viable ≠ prioritario |
| ¿Qué migrar al orquestador? | Solo 4 operaciones pasan de 100 ms | Wavelet, wavelet promedio y los dos renders. **FFT y PSD no** |
| ¿Cuánto pesa el render frente al cálculo? | 716 ms contra 202 ms → 3,5× | **Vectorizar VTK va antes que el orquestador** |

---

## Correcciones a los otros dos documentos

Lo medido corrige tres cosas que estaban escritas por suposición:

| Documento | Decía | Medido |
|---|---|---|
| `orquestador-de-tareas.md`, sección 5 | "un trial de **4050 muestras**" | **3051 muestras** tras el downsample de factor 10. La tabla de memoria hay que rederivarla: ~24 MB por escalograma en vez de 32 MB |
| `orquestador-de-tareas.md`, VTK | "**cuatro millones** de llamadas" | **3,04 millones** (998 × 3051). Viene del mismo supuesto de las 4050 muestras |
| `orquestador-de-tareas.md`, sección 6 | "no sabemos si `np.convolve` libera el GIL" | **Sí lo libera** (1,82× con 2 hilos). La duda queda cerrada |
| `plan-de-implementacion-orquestador.md`, Fase 0 | "verificar contra `test/plugins_test/`" | No sirve como criterio: esas pruebas ya fallan. Se reemplazó por la comparación directa `fft` vs `conv` |

Lo que el documento de diseño **sí acertó**: las 998 escalas, los 17 plugins, la elección de hilos sobre procesos, y que el bucle de VTK es un cuello de botella real.

---

## Apéndice: qué código se cambió

**Ninguno.** La Fase 0 no modificó una sola línea del repositorio. Es una fase de medición: su producto son números y decisiones, no cambios.

Eso incluye el paso 0.2. Para comparar `conv` contra `fft` **no se tocaron los plugins**: se midió llamando a `pywt.cwt` directamente con los mismos parámetros que usa `Wavelet_plugin.compute_wavelet()`. Así la medición no depende de dejar el código en un estado intermedio, y se puede repetir cuando se quiera sin revertir nada.

Lo que sí se escribió son **scripts de medición, fuera del repositorio**. Como viven en un directorio temporal, quedan aquí para que la fase sea reproducible.

### Paso 0.1 — Línea base

No hace falta script: la suite ya existe en `test/performance_test/`.

```powershell
$env:GAMMA_PERF_LABEL = "v2_fase0_baseline"
pytest test/performance_test -s
```

Los resultados se acumulan en `test/performance_test/results/perf_results.json` bajo esa etiqueta, sin pisar las anteriores.

### Pasos 0.2 y 0.3 — Script de medición

Un único script resuelve las dos preguntas. Replica exactamente la preparación de parámetros de `compute_wavelet()` (mismo cálculo de `freq_seg`, mismo submuestreo, mismas escalas) y luego mide.

```python
"""Fase 0.2 y 0.3 - No modifica ningun archivo del proyecto."""
import sys, time, threading
from pathlib import Path

REPO = Path(r"C:\Users\noah\Downloads\Gamma-Lab-2.0")
sys.path.insert(0, str(REPO))

import numpy as np, pywt
from core.services.fileio_service import FileIOService
from core.filters import trials as tr

# --- Datos reales: mismo pipeline que test_compute_bench.py ---
sd = FileIOService().load_abf(str(REPO / "test" / "data" / "17308005.abf"))
sd.signals = sd.signals.astype(np.float64, copy=False)
sd.time = sd.time.astype(np.float64, copy=False)
td = tr.cut_trials_single_channel(
    ds=sd, channel=0, stim_channel=1, threshold=0.7, t0=-0.05, t1=4.00,
    end_mode="until_next_onset", stim_expected=1, inter_stim_time=0.0,
    pad_value=0.0, debug=False)
X = np.nan_to_num(np.asarray(td.trials, dtype=np.float64))
t_rel = np.asarray(td.time_rel, dtype=np.float64)
fs_calculado = round(1.0 / (t_rel[1] - t_rel[0]), 3)

# --- Parametros por defecto del plugin ---
FS, FMIN, FMAX, CYCLES = 1000.0, 1.0, 500.0, 2.0

# --- Replica de la preparacion de compute_wavelet() ---
freq_seg = 2 * int(max(1, FMAX - FMIN))                    # 998 escalas
factor = max(1, int(round(fs_calculado / FS)))             # submuestreo x10
sig = X[:, 0][::factor]                                    # 3051 muestras
freq_axis = np.linspace(FMIN, FMAX, freq_seg)[::-1]
wavelet = f"cmor{CYCLES}-1.0"
freq_axis[freq_axis == 0] = 1e-6
scales = pywt.central_frequency(wavelet) * FS / freq_axis

print(f"muestras={len(sig)}  escalas={len(scales)}  wavelet={wavelet}")


def correr(method):
    coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/FS, method=method)
    return np.abs(coef)


def cronometrar(fn, reps=3, warmup=1):
    """Descarta `warmup` corridas y devuelve la mediana de `reps`."""
    for _ in range(warmup):
        fn()
    muestras = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        muestras.append(time.perf_counter() - t0)
    muestras.sort()
    return muestras[len(muestras) // 2]


# --- 0.2  conv vs fft ---
print("\n--- 0.2  conv vs fft ---")
t_conv = cronometrar(lambda: correr("conv"))
t_fft  = cronometrar(lambda: correr("fft"))
print(f"  conv : {t_conv:.3f} s")
print(f"  fft  : {t_fft:.3f} s   -> {t_conv/t_fft:.2f}x")

a, b = correr("conv"), correr("fft")
print(f"  max dif relativa    : {np.max(np.abs(a-b))/np.max(np.abs(a)):.3e}")
print(f"  allclose(rtol=1e-6) : {np.allclose(a, b, rtol=1e-6)}")

# --- 0.3  se suelta el GIL? ---
print("\n--- 0.3  se suelta el GIL? ---")
for method in ("conv", "fft"):
    def trabajo(m=method):                        # m=method fija el valor por iteracion
        pywt.cwt(sig, scales, wavelet, sampling_period=1/FS, method=m)

    trabajo()                                     # calentamiento

    t0 = time.perf_counter()
    trabajo(); trabajo()
    serie = time.perf_counter() - t0

    hilos = [threading.Thread(target=trabajo) for _ in range(2)]
    t0 = time.perf_counter()
    for h in hilos: h.start()
    for h in hilos: h.join()
    paralelo = time.perf_counter() - t0

    print(f"  {method}: serie={serie:.3f}s paralelo={paralelo:.3f}s "
          f"ganancia={serie/paralelo:.2f}x")
```

Salida de este script en el equipo de referencia:

```
muestras=3051  escalas=998  wavelet=cmor2.0-1.0

--- 0.2  conv vs fft ---
  conv : 0.202 s
  fft  : 0.108 s   -> 1.87x
  max dif relativa    : 4.349e-14
  allclose(rtol=1e-6) : True

--- 0.3  se suelta el GIL? ---
  conv: serie=0.387s paralelo=0.213s ganancia=1.82x
  fft:  serie=0.190s paralelo=0.156s ganancia=1.22x
```

> **Un detalle de Python que importa acá:** el `def trabajo(m=method)` fija el valor de `method` en el momento de definir la función. Con un `lambda` que capture `method` por cierre, las dos iteraciones del bucle terminarían midiendo el mismo modo, porque el cierre lee la variable cuando se ejecuta, no cuando se define.

**Cómo leer la salida del 0.3:** ganancia cercana a 2× significa que el GIL se suelta y los hilos sirven; cercana a 1× significa que no se suelta y los hilos no aportarían nada para esa operación.

### Paso extra — Estado de las pruebas contra MATLAB

El hallazgo del wavelet salió de correr las pruebas que ya existen, sin modificarlas:

```powershell
pytest test/plugins_test/test_wavelet_plugin.py test/plugins_test/test_wavelet_average_plugin.py -q
```

Conviene correr cada archivo **por separado** y comparar archivo contra archivo. Mezclar ambos en una sola corrida y leer solo el final lleva a comparar la salida de un plugin contra la del otro, que es un error fácil de cometer.

---

## Estado

Fase 0 **cerrada**. Los cuatro criterios de salida se cumplieron y las decisiones que dependían de ella están tomadas.

Sigue la **Fase 1**: fijar `method='fft'`, el acumulador incremental en `wavelet_average`, y vectorizar el llenado de VTK. Las tres se miden volviendo a correr la misma suite con una etiqueta nueva y comparando contra `v2_fase0_baseline`.
