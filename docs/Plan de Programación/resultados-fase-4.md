# Resultados de la Fase 4 — Extender el orquestador a los plugins síncronos

*1 de octubre de 2026.*

> **Estado: dos de los tres criterios de salida cumplidos.** El tercero —medir con un archivo de 1-2 GB— no se pudo cerrar porque no hay ningún archivo de ese tamaño en el equipo. Lo que sí se midió deja la decisión fundamentada; el detalle está en la sección 4.
>
> Suite completa al terminar: **148 pasan, 5 fallan**, y los cinco fallos son las discrepancias con MATLAB ya conocidas y documentadas en [`problemas-encontrados.md`](problemas-encontrados.md). No hay ninguno nuevo.

---

## 1. Qué se migró y qué no

El criterio del plan era migrar solo lo que pasa de ~100 ms. Se respetó:

| Plugin | Medición | Decisión | Estado |
|---|---|---|---|
| `wavelet` (individual) | ~133 ms de cálculo + ~81 ms de dibujo | Migrar | ✅ **Migrado al orquestador** |
| `average` | una línea de NumPy, < 1 ms | Extraer a función pura, sin encolar | ✅ **Extraído** |
| `erp` | el cálculo vivía dentro del dibujo | Separar cálculo de dibujo | ✅ **Separado** |
| `open_signal` | 82,5 ms con el archivo de prueba | Medir primero con un archivo grande | ✅ **Migrado** el 2 de octubre, por el SAD y no por el tiempo (ver abajo) |
| `fft`, `fft_average`, `psd`, `psd_average`, `relative_psd` | 3,8 – 11 ms | No migrar | Sin tocar |
| `filter` | 43 ms | No por ahora | Sin tocar |
| `trials` | 18,6 ms | No por ahora | Sin tocar |

---

## 2. Paso 4.1 — El wavelet individual

### El cálculo se movió a `core/`, no a la carpeta del plugin

El plan decía «mover cada `_compute_*` a un `compute.py`» de la carpeta del plugin. Al abrirlo apareció un problema que el plan no contemplaba: el plugin individual tenía **su propia copia** del cálculo, duplicada respecto al `compute.py` del promedio.

| Función | En el plugin individual | En `wavelet_average/compute.py` |
|---|---:|---:|
| `compute_wavelet` | 30 líneas | 31 líneas |
| `normalize_tf` | 22 líneas | 26 líneas |
| `_scale_log` / `scale_log` | 27 líneas | 33 líneas |

Eran **~79 líneas funcionalmente idénticas en dos archivos**. La prueba de que eso ya costaba trabajo: el cambio a `method='fft'` de ese mismo día tuvo que aplicarse en los dos sitios por separado.

Seguir el plan al pie de la letra habría dejado la duplicación en pie, y darle al plugin individual un `compute.py` propio la habría consolidado. Que un plugin importara del otro tampoco servía: **ningún plugin del proyecto importa de otro**, y romper eso ataría dos plugins que deben poder existir por separado (R77).

La salida fue `core/filters/wavelet.py`, que es donde el proyecto ya guarda el cálculo puro compartido —`core/filters/trials.py` lo usan dos plugins y dos servicios—. Queda así:

```
core/filters/wavelet.py                        VOCES_POR_OCTAVA, eje_frecuencias,
                                               compute_wavelet, normalize_tf, scale_log
plugins/.../wavelet/compute.py                 importa de core + wavelet_individual(ctx, ...)
plugins/.../wavelet_average/compute.py         importa de core + wavelet_promedio(ctx, ...)
```

El reparto es: la **matemática** en `core`, y la **orquestación de cada plugin** —el acumulador por trials en uno, el camino de un solo trial en el otro— en su propio `compute.py`. Los dos plugins conservan métodos delegadores de una línea (`compute_wavelet`, `normalize_tf`, `_scale_log`) porque las pruebas heredan de ellos y los llaman.

> **Detalle que condicionó el diseño.** `escenarios_wavelet_average.py` sustituye `cw.compute_wavelet` para simular un trial que falla. Para que siga funcionando, los `compute.py` importan **los nombres sueltos** (`from core.filters.wavelet import compute_wavelet`) y las funciones de alto nivel lo llaman sin cualificar, de modo que se resuelve por el espacio del módulo. Con `import wavelet as x` y `x.compute_wavelet(...)` la sustitución habría dejado de tener efecto y la prueba habría pasado sin probar nada.

### El botón se partió en dos

`on_create_wavelet` quedó con la misma forma que el plugin del promedio desde la Fase 3: lee la señal y los parámetros, valida, y a partir de ahí `submit()`. El dibujo pasó al slot de `finished`.

