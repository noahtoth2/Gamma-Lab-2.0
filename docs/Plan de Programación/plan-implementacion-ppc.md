# Plan de implementación de PPC

*24 de octubre de 2026. Fases para llevar el botón **PPC** del panel *Inter Channel* de `BOARD_FTD_PACC` a Gamma Lab 2.0.*

**Alcance: solo el cálculo.** La interfaz la construye otra persona del equipo. Este documento define, además de las fases, el **contrato de salida** contra el que se puede programar el front desde el primer día, antes de que el cálculo esté terminado.

> ## Criterio de este plan, y en qué se diferencia del de PAC
>
> El plan de PAC decía *«paridad con MATLAB»*: reproducir sus funciones, sus parámetros y sus salidas, señalando los defectos sin corregirlos en silencio.
>
> **Aquí no.** En PPC el defecto no es de precisión: por debajo de unos 50 Hz el mapa **no contiene información sobre los datos**, y replicarlo produciría una figura espectacular y vacía. Así que se aplica el criterio que ya se acordó para PAC Psel —*si MATLAB tiene problemas que no tiene sentido replicar porque quedaría mal el análisis, no se replican*— pero esta vez como norma general del módulo.
>
> Lo que **sí** se mantiene es **qué se entrega**: si MATLAB dibuja un mapa de coherencia frecuencia-logarítmica contra tiempo, Gamma Lab dibuja ese mismo mapa. Mismos ejes, misma clase de figura, mismos parámetros en el panel. Lo que cambian son los números de dentro, y cada cambio queda escrito aquí con la medida que lo justifica.

---

## 1. Qué hay en MATLAB

| Pieza | Dónde |
|---|---|
| Botón | `BOARD_FTD_PACC.mlapp`, panel *Inter Channel*, `PPCButtonPushed` |
| Cálculo | `f_phase_coherence.m`, 58 líneas |
| Transformada | `f_GaborAWTransformMatlab` con `ps_Phases = 1` |
| Dibujo | `f_ImageMatrix` con `s_NonEquAxis = 1`, `jet`, `clim [0 0.5]` |

Valores por omisión del panel:

| Campo | Valor | Qué llega a la función |
|---|---|---|
| `Resample_inter_Ch` | 2000 | `srt = round(10000/2000) = 5` → srate efectivo **2000 Hz** |
| `F min` / `F max` | 0,1 / 500 | banda del mapa |
| `wd` | 0,05 | ventana de **101 muestras** (50 ms) |
| — | — | `ps_FreqSeg = round(500−0,1) = 500` filas, paso 1,0018 Hz |
| — | — | `ps_StDevCycles = 1`, escrito a mano en el `.m` |

Y lo que calcula, en una línea:

```
Coh(f) = | Σ_trials Σ_t e^{i·Δφ(f,t)} | / (N_t · N_trials)
```

Eso es **PLV** (phase-locking value). El **PPC** de Vinck et al. (2010), que es como se llama el botón, es otra cosa:

```
PPC = (2/(N(N−1))) · Σ_{j<k} cos(θ_j−θ_k) = (N·PLV² − 1)/(N − 1)
```

El PPC existe precisamente porque el PLV está sesgado por el número de muestras.

---

## 2. Lo que se midió, y que obliga a corregir

Réplica de `f_phase_coherence` en Python con los valores por defecto. Todo lo de esta sección es **medido**, no deducido.

### 2.1 Por debajo de ~50 Hz el resultado no mira los datos

Con `ps_StDevCycles = 1` la gaussiana tiene σ = 1/f **segundos**, y la ventana dura 0,05 s. A 20 Hz σ ya es la ventana entera. Cuando eso pasa, la gaussiana en frecuencia (σ_f = f/2π) es más estrecha que el espaciado de bins de la FFT de 101 muestras, que es **19,80 Hz**: deja pasar **un solo bin**, la salida es un tono puro `A·e^{i(ω₀t+φ)}` en los dos canales, al restar la rampa se cancela y Δφ queda **constante por construcción** → PLV = 1.

Medido con **ruido blanco independiente** en los dos canales:

| f (Hz) | pendiente de la fase | 2πf esperado | desviación de Δφ | coherencia |
|---:|---:|---:|---:|---:|
| 5,11 | −0,0 | 32,1 | 0,0° | **1,0000** |
| 20,14 | 124,4 | 126,5 | 0,0° | **1,0000** |
| 40,17 | 248,4 | 252,4 | 0,7° | **0,9999** |
| 80,24 | 383,8 | 504,2 | 93,0° | 0,2676 |
| 500,00 | 3187,1 | 3141,6 | 133,0° | 0,0676 |

124,4 rad/s es exactamente el espaciado de bins (2π·2000/101): a 20 Hz el wavelet entrega literalmente el bin 1, y a 40 Hz el bin 2.

**25 de las 500 filas salen clavadas en 1,000000 exacto** (de 0,1 a 25,15 Hz). Cuatro parejas de señales radicalmente distintas dan lo mismo:

| f (Hz) | ruido independiente | canales idénticos | 40 Hz desfase 90° | 40 Hz **contra ruido** |
|---:|---:|---:|---:|---:|
| 5,11 | 1,000000 | 1,000000 | 1,000000 | 1,000000 |
| 20,14 | 1,000000 | 1,000000 | 1,000000 | 1,000000 |
| 40,17 | 0,999899 | 1,000000 | 1,000000 | **0,999930** |
| 200,46 | 0,437096 | 1,000000 | 0,828779 | 0,256574 |

