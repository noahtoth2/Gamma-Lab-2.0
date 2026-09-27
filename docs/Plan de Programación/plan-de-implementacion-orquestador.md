# Plan de implementación del orquestador

*Cómo construirlo, en qué orden, y cómo saber que cada paso quedó bien*

---

## Para qué sirve este documento

`orquestador-de-tareas.md` explica **qué** construir y **por qué**. Este explica **en qué orden hacerlo** y **cómo verificar cada paso**.

Hay una diferencia de criterio entre los dos documentos que conviene decir de frente, porque es la razón de ser de este plan. El documento de diseño cierra con esta frase:

> *"El orquestador **organiza**. Lo que de verdad **optimiza** son tres cosas concretas — el modo de la transformada wavelet, la suma incremental en vez de apilar, y las conversiones a VTK en bloque. Ninguna de las tres es concurrencia."*

Y sin embargo trata a esas tres como notas al margen; la de VTK queda explícitamente fuera de alcance. **Este plan las pone primero.** No por prolijidad, sino porque las tres cambian los números sobre los que se diseña el orquestador:

- Si `method='fft'` baja el wavelet de 4,2 s a menos de 1 s, la pregunta de cuánto hace falta la cola cambia.
- Si no se vectoriza el llenado de VTK, el usuario va a seguir viendo la ventana congelada ~0,7 s **después** de que el hilo terminó — y va a concluir que el orquestador no sirvió. El orquestador no puede arreglar eso, porque VTK obliga a llenar sus estructuras desde el hilo gráfico.
- Si se aplica el acumulador, el pico de memoria baja de ~2 GB a ~100 MB, y media sección 5 del diseño (estimar y rechazar) se queda casi sin casos que atender.

Las tres son de un día cada una y son independientes entre sí y del orquestador.

---

## Las seis fases de un vistazo

| Fase | Qué se hace | Duración | Depende de |
|---|---|---|---|
| **0** | Medir: `fft` vs `conv`, y si el GIL se suelta | ~1 semana | — |
| **1** | Las tres optimizaciones reales | ~1-2 semanas | Fase 0 |
| **2** | Orquestador mínimo | ~2 semanas | Fase 0 |
| **3** | Migrar los dos plugins que ya usan hilos | ~1 semana | Fase 2 |
| **4** | Extender a los plugins síncronos que lo ameriten | ~1 semana | Fase 3 |
| **5** | PAC nace ya orquestado | en paralelo | Fase 2 |
| **6** | Memoria y paralelismo interno — **solo si sobra tiempo** | — | Fase 0, 1 |

Las fases 1 y 2 pueden correr **en paralelo** si hay dos personas: no se tocan entre sí. La Fase 1 toca plugins; la Fase 2 crea un archivo nuevo en `core/`.

---

## Fase 0 — Medir antes de decidir nada

*Objetivo: no diseñar sobre suposiciones.*

Hay dos incógnitas que cambian conclusiones, y las dos se resuelven en una tarde. El documento de diseño las menciona al final, como "por medir". Van al principio.

### 0.1 — Línea base fresca

La infraestructura ya existe. En `test/performance_test/` hay `bench_common.py` con `time_block()` y `record()`, `compare_report.py`, y un histórico en `results/perf_results.json`.

```powershell
$env:GAMMA_PERF_LABEL = "v2_fase0_baseline"
pytest test/performance_test -s
```

Los números de referencia contra los que comparar (etiqueta `gammalab1_baseline_2026-08-16`, equipo de 16 núcleos lógicos, Python 3.11.9, pywt 1.8.0):

| Operación | Mediana |
|---|---|
| `fft._compute_fft` (todos los trials) | 3,8 ms |
| `psd._compute_psd` (Welch) | 5,3 ms |
| `psd_average._compute_psd` | 9,2 ms |
| `wavelet.compute_wavelet` (1 trial) | **216 ms** |
| `wavelet_average.compute_wavelet` (×20 trials) | **4,19 s** |
| `wavelet.render_scalogram` (998×3051) | **725 ms** |
| `wavelet_average.render_scalogram` | **741 ms** |
| `fileio.load_abf` | 60 ms |
| `trials.cut_trials_single_channel` | 18,6 ms |
| `vtk_array.bucle_python` (300 k puntos) | 28,4 ms |
| `vtk_array.numpy_to_vtk` (300 k puntos) | **0,43 ms** ← 66× más rápido |

