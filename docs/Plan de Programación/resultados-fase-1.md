# Resultados de la Fase 1

*Las tres optimizaciones que no son concurrencia*

> **Estado: fase completa.** Los tres pasos están hechos, medidos y verificados. El resumen de punta a punta está al final.

---

## Por qué estas tres van antes que el orquestador

El documento de diseño lo dice en su propia conclusión: *"el orquestador **organiza**; lo que de verdad **optimiza** son tres cosas concretas, y ninguna de las tres es concurrencia"*. Pero las deja como notas al margen.

El plan de implementación las puso primero por tres razones, y las dos primeras ya se confirmaron con datos:

1. **Cambian los números sobre los que se diseña el orquestador.** Hacerlas después es diseñar sobre cifras que van a moverse.
2. **Son baratas.** Las dos aplicadas hasta ahora suman **11 líneas de código**.
3. **Son medibles.** Cada una tiene su antes y su después.

**Fecha:** 18 de septiembre de 2026. Mismo equipo y mismas versiones que la Fase 0 (Intel 16 núcleos lógicos, Windows 10, Python 3.11.9, numpy 2.3.4, PyWavelets 1.8.0, VTK 9.5.2).

---

## 1.1 — `method='fft'` en la transformada wavelet

### Qué se cambió

Un argumento, en dos archivos:

```python
# plugins/analysis/time_frequency/wavelet/wavelet_plugin.py:211
coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs, method="fft")

# plugins/analysis/time_frequency/wavelet_average/wavelet_average_plugin.py:292
coef, _ = pywt.cwt(sig, scales, wavelet,
                   sampling_period=1/fs if fs > 0 else 1.0, method="fft")
```

### Por qué funciona

La transformada wavelet continua **convoluciona** la señal con el wavelet una vez por cada escala de frecuencia — aquí, 998 escalas sobre 3.051 muestras. Y una convolución admite dos caminos de cálculo que dan el mismo resultado:

- **`method='conv'`** (el valor por defecto de PyWavelets): convolución directa. Se desliza el wavelet sobre la señal multiplicando y sumando. El costo crece como *(muestras × largo del wavelet)* por escala.
- **`method='fft'`**: aplica el teorema de convolución — convolucionar en el tiempo equivale a multiplicar en frecuencia. Se transforma, se multiplica (barato) y se vuelve. El costo crece como *N·log N*.

No es una aproximación: es la misma operación matemática por otra ruta.

**Lo que realmente pasaba:** ninguno de los dos plugins pasaba el parámetro, así que la aplicación venía usando el camino lento **sin que nadie lo hubiera decidido**. No fue una elección de diseño, fue un valor por defecto que nadie revisó.

### Medición

Suite completa, etiqueta `v2_fase1_1_cwt_fft` contra `v2_fase0_baseline`:

| Operación | Antes | Después | Cambio |
|---|---:|---:|---:|
| `wavelet.compute_wavelet` (1 trial) | 202,0 ms | **116,0 ms** | **1,74×** |
| `wavelet_average.compute_wavelet` (×20 trials) | 4.213,6 ms | **2.051,0 ms** | **2,05×** |
| `wavelet.render_scalogram` | 716,5 ms | 724,8 ms | sin cambio ✓ |
| `wavelet_average.render_scalogram` | 732,1 ms | 736,8 ms | sin cambio ✓ |

Los renders no se movieron, que es exactamente lo correcto: no se tocó nada del dibujo. El resto de la tabla se movió entre 0,4× y 1,3×, pero son operaciones de menos de un milisegundo cuyas rutas de código no se tocaron: es ruido de medición, no mejora.

### Verificación de que el resultado no cambió

Dos comprobaciones independientes.

**Una —** llamando al método real del plugin con ambos modos sobre el trial real:

```
forma                 : (998, 3051)
max dif absoluta      : 2,587e-14
max dif relativa      : 4,349e-14
allclose(rtol=1e-9)   : True
```

**Dos —** las pruebas de validación contra MATLAB, que ya fallaban antes del cambio (ver el informe de la Fase 0), fallan **idéntico**:

| | Antes de `fft` | Después de `fft` |
|---|---|---|
| `passed` | 6917 / 3.044.898 | **6917 / 3.044.898** |
| peor punto | (row=177, col=2379) | **(row=177, col=2379)** |
| valor de la app | 0,447459 | **0,447459** |

Coincidencia dígito por dígito. Si `fft` hubiera alterado algo, esas cifras se habrían movido.

> **Nota metodológica:** en la primera revisión comparé por error la salida de `test_wavelet_plugin` contra la de `test_wavelet_average_plugin` — pruebas distintas sobre plugins distintos — y pareció que los números habían cambiado. La comparación correcta es archivo contra archivo.

### Expectativa, ajustada

Son **1,74× y 2,05×**, no el salto de orden que sugería el documento de diseño al mencionar N·log N. Es una mejora sólida, pero `wavelet_average` sigue en ~2 s con 20 trials: **sigue necesitando salir del hilo de la interfaz**. Esta optimización no reemplaza al orquestador, lo complementa.

---

## 1.2 — Acumulador incremental en `wavelet_average`

### Qué se cambió

Dentro de `WaveletWorker.run()`, en `wavelet_average_plugin.py`:

```python
# Antes: guardar los N escalogramas y apilarlos al final
scalograms = []
    scalograms.append(scalogram)              # N × 24 MB vivos a la vez
stacked = np.stack(scalograms, axis=0)        # + una copia completa de los N
avg_scalogram = np.mean(stacked, axis=0)

# Ahora: sumar y descartar
acumulador = None
n_validos = 0
    if acumulador is None:
        acumulador = scalogram.astype(np.float64)
    else:
        acumulador += scalogram               # 1 solo vivo a la vez
    n_validos += 1
avg_scalogram = acumulador / n_validos
```

### Por qué funciona

El promedio es la suma dividida entre la cantidad, y la suma se puede armar de a poco: `(a+b+c) = ((a+b)+c)`. No hace falta tener las tres cosas al mismo tiempo.

El problema del código anterior era doble. Primero, guardaba los N escalogramas simultáneamente. Y segundo, `np.stack()` **no reordena la lista: crea un arreglo nuevo con copias de todo**, así que durante ese instante existen los N originales *y* los N copiados. De ahí que el pico fuera aproximadamente el doble del conjunto.

### Medición

Cada variante corrió en un **proceso separado** para que no se contaminaran. Se midió en tres cantidades de trials, porque la afirmación que hay que demostrar no es solo "gasta menos" sino "**deja de crecer**":

| Trials | Lista + `np.stack` | Acumulador | Ahorro |
|---:|---:|---:|---:|
| 10 | 783 MB | **414 MB** | 369 MB |
| 30 | 1.715 MB | **414 MB** | 1.301 MB |
| 60 *(el archivo real)* | 3.107 MB | **414 MB** | **2.693 MB** |

```
acumulador: variacion entre 10 y 60 trials =    +0 MB   (plano)
lista     : variacion entre 10 y 60 trials = +2324 MB   (crece)
```

**El pico del acumulador es exactamente el mismo con 10, 30 o 60 trials: 414 MB.** No "parecido" — idéntico. Eso es lo que significa que la memoria dejó de depender del número de trials: siempre hay un escalograma vivo más el acumulador, sin importar cuántos queden por procesar.

La variante anterior, en cambio, crece de forma lineal: cada trial suma su escalograma a la lista, y el `np.stack` final duplica el conjunto entero.

Descontando los ~295 MB de base que ya estaban antes de promediar (señal cargada, VTK, intérprete), lo que consume el promediado en sí pasa de **~2.810 MB a ~120 MB con el archivo real de 60 trials: unas 23 veces menos**.

### Verificación de que el resultado no cambió

```
max dif absoluta    : 0.000e+00
max dif relativa    : 0.000e+00
allclose(rtol=1e-9) : True
```

Diferencia **exactamente cero**, no "pequeña". Es lo esperable: sumar N matrices y dividir entre N produce los mismos bits que apilarlas y promediarlas, porque es la misma secuencia de sumas en el mismo orden.

