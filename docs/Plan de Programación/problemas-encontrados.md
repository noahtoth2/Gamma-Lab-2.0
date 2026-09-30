# Problemas encontrados por el camino

*Hallazgos que no estaban en el plan y aparecieron al medir e implementar*

---

## Para qué sirve este documento

El plan del orquestador tiene un alcance definido. Pero medir el código de verdad y tocarlo destapa cosas que nadie fue a buscar. Este documento las registra para que **no se pierdan ni se mezclen** con el trabajo del orquestador.

Todo lo que está acá fue **verificado directamente contra el código o ejecutando pruebas**, no inferido. Cada entrada dice cómo se comprobó.

Ninguno de los problemas 1 a 13 lo causaron los cambios de la Fase 1. Los que podían confundirse con eso se verificaron explícitamente. El nº 14 sí es de la Fase 2: estaba en el propio orquestador, y ya se corrigió.

**Última actualización:** 30 de septiembre de 2026, en la revisión de las fases 0, 1 y 2 antes de empezar la Fase 3.

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
| 8 | Señal `progress` declarada y nunca emitida | Baja | ⬜ Lo resuelve la Fase 3 |
| 9 | El spinner es modal e indeterminado | Media | ⬜ Parcial: ya nadie lo usa, falta el widget con Cancelar |
| 10 | `_build_lut` sigue siendo un bucle de Python | Baja | ⬜ Abierto |
| 11 | La suite de benchmarks no mide memoria | Media | ⬜ Abierto |
| 12 | `load_edf` cuadruplica la memoria del archivo | Media | ⬜ Abierto |
| 13 | Error del menú contextual durante los benchmarks | Baja | ⬜ Sin investigar |
| 14 | El orquestador podía cerrar la aplicación al terminar una tarea | **Alta** | ✅ **Arreglado** (30 sep) |
| 15 | `artifact_remove` escribe los datos compartidos desde su hilo | Media | ⬜ Lo resuelve la Fase 3 |
| 16 | Escala logarítmica, eje de tiempo y ejes del escalograma | Media | ✅ **Arreglado** (29 sep) |
| 17 | PyWavelets crea franjas falsas en frecuencias bajas | Media | ⬜ Abierto |
| 18 | Submuestreo inexacto y sin filtro antialias | Media | ⬜ Abierto |
| 19 | Una tarea que lanza `SystemExit` bloquea la cola del orquestador | Baja | ⬜ Abierto |

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

> **Actualización (26 de septiembre de 2026):** `method='fft'` se revirtió y la wavelet volvió a usar convolución. El fallo sigue igual: `test_wavelet_average_plugin` da de nuevo `passed=6917`.

> **Actualización (30 de septiembre de 2026): viene de Gamma Lab 1.0, y ya se conocen las causas.**
>
> - **Es heredado.** Con el mismo archivo y los mismos parámetros, 2.0 produce **exactamente los mismos bits** que el código original de 1.0 (detalle en [`resultados-fase-1.md`](resultados-fase-1.md)). La diferencia con MATLAB ya estaba en 1.0; no la introdujo ninguna fase.
> - **Causas identificadas** en el análisis con la chirp del 29 de septiembre:
>   - la normalización de la wavelet: PyWavelets hace crecer la magnitud con la escala (normalización L2), mientras que MATLAB normaliza para que la magnitud sea la amplitud de la señal (L1);
>   - el submuestreo sin filtro antialias (nº 18);
>   - a eso se suman las franjas de precisión de PyWavelets en frecuencias bajas (nº 17).
> - **Ninguna está corregida todavía.** Es una decisión científica que conviene cerrar con la directora.
> - **Ojo con la prueba de Wavelet Average:** usa `SCALE_LOG = True`. Desde el nº 16 compara nuestras 144 filas logarítmicas con las primeras 144 de las 999 filas lineales de MATLAB, así que esa comparación ya no mide nada útil (ya fallaba antes). Hay que ponerle `SCALE_LOG = False` o exportar la referencia de MATLAB en la misma rejilla.

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

## 8. Señal `progress` declarada y nunca emitida ⬜ LO RESUELVE LA FASE 3

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

> **Estado al 30 de septiembre de 2026:** la mitad del wavelet ya está. Wavelet Average reporta su avance con `ctx.progress` y el texto *«Trial 3/20 (15%)»* llega a la barra de estado de la ventana. La señal muerta de `artifact_remove` sigue igual hasta que se migre en la Fase 3.

---

## 9. El spinner es modal e indeterminado ⬜ LO TOCA LA FASE 2

**Dónde.** `core/utils/plugin_alerts.py:40-63`.

Dos limitaciones, las dos deliberadas en su momento pero problemáticas ahora:

- **`setModal(True)`** (línea 46): bloquea toda la aplicación mientras está visible. Aunque el cálculo corra en otro hilo, el usuario no puede hacer nada más. Es lo contrario de lo que busca el orquestador.
- **`bar.setRange(0, 0)`** (línea 63): barra siempre en modo indeterminado. Nunca muestra un porcentaje, aunque el worker sepa perfectamente en qué trial va.

**Y no hay botón de cancelar en ninguna parte.** Una búsqueda de "cancel" en todo `plugins/` no devuelve nada.

**Por qué importa.** El orquestador puede implementar la cancelación entera por dentro, pero si la interfaz no tiene desde dónde dispararla, el usuario no la va a poder usar. Hace falta un widget de progreso **no modal, determinado y con botón de cancelar**. Es un frente de trabajo de interfaz, no de núcleo.

> **Estado al 30 de septiembre de 2026: parcial.** Wavelet Average ya no abre el spinner modal. Mientras calcula, el botón queda deshabilitado con el texto *«Computing...»*, el resto de la aplicación sigue usable y el avance por trial aparece en la barra de estado. Cambiar de sección o cerrar el proyecto cancela el cálculo. Lo que sigue faltando es el widget propio con porcentaje y botón **Cancelar**. `PluginAlerts.show_spinner()` sigue existiendo, pero hoy ningún plugin lo llama.

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

## 15. `artifact_remove` escribe los datos compartidos desde su hilo ⬜ LO RESUELVE LA FASE 3

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

## 18. Submuestreo inexacto y sin filtro antialias ⬜ ABIERTO

**Dónde.** `compute_wavelet` de los dos plugins: `factor = round(fs_original / densidad)` y después `sig[::factor]`.

**Qué pasa.**

- **Si la densidad no divide a la frecuencia original, el eje queda corrido.** Por ejemplo, de 10.000 a 3.000 Hz: el factor sale 3, la señal queda en 3.333 Hz, pero se la trata como de 3.000, y todas las frecuencias salen un 11 % corridas.
- **Si la densidad elegida es mayor que la original**, el factor queda en 1 pero los ejes se calculan con la densidad pedida: salen mal.
- **`sig[::factor]` no filtra antes de descartar muestras.** Lo que haya por encima de la nueva frecuencia de Nyquist se pliega sobre las frecuencias bajas (aliasing).

Con los valores por defecto (10.000 → 1.000 Hz, factor exacto 10) no hay corrimiento, pero sí falta el antialias.

**Qué hacer.** Usar la densidad efectiva (`fs_original / factor`) para los ejes o rechazar densidades que no dividan, y filtrar antes de submuestrear (por ejemplo con `scipy.signal.decimate`). Afecta al resultado numérico, así que conviene decidirlo con el nº 2.

---

## 19. Una tarea que lanza `SystemExit` bloquea la cola del orquestador ⬜ ABIERTO

**Gravedad: baja.** Verificado ejecutándolo, pero no ocurre con las funciones actuales.

**Qué pasa.** El hilo del orquestador atrapa `Exception`. `SystemExit` hereda de `BaseException`, no de `Exception`, así que se escapa: la tarea no emite ninguna señal, el servicio la sigue dando por corriendo para siempre y **ninguna tarea posterior arranca**. Prueba: una tarea que hace `raise SystemExit(3)` seguida de otra normal; a los 3 s no hubo ninguna señal, `has_active_tasks()` seguía en verdadero y la segunda tarea seguía en cola.

**Qué hacer.** Atrapar `BaseException` en `_Worker.run` y emitir `failed`. Es una línea.

---

## Cómo agrupar esto en trabajo real

**Frente de correctitud científica** *(el más urgente, y no es del orquestador)*
- nº 2 — el wavelet contra MATLAB
- nº 3 — la columna 0 de `psd_average`
- nº 17 — las franjas de precisión de PyWavelets
- nº 18 — el submuestreo inexacto y sin antialias

Son cuestiones de si los números que entrega la herramienta son correctos. Merecen su propio frente y conversación con la directora. Los nº 2, 17 y 18 conviene decidirlos juntos, porque los tres cambian el escalograma.

**Lo que absorben las fases del orquestador**
- nº 8 y nº 15 → Fase 3 (migrar `artifact_remove`)
- nº 9 → el widget de progreso con Cancelar, trabajo de interfaz en paralelo con la Fase 3
- nº 7 → decisión pendiente sobre qué servicios pasan por el Kernel
- nº 19 → una línea en el `TaskService`
- ~~nº 4~~, ~~nº 14~~ → ya resueltos

**Deuda técnica suelta** *(cada una es de horas, no de días)*
- ~~nº 5 — rama muerta al cerrar~~ (resuelto)
- nº 6 — `load_mat` inalcanzable
- nº 10 — el bucle de `_build_lut`

**Huecos de instrumentación** *(sin esto no se puede demostrar el trabajo)*
- nº 11 — medir memoria en los benchmarks
- nº 12 — probar con un archivo grande de verdad

**Sin clasificar**
- nº 13 — el error del menú contextual