### 0.2 — `method='fft'` vs `method='conv'`

Hoy `pywt.cwt` corre en su modo lento sin que nadie lo haya decidido: el valor por defecto es `method='conv'` y ninguno de los dos plugins pasa el parámetro.

- `wavelet_plugin.py:209`:
  ```python
  coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs)
  ```
- `wavelet_average_plugin.py:290`:
  ```python
  coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs if fs > 0 else 1.0)
  ```

Agregar `method='fft'`, volver a correr la suite con otra etiqueta, comparar:

```powershell
$env:GAMMA_PERF_LABEL = "v2_fase0_cwt_fft"
pytest test/performance_test -s
python test/performance_test/compare_report.py v2_fase0_baseline v2_fase0_cwt_fft
```

> **Ojo:** `fft` y `conv` no dan resultados bit a bit idénticos (uno convoluciona en el dominio del tiempo, el otro multiplica en frecuencia). Antes de fijar el cambio hay que verificar contra las pruebas de `test/plugins_test/`, que comparan la salida contra MATLAB. Si la tolerancia no pasa, hay que ajustarla conscientemente y dejarlo documentado — no cambiar el número a ojo.

### 0.3 — ¿El GIL se suelta o no?

Esta es la que más pesa, porque el diseño entero descansa en que sí. La sección 1 del documento afirma *"el GIL se libera dentro del código C de NumPy y SciPy"*, pero la sección 6 admite *"no sabemos si `np.convolve` libera el GIL"*. Las dos frases no pueden ser ciertas a la vez para la operación más cara de la aplicación.

**Por qué importa más de lo que el diseño dice:** si `np.convolve` retiene el GIL, mover el cálculo a un hilo trabajador no libera del todo la interfaz. La ventana se repinta y se puede mover (eso es C++ de Qt, no necesita el GIL), pero **cualquier slot escrito en Python se queda esperando** — un clic, un cambio de pestaña. Eso compromete el R55 (respuesta ≤0,3 s) con el orquestador ya construido y funcionando.

Prueba mínima (archivo suelto, no va al repositorio):

```python
import time, threading
import numpy as np, pywt

sig = np.random.randn(3051)
scales = np.linspace(1, 200, 998)

def trabajo():
    pywt.cwt(sig, scales, "cmor2-1.0", sampling_period=1/1000)

# En serie
t0 = time.perf_counter(); trabajo(); trabajo()
serie = time.perf_counter() - t0

# En dos hilos
h = [threading.Thread(target=trabajo) for _ in range(2)]
t0 = time.perf_counter()
[x.start() for x in h]; [x.join() for x in h]
paralelo = time.perf_counter() - t0

print(f"serie={serie:.2f}s  paralelo={paralelo:.2f}s  ganancia={serie/paralelo:.2f}x")
```

**Cómo leerlo:** ganancia cercana a 2× → el GIL se suelta, los hilos sirven. Ganancia cercana a 1× → el GIL no se suelta con ese modo. Repetir con `method='fft'`, donde `np.fft` sí lo libera.

### Criterio de salida de la Fase 0

- [x] Existe una línea base con etiqueta en `perf_results.json` → `v2_fase0_baseline`.
- [x] Hay números de `conv` vs `fft` y se verificó la equivalencia numérica.
- [x] Hay un sí/no documentado sobre el GIL, para cada modo.
- [x] Con esos datos se decide si la Fase 6 entra al alcance o se descarta.

---

## Resultados de la Fase 0

**Corrida el 2026-09-18. Los resultados completos están en [`resultados-fase-0.md`](resultados-fase-0.md).**

Lo que hay que saber para seguir con el plan:

| Pregunta | Respuesta medida | Decisión |
|---|---|---|
| ¿`method='fft'`? | 1,89× más rápido, diferencia numérica de 4,3e-14 | **Adoptar** en la Fase 1.1 |
| ¿Los hilos sirven, o el GIL estorba? | Se suelta: 1,82× (`conv`), 1,32× (`fft`) | **Hilos confirmados**; el diseño se sostiene |
| ¿Entra la Fase 6 (paralelismo interno)? | Viable, pero el techo con 2 hilos es 1,3-1,8× | **Sigue fuera de la v1** |
| ¿Qué migrar al orquestador? | Solo 4 operaciones pasan de 100 ms | Wavelet, wavelet promedio y los dos renders. **FFT y PSD no** |
| ¿Cuánto pesa el render frente al cálculo? | 716 ms contra 202 ms | **Vectorizar VTK va antes que el orquestador** |

Y un hallazgo que no se fue a buscar: **las pruebas de validación del wavelet contra MATLAB ya fallan hoy**, antes de tocar nada (pasa el 0,23 % de los puntos). Es anterior e independiente del orquestador, pero es una cuestión de correctitud y merece su propio frente de trabajo. Está desarrollado en el documento de resultados.

---

## Fase 1 — Las tres optimizaciones reales

*Objetivo: que el usuario note la mejora aunque el orquestador todavía no exista.*

Ninguna de las tres es concurrencia. Las tres son medibles con la suite que ya está.

### 1.1 — Fijar `method='fft'`

Si la Fase 0 lo respalda, se fija en los dos plugins (`wavelet_plugin.py:209`, `wavelet_average_plugin.py:290`). Un argumento.

### 1.2 — Acumulador incremental en `wavelet_average`

**El problema**, en `WaveletWorker.run()`:

```python
scalograms = []                              # línea 576
...
    scalograms.append(scalogram)             # línea 601 — guarda los N enteros
...
stacked = np.stack(scalograms, axis=0)       # línea 610 — copia completa de todo
avg_scalogram = np.mean(stacked, axis=0)     # línea 611
```

En la línea 610 conviven **la lista y la copia apilada**: por eso el pico es el doble de lo que ocupa el conjunto.

**El cambio** — mismo resultado numérico, porque el promedio es la suma dividida entre la cantidad:

```python
acumulador = None
n_validos = 0

for trial_idx in range(n_trials):
    # ... (igual que hoy: interrupción, nan_to_num, compute_wavelet)
    if scalogram is None or scalogram.size == 0:
        continue

    if acumulador is None:
        acumulador = scalogram.astype(np.float64)
    else:
        acumulador += scalogram
    n_validos += 1

if n_validos == 0:
    raise ValueError("No valid scalograms computed")

avg_scalogram = acumulador / n_validos
```

Nunca hay más de un escalograma vivo: el individual se libera solo al reasignarse la variable en la siguiente vuelta.

**Verificación:** el escalograma promedio resultante debe ser igual al actual dentro de tolerancia numérica (`np.allclose`). El acumulador en `float64` evita pérdida de precisión al sumar muchos trials.

### 1.3 — Vectorizar el llenado de VTK

**El problema**, en `wavelet_average_plugin.py:444-446` y `wavelet_plugin.py:334-336`:

```python
for j in range(n_freqs):
    for i in range(n_times):
        img.SetScalarComponentFromFloat(i, j, 0, 0, float(Z[j, i]))
```

Con 998 × 3051 eso son **3,04 millones** de llamadas al wrapper Python→C++ de VTK, una por píxel. A ~230 ns cada una salen los ~0,7 s medidos.

**La solución ya está escrita y en uso** en `core/utils/adapters.py`, que usa `numpy_support.numpy_to_vtk(...)` — el mismo benchmark de la Fase 0 muestra el factor: 28,4 ms contra 0,43 ms para 300 k puntos.

El reemplazo es una conversión en bloque del arreglo completo, asignada como escalares de la imagen, en lugar del doble bucle. Hay que cuidar el **orden de memoria** (VTK espera los datos en orden x-rápido) — si la imagen sale transpuesta o espejada, es eso.

