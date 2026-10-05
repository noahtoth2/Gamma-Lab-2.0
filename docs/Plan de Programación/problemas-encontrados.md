# Problemas encontrados por el camino

*Hallazgos que no estaban en el plan y aparecieron al medir e implementar*

---

## Para qué sirve este documento

El plan del orquestador tiene un alcance definido. Pero medir el código de verdad y tocarlo destapa cosas que nadie fue a buscar. Este documento las registra para que **no se pierdan ni se mezclen** con el trabajo del orquestador.

Todo lo que está acá fue **verificado directamente contra el código o ejecutando pruebas**, no inferido. Cada entrada dice cómo se comprobó.

Ninguno de los problemas 1 a 13 lo causaron los cambios de la Fase 1. Los que podían confundirse con eso se verificaron explícitamente. El nº 14 sí es de la Fase 2: estaba en el propio orquestador, y ya se corrigió.

**Última actualización:** 30 de septiembre de 2026, al revisar las fases 0, 1 y 2 y al cerrar la Fase 3.

---

## Resumen

| # | Problema | Gravedad | Estado |
|---|---|---|---|
| 1 | 6 archivos de prueba con imports obsoletos | Alta | ✅ **Arreglado** |
| 2 | El wavelet no coincide con MATLAB | **Alta** | ⬜ Abierto · causas identificadas |
| 3 | `psd_average`: baja correlación en la columna 0 | Media | ⬜ Abierto |
| 4 | Hilo que queda vivo al cambiar de pestaña | Media | ✅ **Resuelto** (29 sep) |
| 5 | `Kernel.get_all_plugins()` no existe: rama muerta al cerrar | Baja | ✅ **Resuelto** (29 sep) |
| 6 | `load_mat()` inalcanzable desde la interfaz | Media | ⬜ Abierto |
| 7 | Tres servicios sin registrar en el Kernel | Media | ⬜ Abierto (el `TaskService` sí se registra) |
| 8 | Señal `progress` declarada y nunca emitida | Baja | ✅ **Resuelto** (Fase 3) |
| 9 | El spinner es modal e indeterminado | Media | ✅ **Resuelto** (1 oct) |
| 10 | `_build_lut` sigue siendo un bucle de Python | Baja | ⬜ Abierto |
| 11 | La suite de benchmarks no mide memoria | Media | ⬜ Abierto |
| 12 | `load_edf` cuadruplica la memoria del archivo | Media | ⬜ Abierto |
| 13 | Error del menú contextual durante los benchmarks | Baja | ⬜ Sin investigar |
| 14 | El orquestador podía cerrar la aplicación al terminar una tarea | **Alta** | ✅ **Arreglado** (30 sep) |
| 15 | `artifact_remove` escribe los datos compartidos desde su hilo | Media | ✅ **Resuelto** (Fase 3) |
| 16 | Escala logarítmica, eje de tiempo y ejes del escalograma | Media | ✅ **Arreglado** (29 sep) |
| 17 | PyWavelets crea franjas falsas en frecuencias bajas | Media | ⬜ Abierto |
| 18 | Submuestreo inexacto y sin filtro antialias | Media | ✅ **Cerrado** (1 oct): eje corregido; el antialias se descarta a proposito |
| 19 | Una tarea que lanza `SystemExit` bloquea la cola del orquestador | Baja | ✅ **Arreglado** (30 sep) |
| 20 | `artifact_remove` falla si los trials se generaron en otro canal | Media | ✅ **Arreglado** (30 sep) |
| 21 | Las modificaciones de `artifact_remove` no se guardan en el proyecto | **Alta** | ✅ **Resuelto** (1 oct, opción A) |
| 22 | `MainWindow` conserva código de los hilos viejos que ya nada usa | Baja | ⬜ Abierto |
| 23 | `erp` se quedó fuera de la vectorización de VTK del paso 1.3 | Media | ✅ **Resuelto** (1 oct) |

---

## 1. Seis archivos de prueba con imports obsoletos ✅ ARREGLADO

**Cómo apareció.** Al intentar cerrar el criterio de salida de la Fase 1 (*"`test/plugins_test/` sigue pasando"*), la suite ni siquiera arrancaba.

```
ERROR test/plugins_test/test_average_plugin.py
ERROR test/plugins_test/test_erp_plugin.py
ERROR test/plugins_test/test_fft_average_plugin.py
ERROR test/plugins_test/test_fft_plugin.py
ERROR test/plugins_test/test_psd_average_plugin.py
ERROR test/plugins_test/test_psd_plugin.py
!!!!!!!!! Interrupted: 6 errors during collection !!!!!!!!!
ModuleNotFoundError: No module named 'core.services.fileio'
```

**La causa.** Una reorganización de `core/` movió dos cosas y estos archivos nunca se actualizaron:

| Ruta en el test | Dónde vive realmente |
|---|---|
| `core.services.fileio` | `core.services.fileio_service` |
| `core.services.trial_dataset` | `core.model.trial_dataset` |

Los dos archivos de wavelet sí tenían las rutas nuevas, lo que confirma que fue una actualización a medias, no un cambio deliberado.

Es exactamente el incidente que el propio SAD ya documenta en *"Estabilidad de módulos internos"*, y la razón por la que ese apartado exige que un renombrado actualice a todos sus consumidores en el mismo cambio.

**El arreglo.** Doce líneas: dos imports en cada uno de los seis archivos. Nada más.

**Lo que destapó — y esto es lo importante:**

| | Antes | Después |
|---|---|---|
| Archivos que corren | 2 de 8 | **8 de 8** |
| Pruebas que pasan | 2 | **19** |
| Pruebas que fallan | 4 | 5 |

**Había 19 pruebas de validación funcionando que nadie podía ejecutar.** Cubren FFT, FFT promedio, PSD, PSD promedio, ERP y Average contra referencias de MATLAB. Estuvieron invisibles todo este tiempo por doce líneas.

Y de paso destapó el problema nº 3, que estaba escondido detrás del error de recolección.

> **Por qué importa para el plan:** sin esto, la Fase 3 (mover código de plugins al orquestador) se haría sin red de seguridad. Ahora hay 19 pruebas que avisan si algo se rompe.

---

## 2. El wavelet no coincide con MATLAB ⬜ ABIERTO

**Gravedad: alta.** Es el hallazgo más serio de todos los que hay acá, y no es de rendimiento sino de **correctitud**.

**Cómo apareció.** Al buscar una forma de verificar que `method='fft'` no cambiara los resultados.

**Qué pasa.** Las cuatro pruebas de validación del wavelet contra MATLAB fallan, y ya fallaban antes de tocar nada:

```
test_wavelet_plugin.py::test_correlation_by_row                    FAILED
test_wavelet_plugin.py::test_pointwise_fraction_allowing_outliers  FAILED
test_wavelet_average_plugin.py::test_correlation_by_row            FAILED
test_wavelet_average_plugin.py::test_pointwise_fraction...         FAILED
```