Una senoidal de 40 Hz contra ruido blanco puro da **0,99993** de «coherencia» a 40 Hz. Y como la figura se dibuja con `clim [0 0.5]`, toda esa mitad inferior sale saturada en el color máximo.

### 2.2 Por debajo de ~9 Hz no hay ni fase

La gaussiana cae entera dentro del bin 0 —la componente continua—, el coeficiente sale **real** (se midió |Im/Re| = 8,6·10⁻¹⁶, el epsilon de la máquina) y `angle()` solo puede devolver 0 o 180°. Ahí no se mide una fase: se mide el signo de la media de la ventana.

Con 20 trials de ruido el valor a 1,1 Hz sale **0,1000 exacto**, que es `|n₊ − n₋|/20`: sigue contando signos.

### 2.3 El PLV está sesgado

Fases al azar, 4.000 repeticiones:

| N muestras | PLV medio | PPC medio |
|---:|---:|---:|
| 2 | 0,6348 | −0,0040 |
| 10 | 0,2881 | 0,0047 |
| 101 | 0,0864 | −0,0005 |
| 2000 | 0,0198 | −0,0000 |

Sin sincronía ninguna el PLV da 0,63 con 2 muestras y 0,02 con 2.000. El PPC da 0 en los dos casos.

**El sesgo real es peor que la tabla**, porque MATLAB divide por 101 muestras cuando solo una es independiente: usa una N inflada.

### 2.4 Errores de índices y de ventana

Medido sobre 3 s a 2000 Hz (6.000 muestras):

| Defecto | Medida |
|---|---|
| `Coh_Glb = zeros(…, floor(6000/100))` reserva 60 columnas; el bucle da 59 vueltas | **la última columna queda toda en cero** |
| La última muestra analizada es la 5.901 | **99 muestras (50 ms) no entran nunca** |
| `t = linspace(v_Time(1), v_Time(end), size(Coh_Glb,2))` reparte 60 columnas incluida la vacía | el eje de tiempo queda estirado |
| El paso es igual al ancho | **cero solapamiento**, y una FFT por ventana → el wavelet se enrolla en los bordes |

### 2.5 El eje de frecuencias está sobremuestreado

500 filas con paso 1,0018 Hz contra el ancho real del wavelet, σ_f = f/2π:

| f (Hz) | σ_f (Hz) | filas dentro de 1σ |
|---:|---:|---:|
| 10 | 1,59 | 2 |
| 100 | 15,92 | 16 |
| 500 | 79,58 | 79 |

A 500 Hz cada fila repite casi lo mismo que sus 79 vecinas. Y el eje se construye **lineal** y luego se dibuja en `log10`, así que las frecuencias bajas —las rotas— ocupan la mayor parte de la altura.

### 2.6 Dos cosas en el callback del botón Load

No son de `f_phase_coherence`, pero deciden qué recibe:

- **Con «No Stim» marcado el resultado se descarta.** La rama `GF==1` llena `m_Trials1_wt` con `f_Load_GF` y **nunca asigna `app.m_Trials1`**; después el callback hace `f_Remove_art(app.m_Trials1,…)` y reensambla incondicionalmente desde esa variable, sobrescribiendo lo que `f_Load_GF` produjo. El Load principal no tiene ese bloque y sí respeta la rama.
- Pasa `app.m_Trials2_freq` al `f_Select_Trials` del canal **1**. Solo contamina `m_Trials1_freq_sel`, que PPC no usa.

### 2.7 Una sola ventana para toda la banda no funciona

Esto no es un defecto de MATLAB —es una consecuencia de corregir los anteriores— pero decide el diseño, así que va medido igual.

Una vez que la N deja de estar inflada (decisión 2), la ventana tiene que cumplir dos cosas a la vez: ser **larga** para que quepan ciclos de las frecuencias bajas, y **corta** para que el mapa tenga resolución temporal arriba. Con una sola `wd` no se puede. Medido sobre el caso real —trials de **3 s**, **20 trials**, 2000 Hz, `ciclos = 3`:

| f (Hz) | Una ventana fija de 0,5 s | Una ventana por frecuencia |
|---:|---:|---:|
| 2 | **NaN** | N=20, resolución 3000 ms |
| 4 | **NaN** | N=20, resolución 1500 ms |
| 10 | N=20, resolución 500 ms | N=20, resolución 600 ms |
| 50 | N=80, resolución 500 ms | N=20, resolución **120 ms** |
| 100 | N=160, resolución 500 ms | N=20, resolución **60 ms** |
| 500 | N=820, resolución 500 ms | N=20, resolución **12 ms** |

La ventana fija **desperdicia precisión justo donde está la señal**: a 500 Hz da N=820 —un umbral de ruido de 0,0024, absurdamente fino— y a cambio deja la resolución temporal clavada en medio segundo. La ventana por frecuencia coge ese excedente y lo convierte en tiempo: 12 ms en gamma, 40 veces mejor, y además llega hasta 2 Hz en vez de quedarse en 6.

**Por qué N ≈ 20 y no otro número.** El PPC es insesgado a cualquier N, pero su **varianza** no. Medido con 20.000 repeticiones, comparando el ruido contra un acoplamiento moderado (dispersión circular de 1 rad, PPC verdadero ≈ 0,37):

