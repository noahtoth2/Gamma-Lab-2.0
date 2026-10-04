# Resultados de la Fase 3

*Migrar al orquestador los dos plugins que ya usaban hilos*

> **Estado: fase completa en lo que es de código.** Ningún plugin crea ya hilos propios: todo el trabajo en segundo plano pasa por el `TaskService`. Queda abierto un único criterio, el widget de progreso con botón Cancelar (nº 9 de [`problemas-encontrados.md`](problemas-encontrados.md)), que es trabajo de interfaz.

**Fecha:** 30 de septiembre de 2026. Mismo equipo y versiones que las fases anteriores.

---

## Qué pedía la fase

El plan la describía como *"la jugada de menor riesgo"*: validar el orquestador contra código que ya funcionaba antes de usarlo en código nuevo (PAC). Tenía tres pasos:

| Paso | Estado | Cuándo |
|---|---|---|
| 3.1 `wavelet_average` al orquestador | ✅ | 29 de septiembre |
| 3.2 `artifact_remove` al orquestador | ✅ | 30 de septiembre (este informe) |
| 3.3 Cancelar al salir de la sección | ✅ | 29 de septiembre, en `MainWindow` |

Antes de empezar el paso 3.2 se corrigió un fallo del propio orquestador que podía cerrar la aplicación al terminar una tarea ([`resultados-fase-2.md`](resultados-fase-2.md)).

---

## 3.1 y 3.3, en resumen

Ya estaban hechos y verificados al empezar esta sesión; se registran aquí para que la fase quede completa en un solo documento.

- **`wavelet_average`.** Ya no tiene `WaveletWorker` ni `_cleanup_worker()`. Su cálculo es la función pura `wavelet_promedio` en `wavelet_average/compute.py`, el plugin hace `submit()`, y el avance por trial llega a la barra de estado. Su resultado es **idéntico bit a bit** al de Gamma Lab 1.0 ([`resultados-fase-1.md`](resultados-fase-1.md)).
- **Cancelar al salir.** No se hizo en `IPlugin.stop()`, como decía el plan, sino en `MainWindow.clear_plugin_area`, que cancela las tareas del plugin antes de llamar a su `stop()`. El efecto es el mismo: ningún plugin tiene que acordarse de cancelar. El cierre de la aplicación usa `has_active_tasks()` para el aviso de «Cálculo en curso».

---

## 3.2 — `artifact_remove`

### El problema que había que resolver

El plan decía *"lo mismo con `_ApplyWorker`"*: cambiar su `QThread` por un `submit()`. No alcanzaba, porque su hilo no solo calculaba: la función `apply_modification_to_all_valid` hacía todo dentro del hilo secundario, incluido **escribir** en los datos compartidos.

1. Leía los trials activos del `SignalDataset`.
2. Calculaba la versión modificada.
3. **Escribía** las columnas en el `TrialDataset` base, invalidaba cachés internas y emitía el evento `trials_generated`.

El paso 3 contradice la regla de escritura única de la Fase 2 (R54): mientras escribía, cualquier plugin que leyera esos trials desde la interfaz podía verlos a medio modificar. Y su hilo no se veía al cerrar la aplicación, porque `MainWindow` buscaba un atributo `worker` y el plugin lo guardaba en `_apply_thread`.

### La solución: tres pasos, en tres lugares

| Paso | Función | Dónde corre | Cuánto tarda (60 trials × 30.501 muestras) |
|---|---|---|---:|
| 1. Leer | `preparar_modificacion` (`artifact_logic.py`) | Hilo de la interfaz | ~5 ms |
| 2. Calcular | `calcular_modificacion` (`compute.py`, nuevo) | Orquestador | 30-50 ms borrar · 170-410 ms interpolar |
| 3. Escribir | `escribir_modificacion` (`artifact_logic.py`) | Hilo de la interfaz, en el slot de `finished` | 15-60 ms |

- **Leer** ubica los trials activos y el `TrialDataset` base, arma el mapa de columnas (activos → originales, saltando los descartados) y **copia** los datos. El cálculo trabaja siempre sobre esa copia.
- **Calcular** es una función pura, como la de `wavelet_average`: recibe arreglos de NumPy y devuelve arreglos de NumPy, sin Kernel, `DataStore` ni widgets. Revisa la cancelación entre trial y trial y reporta el avance.
- **Escribir** hace lo que antes hacía el hilo al final: escribe las columnas, invalida la caché de trials activos, marca los trials modificados y emite `trials_generated`, pero ahora desde el hilo de la interfaz.

`apply_modification_to_all_valid` se conserva: son los tres pasos seguidos, sin orquestador. Sirve como referencia en las pruebas y para quien necesite la versión síncrona.