La magnitud descarta que sea una tolerancia mal calibrada:

```
passed = 6917 / 3.044.898  ->  ratio = 0,00227     (pasa el 0,23 % de los puntos)
peor punto: APP = 0,447459   MATLAB = 0,006129     (factor ~73x)
filas con violaciones: 998 de 998
```

Fallan **todas** las filas del escalograma, y la correlación por fila también. Eso apunta a una diferencia estructural: la normalización, la parametrización del wavelet Morlet, o el mapeo de frecuencias a escalas.

**Verificado que NO lo causó la Fase 1.** Tras aplicar `method='fft'`, las cifras del fallo son idénticas dígito por dígito: mismo `passed=6917`, mismo peor punto en `(row=177, col=2379)`, mismo `APP=0.447459`. Si el cambio hubiera alterado algo, esos números se habrían movido.

> **Actualización (1 de octubre de 2026):** `method='fft'` quedó fijado de forma definitiva, y el fallo es indiferente al modo. Corriendo la suite con `conv` y con `fft` sobre el mismo código, las cifras salen idénticas dígito por dígito: `passed=62786/3044898` y correlación mínima 0,5212 en el promedio, `passed=58999/3044898` y mínima 0,3857 en el individual. Las cifras cambiaron respecto al `passed=6917` de arriba, pero por el ajuste de `SCALE_LOG` descrito más abajo, no por el modo de cálculo.

> **Actualización (30 de septiembre de 2026): viene de Gamma Lab 1.0, y ya se conocen las causas.**
>
> - **Es heredado.** Con el mismo archivo y los mismos parámetros, 2.0 produce **exactamente los mismos bits** que el código original de 1.0 (detalle en [`resultados-fase-1.md`](resultados-fase-1.md)). La diferencia con MATLAB ya estaba en 1.0; no la introdujo ninguna fase.
> - **Causas identificadas** en el análisis con la chirp del 29 de septiembre:
>   - la normalización de la wavelet: PyWavelets hace crecer la magnitud con la escala (normalización L2), mientras que MATLAB normaliza para que la magnitud sea la amplitud de la señal (L1);
>   - el submuestreo sin filtro antialias (nº 18);
>   - a eso se suman las franjas de precisión de PyWavelets en frecuencias bajas (nº 17).
> - **Ninguna está corregida todavía.** Es una decisión científica que conviene cerrar con la directora.
> - **Ojo con la prueba de Wavelet Average:** usaba `SCALE_LOG = True`. Desde el nº 16 comparaba nuestras 144 filas logarítmicas con las primeras 144 de las 999 filas lineales de MATLAB, así que esa comparación no medía nada útil (ya fallaba antes).
>
> **Corregido (1 de octubre de 2026):** las dos pruebas de wavelet quedaron en `SCALE_LOG = False`, que es la rejilla en la que está exportada la referencia. El diagnóstico que lo respalda, comparando los tres caminos de cálculo contra el CSV de MATLAB:
>
> | Camino | Forma | Correlación media | Filas > 0,8 |
> |---|---|---|---|
> | Lineal (`escala_log=False`) | 998×3051 | 0,753 | 402/998 |
> | Logarítmico de producción (`geomspace`) | 144×3051 | 0,035 | 0/144 |
> | Lineal + `scale_log` posterior (lo que hacía la prueba) | 998×3051 | 0,221 | 116/998 |
>
> El efecto en las pruebas fue grande: el promedio pasó de fallar **998 filas a fallar 5** (986-990, correlación mínima 0,5212) y el individual de 998 a 596 (mínima 0,3857). Las cuatro siguen sin alcanzar el umbral de 0,8 en todas las filas, pero ahora fallan por la discrepancia real descrita arriba y no por comparar dos rejillas distintas.

**Qué hacer.** Abrirlo como frente de trabajo aparte y levantarlo con la directora. No bloquea al orquestador, pero en una herramienta de análisis científico una discrepancia de este tamaño con la referencia pesa más que cualquier mejora de rendimiento.

---

## 3. `psd_average`: baja correlación en la columna 0 ⬜ ABIERTO

**Cómo apareció.** Estaba escondido detrás del error de recolección del problema nº 1. Al arreglar los imports, salió a la luz.

```
Failed: Low correlation in columns [0] (min=0.5847, threshold=0.95)
Worst correlations: col 0: 0.5847
```

**Qué lo distingue del nº 2.** Es mucho más acotado: **solo falla la columna 0**, todas las demás pasan. En una PSD la columna 0 suele ser la componente continua (0 Hz), que es notoriamente sensible al método de *detrend*. Eso hace pensar en una diferencia de configuración puntual, no en un problema estructural como el del wavelet.

**Verificado que NO lo causó la Fase 1:** no se tocó ningún plugin de PSD.

**Qué hacer.** Revisar cómo maneja el *detrend* y la componente DC el plugin frente al script de MATLAB. Probablemente sea un parámetro, no un algoritmo.

---

## 4. Hilo que queda vivo al cambiar de pestaña ✅ RESUELTO

> **Resuelto el 29 de septiembre de 2026, por otro camino que el previsto.** Wavelet Average ya no tiene hilo propio: manda su cálculo al orquestador. Y al cambiar de sección, `MainWindow.clear_plugin_area` llama a `_cancel_tasks_of(plugin)`, que hace `cancel_all_from(plugin.meta.id)` antes del `stop()`. Así ningún plugin tiene que acordarse de cancelar, que era la idea de la Fase 3; solo que vive en la ventana y no en `IPlugin.stop()`. Lo cubren las 2 pruebas de `test/services_test/test_cancelacion_al_cambiar_seccion.py`. El texto de abajo queda como registro.

**Dónde.** `wavelet_average_plugin.py`, líneas 53-62.

```python
def stop(self):
    #self._cleanup_worker()  # ✅ Asegúrate de limpiar al detener
    """Stop plugin and disable VTK interactor if present."""
    ...
```

La llamada que cancelaría el hilo **está comentada**. El `stop()` solo desactiva el interactor de VTK.

**Por qué es un problema real.** `main_window.py:232-234` ya llama a `active_plugin.stop()` cada vez que el usuario cambia de sección. Si se va de la pestaña mientras el wavelet promedio está calculando, el `QThread` **sigue vivo**, y al terminar intenta renderizar sobre un widget que ya no está visible.

**Cómo se resuelve.** La regla *"cancelar al salir"* de la Fase 3: que `IPlugin.stop()` llame a `cancelar_todas_de(self.meta.id)`. El gancho ya existe; una vez conectado, el problema desaparece para todos los plugins a la vez, sin que ninguno tenga que acordarse de limpiar.

---

## 5. `Kernel.get_all_plugins()` no existe: rama muerta al cerrar ✅ RESUELTO

> **Resuelto el 29 de septiembre de 2026.** La rama ya no existe. Al cerrar, `_on_app_about_to_quit` cancela las tareas de todos los plugins recorriendo `kernel.get_plugins()`, y el aviso de «Cálculo en curso» pregunta al orquestador con `has_active_tasks()`. El texto de abajo queda como registro.