| N | PPC nulo (media ± desv.) | umbral 95 % del ruido | separación con la señal |
|---:|---:|---:|---:|
| 2 | −0,007 ± 0,706 | 0,987 | **−0,62** |
| 5 | −0,001 ± 0,223 | 0,466 | −0,11 |
| 10 | +0,001 ± 0,106 | 0,215 | 0,15 |
| **20** | +0,000 ± 0,052 | **0,103** | **0,26** |
| 40 | +0,000 ± 0,026 | 0,049 | 0,32 |
| 80 | +0,000 ± 0,013 | 0,025 | 0,34 |

20 es la rodilla: la primera N donde un acoplamiento moderado despega del umbral con holgura. Con 2 la desviación es 0,71 y el mapa es ruido puro; con 40 la mejora ya casi no se nota.

---

## 3. Decisiones

Cada fila dice qué hace MATLAB, qué va a hacer Gamma Lab y por qué.

| # | MATLAB | Gamma Lab 2.0 | Motivo |
|---|---|---|---|
| 1 | PLV disfrazado de PPC | **PPC de verdad**, `(N·PLV²−1)/(N−1)` | §2.3. El botón ya se llama así |
| 2 | N = todas las muestras de la ventana | **N = muestras independientes × trials** | §2.1. Contar 101 cuando solo 1 es independiente es de donde sale el sesgo |
| 3 | Devuelve 1 donde no puede medir | **NaN y aviso** | §2.1-2.2. Un 1 se lee como acoplamiento perfecto; un hueco se lee como hueco. Mismo criterio que el Nyquist de MI |
| 4 | Una FFT por ventana | **Una transformada por trial**, y se trocea después | §2.4. Quita el enrollado en los bordes y sale más barato |
| 5 | Sin solapamiento | **Solapamiento configurable, 50 % por omisión** | §2.4 |
| 6 | Última columna en cero, 50 ms sin usar | **Las columnas que se llenan, y la cola cubierta** | §2.4 |
| 7 | Eje de tiempo por `linspace` sobre todo | **El centro real de cada ventana** | §2.4 |
| 8 | 500 filas lineales dibujadas en log | **Eje logarítmico de verdad**, con las filas que σ_f admite | §2.5 |
| 9 | `ps_StDevCycles = 1` a mano | **Parámetro, 3 por omisión** | §2.1. 3 es el valor que la propia cabecera de `f_GaborAWTransformMatlab` documenta como normal |
| 10 | Una ventana `wd` para toda la banda | **Una ventana por frecuencia**, dimensionada para llegar a N ≈ 20 | §2.7. Una sola ventana desperdicia precisión arriba y no llega abajo |
| 11 | `wd = 0,05` es la ventana | **`wd = 0,05` es la ventana *mínima*** | §2.7. El valor del panel sobrevive, reinterpretado como tope a la resolución temporal |
| 12 | No devuelve nada, solo dibuja | **Devuelve un `ResultadoPPC`** | Hace falta para exportar y para que el front dibuje |
| 13 | `clim [0 0.5]` | Lo decide el front | El PPC vive en [−1, 1], no en [0, 1] |

**Lo que no cambia:** la figura sigue siendo un mapa de **frecuencia logarítmica contra tiempo** con barra de color, los parámetros del panel son los mismos seis (resample, F min, F max, wd, y los dos canales), y se añade `ciclos` porque la decisión 9 lo convierte en parámetro.

**Lo que no se arregla aquí:** los dos defectos de §2.6 son del `.mlapp`, no del algoritmo. En Gamma Lab no existen: los trials se generan con el plugin *Trials*, que no tiene esa rama.

---

## 4. El contrato de salida

**Esto es lo primero que se cierra, en la Fase 0, para que la interfaz se pueda escribir en paralelo.** No cambia en las fases siguientes.

```python
@dataclass
class ResultadoPPC:
    """El mapa de consistencia de fase entre dos canales, y sus ejes."""
    mapa: np.ndarray            # (frecuencia, tiempo), float64, valores en [−1, 1]
                                # NaN donde la ventana no da para medir (decisión 3)
    frecuencias: np.ndarray     # eje Y en Hz, DESCENDENTE como en MATLAB
    tiempos: np.ndarray         # eje X en s, rejilla común a todas las filas
    ventanas_s: np.ndarray      # la ventana que usó CADA fila (decisión 10)
    n_muestras: np.ndarray      # N total por fila = independientes × trials; explica cada NaN
    fs_efectiva: float          # la de verdad tras submuestrear, no la pedida
    fs_pedida: float            # la que se escribió en el panel (añadido en la Fase 4)
    n_trials: int
    ventana_min_s: float        # el `wd` del panel, ahora como piso (decisión 11)
    solape: float               # 0,0 a 0,9 — define el paso de la rejilla de tiempo
    ciclos: float               # ps_StDevCycles
    n_objetivo: int             # muestras independientes que se intentó reunir
    filas_sin_resolver: int     # cuántas filas salieron enteras en NaN
    canal_1: str                # nombres, para el título y la exportación
    canal_2: str
```

```python
def ppc_mapa(ctx, trials_1, trials_2, fs_calculado, fs,
             fmin, fmax, wd=0.05, ciclos=3.0, n_freq=None,
             solape=0.5, n_objetivo=20, eje_log=True) -> ResultadoPPC
```

- `trials_1` y `trials_2`: matrices `(muestras, trials)`, los dos canales ya recortados y **alineados**.
- `ctx`: el del orquestador. `ctx.progress(pct, texto)` y `ctx.cancelled`, igual que PAC.
- `wd` es la ventana **mínima**: pone el tope a la resolución temporal y el paso de la rejilla.
- `n_freq=None` elige el número de filas según σ_f (decisión 8); un entero lo fuerza.
- Devuelve `None` si se canceló, como el resto.