```python
handle = tasks.submit(cw.wavelet_individual, owner=self.meta.id, ...)
handle.progress.connect(partial(self._on_wavelet_progress, handle))
handle.finished.connect(partial(self._on_wavelet_done, handle))
handle.failed.connect(partial(self._on_wavelet_failed, handle))
handle.cancelled.connect(partial(self._on_wavelet_cancelled, handle))
```

Se añadieron `_terminar_calculo()` y los cuatro slots, y la guarda de `_on_clear_clicked` que ya tenía el promedio: con un cálculo en curso avisa y no toca los parámetros, porque si no, lo que se dibuja no correspondería a lo que muestra el panel.

Sobre la cancelación: la CWT entra de un salto en el código C de PyWavelets y no vuelve hasta terminar, así que `wavelet_individual` solo puede atender la cancelación en los extremos. Está comentado en el código para que no parezca un olvido. En la práctica da igual, porque son ~133 ms.

### Verificación

La migración no cambió ni un bit. Huella de las pruebas contra MATLAB, antes y después:

| | Antes de migrar | Después |
|---|---|---|
| Individual, correlación mínima | 0,3857 | **0,3857** |
| Individual, `passed` | 58999 / 3.044.898 | **58999 / 3.044.898** |
| Individual, peor punto | (row=993, col=2046), app 0,594818 | **igual** |
| Promedio, correlación mínima | 0,5212 | **0,5212** |
| Promedio, `passed` | 62786 / 3.044.898 | **62786 / 3.044.898** |

---

## 3. Un hueco de cobertura que había que tapar

`test_wavelet_plugin.py` nunca llamaba al `on_create_wavelet` real: usa una clase `WaveletDouble` que **replica** esa lógica de forma sincrónica («*Synchronous logic equivalent to on_create_wavelet*»). Al volverse asíncrono el plugin, el camino nuevo —los cuatro slots, el bloqueo del botón, la cancelación, los resultados tardíos— quedaba sin una sola prueba.

Se añadió `test/ui_test/escenarios_wavelet.py`, calcado del que la Fase 3 hizo para el promedio: **17 escenarios**, todos en verde. Los dos que más importan:

| Escenario | Qué comprueba | Resultado |
|---|---|---|
| **A2** | Que el cálculo no corre en el hilo de la interfaz | corre en `Dummy-1`, no en `MainThread` |
| **H** | Que el resultado por el orquestador es idéntico al del cálculo directo | `max|dif| = 0,000e+00` |

El resto cubre el botón bloqueado mientras calcula, Clear a mitad, cancelación como al cambiar de sección, fallo del cálculo con el aviso en español, cerrar el proyecto a mitad, resultados tardíos sin interfaz, y relanzar mientras calcula sin que la tarea vieja altere a la nueva.

---

## 4. `open_signal`: lo que se pudo medir y lo que no

**No hay ningún archivo de 1-2 GB en el equipo.** Los tres ABF disponibles —en `test/data/` y en la carpeta del MATLAB— pesan 6,87 MB cada uno. El criterio tal como está escrito no se puede cerrar sin un registro grande de verdad.

Lo que sí se midió, con `load_abf` y el archivo de prueba (mediana de 5 cargas, caché del sistema caliente):

| Medida | Valor |
|---|---|
| Archivo en disco | 6,87 MB |
| Señal cargada | (2, 1.800.000) en `float32` |
| Arreglos en memoria | 27,5 MB — **4,00× el tamaño en disco** |
| Tiempo de carga | **82,5 ms** → 12,0 ms por MB |
| Crecimiento del working set | **+54,9 MB** — el doble de los arreglos |
| Pico del proceso | 127,6 MB |

Dos cosas salen de aquí, y la segunda es más grave que la primera:

1. **El tiempo sí justifica el orquestador.** A 12,0 ms por MB, un archivo de 1 GB tarda ~12 s solo en el procesamiento, sin contar la lectura en frío del disco. Está doce veces por encima del segundo de R04, así que la decisión del plan («Sí, migrar») se confirma.

2. **La memoria es el problema real, y el orquestador no lo arregla.** Los arreglos ocupan 4× el archivo —el ABF guarda enteros de 16 bits que se expanden a `float32`, y el eje de tiempo pesa como un canal entero—, y encima el working set crece el **doble** que los arreglos, lo que delata una copia transitoria. Extrapolado:

   | Archivo | Carga | Arreglos | Working set estimado |
   |---|---:|---:|---:|
   | 0,5 GB | ~6 s | ~2 GB | ~4 GB |
   | 1,0 GB | ~12 s | ~4 GB | ~8 GB |
   | 2,0 GB | ~25 s | ~8 GB | ~16 GB |

   Un archivo de 1 GB necesitaría del orden de 8 GB de memoria. Eso es un muro, no una cuestión de latencia: pasarlo por una cola no lo evita.