**Dónde.** `app/view/main_window.py`, líneas 840-841, dentro del cierre de la aplicación:

```python
if hasattr(self.kernel, "get_all_plugins"):
    for name in self.kernel.get_all_plugins():
```

**Qué pasa.** `Kernel` **nunca definió** ese método. Sus métodos son `get_plugins()`, `get_plugin()`, `get_plugins_by_category()`, y ningún `get_all_plugins()`. El `hasattr` da siempre falso y esa rama nunca se ejecuta; siempre cae al camino alternativo.

**Consecuencia.** No es grave hoy porque hay un plan B que funciona, pero es una rama que nadie probó nunca y que da una falsa sensación de cobertura al leer el código.

**Cómo se resuelve.** O se borra la rama, o se agrega el método al Kernel. Cuando exista el orquestador, el cierre de la aplicación tendrá además un único punto natural: preguntarle si quedan tareas activas.

---

## 6. `load_mat()` inalcanzable desde la interfaz ⬜ ABIERTO

**Dónde.** El método existe y está completo en `core/services/fileio_service.py:137`. Pero su única llamada, en `plugins/io/open_signal/open_signal_plugin.py:240`, está comentada:

```python
#     ds = fileio.load_mat(fname)
```

**Consecuencia.** Desde la interfaz solo se pueden abrir archivos `.abf` y `.edf`. El soporte para `.mat` está escrito, probablemente funciona, y **no hay forma de llegar a él**.

**Qué hacer.** Averiguar por qué se comentó — si fue por un fallo concreto o quedó de una prueba. Si funciona, es funcionalidad terminada que el usuario no puede usar.

---

## 7. Tres servicios sin registrar en el Kernel ⬜ LO TOCA LA FASE 2

**Qué dice el SAD.** Que el Kernel registra y expone `DataStore`, `FileIOService`, `ExportService`, `MeasurementService` y `SettingsService`, y que *"los plugins acceden a estos servicios sin crear instancias propias"*.

**Qué hace `main.py`:**

```python
kernel.register_service("DataStore", DataStore())
kernel.register_service("FileIO", FileIOService())
```

Solo dos. `ExportService` y `MeasurementService` los construye directamente `VTKContextMenu` en su constructor, y `SettingsService` no se registra en ningún lado.

**Además, la clave no coincide con el nombre:** el servicio se registra como `"FileIO"`, no `"FileIOService"`. `OpenSignalPlugin` tiene un plan B que crea su propia instancia si no lo encuentra — o sea que el desajuste está compensado con código, no resuelto.

**Qué hacer.** Cuando se registre el `TaskService` en la Fase 2 hay que decidir el criterio: o los cinco servicios pasan por el Kernel, o se corrige el SAD para que describa lo que el sistema realmente hace. Hoy documento y código dicen cosas distintas.

> **Estado al 30 de septiembre de 2026:** la Fase 2 registró el `TaskService` en `main.py`, junto a `DataStore` y `FileIO`. Los otros tres (`ExportService`, `MeasurementService`, `SettingsService`) siguen sin registrarse, y la decisión de criterio sigue pendiente.

---

## 8. Señal `progress` declarada y nunca emitida ✅ RESUELTO

**Dónde.** `artifact_remove_plugin.py:28`:

```python
class _ApplyWorker(QtCore.QObject):
    progress = QtCore.pyqtSignal(int)      # nunca se emite ni se conecta
    finished = QtCore.pyqtSignal(object)
    error    = QtCore.pyqtSignal(str)
```

Código muerto: la señal existe, pero nadie la dispara ni la escucha. Alguien previó el reporte de progreso y quedó a medias.

**Relacionado:** en el otro plugin con hilos pasa lo contrario. `WaveletWorker` **sí** emite progreso por trial (*"Trial 3/20: computed"*), pero solo llega a la consola: nunca se muestra en la interfaz.

Entre los dos está casi todo lo necesario para un indicador de progreso real; lo que falta es unificarlo, que es justo lo que hace el orquestador.

> **Resuelto el 30 de septiembre de 2026 (Fase 3).** `_ApplyWorker` y su señal muerta ya no existen. Los dos plugins reportan su avance con `ctx.progress` del orquestador, y el texto llega a la barra de estado: *«Trial 3/20 (15%)»* en Wavelet Average, *«Aplicando la modificación: Trial 12/60 (20%)»* al interpolar en `artifact_remove`. Falta el widget propio con porcentaje (nº 9).

---

## 9. El spinner es modal e indeterminado ✅ RESUELTO

**Dónde.** `core/utils/plugin_alerts.py:40-63`.

Dos limitaciones, las dos deliberadas en su momento pero problemáticas ahora:

- **`setModal(True)`** (línea 46): bloquea toda la aplicación mientras está visible. Aunque el cálculo corra en otro hilo, el usuario no puede hacer nada más. Es lo contrario de lo que busca el orquestador.
- **`bar.setRange(0, 0)`** (línea 63): barra siempre en modo indeterminado. Nunca muestra un porcentaje, aunque el worker sepa perfectamente en qué trial va.

**Y no hay botón de cancelar en ninguna parte.** Una búsqueda de "cancel" en todo `plugins/` no devuelve nada.

**Por qué importa.** El orquestador puede implementar la cancelación entera por dentro, pero si la interfaz no tiene desde dónde dispararla, el usuario no la va a poder usar. Hace falta un widget de progreso **no modal, determinado y con botón de cancelar**. Es un frente de trabajo de interfaz, no de núcleo.

> **Estado al 30 de septiembre de 2026: parcial.** Wavelet Average ya no abre el spinner modal. Mientras calcula, el botón queda deshabilitado con el texto *«Computing...»*, el resto de la aplicación sigue usable y el avance por trial aparece en la barra de estado. Cambiar de sección o cerrar el proyecto cancela el cálculo. Lo que sigue faltando es el widget propio con porcentaje y botón **Cancelar**. `PluginAlerts.show_spinner()` sigue existiendo, pero hoy ningún plugin lo llama.

> **Resuelto el 1 de octubre de 2026.** El widget nuevo es `core/utils/task_progress.py` → `TaskProgressBar`: no modal, con rango 0-100 y botón **Cancelar** conectado al `cancel()` del `TaskHandle`.
>
> **Va una sola, en la barra de estado de la ventana principal**, enganchada a una señal nueva del orquestador: `TaskService.task_started`, que `submit()` emite con el handle recién creado. Así cualquier plugin que use el orquestador obtiene porcentaje y Cancelar **sin hacer nada**, hoy los tres migrados y mañana PAC. Es la misma decisión de la Fase 3.3: resolverlo en un sitio en vez de que cada plugin se acuerde. La alternativa —un widget que cada plugin embebe— obligaba a tocar tres interfaces y a que cada plugin nuevo se acordara.
>
> Verificado con `test/ui_test/escenarios_progreso.py`, **15 escenarios**: que la barra es determinada y no un spinner indeterminado, que no abre ningún diálogo modal, que el porcentaje avanza, que **Cancelar cancela de verdad** la tarea, que se oculta al terminar, al fallar y al cancelar, y que al relanzar sigue a la tarea nueva sin que la vieja mueva la barra.
>
> **`PluginAlerts.show_spinner()` se dejó en su sitio.** Está dibujado en el diagrama `1_application_core.html` del SDD, así que borrarlo obliga a corregir documentación de tesis. Nada lo llama; queda como decisión aparte.