Y una función suelta, al lado, que convierte el resultado en frases para mostrar:

```python
def avisos(resultado) -> list[str]
```

Devuelve los textos en español de lo que condiciona la lectura del mapa, o una lista vacía. Es una función y no un método del plugin a propósito: la interfaz no tiene por qué volver a deducir estas condiciones, y así se prueba sin levantar Qt. Los errores **no** salen por aquí: lo que impide calcular lo lanza `ppc_mapa` como `ValueError` antes de empezar.

> **Cambios del contrato después de publicarlo.** Se dijo que no cambiaría, y cambió en una cosa: la Fase 4 añadió el campo `fs_pedida` y la función `avisos`. Las dos son añadidos —nada de lo que ya estaba se movió ni cambió de significado—, pero quede escrito.

**Lo que el front puede dar por seguro desde ya:** `mapa` es `(frecuencia, tiempo)` con las frecuencias **descendentes**, hay NaN y hay que dibujarlos transparentes —ya existe el patrón en `modulation_index_plugin.py`—, y el eje Y ya viene en Hz: el logaritmo lo aplica el dibujo, igual que hace `_grafico_mapa_log` en `pac_plugin.py`. El eje de tiempo es **uno solo** para todas las filas, aunque cada una se haya promediado sobre una ventana distinta; `ventanas_s` está para poder decirlo en el pie de la figura, no para dibujar.

---

## 5. Las fases

### Fase 0 — Cerrar decisiones y contrato ✅ *este documento*

Sin código. Salida: la tabla de decisiones del §3 y el contrato del §4. **A partir de aquí la interfaz se puede empezar.**

---

### Fase 1 — La Gabor pasa a `core/filters/`

Hoy `gabor_tf` vive en `plugins/analysis/time_frequency/pac/compute.py`, y está bien: **solo** la usaba PAC Psel. Con PPC pasa a usarla un segundo plugin, y la regla de la arquitectura es que lo que cruza una frontera de plugin vive en `core/filters/`.

| Qué | Dónde |
|---|---|
| Mover `gabor_tf` y su constante `CICLOS_GABOR` | nuevo `core/filters/gabor.py` |
| Dejar un reexport en `pac/compute.py` | `from core.filters.gabor import CICLOS_GABOR, gabor_tf` |

**El reparto de hilos no se mueve: ya está donde debe.** Vive en `core/utils/parallel.py` (`map_ordenado`, `n_hilos`, `memoria_disponible`) y lo usa `pac_promedio` para repartir **trials**, no frecuencias. PPC lo puede usar igual, trial por trial, sin tocarlo.

**Criterio de cierre:** las 124 pruebas de `test_pac_core.py` pasan **sin tocarlas**. Si hay que editar una, el movimiento cambió algo que no debía.

---

### Fase 2 — Acceso a dos canales

Es el único cambio que PPC necesita fuera de su carpeta, y hay que hacerlo antes que el cálculo.

**El problema.** `SignalDataset.get_active_trials(file_name, channel_name)` **ignora el canal que se le pasa**:

```python
# core/model/signal_dataset.py:137
channel_name = self.__trials_dataset[-1].channel_name
```

La lista `__trials_dataset` **sí** guarda un juego por canal —`add_trial_dataset` reemplaza por `(archivo, canal)`, no borra los demás—, así que generar trials en CA1 y luego en IN 7 deja los dos guardados. Lo que falta es poder pedirlos. La línea de arriba tiene encima un `'''Change in future developments'''`: los autores originales lo dejaron marcado.

| Qué | Dónde |
|---|---|
| Honrar `channel_name` cuando venga dado; seguir tomando el último cuando sea `None` | `core/model/signal_dataset.py` |
| `IPlugin.get_trials_de_canal(canal)` | `core/plugins/interfaces.py` |
| Validar que los dos juegos están alineados | `ppc/compute.py` |

**La validación importa.** Los dos canales tienen que venir del **mismo corte**. Comprobado sobre `17308005.abf` con `stim_channel=1`, umbral 0,7, ventana −0,1 a 0,4 s: cortando el canal 0 y después el canal 1 con los mismos parámetros salen **3 trials de 5.000 muestras en los dos**, con los mismos `onsets`, el mismo `time_rel`, la misma `sampling_rate` y el mismo `t0`/`t1` — y datos distintos, como debe ser. Así que el alineamiento **se puede** conseguir; lo que no hay es nada que obligue al usuario a hacerlo así.

Lo que la Fase 3 tiene que comprobar antes de calcular, en este orden: `trials.shape`, `onsets_s`, `sampling_rate`, `t0` y `t1`. Si algo no coincide, error en español diciendo **qué** no cuadra — no recortar al mínimo en silencio.

**Criterio de cierre:** una prueba que genera trials en dos canales del mismo archivo y recupera los dos por nombre; y otra que comprueba que pedir sin nombre sigue devolviendo el último, para no romper los nueve plugins que ya lo llaman así.

---

### Fase 3 — El núcleo

`plugins/analysis/connectivity/ppc/compute.py`. Subcategoría nueva: `main_window.py` agrupa por subcategoría con un `defaultdict`, así que *Connectivity* aparece sola, sin tocar el núcleo; solo habría que añadirla a `explicit_order` si se quiere fijar su sitio.