**Verificación:** la imagen renderizada debe verse idéntica a la de hoy. La comparación más simple es exportar un PNG antes y después con el propio `ExportService` y compararlos.

> **Esto es lo que más se va a notar**, porque el llenado de VTK ocurre en el hilo gráfico **después** de que el hilo trabajador terminó — justo cuando el usuario cree que ya acabó. Es congelamiento que el orquestador no puede quitar.

### Criterio de salida de la Fase 1

- [x] Suite de benchmarks corrida con etiqueta nueva y comparada contra la base → `v2_fase1_completa`.
- [~] `test/plugins_test/` sigue pasando — **no se puede cumplir tal como estaba escrito**, ver abajo.
- [x] El pico de memoria de `wavelet_average` ya no crece con el número de trials → medido en 10, 30 y 60 trials: **414 MB constante**.
- [x] La imagen de VTK no cambió → verificado más fuerte que con un PNG: comparación bit a bit de los escalares (`max diferencia = 0.000e+00`) más lectura por coordenadas en las cuatro esquinas.

> **Criterio que hubo que reformular (segunda vez).** El de `test/plugins_test/` ya se había corregido en la Fase 0 porque las pruebas del wavelet estaban en rojo de antes. Al intentar cerrarlo apareció además que **6 de los 8 archivos de `plugins_test/` ni siquiera se pueden recolectar**: importan `core.services.fileio`, módulo que se renombró a `fileio_service.py` y nunca se actualizó ahí.
>
> ```
> ERROR test/plugins_test/test_average_plugin.py
> ERROR test/plugins_test/test_erp_plugin.py
> ERROR test/plugins_test/test_fft_average_plugin.py
> ERROR test/plugins_test/test_fft_plugin.py
> ERROR test/plugins_test/test_psd_average_plugin.py
> ERROR test/plugins_test/test_psd_plugin.py
> ModuleNotFoundError: No module named 'core.services.fileio'
> ```
>
> Es exactamente el incidente que el propio SAD documenta en "Estabilidad de módulos internos". Los únicos dos archivos que sí corren son los del wavelet, y ésos se verificaron: fallan idéntico a antes del cambio.
>
> **Como criterio de regresión, esta suite no sirve hoy.** Arreglar los 6 imports es trabajo de una hora y devolvería una red de seguridad real para las fases siguientes. Conviene hacerlo antes de la Fase 3, que es cuando se empieza a mover código de plugins de verdad.

---

## Fase 2 — Orquestador mínimo

*Objetivo: que exista y funcione con un caso real. Nada más.*

Alcance recortado a hueso. Lo que **no** entra en esta fase: estimación de memoria, paralelismo interno, prioridades, segunda cola.

### 2.1 — Una sola cola, no dos

El diseño propone dos filas (cálculo y archivo). Empezar con una. La segunda se agrega cuando el estorbo aparezca de verdad — hoy `load_abf` mide 60 ms, no es un problema todavía. Menos piezas, menos que depurar.

### 2.2 — El contrato

```python
# core/services/task_service.py   (archivo nuevo)

class TaskHandle(QObject):
    progress  = pyqtSignal(int, str)     # porcentaje (-1 = indeterminado), mensaje
    finished  = pyqtSignal(object)       # resultado
    failed    = pyqtSignal(str)          # mensaje de error
    cancelled = pyqtSignal()

    def cancel(self) -> None: ...

class TaskService(QObject):
    def submit(self, fn, *, owner: str, **kwargs) -> TaskHandle: ...
    def cancel_all_from(self, owner: str) -> int: ...
    def has_active_tasks(self) -> bool: ...
```

Cuatro señales y un `cancel()`. El `owner` es el `meta.id` del plugin que pide — es la pieza que hace posible la regla "cancelar al salir".

### 2.3 — Las reglas que sí entran

**Escritura única.** El `DataStore` se escribe **solo** desde el slot de `finished`. Como las señales de Qt entre hilos se entregan en el hilo de la interfaz, todo se escribe siempre desde el mismo hilo: eso cumple el R54 sin un solo mutex. Y una tarea cancelada nunca emite `finished`, así que "descartar el resultado parcial" del CU-014 sale gratis.

