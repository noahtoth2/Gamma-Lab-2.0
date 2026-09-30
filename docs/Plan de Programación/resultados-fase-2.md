# Resultados de la Fase 2

*El orquestador mínimo*

> **Estado: fase completa.** El servicio existe, está registrado en el arranque, y los cuatro criterios de salida se cumplieron con pruebas automatizadas.
>
> **Corrección (30 de septiembre de 2026):** una revisión con pruebas de estrés encontró que el servicio podía **cerrar la aplicación entera** al terminar una tarea. Ya está corregido y tiene su prueba. Detalle en [La corrección del 30 de septiembre](#la-corrección-del-30-de-septiembre-el-hilo-se-soltaba-antes-de-tiempo).

---

## Qué se construyó

Un servicio nuevo, `core/services/task_service.py`, que recibe funciones, las ejecuta fuera del hilo de la interfaz, las encola para que corra una a la vez, reporta progreso y permite cancelarlas.

**Fecha:** 19 de septiembre de 2026. Mismo equipo y versiones que las fases anteriores.

### Alcance deliberadamente recortado

El documento de diseño describe más de lo que se construyó. Esto quedó **fuera** a propósito, según lo acordado en el plan:

| Fuera de la v1 | Por qué |
|---|---|
| Segunda cola para archivos | `load_abf` mide 60-79 ms. El problema todavía no existe |
| Estimación de memoria y rechazo previo | El acumulador de la Fase 1 dejó el caso casi sin ocurrencias |
| Paralelismo dentro de una tarea | Viable (el GIL se suelta), pero el techo medido es 1,3-1,8× |
| Prioridades en la cola | No hay ningún caso que las pida |

Menos piezas, menos que depurar, y cada una se puede agregar después sin cambiar el contrato.

---

## El contrato

Tres piezas, y un plugin solo ve las dos primeras.

```python
handle = tasks.submit(compute_fft, owner="fft", X=X, fs=fs)
handle.finished.connect(self._dibujar)
```

### `TaskHandle` — lo que devuelve `submit()`

| Señal | Cuándo |
|---|---|
| `progress(int, str)` | Porcentaje (-1 si no se puede estimar) y mensaje |
| `finished(object)` | El resultado |
| `failed(str)` | Mensaje de error |
| `cancelled()` | Se canceló o se descartó |

Más un `cancel()`. Se emite **exactamente una** de las tres señales terminales por tarea.

### `TaskService` — el servicio

| Método | Para qué |
|---|---|
| `submit(fn, *, owner, **kwargs)` | Encola y devuelve el handle. No bloquea |
| `cancel_all_from(owner)` | Cancela todo de un plugin, corriendo o en cola |
| `has_active_tasks()` | Si queda algo vivo. Para el cierre de la aplicación |
| `pending_count()` | Cuántas esperan |

### `TaskContext` — solo si la tarea lo pide

Una función que declare un parámetro `ctx` lo recibe; una que no, se llama tal cual. Así una función pura **no necesita saber que el orquestador existe**, que es justo lo que pedía el documento de diseño al definir la Tarea como agnóstica.

Después de cancelar, `ctx.progress` ya no envía nada, para que el plugin no muestre avances de una tarea que ya se canceló.

```python
def calculo_largo(ctx, datos):
    for i, x in enumerate(datos):
        if ctx.cancelled:          # cancelacion cooperativa
            return None
        ctx.progress(i * 100 // len(datos), f"elemento {i}")
        ...
```

---

## Las decisiones de diseño, y por qué

### Un hilo por tarea, no un pool

Arrancar un hilo cuesta microsegundos, así que un pool permanente no compra velocidad. Y compra un problema: **si una tarea se cuelga, bloquea la cola para siempre**. Con un hilo por tarea, una tarea colgada se deja atrás y la siguiente arranca igual.

El servicio **no crea ningún hilo al arrancar**: se queda vivo y ocioso, como pedía el diseño.

Cada hilo se libera recién cuando Qt avisa que salió de verdad (su señal `QThread.finished`), no cuando llega el resultado. Es la corrección del 30 de septiembre, explicada más abajo.

### La escritura única sale gratis

Qt entrega las señales entre hilos **en el hilo del receptor**. Como el `TaskHandle` se crea en el hilo de interfaz, el slot conectado a `finished` corre siempre ahí.

Si se respeta la regla *"al `DataStore` solo se escribe desde el slot de `finished`"*, entonces todas las escrituras ocurren en el mismo hilo: **el R54 se cumple sin un solo cerrojo ni mutex**. Y como una tarea cancelada nunca emite `finished`, el *"descarta el resultado parcial"* del CU-014 no necesita código que lo implemente.

Verificado en la prueba de integración: el slot recibe el resultado en el hilo principal.

### La salida de emergencia para el R46

El R46 pide liberar el hilo *"incluso si el cómputo no termina por sí solo"*. Con hilos eso no se puede prometer literalmente: Python no ofrece forma segura de matar un hilo desde afuera.

Lo que hace el servicio:

1. Marca la cancelación y **devuelve el control de inmediato** (no bloquea la interfaz esperando).
2. Programa una revisión a los 2 segundos (eran 3 hasta el 27 de septiembre de 2026; ver el criterio 3).
3. Si para entonces la tarea no se enteró, **se desliga**: emite `cancelled`, libera la cola y arranca la siguiente. El hilo puede seguir vivo un rato, pero lo que devuelva se descarta.

Desde el punto de vista del usuario la interfaz se rehabilita, que es lo que el requisito busca. Conviene ajustar el texto del R46 en el SAD para que describa esto en vez de prometer una terminación forzada que la tecnología no da.

### Regla de reemplazo

Un `submit()` nuevo del mismo `owner` **descarta las que ese owner tenga en cola**, porque su resultado ya es obsoleto. No toca la que esté corriendo: para eso está `handle.cancel()` explícito.

---

## Verificación

### 17 pruebas automatizadas, todas en verde

> Eran 14 al cerrar la fase (12 unitarias y 2 de integración). Desde entonces se sumaron las 2 de `test_cancelacion_al_cambiar_seccion.py` (29 de septiembre) y la de estrés `muchas_tareas_cortas_no_tumban_la_aplicacion` (30 de septiembre).

`test/services_test/test_task_service.py` — 13 pruebas unitarias:

| Prueba | Qué comprueba |
|---|---|
| `resultado_llega_por_finished` | El camino feliz |
| `corre_fuera_del_hilo_principal` | El identificador de hilo dentro de la tarea es distinto al de la interfaz |
| `excepcion_emite_failed_y_no_tumba_nada` | Escenario de Calidad 3, y el servicio queda usable después |
| `progreso_se_reporta` | 20 reportes de progreso llegan, todos entre 0 y 100 |
| `cancelar_tarea_cooperativa` | Emite `cancelled` y **nunca** `finished` |
| `cancelar_encolada_no_la_ejecuta` | La alternativa 1a del CU-014: descartar sin arrancar |
| `una_sola_a_la_vez` | Con 4 tareas simultáneas, el pico de concurrencia es **1**, y en orden |
| `reemplazo_descarta_las_encoladas_del_mismo_owner` | Y no toca la que ya corría |
| `cancel_all_from_limpia_un_owner` | Cancela corriendo + encolada de un owner, no toca las ajenas |
| `tarea_terca_se_desliga_y_devuelve_la_interfaz` | R46: el desligue |
| `has_active_tasks` | El gancho para el cierre de la aplicación |
| `sin_ctx_no_se_inyecta_nada` | Una función pura se llama tal cual |
| `muchas_tareas_cortas_no_tumban_la_aplicacion` | 10.000 tareas seguidas en un proceso aparte: terminan todas y no queda ningún hilo sin liberar (30 de septiembre) |

`test/services_test/test_task_service_integracion.py` — 2 pruebas de punta a punta con el kernel y el plugin reales.

`test/services_test/test_cancelacion_al_cambiar_seccion.py` — 2 pruebas: cambiar de sección cancela las tareas del plugin y no toca las de otros.

```
12 passed in 3.09s      (al cerrar la fase, 19 de septiembre)
 2 passed in 5.20s
17 passed               (30 de septiembre, las tres suites juntas)
```

### Criterio 1 — sin costo en el arranque

```
registro de servicios SIN TaskService: 0.0043 ms
registro de servicios CON TaskService: 0.0069 ms
hilos vivos tras crearlo: 1 (solo el principal)
```

**+2,6 microsegundos.** Y un solo hilo: confirma que no levanta ningún pool, los crea por tarea y bajo demanda.

### Criterio 2 — un plugin real, de punta a punta

La prueba de integración monta el kernel igual que `main.py`, obtiene el servicio con `kernel.get_service("TaskService")` —como haría cualquier plugin— y manda el `compute_wavelet` **real** sobre el archivo ABF real.

| | |
|---|---|
| Forma del resultado | (998, 3051) |
| Contra el cálculo síncrono | `np.array_equal` → **idéntico** |
| Hilo donde llega `finished` | **el principal** |

Que el resultado sea idéntico al síncrono es lo que de verdad importa de cara a la Fase 3: pasar por el orquestador no cambia nada del cálculo.

### Criterio 3 — cancelar devuelve la interfaz rápido

La prueba usa una tarea que **ni siquiera acepta `ctx`**, o sea que no tiene forma de enterarse de la cancelación — el peor caso posible. Con el umbral de desligue en 200 ms:

| | |
|---|---|
| Tiempo hasta recuperar la interfaz | **< 1 s** (criterio: < 3 s) |
| ¿Emitió `finished`? | No. El resultado de la tarea desligada se descarta |
| ¿La cola siguió? | Sí: la siguiente tarea corrió sin esperar a la terca |

> **Corrección (27 de septiembre de 2026).** Ese "< 1 s" es de la prueba, que usa un umbral de 200 ms. En la aplicación el umbral era de 3.000 ms, y con ese valor una tarea terca liberaba la interfaz a los **3,000 s**: justo en el límite, no por debajo. Se bajó a **2.000 ms** (`DEFAULT_CANCEL_TIMEOUT_MS`), y ahora la libera a los **2,000 s**.
>
> Wavelet Average sí revisa la cancelación en cada trial, así que se detiene sola al terminar el trial en curso. En este equipo un trial tardó entre 0,27 s y 2,1 s según el estado de la CPU (la misma variación aparece sin hilos), y la cancelación midió entre 0,20 s y 2,0 s. Si un trial tarda más de 2 s, la tarea se desliga a los 2,0 s y termina sola al acabar ese trial; su resultado se descarta. En todos los casos la interfaz vuelve en unos 2 s como máximo.

### Criterio 4 — una excepción no tumba nada

```
ValueError: fallo a proposito   ->   failed("fallo a proposito")
```

Desde el 27 de septiembre de 2026, `failed` lleva solo el mensaje, sin el nombre de la excepción en inglés, porque ese texto llega tal cual al aviso que ve el usuario. Si la excepción no trae mensaje, lleva su tipo (por ejemplo `"ValueError"`).

Y justo después, otra tarea en el mismo servicio se ejecuta con normalidad.

### Además: la interfaz sigue respondiendo durante el cálculo

La segunda prueba de integración cuenta las vueltas del bucle de eventos mientras corre el wavelet. Si el cálculo bloqueara el hilo principal, el contador se quedaría cerca de cero. Da muy por encima del umbral, o sea que el bucle de eventos sigue girando: es la evidencia del **R55**.

---

## Sin regresiones

Conjunto completo de pruebas (sin los benchmarks):

```
5 failed, 91 passed, 25 deselected in 43.51s
```

Los 5 fallos son exactamente los mismos de validación contra MATLAB que ya estaban documentados **antes** de esta fase (4 del wavelet, 1 de `psd_average`). No apareció ninguno nuevo.

Con la corrección del 30 de septiembre:

```
5 failed, 100 passed, 25 deselected
```

Son los mismos 5 fallos. La prueba número 100 es la de estrés nueva.

---

## La corrección del 30 de septiembre: el hilo se soltaba antes de tiempo

### Qué pasaba

Cada tarea corre en un `QThread`. Cuando la función termina, el hilo emite la señal interna `done` desde **dentro** de `run()`, y el servicio la recibe en el hilo de interfaz, en `_on_worker_done`. Hasta el 30 de septiembre, ese mismo slot soltaba el hilo:

```python
task.worker.deleteLater()
task.worker = None      # la última referencia de Python al QThread
```

Al perder la última referencia, PyQt destruye el objeto de C++ en ese mismo instante; el `deleteLater()` no llega a actuar. Pero cuando llega `done`, al hilo todavía le falta volver de `run()` y cerrarse. Son microsegundos. Si el hilo de interfaz ganaba esa carrera, Qt se encontraba destruyendo un hilo que seguía corriendo y **abortaba el proceso entero**:

```
QThread: Destroyed while thread is still running
```

Sin traceback, sin aviso, sin la opción de guardar: la aplicación se cerraba. En Windows ese mensaje ni siquiera sale por consola, salvo con `QT_FORCE_STDERR_LOGGING=1`. Los hilos desligados del R46 tenían el mismo problema cuando llegaba su resultado tardío.

### Por qué no lo detectaron las pruebas

La carrera ocurre una vez por tarea, en el instante en que termina. Las pruebas unitarias lanzan entre 1 y 4 tareas cada una: pocas oportunidades. Con volumen apareció enseguida:

| 3.000 tareas cortas seguidas | Corridas | Se cayó |
|---|---:|---:|
| Antes de la corrección | 20 | **13** |
| Después | 20 | **0** |

En uso normal el riesgo por tarea es pequeño, pero cuando ocurre se pierde lo que no estaba guardado. Y la Fase 3 va a mandar más trabajo por el orquestador.

### El cambio

Tres puntos, todos en `core/services/task_service.py`:

```python
# 1. El servicio guarda cada hilo vivo
self._threads = set()

# 2. Al arrancar una tarea: se guarda el hilo y se conecta a la señal propia
#    de Qt ANTES de start()
self._threads.add(worker)
worker.done.connect(self._on_worker_done)
worker.finished.connect(self._release_thread)
worker.start()

def _release_thread(self) -> None:
    worker = self.sender()
    self._threads.discard(worker)
    worker.deleteLater()

# 3. _on_worker_done ya no suelta el hilo: solo entrega el resultado
```

**Por qué esto lo resuelve.** `QThread.finished` la emite el propio Qt cuando el hilo ya salió de `run()` y está en su etapa de cierre, que es donde el destructor de `QThread` sabe esperar. Liberar a partir de ahí es seguro.

**Por qué la conexión va antes de `start()`.** Una tarea muy corta puede terminar antes de que se alcance a conectar después, y su hilo quedaría retenido para siempre. Pasó en el primer prototipo de esta corrección.

**Qué no cambió.** El contrato con los plugins es el mismo (`submit`, las cuatro señales, `cancel`), y el resultado llega por el mismo camino. Ningún plugin se tocó.

### Cómo se verificó

| Comprobación | Resultado |
|---|---|
| Prueba nueva `muchas_tareas_cortas_no_tumban_la_aplicacion` (10.000 tareas en un proceso aparte) con el código **anterior**, tomado de git | Falla 10 de 10 veces: la prueba sí detecta el problema |
| La misma prueba con el código corregido | Pasa 10 de 10 |
| 20 corridas de 3.000 tareas con el código del repositorio | 0 caídas |
| 150 tareas que ignoran la cancelación (desligue del R46) | Todas emiten una sola señal final y no queda ningún hilo retenido |
| 1.500 operaciones al azar (`submit`, `cancel`, `cancel_all_from`, reemplazo) con otro hilo acaparando el GIL | Cada una de las 838 tareas emitió **una sola** señal final |
| Durante un promedio real de 20 trials, un temporizador de 10 ms en el hilo de interfaz | Hueco máximo 34 ms, p99 19 ms (R55: ≤ 300 ms) |
| Cerrar la aplicación a mitad de un Wavelet Average, en 10 momentos distintos | Salida limpia las 10 veces |
| Suite completa sin benchmarks | 100 pasan; fallan las mismas 5 comparaciones con MATLAB |

> **Pendiente, de gravedad baja:** si una tarea lanzara `SystemExit` (hereda de `BaseException`, no de `Exception`), el hilo no emitiría ninguna señal y la cola quedaría bloqueada. Se verificó ejecutándolo; no ocurre con las funciones actuales. Nº 19 de [`problemas-encontrados.md`](problemas-encontrados.md).

---

## Apéndice: qué código se cambió

### Archivos nuevos

| Archivo | Líneas (al 27 de septiembre de 2026) | Qué es |
|---|---:|---|
| `core/services/task_service.py` | 207 (218 tras la corrección del 30 de septiembre) | El servicio |
| `test/services_test/test_task_service.py` | 235 (273 con la prueba de estrés) | 12 pruebas unitarias (13 desde el 30 de septiembre) |
| `test/services_test/test_task_service_integracion.py` | 129 | 2 pruebas de punta a punta |

### Archivo modificado: `main.py`

Dos líneas, más un comentario que explica el orden:

```diff
 from core.services.data_store import DataStore
 from core.services.fileio_service import FileIOService
+from core.services.task_service import TaskService
```

```diff
     # 1) Core services
+    # Van antes del descubrimiento de plugins: register_plugin() llama a
+    # initialize(kernel), y desde ahi un plugin ya puede pedir cualquier
+    # servicio. Si estas lineas se mueven despues, recibiria None.
     kernel.register_service("DataStore", DataStore())
     kernel.register_service("FileIO", FileIOService())
+    kernel.register_service("TaskService", TaskService())
```

El orden importa: `register_plugin()` llama a `initialize(kernel)`, y desde ese momento un plugin ya podría pedir el servicio. Por eso va antes del descubrimiento de plugins.

### Lo que NO se cambió

- **Ningún plugin.** Esta fase construye la herramienta; usarla es la Fase 3.
- **El Kernel.** El servicio se registra con el mecanismo que ya existía; no hizo falta tocarlo.
- **`requirements.txt`.** Cero dependencias nuevas: todo sale de PyQt5, que ya estaba.

---

## Lo que queda anotado para las fases siguientes

**El widget de progreso no existe todavía.** El servicio reporta progreso y acepta cancelación, pero `PluginAlerts.show_spinner()` sigue siendo modal, indeterminado y sin botón de cancelar (problema nº 9 del documento de hallazgos). Sin ese widget, el usuario no tiene desde dónde disparar la cancelación que el orquestador ya sabe atender. **Es trabajo de interfaz y puede ir en paralelo con la Fase 3.**

**`IPlugin.stop()` todavía no llama a `cancel_all_from()`.** La conexión está diseñada y el servicio ya la soporta, pero conectarla es parte de la Fase 3 — y es lo que arreglará el hilo colgado del problema nº 4.

> **Resuelto el 29 de septiembre de 2026, por otro camino:** la cancelación la hace `MainWindow.clear_plugin_area` al cambiar de sección, antes del `stop()` del plugin (nº 4).

**El cierre de la aplicación no consulta `has_active_tasks()`.** El método existe para eso; falta usarlo en `_on_app_about_to_quit`, donde hoy hay además una rama muerta (problema nº 5).

> **Resuelto el 29 de septiembre de 2026:** el aviso de «Cálculo en curso» al cerrar consulta `has_active_tasks()`, `_on_app_about_to_quit` cancela las tareas de todos los plugins, y la rama muerta ya no existe (nº 5).

---

## Estado

| Paso | Estado |
|---|---|
| 2.1 Una sola cola | ✅ |
| 2.2 El contrato (`submit` / 4 señales / `cancel`) | ✅ |
| 2.3 Escritura única, reemplazo, cancelación cooperativa | ✅ |
| 2.4 Salida de emergencia del R46 | ✅ |
| 2.5 Registrado en `main.py` | ✅ |
| Corrección del hilo que se soltaba antes de tiempo | ✅ 30 de septiembre |

Sigue la **Fase 3**. `wavelet_average` ya está migrado y la cancelación al cambiar de sección ya funciona; falta migrar `artifact_remove`, separando su lectura, su cálculo y su escritura (nº 15 de [`problemas-encontrados.md`](problemas-encontrados.md)).