El algoritmo, por pasos:

1. **Submuestrear** con `tasa_efectiva(fs_calculado, fs)`, el mismo de PAC y MI, que devuelve la tasa real y no la pedida (problema nº 18).
2. **Elegir la ventana de cada fila** (decisión 10). Se parte de cuántas muestras independientes hace falta pedirle a **cada** trial para reunir `n_objetivo` entre todos:

   ```
   n_ind = ceil(n_objetivo / n_trials)
   w(f)  = clip( 2·ciclos·n_ind / f ,  wd ,  largo del trial )
   ```

   El `2·ciclos/f` son los 2σ que separan dos puntos casi independientes. Con 20 trials `n_ind` vale 1 y la ventana es `6/f` segundos; con 1 trial vale 20 y la ventana crece veinte veces, que es como un solo trial todavía da mapa en gamma.
3. **Transformar cada trial entero una vez** con `gabor_tf(..., magnitudes=False)` — decisión 4. Por tandas de frecuencias para no reservar la matriz completa: 500 filas × 6.000 muestras × 16 B son 48 MB por trial, y por tandas de 32 filas son 3 MB.
4. **Promediar `z = e^{iΔφ}` por filas** con una media móvil del ancho `w(f)` de cada una, muestreada en la rejilla común `tiempos` (paso `wd·(1−solape)`). Es un `cumsum` por fila: no hace falta trocear nada, y por eso la opción B no cuesta más código que la A.
5. **Acumular** sobre trials. Acumulador complejo, como `pac_promedio`: `Σ z` y el conteo, nada más.
6. **PPC** `= (N·PLV² − 1)/(N − 1)` con `PLV = |Σz| / (L(f)·n_trials)` y `N = n_ind·n_trials`, donde `L(f)` son las muestras que caben en `w(f)`. Si `N < 2`, o si `2·ciclos·n_ind/f` no cabe en el trial → **NaN**.

Nota sobre el paso 6: el cociente usa **dos divisores distintos a propósito**. El PLV se divide por todas las muestras promediadas, `L(f)`, porque es la media de todas ellas; la corrección del sesgo usa `N`, las que de verdad son independientes. Confundir las dos es exactamente el error de MATLAB (§2.3).

**Hizo falta ampliar la Gabor.** `gabor_tf` reparte su eje linealmente entre `fmin` y `fmax`, y PPC necesita dos cosas que eso no permite: un eje **logarítmico** (decisión 8) y poder pedir **tandas** de 32 filas (paso 3). Se añadió `gabor_en(sig, fs, frecuencias, …)` en `core/filters/gabor.py`, que transforma sobre un eje dado y usa el arreglo tal como llega. `gabor_tf` pasó a ser una envoltura de tres líneas sobre ella y **conserva su comportamiento exacto**: las 124 pruebas de PAC siguen pasando sin tocarlas.

**Tres cosas que solo aparecieron al probarlo**, y que están arregladas:

1. **Media muestra de redondeo quitaba la mitad de la N.** `largos = round(ancho·fs)` podía quedar medio paso por debajo de lo pedido, y el `floor` de `n_ind` contaba 1 en vez de 2: la fila reportaba N=10 donde tenía 20. Se redondea **hacia arriba**.
2. **Las columnas de los extremos salían enteras en NaN**, porque la rejilla llegaba más allá de donde cabe ninguna ventana. Se recortan. Una columna vacía en el borde es justo lo que se le critica al MATLAB (§2.4), y da igual que aquí fuera NaN y allí un cero.
3. **El aviso de «no cabe» era inalcanzable.** Como la ventana se acota al largo del trial, siempre «cabía»; lo que falla de verdad es no reunir dos muestras independientes. La comprobación se movió detrás del cálculo de `N`.

---

### Fase 4 — Guardas y avisos

Dos cosas distintas, y conviene no mezclarlas. Un **error** impide calcular y se lanza antes de empezar, para no hacer esperar y luego fallar. Un **aviso** no impide nada: el mapa está bien, pero hay algo que condiciona cómo se lee.

**Errores** — `ValueError` en español desde `ppc_mapa`:

| Situación | Mensaje |
|---|---|
| `fmax` pasa del Nyquist efectivo | Dice el Nyquist que deja el remuestreo y qué bajar |
| Ninguna frecuencia reúne 2 muestras independientes | Dice qué ventana haría falta y cuánto dura el trial |
| Los dos canales no traen la misma matriz | Dice las dos formas |
| Parámetros fuera de rango (`wd`, `solape`, `ciclos`, `n_objetivo`) | Cada uno con el valor recibido |
| Los dos canales no están alineados (`validar_alineacion`) | Dice **en qué** difieren: forma, onsets, fs o ventana de recorte |

**Avisos** — la lista que devuelve `avisos(resultado)`:

| Situación | Por qué hace falta decirlo |
|---|---|
| Los dos canales son el mismo | El PPC de una señal consigo misma vale 1 en todo el mapa por definición |
| El remuestreo pedido no se alcanzó | El factor es entero: pedir 300 sobre 1.000 deja 333,3 Hz, y **todo** el eje de frecuencias con ello (problema nº 18) |
| Filas enteras sin medir | Salen en blanco a propósito; MATLAB las devolvía valiendo 1 |
| Filas por debajo de `n_objetivo` | Ahí el valor es más ruidoso. Si el mínimo baja de 5 se dice además que **no se puede leer**: con fases al azar la desviación del PPC es 0,7 para N=2 y 0,2 para N=5 |
| Más del 5 % del mapa en blanco | Es el cono de influencia, no un dato que falte. Quien mire el mapa por primera vez lo lee al revés |