---

## 10. `_build_lut` sigue siendo un bucle de Python ⬜ ABIERTO

**Dónde.** `wavelet_plugin.py:412` y su equivalente en `wavelet_average_plugin.py`.

```python
for i in range(N):      # N = 256
    ...
    lut.SetTableValue(i, r, g, b, 1.0)
```

Es **el mismo patrón** que acabamos de eliminar en el llenado de la imagen: llamadas al wrapper de VTK una por una, en vez de una conversión en bloque.

**Por qué es mucho menos grave.** 256 iteraciones contra 3.044.898. Pero es parte de los ~90 ms que quedan en `render_scalogram` después de la Fase 1, y es de la misma familia.

---

## 11. La suite de benchmarks no mide memoria ⬜ ABIERTO

**Cómo apareció.** El paso 1.2 (acumulador) mejora la memoria, no el tiempo. Su beneficio —de 3.107 MB a 414 MB con el archivo real— **no aparece en ningún benchmark**, porque `test/performance_test/` solo cronometra.

Hubo que medirlo con un script aparte, usando `GetProcessMemoryInfo` de la API de Windows vía `ctypes`.

> **Detalle técnico para quien lo retome:** `tracemalloc` no sirve. NumPy reserva los datos de sus arrays con `malloc` directo, fuera del asignador de Python, así que `tracemalloc` no los ve y da un número engañosamente bajo.

**Qué hacer.** Agregar medición de pico de memoria a `bench_common.py`, junto a `time_block()`. Sin eso, el antes/después de la tesis solo cubre una de las dos dimensiones, y la mejora de memoria es la más grande que consiguió la Fase 1.

---

## 12. `load_edf` cuadruplica la memoria del archivo ⬜ ABIERTO

**Dónde.** `core/services/fileio_service.py`, en el bucle de canales de `load_edf`:

```python
signals_raw.append(np.asarray(sig, dtype=np.float64))
```

**Qué pasa.** Los archivos EDF guardan típicamente enteros de 16 bits. Convertirlos a `float64` es una **expansión de 4×**: un archivo de 2 GB se vuelve ~8 GB en memoria.

**Relacionado, en `load_abf`:** `np.stack(signal_rows, axis=0)` crea un arreglo nuevo con copias de todos los canales; durante ese instante conviven la lista y la copia, o sea un pico transitorio del doble.

**Por qué importa.** El Escenario de Calidad 2 del SAD plantea explícitamente archivos de 1-2 GB como caso de estrés, con visualización inicial en menos de 8 segundos. Hoy **nadie ha probado eso**: el archivo de pruebas son 7 MB y `load_abf` mide 60-79 ms.

**Qué hacer.** Conseguir un archivo grande de verdad y medir. Ahí es donde `numpy.memmap` o la lectura por bloques tendrían sentido — a diferencia del wavelet, donde el acumulador ya resolvió el problema sin tocar disco.

> **Medido el 1 de octubre de 2026 en la Fase 4, y las dos predicciones se confirman.** Con `load_abf` y el ABF de prueba (6,87 MB en disco, mediana de 5 cargas):
>
> | Medida | Valor |
> |---|---|
> | Arreglos en memoria | 27,5 MB — **4,00× el tamaño en disco** |
> | Crecimiento del working set | +54,9 MB — **el doble de los arreglos**, el pico transitorio de `np.stack` |
> | Tiempo de carga | 82,5 ms → **12,0 ms por MB** |
>
> La señal queda en `float32`, no en `float64`, así que el 4× viene de los enteros de 16 bits del ABF más el eje de tiempo, que pesa como un canal entero. Extrapolado linealmente, un archivo de 1 GB daría ~4 GB de arreglos, ~8 GB de working set y ~12 s de carga — sin contar la lectura en frío del disco, porque esta medición se tomó con la caché caliente.
>
> **Sigue faltando el archivo grande.** No hay ninguno en el equipo: los tres ABF disponibles pesan 6,87 MB. Mientras no se consiga, el Escenario de Calidad 2 del SAD no se puede ni verificar ni refutar, y la extrapolación de arriba es solo indicativa. Detalle en [`resultados-fase-4.md`](resultados-fase-4.md).

> **Actualización (2 de octubre de 2026): la duplicación está corregida, y la causa no era la que decía esta entrada.**
>
> El escenario del SAD no solo pide un tiempo: también exige cargar «sin duplicación innecesaria de datos». Eso **sí** se puede verificar con el archivo de 7 MB, y se verificó.
>
> **La atribución anterior era incorrecta.** Esta entrada culpaba al `np.stack` de `load_abf`. Se quitó esa copia y **la medición no se movió**: seguía en 2,00×. El diagnóstico mostró por qué: **pyabf ya tiene el archivo entero en memoria** —`abf.data` son 13,7 MB y `abf.sweepX` otros 13,7 MB en `float64`—, y abrir el ABF ya cuesta +27,9 MB, casi exactamente el tamaño del resultado. Nosotros lo copiábamos otra vez. El `np.stack` era un transitorio real pero menor; la copia dominante era la nuestra sobre la de la librería.
>
> **La corrección** es quedarse con los arreglos de pyabf en lugar de copiarlos: el objeto `abf` muere al salir del cargador, así que NumPy los mantiene vivos y nadie más los referencia. Con una sola sweep, `abf.data[ch]` **es** la sweep 0 del canal (verificado); con varias sweeps hay que armar la matriz, y para eso se escribe en un arreglo ya reservado en vez de apilar al final.
>
> Medido en un proceso limpio, porque medir cargas sucesivas en el mismo proceso confunde «copia viva» con «liberada pero no devuelta al sistema»:
>
> | | Residente tras cargar | Pico del proceso |
> |---|---:|---:|
> | Antes | +55,2 MB (**2,01×**) | +75,8 MB (2,76×) |
> | Después | **+27,7 MB (1,01×)** | +55,1 MB (2,01×) |
>
> La duplicación residente desaparece. El 2,01× de pico que queda es un transitorio **interno de pyabf** mientras lee y convierte el archivo; está en la librería, no en nuestro código. Extrapolado a 1 GB: el residente baja de ~8 GB a ~4 GB.
>
> **`load_edf` tenía el mismo patrón, y peor.** En su camino de remuestreo los canales crudos seguían vivos mientras se construía la matriz remuestreada: hasta el triple. Ahora lee la cabecera primero (`getNSamples()`), reserva la matriz y escribe canal por canal, interpolando directo en la fila que le toca. Solo un canal crudo vive a la vez.
>
> **Verificación.** `load_edf` no tenía pruebas y no hay archivos EDF en el proyecto, así que se generan sintéticos con `pyedflib.EdfWriter` y se comparan contra la lógica original usada como oráculo: **idéntico** en los cuatro casos, incluido el de remuestreo. Todo en `test/services_test/test_fileio_sin_duplicar.py`, **10 pruebas**.
>
> De paso hubo que completar dos dobles de prueba: `DummyABF` no exponía `data` y los `DummyEDF` no tenían `getNSamples()`, atributos que las librerías reales sí tienen. Eran modelos incompletos de la API.
>
> **Lo que sigue pendiente** es solo el umbral de los 8 segundos con 1-2 GB, que necesita el archivo.