**Conclusión sobre la segunda cola:** la pregunta que el criterio quería responder era si hace falta una segunda cola para no bloquear los cálculos mientras se carga un archivo. La medición dice que antes de eso hay que resolver la expansión de memoria —el problema nº 12 ya registra algo parecido para `load_edf`—, porque con archivos de ese tamaño la aplicación no llega a la cola: se queda sin RAM. La extrapolación es lineal y por tanto solo indicativa; conviene rehacerla con un archivo real antes de decidir.

### Actualización (2 de octubre de 2026): el escenario del SAD dice más que un número

Al revisar el Escenario de Calidad 2 completo apareció que el umbral de los 8 segundos es **una** de sus afirmaciones, y las demás **sí** se pueden verificar con los archivos que hay:

| Lo que afirma el escenario | ¿Depende del archivo grande? | Estado |
|---|---|---|
| «el umbral base de carga es ≤ 2 s para el archivo típico» | No | ✅ **Pasa**: 82,5 ms, 24× de margen |
| «Visualización inicial en menos de 8 s para el caso de estrés (1-2 GB)» | **Sí** | ⬜ No verificable |
| «sin duplicación innecesaria de datos» | No | ✅ **Corregido**: de 2,01× a 1,01× (nº 12) |
| «la lectura corre en el servicio de tareas, fuera del hilo de la UI» | No | ✅ **Corregido**: `open_signal` migrado |

**Por qué se migró `open_signal` aunque mida 82,5 ms.** La decisión de esta fase fue migrar solo lo que pasara de 100 ms, y con ese criterio quedó fuera. Pero el escenario del SAD exige la lectura en el servicio de tareas **sin condicionarlo al tiempo**, así que era un requisito trazado que el criterio de los 100 ms no cubría. La migración sigue el patrón de la Fase 3: el diálogo de archivos, los avisos y el registro en el `DataStore` se quedan en el hilo de la interfaz; solo la lectura se encola, en `plugins/io/open_signal/compute.py` → `cargar_senal`.

Verificado con `test/ui_test/escenarios_open_signal.py`, **11 escenarios**, entre ellos que la lectura corre en `Dummy-1` y no en `MainThread`, que un formato no soportado no encola nada, que un archivo ilegible avisa sin tumbar la aplicación, y que un resultado que llega cuando la interfaz ya no está se descarta sin error.

**Un error de trazabilidad detectado en el SAD, sin corregir.** El escenario declara trazar a NFR-P-03 (R48), NFR-P-14 (R72) y NFR-P-10 (R56), que en el SRS son «cómputo de Wavelet ≤ 10 s», «reutilizar la representación gráfica» y «promedio de trials ≤ 1 s». **Ninguno de los tres habla de cargar archivos.** Queda anotado para corregir en el documento.

---

## 5. `average` y `erp`

Los dos tenían que quedar con el cálculo separado del dibujo aunque no se encolen, y así quedaron.

### `average`

Era literalmente una línea dentro de `_on_calculate_average`. Ahora está en `plugins/analysis/time/average/compute.py` como `promedio_trials(trials)`, con una guarda para el caso de cero trials y otra para una matriz de una sola dimensión, que antes habría reventado con un error de eje. La llamada va envuelta en un aviso en español.

Esta extracción **ya estaba cubierta**: `test_average_plugin.py` llama al `_on_calculate_average` real y compara contra MATLAB.

### `erp`

El cálculo vivía dentro de `_render_heatmap`: el submuestreo a 2.000 muestras, el rango de color por percentiles 2 y 98, y los parámetros del eje de tiempo. Todo eso está ahora en `plugins/analysis/time/erp/compute.py` como `preparar_mapa_calor(t, sel)`.

De paso, los nueve `print` de depuración de ese método —incluido un encabezado `=== DEBUG HEATMAP ===`— pasaron al `_log` del plugin, que es el mecanismo del proyecto.

**Aquí apareció un fallo propio que conviene registrar.** Al extraer el cálculo, `t_end` se quedó sin devolver, y `_render_heatmap` lo usa para fijar el eje horizontal. **La suite completa pasó sin detectarlo**, porque `test_erp_plugin.py` no toca el mapa de calor: la lógica estaba dentro del método de dibujo, y sin pantalla no se puede dibujar. Justamente por eso valía la pena extraerla.

