# Resultados de la Fase 5 — PAC nace ya orquestado

*12 de octubre de 2026.*

La Fase 5 no pedía migrar nada: pedía que **el primer consumidor nuevo del orquestador naciera bien**, en vez de acabar con su propio `QThread` y dejar tres patrones ad-hoc en el proyecto en vez de dos.

Se cumplió. PAC entró directamente con el patrón de la Fase 3, sin pasar por una versión síncrona intermedia.

---

## Lo que la fase exigía, y cómo quedó

| Exigencia del plan | Estado |
|---|---|
| La lógica como **función pura** en `compute.py`: recibe NumPy, devuelve NumPy, no toca widgets ni `DataStore` | ✅ `plugins/analysis/time_frequency/pac/compute.py` importa solo `numpy`, `scipy` y `core.filters`. **Ni Qt ni VTK** |
| El plugin solo hace `submit()` y dibuja en el slot de `finished` | ✅ Los tres modos se encolan con `tasks.submit(..., owner=self.meta.id)`; las cuatro señales conectadas, cada una con su guarda `if handle is not self._handle` |
| Nada de hilos propios | ✅ Ni `QThread` ni `threading` en el plugin ni en su `compute.py` |

Las tres se comprueban solas: `test/ui_test/escenarios_pac.py` incluye un escenario que anota el nombre del hilo donde corre el cálculo y falla si es `MainThread`.

---

## Por qué hacía falta: las medidas

Sobre el ABF de prueba (`17308005.abf`, 10 kHz) recortado en 20 trials de 3 s, con los parámetros por defecto del panel —fase 3-8 Hz, amplitud 25-500 Hz, remuestreo a 2 kHz—:

| Operación | Tiempo | Umbral de la Fase 4 (100 ms) |
|---|---:|---|
| PAC, un trial | **836 ms** | 8× por encima |
| **PAC Average, 20 trials** | **16 881 ms** | **169× por encima** |
| PAC Psel, 20 trials | **1 684 ms** | 17× por encima |

Los 17 segundos de PAC Average son el argumento más claro que ha dado el proyecto a favor del orquestador. Y son con **20** trials: el archivo real da 60, así que la cifra realista ronda los **50 segundos**. Sin la cola, la ventana se queda congelada ese tiempo entero, sin barra de avance y sin forma de cancelar.

Para comparar, lo que motivó la Fase 2 fue el wavelet individual con sus 216 ms.

---

## Lo que se construyó

Tres operaciones, no una. El combo del plugin ofrece **PAC**, **PAC Average** y **PAC Psel**, y cada una va por la cola.

| Modo | Función | Origen en MATLAB |
|---|---|---|
| PAC | `pac_un_trial` | `f_Phase_PAC` |
| PAC Average | `pac_promedio` | `f_Phase_PAC_Average` |
| PAC Psel | `pac_psel` | `f_Phase_PAC_Pdetect` (522 líneas) |

Más el **índice de modulación**, que es un plugin aparte porque es otro algoritmo —barre una rejilla con filtros IIR y no usa wavelet—, y también nació orquestado.

Piezas de cálculo compartidas que salieron de aquí:

- `core/filters/iir.py` — réplica de `f_GetIIRFilter` y `f_IIRBiFilter`. Está en `core` porque lo usan **dos** plugins (`pac` y `modulation_index`); el cálculo propio de cada uno se quedó en su carpeta.
- `morse_tf` y `gabor_tf` en el `compute.py` de PAC — las dos transformadas, portadas desde cero porque ninguna librería de Python las trae.

---

## Avance y cancelación, que es la mitad del punto

El `ctx` que inyecta el orquestador se usa de verdad, no de adorno:

- **PAC Average** informa `Trial n/N`; con 60 trials y 50 segundos, sin eso la espera sería ciega.
- **PAC Psel** informa `Ciclo n/N` —en una corrida real con tus datos fueron **127 ciclos**— y comprueba `ctx.cancelled` en cada vuelta, así que cancelar responde en el tiempo de un ciclo y no al final.
- **MI** informa en dos tramos, `Fase n/N` y `Amplitud n/178`, porque son dos bucles de filtros seguidos.

---

## Qué lo respalda

| | |
|---|---|
| Pruebas de núcleo de PAC | **116** en `test/plugins_test/test_pac_core.py` |
| Escenarios de interfaz de PAC | **40** en `test/ui_test/escenarios_pac.py` |
| Pruebas de núcleo de MI | **27** |
| Escenarios de interfaz de MI | **34** |
| Suite completa | **348 pasan**, 5 fallan (los de wavelet y `psd_average` contra MATLAB, anteriores e independientes) |

Los escenarios cubren lo que el orquestador tiene que garantizar y no solo que el número salga bien: que el cálculo corra fuera del hilo de interfaz, que cancelar deje todo en reposo sin dibujar, que un resultado que llega cuando ya no hay interfaz se descarte sin excepción, y que pulsar *Clear* a mitad avise en vez de tocar los parámetros.

---

## Lo que esta fase destapó y no era suyo

Dos cosas aparecieron al construir PAC y se arreglaron fuera de alcance, porque afectaban a todo el programa:

**El temporizador de VTK cerraba la aplicación.** Cada plugin crea su propio `QVTKRenderWindowInteractor` —son quince— y al cambiar de pestaña `Kernel.stop_plugins()` solo llama a `Disable()`: el `QTimer` seguía entrando en VTK sobre un widget oculto. Tres violaciones de acceso capturadas con `PYTHONFAULTHANDLER=1`. Es el nº 24 de `problemas-encontrados.md`; el arreglo está en `core/utils/vtk_temporizador.py`.

**El z-score normalizaba por N en vez de N−1.** `std(m, [], 2)` de MATLAB usa N−1 por omisión. Un 0,5 % en todo el mapa de PAC y PAC Average. Es el tipo de error que solo sale al comparar contra la referencia, y por eso importa la Fase 7 del plan de PAC.

---

## Estado del plan del orquestador

| Fase | Estado |
|---|---|
| 0 — Medir | ✅ |
| 1 — Las tres optimizaciones | ✅ |
| 2 — Orquestador mínimo | ✅ |
| 3 — Migrar los dos plugins con hilos | ✅ |
| 4 — Extender a los síncronos | ✅ dos de tres criterios; falta la medición con un archivo de 1-2 GB, que **no existe en el equipo** |
| **5 — PAC nace ya orquestado** | ✅ **cerrada aquí** |
| 6 — Memoria y paralelismo interno | ⬜ **fuera de la v1**, por decisión de la Fase 0: el techo con dos hilos es 1,3-1,8× |

**El plan está terminado salvo esa medición.** La Fase 6 no está pendiente: está descartada para esta versión con una medida que lo justifica.