**Reemplazo.** Una solicitud nueva del mismo `owner` descarta la anterior que siga esperando en la cola.

**Cancelación cooperativa.** La función recibe un objeto para consultar si la cancelaron; el bucle lo consulta cada cierto número de vueltas.

### 2.4 — La salida de emergencia que el diseño no menciona

El R46 pide liberación **garantizada** "incluso si el cómputo no termina por sí solo". Con hilos y cancelación cooperativa eso no se puede prometer: si `pywt.cwt` está a mitad de una llamada, hay que esperar a que vuelva.

Hacen falta las dos cosas:

1. **En el código:** tras pedir la cancelación, esperar N segundos (3 es razonable); si el hilo no responde, **desligarse** de él — devolverle la interfaz al usuario de inmediato, marcar la tarea como cancelada, y descartar su resultado cuando eventualmente llegue.
2. **En el SAD:** ajustar el texto del R46 para que diga lo que el diseño puede cumplir de verdad. Prometer terminación forzada con hilos es prometer algo que Python no da.

### 2.5 — Registrarlo

En `main.py`, junto a los servicios que ya están (líneas 47-48):

```python
kernel.register_service("DataStore", DataStore())
kernel.register_service("FileIO", FileIOService())
kernel.register_service("TaskService", TaskService())   # ← nuevo
```

Va **antes** del descubrimiento de plugins, porque `register_plugin()` llama a `initialize(kernel)` y a partir de ahí un plugin ya podría pedir el servicio.

### Criterio de salida de la Fase 2

- [x] `TaskService` registrado y arrancando sin efecto sobre el tiempo de inicio → **+2,6 µs** y **cero hilos** al arrancar (los crea por tarea, bajo demanda).
- [x] Un plugin de prueba manda una función, recibe `finished` y dibuja → prueba de integración con el wavelet real: resultado **idéntico** al síncrono y entregado en el hilo de interfaz.
- [x] Cancelar durante la ejecución devuelve la interfaz en menos de 3 s → medido **< 1 s** incluso con una tarea que ignora la cancelación.
- [x] Una excepción dentro de la tarea emite `failed` y **no** tumba la aplicación → verificado, y el servicio queda usable después.

Resultados completos en [`resultados-fase-2.md`](resultados-fase-2.md).

---

## Fase 3 — Migrar los dos plugins que ya usan hilos

*Objetivo: validar la abstracción contra código que ya funciona, antes de usarla en código nuevo.*

Esta es la jugada de menor riesgo del plan. Si la migración de `wavelet_average` produce exactamente el mismo resultado que hoy, la abstracción está probada.

### 3.1 — `wavelet_average`

Quitar la clase anidada `WaveletWorker` (línea 554) y el `_cleanup_worker()` (línea 64). El cuerpo de `run()` se convierte en una función pura en un `compute.py` de la carpeta del plugin. `on_create_wavelet` pasa a hacer `submit()`; `_on_wavelet_done` (línea 241) se conecta a `finished` y queda casi igual.

Además: `WaveletWorker.log_signal` ya emite progreso por trial (*"Trial 3/20: computed"*) que hoy solo llega a consola. Conectarlo a `progress` hace que se vea — es el R04 casi gratis.

### 3.2 — `artifact_remove`

Lo mismo con `_ApplyWorker` (línea 27) y el bloque `QThread` + `moveToThread` (líneas 299-315). De paso muere la señal `progress` (línea 28) que está definida y **nunca se emite ni se conecta**.

También desaparece la duplicación de las cuatro líneas que rehabilitan los botones, hoy repetidas en `_on_apply_finished` (806) y `_on_apply_error` (835).

### 3.3 — Cancelar al salir: arreglar el bug confirmado

Hoy hay un hilo que queda colgado. `Wavelet_average_plugin.stop()` (líneas 53-62) solo desactiva el interactor VTK; la línea 54 tiene esto **comentado**:

```python
#self._cleanup_worker()  # ✅ Asegúrate de limpiar al detener
```