### Tres decisiones que conviene conocer

**Antes de escribir se comprueba que los datos sigan siendo los mismos.** Entre la lectura y la escritura pasa el tiempo del cálculo. Si en ese rato cambió la señal activa, el `TrialDataset` base o los trials descartados, el mapa de columnas ya no vale y escribir podría pisar columnas equivocadas. En ese caso no se escribe nada y se avisa: *"Los trials cambiaron mientras se calculaba la modificación; no se aplicó ningún cambio. Vuelve a aplicarla."* Antes no se comprobaba.

**No se puede lanzar un segundo «Apply» mientras hay uno en curso.** El botón se deshabilitaba, pero un evento de datos a mitad del cálculo recargaba la vista y lo volvía a habilitar. Un segundo «Apply» habría calculado sobre los datos de antes del primero y, al escribir, habría borrado la primera modificación. Ahora el botón queda deshabilitado mientras haya una tarea, y además el plugin rechaza el segundo pedido aunque el botón se habilitara.

**Salir de la sección a mitad de una modificación la cancela, y no se escribe nada.** Es la regla de cancelar al salir, igual que en `wavelet_average`. La barra de estado lo avisa: *"La modificación se canceló; no se aplicó ningún cambio."* Antes el hilo seguía y escribía igual. Como el cálculo dura menos de medio segundo con el archivo de prueba, es difícil que pase; si pasa, los datos quedan exactamente como estaban.

### Lo demás que cambió en el plugin

- **Se fueron `_ApplyWorker`, el `QThread` y el `moveToThread`**, con la señal `progress` que nunca se emitía (nº 8). El avance ahora es real: `ctx.progress` por trial al interpolar, que llega a la barra de estado.
- **Las cuatro líneas que rehabilitaban los botones**, repetidas en `_on_apply_finished` y `_on_apply_error`, quedaron en un solo lugar (`_set_apply_busy`).
- **Tras un error, la vista se vuelve a dibujar.** Antes el gráfico quedaba en blanco.
- **Mensajes en español:** validaciones, errores de datos, avisos de resultado y errores del cálculo. Un punto no numérico ahora dice *"El punto A debe ser un número (se recibió «abc»)."* en vez del error de Python en inglés.
- **Cada manejador ignora las señales de una tarea que ya no es la vigente**, con el mismo patrón que `wavelet_average` (`functools.partial` + comparación con el handle vigente).

---

## Verificación

### El resultado numérico no cambió

Antes de modificar nada se corrió el código anterior (tomado de git) en 11 escenarios, cada uno sobre una copia nueva de la señal real. Después se corrieron los mismos escenarios con el código nuevo:

| Escenario | Resultado |
|---|---|
| Cortar desde el inicio | Idéntico |
| Borrar un intervalo, y el mismo con A > B | Idéntico |
| Interpolar un intervalo | Idéntico |
| Interpolar y borrar con trials descartados (3, 10, 25 · 0, 59) | Idéntico: los descartados no se tocan |
| Intervalo de una sola muestra, y cortar antes del inicio | Idéntico: no modifica nada |
| Trials generados en el segundo canal | Idéntico al migrar: fallaba igual (nº 20). Después se corrigió aparte; ver abajo |
| Modo desconocido | Idéntico: mismo tipo de error |
| Tres modificaciones seguidas sobre la misma señal | Idéntico |

«Idéntico» quiere decir todo a la vez:
- los trials resultantes bit a bit, incluidos los NaN;
- el valor devuelto y el tipo de error;
- la lista de trials marcados como modificados;
- los trials activos que ve el resto de la aplicación;
- los eventos emitidos.

### El plugin, de punta a punta

Una prueba funcional con el plugin real, el `TaskService` real y la señal real (solo el dibujo de VTK sustituido, porque sin pantalla no hay OpenGL). Pasaron **23 de 23** comprobaciones:

- en los tres modos del selector, trials idénticos bit a bit al código anterior, controles bloqueados durante el cálculo y liberados al terminar, y aviso en español;
- validaciones (punto vacío, no numérico, A = B, sin señal activa): aviso en español y no se encola nada;
- un segundo «Apply» durante el cálculo: rechazado, aunque un evento haya recargado la vista;
- cancelar a mitad, como al cambiar de sección: trials intactos, ningún evento, controles de vuelta y aviso en la barra de estado;
- descartar un trial a mitad del cálculo: no se escribe y se avisa;
- el cálculo falla: aviso en español, trials intactos y controles de vuelta;
- cerrar la aplicación a mitad: `MainWindow` detecta el cálculo y, tras cancelar, no queda nada corriendo ni se escribe nada.

### Pruebas nuevas en el repositorio