### Cómo se midió, y por qué no con `tracemalloc`

NumPy reserva los datos de sus arrays con `malloc` directo, por fuera del asignador de memoria de Python. `tracemalloc` engancha las APIs `PyMem_*`, así que **no ve los arrays grandes** — habría dado un número engañosamente pequeño.

Se usó `GetProcessMemoryInfo` de la API de Windows vía `ctypes` (sin dependencias nuevas), leyendo `PeakWorkingSetSize`, que es el pico real de memoria física del proceso.

> **Detalle a tener en cuenta si alguien reproduce esto:** hay que declarar `GetCurrentProcess.restype = HANDLE` explícitamente. Sin eso, ctypes asume `c_int` y en 64 bits el handle se trunca; la llamada falla en silencio y devuelve 0 MB.

### Lo que este paso enseña sobre el plan

**Este es el único de los tres cambios cuyo beneficio no aparece en la suite de benchmarks**, porque esa mide tiempo y esto es memoria. Sin medirlo aparte habría quedado como el único de los tres imposible de demostrar con números.

Conviene considerar agregar una medición de memoria a la suite de `test/performance_test/`, para que el antes/después de la tesis cubra las dos dimensiones.

---

## 1.3 — Vectorizar el llenado de VTK

### Por qué pasó a ser el más importante

Tras el paso 1.1, el reparto de costos del wavelet quedó descompensado:

| | Antes de la Fase 1 | Tras el 1.1 |
|---|---:|---:|
| Calcular (`compute_wavelet`) | 202 ms | **116 ms** |
| Dibujar (`render_scalogram`) | 716 ms | **725 ms** |
| **Proporción** | 3,5× | **6,2×** |

Dibujar había pasado a costar más de seis veces lo que calcular. El cuello de botella se movió de sitio.

### Qué se cambió

En `wavelet_plugin.py` y `wavelet_average_plugin.py`, el bucle que llenaba la imagen píxel por píxel:

```python
# Antes: una llamada al wrapper de VTK por cada pixel
img.AllocateScalars(vtk.VTK_FLOAT, 1)
for j in range(n_freqs):
    for i in range(n_times):
        img.SetScalarComponentFromFloat(i, j, 0, 0, float(Z[j, i]))

# Ahora: una sola conversion en bloque
Z_plano = np.ascontiguousarray(Z, dtype=np.float32).ravel()
arr = numpy_support.numpy_to_vtk(Z_plano, deep=True, array_type=vtk.VTK_FLOAT)
img.GetPointData().SetScalars(arr)
```

Más el `import` de `numpy_support` en ambos archivos. Con 998 × 3051 se pasa de **3.044.898 llamadas** al wrapper Python→C++ a **una**.

### El detalle que había que acertar: el orden de memoria

`vtkImageData` guarda sus escalares en orden *x-rápido*: el píxel `(i, j)` vive en la posición plana `j * n_times + i`. Y el recorrido en orden C de un arreglo de forma `(n_freqs, n_times)` da exactamente ese mismo índice. Por eso `Z.ravel()` es directamente el orden que VTK espera, sin transponer nada.

Un detalle que sí podía morder: en la rama lineal, `Z` viene de `np.flipud(...)`, que devuelve una **vista con zancadas negativas** — no es contigua en C. De ahí el `np.ascontiguousarray()` antes del `ravel()`.

### Medición aislada

Construyendo la misma imagen por los dos caminos, sobre un escalograma real de 998 × 3051:

| | Tiempo |
|---|---:|
| Bucle píxel a píxel | 616,1 ms |
| Vectorizado | **7,5 ms** |
| | **82× más rápido** |

### Verificación de que la imagen es idéntica

```
escalares bucle       : (3044898,) float32
escalares vectorizado : (3044898,) float32
identicos bit a bit   : True
max diferencia        : 0.000e+00
```

Y una comprobación específica contra transposición o espejado, leyendo por coordenadas `(i, j)` en las cuatro esquinas y en puntos interiores:

| Coordenada | Bucle | Vectorizado | `Z[j,i]` | |
|---|---:|---:|---:|---|
| (0, 0) | 0,248971 | 0,248971 | 0,248971 | ✓ |
| (3050, 0) | 0,167697 | 0,167697 | 0,167697 | ✓ |
| (0, 997) | 0,008957 | 0,008957 | 0,008957 | ✓ |
| (3050, 997) | 0,004989 | 0,004989 | 0,004989 | ✓ |
| (1964, 177) | 0,023671 | 0,023671 | 0,023671 | ✓ |
| (500, 500) | 0,014172 | 0,014172 | 0,014172 | ✓ |

Las esquinas son la prueba que importa: si la imagen estuviera volteada o transpuesta, esos cuatro puntos serían los primeros en delatarlo.

### Efecto sobre el render completo

En la suite, `render_scalogram` no solo llena la imagen: también construye la tabla de color, arma el gráfico, configura los ejes y renderiza.

| | Fase 0 | Fase 1 | |
|---|---:|---:|---|
| `wavelet.render_scalogram` | 716,5 ms | **97,7 ms** | **7,34×** |
| `wavelet_average.render_scalogram` | 732,1 ms | **80,4 ms** | **9,11×** |

Los ~90 ms que quedan son el resto del trabajo de renderizado —entre otras cosas, la construcción de la tabla de color, que es otro bucle de Python de 256 iteraciones—. El llenado de la imagen dejó de ser el costo dominante.

---

## Resumen de la fase

Comparación completa: `v2_fase0_baseline` contra `v2_fase1_completa`.

| Operación | Fase 0 | Fase 1 | Mejora |
|---|---:|---:|---:|
| `wavelet.compute_wavelet` (1 trial) | 202,0 ms | **103,1 ms** | **1,96×** |
| `wavelet.render_scalogram` | 716,5 ms | **97,7 ms** | **7,34×** |
| `wavelet_average.compute_wavelet` (×20) | 4.213,6 ms | **2.077,9 ms** | **2,03×** |
| `wavelet_average.render_scalogram` | 732,1 ms | **80,4 ms** | **9,11×** |

### Lo que siente el investigador

Sumando cálculo más dibujo, que es lo que transcurre entre pulsar el botón y ver el resultado:

| Acción | Antes | Ahora | |
|---|---:|---:|---|
| Un wavelet individual | 918,5 ms | **200,8 ms** | **4,6× más rápido** |
| Un wavelet promedio (20 trials) | 4.945,7 ms | **2.158,3 ms** | **2,3× más rápido** |
| Pico de memoria (30 trials) | 1.715 MB | **414 MB** | **4,1× menos** |
| Pico de memoria (60 trials, el archivo real) | 3.107 MB | **414 MB** | **7,5× menos** |

### El costo de todo esto

| | |
|---|---|
| Archivos tocados | 2 |
| Líneas modificadas | 19 insertadas, 7 borradas |
| Dependencias nuevas | **ninguna** |
| Cambios en el resultado numérico | **ninguno** (verificado en los tres pasos) |
| Concurrencia introducida | **ninguna** |

Ese último punto es el que conviene subrayar: **todo lo anterior se consiguió sin un solo hilo nuevo**. Es exactamente lo que anticipaba la conclusión del documento de diseño — que lo que optimiza no es la concurrencia — y es la razón por la que estas tres tareas se pusieron antes del orquestador y no después.

### Por qué el orden importaba

De haber construido primero el orquestador, habría movido los ~200 ms de cómputo a un hilo trabajador y dejado **716 ms de renderizado congelando la ventana**, en `wavelet_average` justo *después* de que el hilo terminara — es decir, en el momento en que el usuario cree que ya acabó. La conclusión razonable habría sido "el orquestador no sirvió".

Ahora el reparto es otro: el render está en ~80-98 ms, por debajo del umbral de percepción, y lo que queda por sacar del hilo de interfaz son los ~2 s del cómputo promedio. Eso sí es trabajo para el orquestador.

---

## Apéndice: todo el código que cambió