**Ningún aviso abre un diálogo.** El plugin los registra y, si quiere, los pone bajo el gráfico. Un modal abre un bucle de eventos anidado y el temporizador de `QVTKRenderWindowInteractor` sigue disparando dentro de él: es el nº 24 de `problemas-encontrados.md`. Es la misma decisión que se tomó para los avisos de MI.

Con una corrida sana **no sale ninguno o sale uno**. Si avisara de todo siempre, nadie leería el que importa; hay una prueba que lo fija.

---


### Auditoría de las fases 1-4 *(25 de octubre)*

Repaso buscando defectos en lo construido, no en MATLAB. Salieron cinco; cuatro arreglados y uno documentado.

| # | Defecto | Estado |
|---|---|---|
| 1 | **Dos canales planos daban PPC = 1,0000 en todo el mapa** | ✅ arreglado |
| 2 | `n_freq=1` se subía a 2 **en silencio** | ✅ arreglado |
| 3 | El error de Nyquist imprimía el mismo número dos veces | ✅ arreglado |
| 4 | Sesgo residual de −0,009 bajo la hipótesis nula | 📌 documentado, no corregido |
| 5 | Un tramo plano **dentro** de un trial vivo no se detecta | 📌 límite conocido |

**1. El falso positivo del canal plano.** Es el peor de los cinco, porque es el que alguien enseñaría como hallazgo. El PPC normaliza cada coeficiente a módulo 1, así que la amplitud desaparece: da igual que valga 4 o 10⁻²⁵. Con un canal constante —electrodo muerto, saturación— los coeficientes son polvo numérico de 10⁻²⁵, pero **repetible**, y al normalizarlo sale una fase perfecta. Medido: dos canales constantes daban **1,0000 en todas las celdas**. Se comprueba ahora a la entrada, donde el criterio es claro —desviación cero es desviación cero— y el error nombra el canal y los trials.

**2 y 3.** Subir `n_freq` de 1 a 2 sin decirlo es la misma clase de cosa que hace MATLAB al subir `fmin` de 0 a 0,1, y es justo lo que este puerto decidió no replicar: ahora lanza error si el número se pidió a mano, y solo se ajusta cuando lo decide el cálculo. El mensaje de Nyquist usaba `:g`, de seis cifras, y con `fmax = 250,0001` sobre un Nyquist de 250 imprimía «250 Hz pasa del Nyquist (250 Hz)».

**4. El sesgo residual, que es lo único aproximado del cálculo.** `n_ind` supone que dos puntos separados 2σ ya son independientes. Se midió directo, con 400 ventanas de ruido y usando que `E[PLV²] = 1/N` cuando no hay sincronía:

| f (Hz) | ventana | N que usamos | N medida | razón |
|---:|---:|---:|---:|---:|
| 20 | 602 ms | 2 | 2,31 | 0,87 |
| 50 | 242 ms | 2 | 2,53 | 0,79 |
| 100 | 122 ms | 2 | 2,32 | 0,86 |
| 200 | 62 ms | 2 | 2,41 | 0,83 |

Contamos **de menos**, un 15-20 %. Contar de menos hace que la corrección se pase, así que el mapa queda sesgado **hacia abajo**: con ruido independiente la media sale −0,009 en vez de 0 (40 corridas, N=20, 7,7σ del cero, así que es sistemático y no azar).

No se corrige, por dos razones. Es **diez veces más chico que el umbral de ruido al 95 %** para esa misma N (0,103), así que no cambia ninguna lectura. Y el error va en la dirección segura: esta medida nunca inventa acoplamiento, que es el defecto que vinimos a arreglar. Calibrar el 2 a 1,74 sería ajustar una constante a una sola medida y heredar su dependencia de `ciclos`. Hay una prueba que fija el signo y el tamaño, para que un cambio futuro que lo vuelva **positivo** salte.

**Lo que se comprobó y estaba bien:** el orden de los trials no cambia el resultado (1,7·10⁻¹⁶, o sea que el acumulador conmuta y no se cuela estado entre trials); trocear por tandas tampoco lo cambia y cuesta solo un **4 %** —7 tandas contra una, porque cada llamada repite la FFT de la señal—, que es un precio razonable por acotar la memoria; `fmax` justo en el Nyquist se acepta; los largos par e impar dan la misma forma; y los NaN de la entrada se absorben.

---


### Fase 5 — Orquestación y paralelismo

> **La fase se partió en dos.** Se escribió copiando el orden que tuvo PAC, pero allí el plugin ya existía y solo había que migrarlo. Aquí no existe, así que la mitad de **orquestación** —`tasks.submit` y los cuatro slots— es parte de construir el plugin y se hace con la Fase 6. La mitad de **paralelismo** no depende de nada y se hizo sola, que además era la que podía no servir.

#### 5a. Paralelismo ✅

El reparto va **por trials**, con el mismo `map_ordenado` de `core/utils/parallel.py` que usa `pac_promedio`. Él pone el avance, la cancelación y el límite de hilos por memoria. En `compute.py` el cambio fue sacar el cuerpo del bucle a una función `aporte_de(trial)` que no toca nada de fuera.

**Medido el 25 de octubre**, trials de 3 s a 2.000 Hz, el mejor de tres corridas y con los **mismos datos** en las dos columnas:

| escenario | 1 hilo | 4 hilos | gana |
|---|---:|---:|---:|
| 5 trials, 200 filas | 1.050 ms | 576 ms | **1,82×** |
| 20 trials, 200 filas | 4.223 ms | 1.832 ms | **2,31×** |
| 20 trials, eje completo (322 filas) | 4.963 ms | 1.981 ms | **2,50×** |
| 60 trials, 200 filas | 13.432 ms | 5.051 ms | **2,66×** |

Y el resultado sale **idéntico bit a bit** en los cuatro: cada trial es independiente y `map_ordenado` devuelve en orden, así que la suma no depende de quién acabe primero.

**Cuántos hilos:** 1,93× con dos, 2,38× con tres, **2,56× con cuatro**, y con seis u ocho ya no mejora (2,33× y 2,49×). Coincide con el `MAX_HILOS = 4` que el proyecto ya tenía, así que el valor no se inventa aquí.

**Lo que cuesta:** memoria. 24 MB en serie contra **89 MB** con cuatro hilos, porque conviven los acumulados de todos los trials más las tandas en vuelo. `map_ordenado` ya acota los hilos por memoria disponible, así que en un equipo apretado baja solo.

> **En MI el mismo reparto salió más lento (0,65×).** Aquí gana porque la unidad de trabajo es grande: un trial entero es una transformada de 6.000 muestras por 200 frecuencias, así que arrancar el hilo no se nota y la FFT de NumPy suelta el GIL. En MI las tandas eran demasiado chicas. Es la razón por la que esta fase se midió antes de darla por buena.

`hilos=1` sigue corriendo en el hilo que llama, sin pool: es lo que permite usar este `compute` desde una prueba o un script sin levantar nada.

#### 5b. Orquestación ✅

`plugins/analysis/connectivity/ppc/ppc_plugin.py`. El patrón es el de PAC: `tasks.submit(cp.ppc_mapa, owner=self.meta.id, ...)` y los cuatro slots, cada uno con su guarda `if handle is not self._handle`. El cálculo corre fuera del hilo de la interfaz —hay una prueba que anota el nombre del hilo y falla si es el de la interfaz—, el botón pasa a *Computing...* y vuelve, y salir de la pestaña cancela lo que esté en vuelo.

Lo que se decide **antes** de encolar, para no hacer esperar y luego fallar: que haya dos canales con trials, que sean **distintos**, y que estén alineados (`validar_alineacion`). Los avisos de `compute.avisos` se registran en el log al terminar, sin abrir ningún diálogo. El único camino que abre diálogo es un fallo de verdad.

La cola hace falta gane o no el paralelismo: aun con cuatro hilos, 20 trials tardan **1,98 s** y 60 tardan **5,05 s**, muy por encima del umbral de 100 ms de la Fase 4 del plan del orquestador.

**Un hueco que apareció al probarlo.** Con un solo canal con trials, los dos combos apuntaban al mismo y el plugin calculaba igual: varios segundos para acabar enseñando un mapa entero de unos y un aviso diciendo que no significa nada. Ahora se rechaza antes de encolar. La rama de `avisos` se queda, porque sigue siendo alcanzable si alguien llama al cálculo desde un script.

**Sobre las pruebas, que tuvieron que montarse de otra forma.** Usan el `TaskService` de verdad —es justo el contrato que se quiere comprobar— pero la interfaz es un doble, y no por comodidad: las cuatro pruebas del proyecto que levantan Qt crean una `QCoreApplication`, con la que construir widgets **aborta el proceso sin mensaje**. Si esta prueba levantara una `QApplication` y otra hubiera creado antes la `QCoreApplication`, se caería la suite entera. El doble ofrece la misma API que el plugin usa, y el contrato de nombres se comprueba aparte: una prueba lee los dos archivos, saca cada `self.ui.<algo>` del plugin y verifica que la interfaz lo defina. Es lo que más probablemente se rompa al reemplazar el andamio, y falla diciendo qué nombre falta.

---

### Fase 6 — El plugin

> **Lo que ya está hecho de esta fase**, porque vino con la 5b: `properties.yml`, `ppc_plugin.py` con toda la orquestación, y `ppc_plugin_ui.py` como **andamio provisional**. Falta el dibujo (`render_resultado`, declarado y vacío a propósito) y el icono `icn_ppc.png`.


### Fase 6 — El plugin

| Archivo | Qué |
|---|---|
| `properties.yml` | `id: ppc`, `category: Analysis`, `subcategory: Connectivity`, `logic_class: Ppc_plugin` |
| `ppc_plugin.py` | `submit()` + los cuatro slots, y el dibujo |
| `icn_ppc.png` | el icono |

**La interfaz la hace la compañera.** Lo que el cálculo le pide:

- Seis campos: Ch 1, Ch 2, Resample, F min, F max, wd — y uno nuevo, `ciclos` (decisión 9). `wd` conserva su nombre y su 0,05 por omisión, pero la etiqueta de ayuda tiene que decir *ventana mínima* (decisión 11).
- Un panel: el mapa frecuencia-log contra tiempo con barra de color. Es la única figura que MATLAB dibuja; la otra llamada a `f_ImageMatrix`, la de eje lineal, está comentada en el `.m`.
- Reutilizable tal cual: `_grafico_mapa_log` de `pac_plugin.py` (ya hace `remuestrear_en_log` y las marcas 32/100/316 Hz) y la transparencia de NaN de `modulation_index_plugin.py`.