`test/services_test/test_artifact_remove_orquestador.py`, 6 pruebas:

| Prueba | Qué comprueba |
|---|---|
| `por_el_orquestador_da_lo_mismo_que_sin_el` | Leer + calcular en el `TaskService` + escribir da los mismos trials que la versión síncrona, con descartes |
| `el_calculo_no_toca_los_datos_compartidos` | El cálculo recibe una copia y, aunque termine, los trials no cambian hasta `escribir_modificacion` |
| `no_escribe_si_los_trials_cambiaron_mientras_calculaba` | Si se descarta un trial entre leer y escribir, no se escribe |
| `cancelar_no_escribe_nada` | Una tarea cancelada emite solo `cancelled` y los trials quedan intactos |
| `funciona_con_trials_de_otro_canal` | Con trials del segundo canal, la modificación se aplica a ese canal (corrección nº 20) |
| `ningun_plugin_crea_hilos_propios` | Recorre `plugins/` buscando `QThread`, `moveToThread` o `threading.Thread`. Protege la regla de esta fase para lo que venga, empezando por PAC |

`test/ui_test/` (nueva carpeta), las pruebas de **interfaz** de los dos plugins migrados:

| Archivo | Qué es |
|---|---|
| `test_plugins_con_orquestador.py` | 2 pruebas, una por plugin. Cada una corre su archivo de escenarios **en un proceso aparte** y falla si falla cualquier escenario, si Qt aborta o si hay una excepción en un slot |
| `escenarios_wavelet_average.py` | 15 escenarios: botón bloqueado y liberado, Clear a mitad, cancelar a mitad, fallo de un trial con su número, cerrar el proyecto a mitad, recalcular después, resultado tardío sin interfaz y relanzar mientras calcula |
| `escenarios_artifact_remove.py` | 22 escenarios: los de la prueba funcional de arriba más la cola compartida (esperar detrás de otro plugin, y salir de la sección mientras espera) |

**Por qué en un proceso aparte.** Estas pruebas necesitan una `QApplication` con widgets. El resto de la suite crea `QCoreApplication`, y Qt no permite reemplazarla dentro del mismo proceso. Además, si algo hiciera abortar a Qt, solo falla esta prueba y no toda la sesión de pytest.

> **Un detalle de estas pruebas.** Cada escenario crea su propio plugin, y la prueba los conserva a todos hasta el final. La primera versión no lo hacía: el recolector de basura de Python vaciaba un plugin descartado y Qt todavía le mandaba un evento de ocultar a su widget, lo que hacía fallar el filtro de visibilidad del plugin. Con el recolector desactivado no pasaba, lo que confirmó la causa. En la aplicación no puede ocurrir, porque cada plugin vive toda la sesión.

### Sin regresiones

```
5 failed, 109 passed, 25 deselected
```

Son las 100 de antes de la fase, las 6 nuevas de `artifact_remove`, la del nº 19 en `test_task_service.py` y las 2 de interfaz. Los 5 fallos son las mismas comparaciones con MATLAB heredadas de Gamma Lab 1.0. Además, la aplicación real arranca con los 17 plugins, registra `Remove Artifact` y se cierra limpia incluso con un cálculo en curso.

---

## Revisión posterior (30 de septiembre de 2026)

Después de cerrar la fase se revisó otra vez todo lo que la rodea, con el orquestador ya corregido:

- **Wavelet Average (3.1):** la prueba funcional volvió a pasar completa (14 de 14). Hoy es `escenarios_wavelet_average.py`.
- **La cola compartida:** una modificación de `artifact_remove` que espera detrás de la tarea de otro plugin se aplica igual al terminar aquella. Si el usuario sale de la sección mientras espera, se descarta al instante y la otra tarea sigue. Estos dos casos no se habían probado.
- **Cada camino que destruye la interfaz de un plugin** (cerrar el proyecto, abrir otro, salir de la aplicación) cancela primero sus tareas. Se revisó en `MainWindow`.

No apareció ningún error de la fase. Aparecieron dos cosas que ya existían y quedaron registradas en [`problemas-encontrados.md`](problemas-encontrados.md):

- **nº 21, gravedad alta:** las modificaciones de `artifact_remove` no se guardan en el proyecto, y el plugin no marca el proyecto como modificado. Al reabrirlo, los trials vuelven a estar sin modificar. Hay que elegir entre guardar la receta de las modificaciones o guardar los datos.
- **nº 22, limpieza:** `MainWindow` todavía busca los hilos viejos de los plugins (`worker`, `_cleanup_worker`), que ya ningún plugin tiene.

---

## Dos errores que ya existían, corregidos al cerrar la fase