---

## 13. Error del menú contextual durante los benchmarks ⬜ SIN INVESTIGAR

**Cómo apareció.** Repetidamente en la salida de la suite de rendimiento:

```
[PluginAlerts] INFO: Error creating contextual menu
 'NoneType' object has no attribute 'name'
```

**Estado.** No investigado. Puede ser solo un artefacto del entorno de pruebas, donde los plugins se instancian sin ventana ni señal activa y algo que normalmente existe llega en `None`. Pero conviene confirmarlo: si ocurre también en uso normal, es un error silencioso que el usuario nunca ve porque se registra como `INFO`.

**Nota aparte:** llamar `alerts.info(...)` para reportar un error ya es cuestionable de por sí. Debería ser `alerts.error(...)`, o no ser una alerta en absoluto.

---

## 14. El orquestador podía cerrar la aplicación al terminar una tarea ✅ ARREGLADO

**Gravedad: alta.** Cuando pasaba, la aplicación se cerraba de golpe, sin aviso, y se perdía lo que no estuviera guardado.

**Cómo apareció.** En la revisión del 30 de septiembre, con pruebas de estrés sobre el `TaskService`: 3.000 tareas cortas seguidas. El proceso moría sin traceback; forzando los mensajes de Qt a la consola (`QT_FORCE_STDERR_LOGGING=1`) apareció la causa:

```
QThread: Destroyed while thread is still running
```

**Qué pasaba.** Al llegar el resultado de una tarea, el servicio soltaba la última referencia a su `QThread`. PyQt lo destruía en ese instante, pero el hilo emite su resultado *antes* de terminar de salir de `run()`. Si el hilo de interfaz ganaba esa carrera, Qt abortaba el proceso. Lo mismo con los hilos desligados del R46.

**Por qué no lo vieron las pruebas.** Cada prueba unitaria lanzaba de 1 a 4 tareas; la carrera necesita volumen. Con 3.000 tareas se cayó en 13 de 20 corridas.

**El arreglo.** El servicio guarda cada hilo hasta que Qt emite su propia señal `QThread.finished`, que llega cuando el hilo ya salió; recién ahí lo libera. La conexión se hace antes de `start()`. El contrato con los plugins no cambió. Después del arreglo: 0 caídas en 20 corridas, y una prueba nueva de 10.000 tareas que con el código anterior falla 10 de 10 veces.

Detalle completo en [`resultados-fase-2.md`](resultados-fase-2.md).

---

## 15. `artifact_remove` escribe los datos compartidos desde su hilo ✅ RESUELTO

> **Resuelto el 30 de septiembre de 2026, en la Fase 3**, de la forma que se describe abajo: leer en la interfaz, calcular en el orquestador (`artifact_remove/compute.py`) y escribir en el slot de `finished`. Antes de escribir se comprueba que los trials no hayan cambiado. El resultado es idéntico bit a bit al anterior en 11 escenarios, y `MainWindow` ya ve el cálculo al cerrar. Detalle en [`resultados-fase-3.md`](resultados-fase-3.md). El texto de abajo queda como registro.

**Dónde.** `plugins/preprocessing/prepare/artifact_remove/artifact_logic.py`, función `apply_modification_to_all_valid`, que corre dentro del `_ApplyWorker` en un `QThread` propio.

**Qué pasa.** La función no solo calcula: al final **escribe** las columnas modificadas en el `TrialDataset` base de la señal (`td_base.trials[:, orig_col] = ...`) e invalida cachés internas del `SignalDataset`, todo desde el hilo secundario. Eso contradice la regla de escritura única de la Fase 2 (R54): mientras escribe, cualquier plugin que lea esos trials desde la interfaz podría ver datos a medio modificar.

**Además, su hilo no se ve al cerrar.** `_any_background_worker_running` busca un atributo `worker` en cada plugin, y `artifact_remove` guarda su hilo en `_apply_thread`. Si se cierra la aplicación a mitad de una modificación, no aparece el aviso de «Cálculo en curso».

**Cómo se resuelve en la Fase 3.** No basta con cambiar el `QThread` por un `submit()`: hay que partir la función en tres.

1. **Leer**, en el hilo de interfaz: los trials activos, el eje de tiempo y el mapa de índices.
2. **Calcular**, en una función pura dentro del orquestador: el `out_active` modificado.
3. **Escribir**, en el slot de `finished`: las columnas al `TrialDataset` base y la invalidación de cachés.

---

## 16. Escala logarítmica, eje de tiempo y ejes del escalograma ✅ ARREGLADO

**Cuándo.** 29 de septiembre de 2026, en los dos plugins de wavelet. No es del orquestador, pero cambia lo que muestra el escalograma, así que conviene tenerlo registrado.

| Qué pasaba | Qué hace ahora |
|---|---|
| Con escala logarítmica, el escalograma se calculaba en la rejilla lineal y después se **interpolaba** a una logarítmica. En frecuencias bajas eso inventaba franjas, y el z-score por fila se deformaba | La transformada se calcula **directamente** en frecuencias logarítmicas: 16 filas por octava, 144 filas entre 1 y 500 Hz. Con z-score, cada fila tiene exactamente media 0 y desviación 1 |
| El eje de tiempo empezaba en 0 | Empieza en el `time_rel` real del trial (−0,05 s en el archivo de prueba) |
| Los ejes del dibujo se ajustaban solos (modo AUTO de VTK): quedaba una franja vacía a la derecha y el eje logarítmico no terminaba en `fmax` | Ejes fijos a los datos |
| Marcas del eje logarítmico cada media década con decimales | Marcas 1-2-5 (1, 2, 5, 10, 20, 50…) |
| El plugin individual fallaba con `NameError` si faltaba el eje de tiempo, dividía por cero al normalizar una fila constante y no avisaba si el cálculo fallaba | Avisos en español en los tres casos |
| No se validaba que `fmax > fmin` ni que `fmax` no pasara de la mitad de la densidad de muestreo | Se valida en los dos plugins antes de calcular |

En escala lineal el resultado numérico no cambió: sigue idéntico bit a bit al de Gamma Lab 1.0.

**Consecuencia para las pruebas contra MATLAB:** ver la actualización del nº 2 sobre `SCALE_LOG`.