Dos archivos, cinco puntos de cambio. Nada más se tocó en el repositorio.

```
plugins/analysis/time_frequency/wavelet/wavelet_plugin.py                 | 18 +++++++----
plugins/analysis/time_frequency/wavelet_average/wavelet_average_plugin.py | 36 +++++++++++++-----
2 files changed, 37 insertions(+), 17 deletions(-)
```

### Resumen por punto de cambio

| # | Archivo | Línea | Paso | Qué |
|---|---|---:|---|---|
| 1 | `wavelet_plugin.py` | 4 | 1.3 | `import numpy_support` |
| 2 | `wavelet_plugin.py` | 211 | 1.1 | `method="fft"` en `pywt.cwt` |
| 3 | `wavelet_plugin.py` | 334-341 | 1.3 | Llenado de VTK vectorizado |
| 4 | `wavelet_average_plugin.py` | 4 | 1.3 | `import numpy_support` |
| 5 | `wavelet_average_plugin.py` | 292 | 1.1 | `method="fft"` en `pywt.cwt` |
| 6 | `wavelet_average_plugin.py` | 445-452 | 1.3 | Llenado de VTK vectorizado |
| 7 | `wavelet_average_plugin.py` | 582-624 | 1.2 | Acumulador incremental |

### 1. `wavelet_plugin.py` — import (paso 1.3)

```diff
 from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
+from vtkmodules.util import numpy_support
 import vtk
 import numpy as np
```

### 2. `wavelet_plugin.py:211` — `method="fft"` (paso 1.1)

```diff
-        coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs)
+        # method="fft": ~1.9x mas rapido que el "conv" por defecto de PyWavelets,
+        # con resultado numericamente identico (diferencia relativa ~4e-14).
+        coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs, method="fft")
         scalogram = np.abs(coef)
```

### 3. `wavelet_plugin.py:334-341` — llenado de VTK (paso 1.3)

```diff
-        img.AllocateScalars(vtk.VTK_FLOAT, 1)
-        
-        for j in range(n_freqs):
-            for i in range(n_times):
-                img.SetScalarComponentFromFloat(i, j, 0, 0, Z[j, i])
+        # Conversion en bloque en vez de pixel por pixel: el bucle anterior hacia
+        # n_freqs * n_times llamadas al wrapper de VTK (3 millones para 998x3051).
+        # vtkImageData guarda los escalares en orden x-rapido, o sea
+        # plano[j * n_times + i], que es exactamente el orden C de Z.ravel().
+        # Mismo patron que core/utils/adapters.py.
+        Z_plano = np.ascontiguousarray(Z, dtype=np.float32).ravel()
+        arr = numpy_support.numpy_to_vtk(Z_plano, deep=True, array_type=vtk.VTK_FLOAT)
+        img.GetPointData().SetScalars(arr)
         img.Modified()
```

### 4 y 5. `wavelet_average_plugin.py` — import y `method="fft"`

```diff
 from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
+from vtkmodules.util import numpy_support
 import vtk
```

```diff
-            coef, _ = pywt.cwt(sig, scales, wavelet, sampling_period=1/fs if fs > 0 else 1.0)
+            # method="fft": ~1.9x mas rapido que el "conv" por defecto de PyWavelets,
+            # con resultado numericamente identico (diferencia relativa ~4e-14).
+            coef, _ = pywt.cwt(sig, scales, wavelet,
+                               sampling_period=1/fs if fs > 0 else 1.0, method="fft")
             scalogram = np.abs(coef)
```

Es el mismo cambio que en el plugin individual; la única diferencia es que aquí `sampling_period` lleva su guarda contra `fs = 0`, que ya estaba.

### 6. `wavelet_average_plugin.py:445-452` — llenado de VTK (paso 1.3)

Idéntico al del plugin individual, salvo que el original tenía un `float(...)` de más dentro del bucle:

```diff
-        img.AllocateScalars(vtk.VTK_FLOAT, 1)
-
-        for j in range(n_freqs):
-            for i in range(n_times):
-                img.SetScalarComponentFromFloat(i, j, 0, 0, float(Z[j, i]))
+        Z_plano = np.ascontiguousarray(Z, dtype=np.float32).ravel()
+        arr = numpy_support.numpy_to_vtk(Z_plano, deep=True, array_type=vtk.VTK_FLOAT)
+        img.GetPointData().SetScalars(arr)
         img.Modified()
```

### 7. `wavelet_average_plugin.py:582-624` — acumulador (paso 1.2)

Este es el único cambio que toca la lógica del bucle, y va en tres puntos dentro de `WaveletWorker.run()`.

**Declaración**, antes del bucle:

```diff
                 plugin = self.plugin
-                scalograms = []
+                # Reduccion incremental: se acumula la suma de los escalogramas y se
+                # descarta cada uno tras sumarlo, en vez de guardar los N en una lista
+                # y apilarlos al final. El pico de memoria deja de crecer con n_trials.
+                acumulador = None
+                n_validos = 0
                 n_trials = self.data.shape[1]
```

**Dentro del bucle**, donde antes se acumulaba en la lista:

```diff
-                        scalograms.append(scalogram)
+                        if acumulador is None:
+                            acumulador = scalogram.astype(np.float64)
+                        else:
+                            acumulador += scalogram
+                        n_validos += 1
```

**Al salir del bucle**, donde antes se apilaba y promediaba:

```diff
-                if not scalograms:
+                if n_validos == 0:
                     raise ValueError("No valid scalograms computed")
 
-                stacked = np.stack(scalograms, axis=0)
-                avg_scalogram = np.mean(stacked, axis=0)
+                avg_scalogram = acumulador / n_validos
```

**Detalles de este cambio que conviene conocer:**

- `scalogram.astype(np.float64)` **copia**, que es lo que se quiere: el acumulador no debe quedar apuntando al arreglo que devolvió el plugin, porque después se le suma encima.
- El acumulador es `float64` aunque los escalogramas vengan en la precisión que vengan. Sumar 200 matrices en `float32` acumularía error de redondeo; en `float64` no es un problema.
- La condición de error cambió de `if not scalograms` a `if n_validos == 0`: es la misma condición (ningún trial válido), expresada sobre el contador.
- Un trial con forma distinta a los demás antes reventaba al final, en el `np.stack`, después de haber calculado todo. Ahora falla en el `+=` de ese trial, lo atrapa el `except` que ya existía, se registra como *"Trial N failed"* y el promedio sigue con los válidos. Es un cambio de comportamiento pequeño y a mejor.

### Lo que NO se cambió

- **Ningún archivo de `core/`.** Ni el Kernel, ni los servicios, ni los adaptadores.
- **Ninguno de los otros 15 plugins.**
- **Ninguna prueba.** Las suites de `test/` corrieron tal cual estaban.
- **`requirements.txt`.** Cero dependencias nuevas: `numpy_support` viene dentro de VTK, que ya estaba.
- **La matemática.** Los tres pasos se verificaron y ninguno altera el resultado.

---

## Estado y lo que sigue

| Paso | Estado |
|---|---|
| 1.1 `method='fft'` | ✅ Hecho, medido, verificado |
| 1.2 Acumulador incremental | ✅ Hecho, medido, verificado |
| 1.3 Vectorizar VTK | ✅ Hecho, medido, verificado |

Etiquetas en `perf_results.json`: `v2_fase0_baseline` → `v2_fase1_1_cwt_fft` → `v2_fase1_completa`.

**Dos cosas pendientes que esta fase dejó anotadas:**

1. **La suite no mide memoria.** El beneficio del paso 1.2 hubo que medirlo aparte. Vale la pena incorporar una medición de pico de memoria a `test/performance_test/` para que el antes/después de la tesis cubra las dos dimensiones.
2. **La tabla de color sigue siendo un bucle de Python** (`_build_lut`, 256 iteraciones). Es pequeño comparado con lo que se acaba de arreglar, pero es del mismo tipo y está en los ~90 ms restantes del render.

Sigue la **Fase 2**: el orquestador mínimo.