Durante la fase se dejaron idénticos, para que la migración se pudiera verificar contra el código anterior bit a bit. Se corrigieron después, cada uno con su prueba:

**El canal de los trials (nº 20).** `artifact_logic` y el plugin buscaban el canal en `sd.trials_dataset`, un atributo que `SignalDataset` no tiene: el campo real es privado. El error se tragaba y siempre se usaba el primer canal de la señal, así que con trials de otro canal «Apply» fallaba con *"No se encontró el conjunto de trials original"*. Ahora usan la API pública `sd.get_all_trials_datasets()`. Al repetir los 11 escenarios, los otros 10 siguen idénticos bit a bit y este ahora modifica los 60 trials del canal `IN 7`.

**`SystemExit` dentro de una tarea (nº 19).** Es del orquestador, no del plugin. `_Worker.run` atrapaba `Exception`, y `SystemExit` hereda de `BaseException`: la tarea no emitía ninguna señal y la cola quedaba bloqueada para siempre. Ahora atrapa `BaseException` y la tarea emite `failed`.

## Lo que NO se cambió

No se tocaron el dibujo con VTK, la navegación entre trials ni la interfaz del plugin.

---

## Criterios de salida

- [x] Ya no queda ningún `QThread` ni `moveToThread` fuera de `core/services/task_service.py` → verificado, y ahora lo vigila `ningun_plugin_crea_hilos_propios`.
- [x] El resultado numérico de los dos plugins es idéntico al de antes de migrar → `wavelet_average` bit a bit contra 1.0; `artifact_remove` bit a bit contra el código anterior en 11 escenarios.
- [x] Cambiar de sección con un cálculo corriendo ya no deja hilos vivos → `test_cancelacion_al_cambiar_seccion.py` y `cancelar_no_escribe_nada`.
- [~] La barra de progreso muestra el avance real por trial → llega como texto a la barra de estado en los dos plugins; falta el widget con porcentaje y botón Cancelar (nº 9).
- [x] Cerrar la aplicación a mitad de una modificación de `artifact_remove` muestra el aviso de «Cálculo en curso» y no deja el hilo huérfano.

---

## Apéndice: qué código cambió

| Archivo | Cambio |
|---|---|
| `plugins/preprocessing/prepare/artifact_remove/compute.py` | **Nuevo.** `calcular_modificacion`, pura, con cancelación y avance |
| `plugins/preprocessing/prepare/artifact_remove/artifact_logic.py` | Partido en `preparar_modificacion` y `escribir_modificacion`; `apply_modification_to_all_valid` queda como los tres pasos seguidos. Mensajes en español. El canal se toma con `get_all_trials_datasets()` (nº 20) |
| `plugins/preprocessing/prepare/artifact_remove/artifact_remove_plugin.py` | Sin `_ApplyWorker` ni `QThread`: lee, hace `submit()` y escribe en el slot de `finished`. Guarda contra un segundo «Apply», manejadores de progreso, error y cancelación, y controles en un solo lugar. El canal, igual que en `artifact_logic` (nº 20) |
| `test/services_test/test_artifact_remove_orquestador.py` | **Nuevo.** 6 pruebas |
| `core/services/task_service.py` | Una línea: `_Worker.run` atrapa `BaseException` (nº 19) |
| `test/services_test/test_task_service.py` | Una prueba nueva: `systemexit_en_la_tarea_no_bloquea_la_cola` |
| `test/ui_test/test_plugins_con_orquestador.py` | **Nuevo.** 2 pruebas de interfaz, cada una en un proceso aparte |
| `test/ui_test/escenarios_wavelet_average.py` | **Nuevo.** 15 escenarios de Wavelet Average |
| `test/ui_test/escenarios_artifact_remove.py` | **Nuevo.** 22 escenarios de Remove Artifact |

No se tocaron `main.py` ni otros plugins, y no hay dependencias nuevas.

---

## Lo que sigue

- **Decidir cómo guardar las modificaciones de artefactos en el proyecto** (nº 21). Es pérdida de trabajo del usuario, así que conviene antes de agregar funciones nuevas.
- **El widget de progreso con botón Cancelar** (nº 9). Es lo único que falta para cerrar del todo la fase, y es trabajo de interfaz: el orquestador ya reporta el avance y ya sabe cancelar.
- **Fase 4:** extender el orquestador a los plugins síncronos que pasan de 100 ms. Con el archivo de prueba, hoy solo el wavelet individual (~190 ms); `open_signal` hay que medirlo con un archivo grande de verdad.
- **Fase 5:** PAC nace ya orquestado, con su cálculo en un `compute.py`. La prueba `ningun_plugin_crea_hilos_propios` avisará si alguien le pone un hilo propio.