---

## 17. PyWavelets crea franjas falsas en frecuencias bajas ⬜ ABIERTO

**Cómo apareció.** Revisando el escalograma logarítmico del nº 16: entre 1 y 5 Hz se veían líneas horizontales tenues, en escala lineal y logarítmica.

**Qué pasa.** `pywt.cwt` construye la wavelet con una resolución fija (`precision=12`, su valor por defecto). En escalas grandes, que son las frecuencias bajas, esa resolución no alcanza y la convolución produce errores que cambian de fila a fila. Comparado contra una convolución exacta con la misma Morlet:

| Frecuencia | PyWavelets (`precision=12`) | Exacta |
|---:|---:|---:|
| 1,00 Hz | 0,2449 | 0,0613 |
| 1,14 Hz | **0,4478** | 0,0577 |
| 1,48 Hz | 0,0918 | 0,0119 |
| 3,68 Hz | 0,0759 | 0,0132 |

Con `precision=16` la mayoría de las filas coinciden con la exacta dentro de un 1 %, aunque todavía quedan algunas con desvíos (a 2,84 Hz y 4,20 Hz).

**Qué hacer.** Evaluar pasar `precision=16` en los dos plugins, medir cuánto cuesta en tiempo y decidirlo junto con el nº 2, porque puede explicar parte de la diferencia con MATLAB.

---

## 18. Submuestreo inexacto y sin filtro antialias ✅ CERRADO

**Dónde.** `compute_wavelet` de los dos plugins: `factor = round(fs_original / densidad)` y después `sig[::factor]`.

**Qué pasa.**

- **Si la densidad no divide a la frecuencia original, el eje queda corrido.** Por ejemplo, de 10.000 a 3.000 Hz: el factor sale 3, la señal queda en 3.333 Hz, pero se la trata como de 3.000, y todas las frecuencias salen un 11 % corridas.
- **Si la densidad elegida es mayor que la original**, el factor queda en 1 pero los ejes se calculan con la densidad pedida: salen mal.
- **`sig[::factor]` no filtra antes de descartar muestras.** Lo que haya por encima de la nueva frecuencia de Nyquist se pliega sobre las frecuencias bajas (aliasing).

Con los valores por defecto (10.000 → 1.000 Hz, factor exacto 10) no hay corrimiento, pero sí falta el antialias.

**Qué hacer.** Usar la densidad efectiva (`fs_original / factor`) para los ejes o rechazar densidades que no dividan, y filtrar antes de submuestrear (por ejemplo con `scipy.signal.decimate`). Afecta al resultado numérico, así que conviene decidirlo con el nº 2.

> **Actualización (1 de octubre de 2026): el problema se partió en dos, y solo uno era una decisión científica.**
>
> ### El eje corrido: ✅ corregido
>
> No era una decisión, era un bug nuestro. Se verificó que **MATLAB no lo tiene**: `f_tf.m:8` y `f_Phase_PAC.m:6` calculan `srate = srate/srt`, o sea la tasa efectiva. Y nuestro propio `fft_average_plugin.py:195` ya hacía `fs_eff = fs / srt`. El wavelet era el único camino que usaba la densidad **pedida**.
>
> Medido con un tono puro de 100 Hz, antes y después:
>
> | Densidad pedida | Factor | Tasa real | Pico antes | Pico después |
> |---:|---:|---:|---:|---:|
> | 1.000 | 10 | 1.000,0 | 98,6 Hz | 98,6 Hz |
> | 2.500 | 4 | 2.500,0 | 98,6 Hz | 98,6 Hz |
> | **3.000** | 3 | **3.333,3** | **89,1 Hz** | **98,6 Hz** |
> | **4.000** | 2 | **5.000,0** | **79,1 Hz** | **98,6 Hz** |
> | **7.000** | 1 | **10.000,0** | **69,1 Hz** | **98,6 Hz** |
>
> (El −1,4 % residual es la resolución del eje, de ~0,5 Hz, no el bug: es idéntico en todas las densidades.)
>
> Dentro de un mismo análisis el error era un **porcentaje constante** en todo el eje, no creciente con la frecuencia; lo que crecía con la frecuencia era el error en Hz absolutos. Lo que determinaba la magnitud era la densidad pedida.
>
> Se arregló con una función nueva, `tasa_efectiva(fs_calculado, fs)`, usada en las escalas, el `sampling_period` y el eje de tiempo. **De paso se tapó un agujero en la validación:** comparaba `fmax` contra la mitad de la densidad **pedida**, así que con 3.800 Hz —factor 3, Nyquist real 1.666— dejaba pasar un `fmax` de 1.800. Ahora se valida contra la tasa efectiva, y la comprobación duplicada de los dos plugins se unificó. Los plugins avisan en español cuando la densidad pedida no es alcanzable.
>
> **El arreglo es inerte para la suite:** las pruebas contra MATLAB usan 1.000 Hz sobre un archivo de 10.000, factor 10 exacto, así que `fs_efectiva == fs`. No se movió ninguna cifra (171 pasan, los 5 fallos conocidos).
>
> ### El antialias: ✅ decidido — no se filtra, para coincidir con MATLAB
>
> Se implementó el filtro, se midió su efecto y **se decidió no usarlo**. El código del filtro se quitó: dejar un parámetro que nadie enciende es peor que una limitación documentada.
>
> **El aliasing es real**, y quedó medido: un tono de 800 Hz submuestreado a 1.000 Hz (Nyquist 500) **reaparece en 200 Hz**, donde no se distingue de uno legítimo. Con un filtro previo, su energía ahí bajaba más de diez veces.
>
> **Pero filtrar aparta el resultado de la referencia**, y bastante:
>
> | | Correlación media | Filas > 0,8 | Filas que fallan |
> |---|---:|---:|---:|
> | Individual, sin filtro (MATLAB) | 0,7527 | 402/998 | 596 |
> | Individual, con filtro | 0,7414 | 446/998 | 552 |
> | **Promedio, sin filtro (MATLAB)** | **0,9610** | **993/998** | **5** |
> | **Promedio, con filtro** | 0,8667 | 627/998 | **371** |
>
> En el promedio la concordancia se derrumba: de 5 filas que fallan a 371. La explicación es directa: **la referencia de MATLAB se generó sin filtrar, así que tiene el aliasing dentro**. Al quitárselo a nuestro resultado, deja de parecerse a una referencia que lo tiene.
>
> **La decisión (1 de octubre de 2026):** la referencia del proyecto es el MATLAB de `BOARD_FTD_PACC`, no Gamma Lab 1.0, y 2.0 debe compararse siempre contra él. Como filtrar rompe esa comparación, no se filtra. Queda como **limitación conocida y heredada**, no como olvido.
>
> Dato que vale para la tesis: el promedio sin filtro tiene correlación media **0,9610** con MATLAB y **993 de 998 filas** por encima de 0,8. La concordancia es buena — y parte de ella viene de que los dos programas comparten el mismo aliasing. Conviene decirlo explícitamente en el documento en lugar de dejarlo implícito.
>
> **Lo que queda si algún día se revisa:** el aliasing es del submuestreo, no del wavelet, así que el mismo criterio aplica a PAC, cuyo MATLAB también usa `downsample`. Si se decidiera corregir, habría que corregir los dos programas a la vez y regenerar la referencia.
>
> Verificado con `test/plugins_test/test_submuestreo_wavelet.py`, **20 pruebas**: la tasa efectiva en siete combinaciones, que un tono cae en su frecuencia con seis densidades distintas, que el corrimiento ya no crece a lo largo del eje, el rechazo del `fmax` imposible, y una prueba que **documenta el aliasing** —el tono de 800 Hz tiene que seguir apareciendo en 200— de modo que si alguien añade el filtro, esa prueba falla y obliga a actualizar esta entrada.