Se añadió `test/plugins_test/test_erp_compute.py` con **13 pruebas**, usando como oráculo el código original copiado literalmente. Cubren la coincidencia con el original en cinco tamaños distintos, el submuestreo y su ausencia, el eje de tiempo, los datos constantes, los NaN totales y parciales, el error con una matriz de una dimensión, y una regresión explícita para el `t_end` que faltaba.

---

## 6. Hallazgo para la lista de problemas

**`erp` se quedó fuera de la vectorización del paso 1.3.** `_render_heatmap` todavía llena la imagen de VTK con un doble bucle de Python:

```python
for j in range(K):
    for i in range(Tn):
        img.SetScalarComponentFromFloat(i, j, 0, 0, X[j, i])
```

Es el mismo patrón que la Fase 1.3 reemplazó en los dos plugins de wavelet, donde se midió **82× más lento** que la versión vectorizada. Con el límite de 2.000 muestras y 60 trials son hasta 120.000 llamadas. El plugin ya importa `numpy_support`, así que el arreglo es el mismo que se aplicó entonces.

No se tocó: está fuera del alcance de esta fase, que era separar cálculo de dibujo. Queda propuesto como entrada nueva.

---

## 7. Criterios de salida

- [x] **Todo lo que pasa de 100 ms va por el orquestador** → el wavelet individual migrado y verificado; el resto de los plugins está por debajo del umbral, salvo `open_signal`, que depende del punto siguiente.
- [x] **`average` y `erp` tienen su cálculo separado del dibujo, aunque no se encolen** → `promedio_trials` y `preparar_mapa_calor`, con 13 pruebas nuevas para el segundo.
- [ ] **Medición con un archivo grande de verdad (1-2 GB) para decidir si hace falta la segunda cola** → **no se pudo**: no existe un archivo así en el equipo. Hay medición y extrapolación fundamentada en la sección 4, y la conclusión provisional es que el cuello de botella es la memoria, no la cola.

---

## 8. Apéndice: qué código cambió

| Archivo | Cambio |
|---|---|
| `core/filters/wavelet.py` | **Nuevo.** El cálculo de wavelet compartido por los dos plugins |
| `plugins/analysis/time_frequency/wavelet/compute.py` | **Nuevo.** `wavelet_individual(ctx, ...)` |
| `plugins/analysis/time_frequency/wavelet/wavelet_plugin.py` | `on_create_wavelet` partido en `submit()` + slot de `finished`; cuatro slots nuevos y `_terminar_calculo()`; los tres métodos de cálculo son ahora delegadores; guarda en `_on_clear_clicked`; se quitaron los imports de `pywt` e `interp1d`, que quedaron sin uso |
| `plugins/analysis/time_frequency/wavelet_average/compute.py` | El cálculo se fue a `core`; conserva `wavelet_promedio` y reexporta los nombres compartidos |
| `plugins/analysis/time/average/compute.py` | **Nuevo.** `promedio_trials` |
| `plugins/analysis/time/average/average_plugin.py` | Usa `promedio_trials`, con aviso en español si falla |
| `plugins/analysis/time/erp/compute.py` | **Nuevo.** `preparar_mapa_calor` |
| `plugins/analysis/time/erp/erp_plugin.py` | `_render_heatmap` usa `preparar_mapa_calor`; los `print` de depuración pasaron a `_log` |
| `test/ui_test/escenarios_wavelet.py` | **Nuevo.** 17 escenarios del wavelet individual |
| `test/ui_test/test_plugins_con_orquestador.py` | Registra los escenarios nuevos |
| `test/plugins_test/test_erp_compute.py` | **Nuevo.** 13 pruebas de `preparar_mapa_calor` |

No se tocaron `main.py`, el `TaskService` ni ningún otro plugin, y no hay dependencias nuevas.

---

## 9. Lo que sigue

- ~~**Vectorizar el llenado de VTK en `erp`**~~ *(sección 6). Hecho el 1 de octubre de 2026: 91,3× más rápido con 60 trials y escalares idénticos (nº 23).*
- **Conseguir un archivo de 1-2 GB** para cerrar el tercer criterio, y de paso revisar la expansión de memoria de `load_abf` (4× en arreglos, 8× en working set).
- ~~**El widget de progreso con botón Cancelar** (nº 9).~~ *Hecho el 1 de octubre de 2026, junto con los nº 21 y nº 23. Sirve para los tres plugins migrados a la vez.*
- **Fase 5: PAC.** El análisis previo está en [`analisis-pac.md`](analisis-pac.md), con dos decisiones pendientes de consultar con la directora.
