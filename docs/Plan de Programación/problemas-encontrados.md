# Problemas encontrados por el camino

*Hallazgos que no estaban en el plan y aparecieron al medir e implementar*

---

## Para qué sirve este documento

El plan del orquestador tiene un alcance definido. Pero medir el código de verdad y tocarlo destapa cosas que nadie fue a buscar. Este documento las registra para que **no se pierdan ni se mezclen** con el trabajo del orquestador.

Todo lo que está acá fue **verificado directamente contra el código o ejecutando pruebas**, no inferido. Cada entrada dice cómo se comprobó.

Ninguno de estos problemas lo causaron los cambios de la Fase 1. Los que podían confundirse con eso se verificaron explícitamente.

**Última actualización:** 19 de septiembre de 2026, al cerrar la Fase 1.

---

## Resumen

| # | Problema | Gravedad | Estado |
|---|---|---|---|
| 1 | 6 archivos de prueba con imports obsoletos | Alta | ✅ **Arreglado** |
| 2 | El wavelet no coincide con MATLAB | **Alta** | ⬜ Abierto |
| 3 | `psd_average`: baja correlación en la columna 0 | Media | ⬜ Abierto |
| 4 | Hilo que queda vivo al cambiar de pestaña | Media | ⬜ Lo resuelve la Fase 3 |
| 5 | `Kernel.get_all_plugins()` no existe: rama muerta al cerrar | Baja | ⬜ Abierto |
| 6 | `load_mat()` inalcanzable desde la interfaz | Media | ⬜ Abierto |
| 7 | Tres servicios sin registrar en el Kernel | Media | ⬜ Lo toca la Fase 2 |
| 8 | Señal `progress` declarada y nunca emitida | Baja | ⬜ Lo resuelve la Fase 3 |
| 9 | El spinner es modal e indeterminado | Media | ⬜ Lo toca la Fase 2 |
| 10 | `_build_lut` sigue siendo un bucle de Python | Baja | ⬜ Abierto |
| 11 | La suite de benchmarks no mide memoria | Media | ⬜ Abierto |
| 12 | `load_edf` cuadruplica la memoria del archivo | Media | ⬜ Abierto |
| 13 | Error del menú contextual durante los benchmarks | Baja | ⬜ Sin investigar |

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

## 4. Hilo que queda vivo al cambiar de pestaña ⬜ LO RESUELVE LA FASE 3

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

## 5. `Kernel.get_all_plugins()` no existe: rama muerta al cerrar ⬜ ABIERTO

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

---

## 9. El spinner es modal e indeterminado ⬜ LO TOCA LA FASE 2

**Dónde.** `core/utils/plugin_alerts.py:40-63`.

Dos limitaciones, las dos deliberadas en su momento pero problemáticas ahora:

- **`setModal(True)`** (línea 46): bloquea toda la aplicación mientras está visible. Aunque el cálculo corra en otro hilo, el usuario no puede hacer nada más. Es lo contrario de lo que busca el orquestador.
- **`bar.setRange(0, 0)`** (línea 63): barra siempre en modo indeterminado. Nunca muestra un porcentaje, aunque el worker sepa perfectamente en qué trial va.

**Y no hay botón de cancelar en ninguna parte.** Una búsqueda de "cancel" en todo `plugins/` no devuelve nada.

**Por qué importa.** El orquestador puede implementar la cancelación entera por dentro, pero si la interfaz no tiene desde dónde dispararla, el usuario no la va a poder usar. Hace falta un widget de progreso **no modal, determinado y con botón de cancelar**. Es un frente de trabajo de interfaz, no de núcleo.

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

## Cómo agrupar esto en trabajo real

**Frente de correctitud científica** *(el más urgente, y no es del orquestador)*
- nº 2 — el wavelet contra MATLAB
- nº 3 — la columna 0 de `psd_average`

Son cuestiones de si los números que entrega la herramienta son correctos. Merecen su propio frente y conversación con la directora.

**Lo que absorben las fases del orquestador**
- nº 4 y nº 8 → Fase 3
- nº 7 y nº 9 → Fase 2

**Deuda técnica suelta** *(cada una es de horas, no de días)*
- nº 5 — rama muerta al cerrar
- nº 6 — `load_mat` inalcanzable
- nº 10 — el bucle de `_build_lut`

**Huecos de instrumentación** *(sin esto no se puede demostrar el trabajo)*
- nº 11 — medir memoria en los benchmarks
- nº 12 — probar con un archivo grande de verdad

**Sin clasificar**
- nº 13 — el error del menú contextual