---

## 19. Una tarea que lanza `SystemExit` bloquea la cola del orquestador ✅ ARREGLADO

> **Arreglado el 30 de septiembre de 2026.** `_Worker.run` atrapa `BaseException`, así que la tarea emite `failed` y la cola sigue. Lo cubre la prueba `systemexit_en_la_tarea_no_bloquea_la_cola`. El texto de abajo queda como registro.

**Gravedad: baja.** Verificado ejecutándolo, pero no ocurre con las funciones actuales.

**Qué pasa.** El hilo del orquestador atrapa `Exception`. `SystemExit` hereda de `BaseException`, no de `Exception`, así que se escapa: la tarea no emite ninguna señal, el servicio la sigue dando por corriendo para siempre y **ninguna tarea posterior arranca**. Prueba: una tarea que hace `raise SystemExit(3)` seguida de otra normal; a los 3 s no hubo ninguna señal, `has_active_tasks()` seguía en verdadero y la segunda tarea seguía en cola.

**Qué hacer.** Atrapar `BaseException` en `_Worker.run` y emitir `failed`. Es una línea.

---

## 20. `artifact_remove` falla si los trials se generaron en otro canal ✅ ARREGLADO

> **Arreglado el 30 de septiembre de 2026.** `artifact_logic.py` y el plugin toman el último `TrialDataset` con `sd.get_all_trials_datasets()`. De los 11 escenarios con que se verificó la Fase 3, los otros 10 siguen idénticos bit a bit, y este ahora funciona: modifica los 60 trials del canal `IN 7`. Lo cubre la prueba `funciona_con_trials_de_otro_canal`. El texto de abajo queda como registro.

**Cómo apareció.** Al capturar el comportamiento de `artifact_remove` antes de migrarlo en la Fase 3, uno de los escenarios generó los trials en el segundo canal del archivo de prueba (`IN 7`).

**Qué pasa.** Para saber qué canal modificar, `artifact_logic.py` lee `sd.trials_dataset[-1].channel_name`. Pero `SignalDataset` no tiene ningún atributo `trials_dataset`: el campo real es privado (`__trials_dataset`). El error lo atrapa un `try`, y la función cae siempre al primer canal de la señal (`channel_names[0]`). Si los trials son de otro canal, no encuentra el `TrialDataset` base y «Apply» termina con:

> *No se encontró el conjunto de trials original para (17308005.abf, CA1).*

El plugin tiene la misma búsqueda en su propio `_get_current_channel_name`.

**Verificado que no lo causó la Fase 3:** falla igual con el código anterior y con el migrado. Se dejó idéntico a propósito, porque arreglarlo cambia el comportamiento.

**Qué hacer.** Usar la API pública que ya existe: `sd.get_all_trials_datasets()[-1].channel_name`. Son dos líneas, en `artifact_logic.py` y en el plugin, más una prueba con trials del segundo canal.

---

## 21. Las modificaciones de `artifact_remove` no se guardan en el proyecto ✅ RESUELTO

**Gravedad: alta.** Es pérdida silenciosa de trabajo del investigador.

**Cómo apareció.** En la revisión de la Fase 3 (30 de septiembre), siguiendo qué pasa con los datos después de «Apply». Verificado leyendo el código de guardar y abrir proyectos; no se reprodujo con un proyecto real.

**Qué pasa.** Dos cosas que se suman:

1. **El proyecto no guarda los valores de los trials**, sino cómo se generaron. `ProjectService._trials_to_json` guarda por cada `TrialDataset` sus `generation_params` (canal, umbral, ventana…) y los índices descartados. Al abrir, `_restore_trials` vuelve a cortar los trials desde la señal cruda con esos parámetros y reaplica los descartes. **No hay nada que reaplique las modificaciones de `artifact_remove`**: al reabrir, los trials vuelven a estar como antes de modificarlos. Tampoco se guarda el metadato `modified_trials`.
2. **`artifact_remove` nunca marca el proyecto como modificado.** Los plugins de análisis y el de trials llaman a `mark_project_dirty()`; este no. Si lo último que se hizo fue modificar artefactos, al cerrar no aparece el aviso de cambios sin guardar.

**No lo causó la Fase 3:** pasaba igual con el código anterior. La migración no cambió qué se guarda.

**Qué hacer: hay que elegir un diseño.**

| Opción | Cómo | A favor | En contra |
|---|---|---|---|
| **A. Guardar la receta** | Guardar en el proyecto la lista de modificaciones aplicadas (modo, A, B, en orden) junto a los `generation_params`, y reaplicarlas al abrir, después de los descartes | Sigue el diseño que ya usa el proyecto (guardar cómo, no el resultado). Ocupa unos bytes. El cálculo es determinista, así que se reconstruye el mismo resultado bit a bit | Hay que guardar también los descartes vigentes en el momento de cada modificación, porque afectan a qué columnas se tocaron. Abrir un proyecto tarda lo que tarde reaplicar |
| **B. Guardar los datos** | Guardar la matriz de trials modificada (por ejemplo, un `.npy` dentro de la carpeta del proyecto) | Exacto y simple de restaurar | 14,6 MB por cada 60 trials de 30.501 muestras, y cambia el formato del proyecto a guardar datos derivados |

En los dos casos, además, `artifact_remove` tiene que llamar a `mark_project_dirty()` después de escribir. Esa parte es una línea y no depende de la opción.