Como `main_window.py:232-234` ya llama a `active_plugin.stop()` al cambiar de sección, si el investigador se va de la pestaña mientras el wavelet corre, el hilo sigue vivo y al terminar intenta renderizar sobre un widget que ya no está.

**El gancho ya existe.** Basta con que `IPlugin` tenga una implementación por defecto:

```python
def stop(self):
    tasks = self.kernel.get_service("TaskService")
    if tasks:
        tasks.cancel_all_from(self.meta.id)
```

Y el bug desaparece **para todos los plugins a la vez**, sin que ninguno tenga que acordarse de limpiar nada.

> Aprovechando el paso: `main_window.py:665` pregunta por `kernel.get_all_plugins()`, un método que `Kernel` nunca definió — esa rama del cierre de la aplicación nunca se ejecuta. El `has_active_tasks()` del orquestador es el lugar natural para reemplazar ese apaño al cerrar.

### Criterio de salida de la Fase 3

- [ ] Ya no queda ningún `QThread` ni `moveToThread` fuera de `core/services/task_service.py`.
- [ ] El resultado numérico de los dos plugins es idéntico al de antes de migrar.
- [ ] Cambiar de sección con un wavelet corriendo ya no deja hilos vivos.
- [ ] La barra de progreso muestra el avance real por trial.

---

## Fase 4 — Extender a los plugins síncronos

*Objetivo: cubrir lo que de verdad se siente, no todo por simetría.*

La parte mecánica: mover cada `_compute_*` a un `compute.py` y partir el botón en dos — lo que pide y lo que dibuja cuando llega la respuesta.

**Criterio para decidir qué migrar: solo lo que mida más de ~100 ms.**

| Plugin | Medición | ¿Migrar? |
|---|---|---|
| `wavelet` (individual) | 216 ms + 725 ms de render | **Sí** |
| `open_signal` (archivos grandes) | 60 ms con el archivo de prueba; sin medir con 1-2 GB | **Sí**, medir primero |
| `average` | cálculo de una línea (`average_plugin.py:66`) | Extraerlo a función pura igual, aunque no se encole |
| `erp` | sin función de cálculo: el NumPy vive dentro de `_render_heatmap` (línea 290) | Separar cálculo de dibujo primero |
| `fft`, `fft_average`, `psd`, `psd_average`, `relative_psd` | 3,8 – 11 ms | **No.** Pasarlos por la cola agrega riesgo para cero beneficio visible |
| `filter` | 43 ms señal completa | No por ahora |
| `trials` | 18,6 ms | No por ahora |

> El documento de diseño enumera "13 cálculos" pero se deja fuera `load_mat` (existe en `fileio_service.py`, aunque su llamada esté comentada en `OpenSignalPlugin`) y no lista a `erp`, del que después habla. El conteo real está más cerca de 15. Conviene corregirlo ahí.

### Criterio de salida de la Fase 4

- [ ] Todo lo que pasa de 100 ms va por el orquestador.
- [ ] `average` y `erp` tienen su cálculo separado del dibujo, aunque no se encolen.
- [ ] Medición con un archivo grande de verdad (1-2 GB) para decidir si hace falta la segunda cola.

---

## Fase 5 — PAC nace ya orquestado

*En paralelo con el frente de PAC, no después.*

Hoy `plugins/analysis/time_frequency/pac/` tiene la interfaz completa (`pac_plugin_ui.py`, 223 líneas) y un `pac_plugin.py` de **17 líneas** con `process()` y `stop()` en `pass`. O sea: el esqueleto y la UI están; la lógica no existe.

Es la oportunidad de que el primer consumidor nuevo del orquestador nazca bien:

- La lógica de PAC se escribe desde el principio como **función pura** en `compute.py` — recibe NumPy, devuelve NumPy, no toca widgets ni `DataStore`.
- El plugin solo hace `submit()` y dibuja en el slot de `finished`.
- Así se cumple lo que el UC-01 ya da por sentado: *"el plugin delega el cómputo al orquestador del núcleo en vez de instanciar hilos propios"*.

