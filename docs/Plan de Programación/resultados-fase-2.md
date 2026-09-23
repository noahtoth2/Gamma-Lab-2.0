# Resultados de la Fase 2

*El orquestador mínimo*

> **Estado: fase completa.** El servicio existe, está registrado en el arranque, y los cuatro criterios de salida se cumplieron con pruebas automatizadas.

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

### La escritura única sale gratis

Qt entrega las señales entre hilos **en el hilo del receptor**. Como el `TaskHandle` se crea en el hilo de interfaz, el slot conectado a `finished` corre siempre ahí.

Si se respeta la regla *"al `DataStore` solo se escribe desde el slot de `finished`"*, entonces todas las escrituras ocurren en el mismo hilo: **el R54 se cumple sin un solo cerrojo ni mutex**. Y como una tarea cancelada nunca emite `finished`, el *"descarta el resultado parcial"* del CU-014 no necesita código que lo implemente.

Verificado en la prueba de integración: el slot recibe el resultado en el hilo principal.

### La salida de emergencia para el R46

El R46 pide liberar el hilo *"incluso si el cómputo no termina por sí solo"*. Con hilos eso no se puede prometer literalmente: Python no ofrece forma segura de matar un hilo desde afuera.

Lo que hace el servicio:

1. Marca la cancelación y **devuelve el control de inmediato** (no bloquea la interfaz esperando).
2. Programa una revisión a los 3 segundos.
3. Si para entonces la tarea no se enteró, **se desliga**: emite `cancelled`, libera la cola y arranca la siguiente. El hilo puede seguir vivo un rato, pero lo que devuelva se descarta.

Desde el punto de vista del usuario la interfaz se rehabilita, que es lo que el requisito busca. Conviene ajustar el texto del R46 en el SAD para que describa esto en vez de prometer una terminación forzada que la tecnología no da.

### Regla de reemplazo

Un `submit()` nuevo del mismo `owner` **descarta las que ese owner tenga en cola**, porque su resultado ya es obsoleto. No toca la que esté corriendo: para eso está `handle.cancel()` explícito.

---

## Verificación

### 14 pruebas automatizadas, todas en verde

`test/services_test/test_task_service.py` — 12 pruebas unitarias:

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

`test/services_test/test_task_service_integracion.py` — 2 pruebas de punta a punta con el kernel y el plugin reales.

```
12 passed in 3.09s
 2 passed in 5.20s
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

### Criterio 4 — una excepción no tumba nada

```
ValueError: fallo a proposito   ->   failed("ValueError: fallo a proposito")
```

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

---

## Apéndice: qué código se cambió

### Archivos nuevos

| Archivo | Líneas | Qué es |
|---|---:|---|
| `core/services/task_service.py` | 290 | El servicio |
| `test/services_test/test_task_service.py` | 250 | 12 pruebas unitarias |
| `test/services_test/test_task_service_integracion.py` | 150 | 2 pruebas de punta a punta |

### Archivo modificado: `main.py`

Dos líneas, más un comentario que explica el orden:

```diff
 from core.services.data_store import DataStore
 from core.services.fileio_service import FileIOService
+from core.services.task_service import TaskService
```

```diff
     # 1) Core services
+    # Registered before discovering plugins: register_plugin() calls
+    # initialize(kernel), and from that point a plugin may ask for any service.
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

**El cierre de la aplicación no consulta `has_active_tasks()`.** El método existe para eso; falta usarlo en `_on_app_about_to_quit`, donde hoy hay además una rama muerta (problema nº 5).

---

## Estado

| Paso | Estado |
|---|---|
| 2.1 Una sola cola | ✅ |
| 2.2 El contrato (`submit` / 4 señales / `cancel`) | ✅ |
| 2.3 Escritura única, reemplazo, cancelación cooperativa | ✅ |
| 2.4 Salida de emergencia del R46 | ✅ |
| 2.5 Registrado en `main.py` | ✅ |

Sigue la **Fase 3**: migrar `wavelet_average` y `artifact_remove` al orquestador, y conectar `IPlugin.stop()`.