---

### Fase 7 — Verificación

Dos bancos, porque son dos preguntas distintas.

**a) ¿Está bien portada la Gabor?** Esa sí tiene que dar **idéntico** a MATLAB. Un `modo_matlab=False` que reproduce la aritmética original —PLV, sin submuestrear, sin solapamiento, una FFT por ventana— usado **solo por las pruebas**, igual que `limite_matlab` en `modulation_index/compute.py`. Pide ejecutar MATLAB una vez y exportar `Coh_Glb`, como `test/data/exportar_referencia_pac.m`.

**b) ¿Está bien el PPC corregido?** Contra verdad conocida, que es más fuerte que contra MATLAB:

| Prueba | Qué tiene que salir |
|---|---|
| Ruido independiente en los dos canales | PPC ≈ 0 **en toda la banda**, incluidas las filas que MATLAB clava en 1 |
| Dos senoidales con desfase fijo | PPC ≈ 1 en su frecuencia y ≈ 0 en el resto |
| Senoidal contra ruido | PPC ≈ 0 **también en su frecuencia** — el caso que MATLAB da 0,99993 |
| Canales idénticos | PPC = 1 en toda la banda |
| Desfase que cambia a mitad de la señal | el mapa lo marca en el tiempo correcto |
| Geometría | la última columna **tiene datos**, la cola está cubierta, los centros caen donde deben |
| `ventanas_s` | vale `clip(2·ciclos·ceil(n_objetivo/n_trials)/f, wd, largo)` fila a fila |
| `n_muestras` | vale `ceil(n_objetivo/n_trials)·n_trials`, y es ≥ `n_objetivo` donde no hay NaN |
| Resolución temporal | con 20 trials de 3 s, la ventana a 500 Hz mide 12 ms y a 2 Hz los 3 s enteros (§2.7) |
| Un solo trial | sigue dando mapa por encima de ~50 Hz, y NaN solo donde la ventana no cabe |

---

## 6. Orden y dependencias

```
Fase 0  ──┬──▶ Fase 1 ──▶ Fase 3 ──▶ Fase 4 ──▶ Fase 5 ──▶ Fase 7
          ├──▶ Fase 2 ──────┘
          └──▶ Fase 6  (interfaz, en paralelo desde el primer día)
```

Las fases 1 y 2 no dependen entre sí y se pueden hacer en cualquier orden. La 6 solo necesita el contrato del §4, que ya está cerrado.

---

## 7. Lo que se decidió el 24 de octubre

Estos tres puntos quedaron abiertos cuando se escribió el plan y se cerraron el mismo día, después de correr los números del §2.7 contra el caso real. **La primera versión de este documento recomendaba lo contrario en los tres**; se cambió porque la medida no la respaldaba.

| Punto | Qué decía antes | Qué se decidió | Por qué |
|---|---|---|---|
| **Ventana fija o por frecuencia** | Fija, por simplicidad | **Por frecuencia** | §2.7. La fija desperdicia N arriba (820 a 500 Hz) y no llega abajo (NaN por debajo de 6 Hz). La variable da 12 ms de resolución en gamma y llega a 2 Hz. Y no cuesta más código: es un `cumsum` por fila en vez de un troceo |
| **`wd` por omisión** | Subirlo a 0,5 s | **Dejarlo en 0,05 s**, como MATLAB, pero significando *ventana mínima* | Con ventana por frecuencia ya no hace falta subirlo: el valor del panel sobrevive y pasa a ser el tope de la resolución temporal |
| **Qué pasa con 1 trial** | NaN en las frecuencias bajas | **Ensanchar la ventana** y dar NaN solo donde no quepa en el trial | Un trial sigue dando mapa por encima de ~50 Hz. Un NaN plano era tirar información que sí está |

Y uno que no estaba en duda:

| Punto | Decisión |
|---|---|
| **Exportar** | CSV del mapa, con el mismo `_secciones_resultado` que PAC |

---

## 8. Estado

| Fase | Estado |
|---|---|
| 0 — Decisiones y contrato | ✅ este documento |
| 1 — Gabor a `core/filters/` | ✅ `core/filters/gabor.py`. Las 124 de `test_pac_core.py` pasan **sin tocarlas**, más 6 nuevas en `test/services_test/test_gabor_en_core.py` |
| 2 — Acceso a dos canales | ✅ `get_active_trials` honra el canal, `IPlugin.get_trials_de_canal`. 12 pruebas en `test/services_test/test_trials_por_canal.py`; el alineamiento comprobado sobre el ABF real |
| 3 — El núcleo | ✅ `plugins/analysis/connectivity/ppc/compute.py` y `gabor_en` en core. 40 pruebas en `test/plugins_test/test_ppc_core.py` |
| 4 — Guardas y avisos | ✅ 5 errores y 5 avisos, `avisos(resultado)` en `compute.py`. 12 pruebas más |
| 5a — Paralelismo | ✅ `map_ordenado` sobre los trials. **1,8× a 2,7×**, idéntico bit a bit. 12 pruebas más |
| 5b — Orquestación | ✅ `ppc_plugin.py` con `submit` y los cuatro slots. 19 pruebas en `test/plugins_test/test_ppc_plugin_orquestado.py` |
| 6 — El plugin (interfaz: otra persona) | 🟨 `properties.yml` y la clase lógica hechas; falta `render_resultado`, el icono y la interfaz de verdad |
| 7 — Verificación | ⬜ |