Si PAC se escribe antes de que el orquestador esté listo, va a terminar con su propio `QThread` y habrá **tres** patrones ad-hoc en vez de dos.

---

## Fase 6 — Solo si sobra tiempo

Nada de esto entra al alcance inicial. Cada punto tiene una condición de entrada:

| Qué | Entra solo si… |
|---|---|
| Estimar memoria y rechazar antes de empezar | …después del acumulador siguen apareciendo casos reales de `MemoryError`. Además `psutil` **no está en `requirements.txt`**: es dependencia nueva, hay que decirlo. |
| Paralelismo dentro de una tarea (sección 6 del diseño) | …la prueba del GIL de la Fase 0 salió positiva. Si no, no sirve de nada. |
| Segunda cola para archivos | …la medición con archivos de 1-2 GB demuestra que estorba. |
| `numpy.memmap` para señales enormes | …la carga de 1-2 GB no cabe en RAM. Ojo: `load_edf` convierte a `float64`, lo que puede multiplicar por 4 el tamaño de un EDF de enteros de 16 bits. |

---

## Lo que este plan recorta del diseño, y por qué

| Parte del diseño | Decisión | Motivo |
|---|---|---|
| Sección 6 completa (paralelismo interno) | Fuera de la v1 | Es lo más complejo y lo de valor menos seguro; depende de la incógnita del GIL. Además contradice el objetivo declarado: *"el objetivo no es que los cálculos vayan más rápido"*. |
| "Avisar antes" por memoria | A la Fase 6 | El acumulador deja el caso casi sin ocurrencias. Y arrastra una dependencia nueva. |
| Dos colas | Empezar con una | `load_abf` mide 60 ms. El problema todavía no existe. |
| Las tres optimizaciones "fuera de alcance" | **Entran primero** | Son las que cambian lo que el usuario siente, y cambian los números del propio diseño. |

---

## Riesgos y cómo se ven venir

| Riesgo | Señal temprana | Qué hacer |
|---|---|---|
| El GIL no se suelta con `conv` | Fase 0.3 da ganancia ≈1× | Fijar `method='fft'` es obligatorio, no opcional |
| `fft` cambia los resultados numéricos | `test/plugins_test/` falla | Ajustar tolerancia conscientemente y documentarlo; si no, quedarse en `conv` y replantear |
| La imagen de VTK sale transpuesta al vectorizar | Se ve al primer render | Es el orden de memoria (VTK espera x-rápido) |
| El orquestador se come el tiempo de la Fase 3 | Fin de la semana 2 sin un caso funcionando | Recortar más: sin reemplazo, sin progreso; solo submit/finished/cancel |
| PAC se escribe con su propio hilo | Aparece un `QThread` en `pac_plugin.py` | Sincronizar los dos frentes antes de la semana 3 |

---

## Reparto sugerido

El PMP asigna cuatro frentes (UX/UI, paralelización núcleo, amplitude coupling, paralelización módulo). Traducido a estas fases:

- **Quien lleve "paralelización núcleo"** → Fases 0 y 2 (medir y construir el `TaskService`).
- **Quien lleve "paralelización módulo"** → Fases 1 y 3 (las tres optimizaciones y migrar los dos plugins con hilos).
- **Quien lleve "amplitude coupling"** → Fase 5, coordinando con la 2 para no adelantarse con un hilo propio.
- **Quien lleve UX/UI** → el widget de progreso no modal con botón **Cancelar**. Hoy no existe ninguno: `PluginAlerts.show_spinner()` (línea 40) es modal, indeterminado (`setRange(0, 0)`, línea 63) y sin forma de cancelar. Sin ese widget, la cancelación del orquestador no tiene por dónde dispararse.

Las fases 1 y 2 no se tocan entre sí, así que pueden ir en paralelo desde la semana 2.

---

## En una línea

Primero medir, después las tres optimizaciones que sí se sienten, después un orquestador mínimo, después migrar lo que ya funciona, y solo al final lo nuevo. El orquestador organiza; lo que se nota es lo otro — y por eso lo otro va primero.