> **Resuelto el 1 de octubre de 2026 con la opción A.**
>
> **Dónde quedó el cálculo.** Reaplicar la receta al abrir es trabajo de `ProjectService`, y core no debe importar de `plugins/`. El cálculo se movió a `core/filters/artifacts.py`, que es la misma situación de `core/filters/trials.py`: `_restore_trials` ya llamaba a `cut_trials_single_channel` de ahí para reconstruir los trials, así que reaplicar una modificación es la misma clase de operación en la misma capa. El `compute.py` del plugin reexporta los nombres, de modo que las rutas de import de las pruebas y la sustitución de los escenarios siguen funcionando.
>
> **Qué se guarda.** Por cada modificación, una receta con `mode`, `point_a`, `point_b` y `discarded_indices` —los descartes vigentes en ese momento, porque determinan qué columnas del TrialDataset base se tocaron—. Van en `metadata["modificaciones"]`, el manifiesto las escribe como `modifications` junto a los `generation_params`, y `_restore_trials` las reaplica **después** de los descartes.
>
> **La línea que faltaba.** `artifact_remove` ya llama a `mark_project_dirty()` en el slot de `finished`, así que cerrar después de modificar sí avisa de cambios sin guardar.
>
> Verificado con `test/services_test/test_persistencia_artifact_remove.py`, **15 pruebas**. La central comprueba que la reconstrucción es **idéntica bit a bit** en cuatro escenarios de descartes (ninguno, tres en medio, el primero, varios en los extremos), y antes confirma que al recortar de cero los trials **no** salen ya modificados, para que el escenario pruebe algo. También: que la receta sobrevive a `json.dumps`, que dos modificaciones encadenadas se reconstruyen igual, que **con ventanas solapadas el orden se respeta**, que una receta inválida se salta sin interrumpir las demás, y que el manifiesto no inventa la clave cuando no hubo modificaciones.
>
> **Un detalle medido de paso:** dos modificaciones sobre ventanas **disjuntas** conmutan, así que ahí el orden no cambia el resultado. La prueba del orden usa ventanas que se solapan, donde sí importa.

---

## 22. `MainWindow` conserva código de los hilos viejos que ya nada usa ⬜ ABIERTO

**Gravedad: baja.** No hace daño; es limpieza.

**Dónde.** `app/view/main_window.py`: `_any_background_worker_running` todavía recorre los plugins buscando un atributo `worker`, y `_stop_all_background_workers` busca un método `_cleanup_worker`. Eran los hilos propios de `wavelet_average`. Desde la Fase 3 ningún plugin los tiene (verificado con una búsqueda en `plugins/`), y todo lo que corre en segundo plano lo conoce el `TaskService`.

**Qué hacer.** Borrar esos dos bucles y dejar solo las llamadas al orquestador (`has_active_tasks()` y `_cancel_all_tasks()`). La prueba `ningun_plugin_crea_hilos_propios` garantiza que no vuelvan a hacer falta.

---

## 23. `erp` se quedó fuera de la vectorización de VTK del paso 1.3 ✅ RESUELTO

**Gravedad: media.** Es tiempo de dibujo en el hilo de la interfaz, que es justo lo que la Fase 1.3 se propuso quitar.

**Cómo apareció.** Al separar cálculo de dibujo en la Fase 4.

**Dónde.** `plugins/analysis/time/erp/erp_plugin.py`, en `_render_heatmap`:

```python
for j in range(K):
    for i in range(Tn):
        img.SetScalarComponentFromFloat(i, j, 0, 0, X[j, i])
```

**Por qué importa.** Es el mismo patrón que el paso 1.3 reemplazó en los dos plugins de wavelet, donde se midió **82× más lento** que la versión vectorizada con `numpy_support.numpy_to_vtk`. Con el límite de 2.000 muestras del mapa de calor y 60 trials son hasta 120.000 llamadas al método de VTK, una por punto, desde Python.

La Fase 1.3 solo tocó los dos plugins de wavelet porque eran los que se habían medido; a `erp` nunca se le aplicó, aunque tiene la misma forma.

**Qué hacer.** El arreglo es el que ya está escrito dos veces en el proyecto, y el plugin **ya importa `numpy_support`**: basta con envolver la matriz en un arreglo de VTK y asignarla de una vez, cuidando el orden de memoria (VTK espera x-rápido, así que la matriz va contigua por filas de tiempo).

**Por qué no se hizo en la Fase 4.** El alcance de esa fase era separar cálculo de dibujo, no optimizar el dibujo. Ahora que `preparar_mapa_calor` existe, el cambio queda contenido en el método de dibujo.

> **Resuelto el 1 de octubre de 2026.** El doble bucle se reemplazó por el patrón del paso 1.3, que el plugin ya tenía importado:
>
> ```python
> X_plano = np.ascontiguousarray(X, dtype=np.float32).ravel()
> arr = numpy_support.numpy_to_vtk(X_plano, deep=True, array_type=vtk.VTK_FLOAT)
> img.GetPointData().SetScalars(arr)
> ```
>
> Medido construyendo el `vtkImageData` por los dos caminos y comparando sus escalares:
>
> | Tamaño | Bucle | Vectorizado | Ganancia | Escalares |
> |---|---:|---:|---:|---|
> | 3 × 500 | 0,8 ms | 0,2 ms | 4,1× | idénticos |
> | 20 × 2.000 | 11,1 ms | 0,3 ms | 40,3× | idénticos |
> | 60 × 2.000 | 36,0 ms | 0,4 ms | **91,3×** | idénticos |
>
> El 91× con 60 trials es consistente con el 82× que midió la Fase 1.3. Verificado con `test/plugins_test/test_erp_vtk_llenado.py`, **7 pruebas**: los mismos escalares que el bucle en cinco tamaños, que el tiempo queda en la x —si se invirtiera el orden la imagen saldría transpuesta, que era el riesgo anotado para la vectorización— y que los NaN se conservan en los mismos puntos.

---

## Cómo agrupar esto en trabajo real

**Frente de correctitud científica** *(el más urgente, y no es del orquestador)*
- nº 2 — el wavelet contra MATLAB
- nº 3 — la columna 0 de `psd_average`
- nº 17 — las franjas de precisión de PyWavelets
- ~~nº 18 — el submuestreo~~ (cerrado: eje corregido, antialias descartado para coincidir con MATLAB)

Son cuestiones de si los números que entrega la herramienta son correctos. Merecen su propio frente y conversación con la directora. Los nº 2, 17 y 18 conviene decidirlos juntos, porque los tres cambian el escalograma.

**Lo que absorben las fases del orquestador**
- nº 7 → decisión pendiente sobre qué servicios pasan por el Kernel
- ~~nº 4~~, ~~nº 8~~, ~~nº 9~~, ~~nº 14~~, ~~nº 15~~, ~~nº 19~~ → ya resueltos

**Pérdida de trabajo del usuario**
- ~~nº 21 — las modificaciones de artefactos no se guardan en el proyecto~~ (resuelto el 1 de octubre con la opción A: se guarda la receta)

**Deuda técnica suelta** *(cada una es de horas, no de días)*
- ~~nº 23 — el bucle de VTK en `erp`~~ (resuelto)
- nº 22 — código de los hilos viejos en `MainWindow`
- ~~nº 20 — `artifact_remove` con trials de otro canal~~ (resuelto)
- ~~nº 5 — rama muerta al cerrar~~ (resuelto)
- nº 6 — `load_mat` inalcanzable
- nº 10 — el bucle de `_build_lut`

**Huecos de instrumentación** *(sin esto no se puede demostrar el trabajo)*
- nº 11 — medir memoria en los benchmarks
- nº 12 — probar con un archivo grande de verdad

**Sin clasificar**
- nº 13 — el error del menú contextual
