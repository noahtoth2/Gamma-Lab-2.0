# Análisis de PAC: cómo lo hace Gamma Lab 1.0 y cómo implementarlo en 2.0

*1 de octubre de 2026. Análisis previo a la Fase 5. No se escribió código: este documento es para decidir antes de implementar.*

Fuente analizada: `C:\Users\noah\Downloads\BOARD_FTD_PACC` — los siete archivos de PAC, las funciones de apoyo (filtros y transformadas) y el código de la interfaz extraído de `BOARD_FTD_PACC.mlapp`.

---

## 1. En MATLAB no hay «un» PAC: hay cinco botones y dos algoritmos distintos

La app de 1.0 expone cinco entradas a PAC, y no son variantes de lo mismo:

| Botón en la app | Llama a | Líneas | Qué produce |
|---|---|---:|---|
| `MIButton` | `f_PAC_sing` | 90 | **Comodulograma**: matriz frecuencia de amplitud × frecuencia de fase |
| `PACButton` | `f_Phase_PAC` | 164 | **Mapa fase-frecuencia** de un trial |
| `PACAverageButton` | `f_Phase_PAC_Average` | 119 | El mismo mapa, promediado sobre los trials |
| `PACPselButton` | `f_Phase_PAC_Pdetect` | 522 | Detección de picos |
| `PACButton_2` | `f_Phase_PAC_Pdetect_window` | 664 | Inter-canal por ventanas |

Las dos familias:

- **`f_PAC_sing`** barre una **rejilla** de frecuencias. Para cada frecuencia de fase filtra en una banda de 1 Hz de ancho, para cada frecuencia de amplitud filtra en una banda de 10 Hz, y calcula el índice de modulación por longitud de vector medio:

  - `MI = |mean(amp · e^{iφ})|` — índice de Canolty
  - `MInorm = |Σ(amp · e^{iφ}) / Σ amp|` — variante normalizada de Özkurt

  Usa filtros IIR y la transformada de Hilbert. **No usa wavelet.**

- **`f_Phase_PAC`** trabaja con **una sola** banda de fase y **un rango** de amplitud. Saca la fase instantánea por Hilbert, hace una transformada tiempo-frecuencia con wavelet de Morse sobre el rango de amplitud, y agrupa la potencia en 100 bins de fase.

---

## 2. Cuál de los cinco corresponde a la interfaz que 2.0 ya tiene

No hay que adivinarlo. El `properties.yml` del plugin de 2.0 ya está escrito y describe el algoritmo:

> *«Calculates the relationship between the phase of a low-frequency band and the amplitude of a frequency range in an EEG signal **using the Wavelet Transform**. Allows users to select the **phase band, amplitude frequency range**, and **trial mode (single trial or average across multiple trials)**. The output includes a **phase-frequency coupling map**, a **histogram of amplitude distribution as a function of phase**, and a **mean coupling vector with its magnitude and angle**.»*

Cada parte tiene su correspondencia exacta:

| La descripción dice | En el MATLAB es |
|---|---|
| «using the Wavelet Transform» | `f_MorseAWTransformMatlab` |
| «phase band» | `P1`, `P2` |
| «amplitude frequency range» | `A1`, `A2` |
| «single trial or average» | `f_Phase_PAC` y `f_Phase_PAC_Average` |
| «phase-frequency coupling map» | `m_phase_av_aux` |
| «histogram of amplitude distribution as a function of phase» | `hist_pre_1` |
| «mean coupling vector with its magnitude and angle» | `v_pha_av_pre1` |

Eso **descarta** `f_PAC_sing`, que no usa wavelet y produce un comodulograma, no un mapa fase-frecuencia.

**Alcance recomendado:** implementar únicamente `f_Phase_PAC` y `f_Phase_PAC_Average`. Los dos `Pdetect` suman 1.186 líneas con lógica de detección de picos y comparación entre canales; son un frente de trabajo aparte, no parte de este plugin. El comodulograma (`f_PAC_sing`) tampoco entra: si más adelante se quiere, es un plugin distinto con su propia interfaz, porque necesita cuatro parámetros más (`Pstep`, `Astep` y los rangos de barrido).

---

## 3. El algoritmo, paso a paso

Firma en MATLAB: `f_Phase_PAC(P1, P2, A1, A2, v_Data, srate, srt, Tr, GF, vtime)`

1. **Submuestreo** por factor `srt = round(fs / sample_density)`, con `downsample` — sin filtro antialias.
2. **Fase instantánea**: filtro pasa-banda Chebyshev II en `[P1, P2]`, aplicado de forma bidireccional (adelante, voltear, adelante, voltear → fase cero), y después `angle(hilbert(·))`.
3. **Amplitud**: transformada de Morse sobre `[A1, A2]`, con `FreqSeg = 4·(A2 − A1)` filas y `cycles = 1`, devolviendo magnitudes. El resultado es una matriz **frecuencia × tiempo**.
4. **Agrupación por fase**: 100 bins entre −π y π. Por cada bin se buscan los instantes cuya fase cae dentro, se suman esas columnas de la matriz tiempo-frecuencia, y se cuenta cuántas eran.
5. **Promedio por bin**: la suma dividida por la cuenta → `m_phase_av`, de forma frecuencia × bin.
6. **Histograma**: `hist_pre_1 = sum(m_phase_av, axis=0)`, un valor por bin de fase.
7. **Normalización**: z-score de **cada fila** a lo largo de los bins. Es lo que se dibuja como mapa.
8. **Vector medio de acoplamiento**: `mean(hist_pre_1 · e^{i·bins})`, del que se toman magnitud y ángulo.

`f_Phase_PAC_Average` es idéntica salvo en un punto: acumula `m_phase` y `v_phase_num` **sobre todos los trials** y divide una sola vez al final. Es exactamente el patrón de acumulador incremental que ya se usa en `wavelet_promedio` desde el paso 1.2.

### El parámetro `GF`

En la app de 1.0, `GF` es el valor de la casilla `NoStimCheckBox`: *registro sin estimulación*. Cuando `GF == 1` no hay trials, hay un único registro continuo, y el código fuerza `Tr = 1`. En 2.0 eso corresponde al `trialModeComboBox`, que hoy solo tiene la opción `"trials"`.

---

## 4. Qué hay que portar y qué ya existe en 2.0

| Pieza de MATLAB | Estado en Gamma Lab 2.0 | Esfuerzo estimado |
|---|---|---|
| `f_MorseAWTransformMatlab` | **No existe.** PyWavelets no trae el wavelet de Morse | ~30 líneas de NumPy |
| `f_GetIIRFilter` (Chebyshev II, orden automático) | **No existe.** El plugin `filter` usa Butterworth | ~15 líneas de SciPy |
| `f_IIRBiFilter` (bidireccional) | **No existe**, pero `sosfiltfilt` cumple la misma función | 1 línea |
| `hilbert` | **No se usa en ninguna parte** del proyecto | `scipy.signal.hilbert` |
| Acumulador sobre trials | ✅ Patrón probado en `wavelet_promedio` | Copiar |
| `submit()` + progreso + cancelación | ✅ `TaskService`, validado en la Fase 3 | Copiar |
| Dibujo de la matriz en VTK | ✅ Patrón vectorizado del paso 1.3 | Copiar |

### La transformada de Morse no es el obstáculo que parecía

A primera vista parecía la parte difícil, porque ninguna librería de Python la trae. Pero el MATLAB la calcula **en el dominio de la frecuencia**, así que es FFT, aritmética vectorial e IFFT — nada más:

```
γ = 3                      (valor por defecto)
β = (cycles·π)² / γ        con cycles = 1  →  β = π²/3 ≈ 3,2899
pico = (β/γ)^(1/γ)         ≈ 1,0312
escala = pico / (2π·f)

Ψ(ω) = 2 · exp[ (β/γ)·((1 + ln γ) − ln β) + β·ln(ω·escala) − (ω·escala)^γ ]

coef = IFFT( FFT(señal) · Ψ )
```

Detalles del original que hay que respetar al portarlo:

- Solo se llena **la mitad del espectro** (`1:s_HalfLen`), porque es un wavelet analítico; el resto queda en cero.
- El eje de frecuencias se construye lineal y después se **invierte**: queda en orden descendente.
- Si la señal tiene longitud **par**, se descarta la última muestra antes de transformar y se duplica la última columna al final.
- El eje angular es `v_WAxis = (2π/N)·(0:N−1)·fs`.

Como todo son `np.fft.fft`, operaciones vectoriales y `np.fft.ifft`, el GIL se libera durante el cálculo. Encaja bien en el orquestador, igual que el wavelet.

> Ojo con la documentación del propio archivo: la cabecera dice *«Time in rows, frequency in columns»*, pero el código hace `m_MorseWT = zeros(numel(v_FreqAxis), numel(v_TimeAxis))`, o sea **frecuencia en filas**. El comentario está equivocado; `f_Phase_PAC` la usa correctamente como frecuencia × tiempo.

---

## 5. Problemas encontrados en el código de 1.0

Hay que decidir sobre estos **antes** de escribir código, porque determinan si 2.0 reproduce el comportamiento de 1.0 o lo corrige.

### 5.1 `f_PAC_sing:41` — un límite fijo donde debería ir el tamaño del rango

```matlab
%for counta = 1:(size(amp_range,2)     % <- comentado, y le falta un parentesis
for counta = 1:178                     % <- lo que se ejecuta
```

El bucle de amplitud siempre da 178 vueltas, sin importar el rango que el usuario haya pedido. El bucle correcto quedó comentado en la línea de arriba. Solo afecta al comodulograma, así que si no se porta `f_PAC_sing`, no importa.

### 5.2 `f_Phase_PAC:126` y `:134` — `fliplr` sobre un vector columna no hace nada

```matlab
v_h_Filt_P = filter(h_FiltP, v_Data);
v_h_Filt_P = filter(h_FiltP, fliplr(v_h_Filt_P));   % fliplr en una columna: sin efecto
v_h_Filt_P = fliplr(v_h_Filt_P);                    % tampoco
```

`fliplr` invierte columnas, y un vector columna tiene una sola. El filtrado «bidireccional» de esa sección aplica en realidad el filtro **dos veces hacia adelante**, así que no es de fase cero y acumula retardo. Afecta solo a las cuatro gráficas de señales del final, no al cálculo de PAC. La función `f_IIRBiFilter`, que sí se usa para el cálculo, emplea `flipud` correctamente.

### 5.3 Submuestreo sin filtro antialias

`downsample(v_Data, srt)` toma una muestra de cada `srt` sin filtrar antes. Es el mismo problema que ya está abierto como nº 18 en [`problemas-encontrados.md`](problemas-encontrados.md), y aquí entra por la misma puerta.

### 5.4 Dos divisiones por cero sin guarda

- Si algún bin de fase queda vacío, `v_phase_num(countp)` es 0 y `m_phase_av` sale con infinitos. Con 100 bins y trials cortos es posible.
- En el z-score, `m_phase_av_std` puede ser 0 para una fila constante.

### 5.5 `f_Phase_PAC_Average:52` calcula la transformada dos veces

La línea 52 calcula la transformada del primer trial solo para conocer la forma de la matriz, y el bucle la vuelve a calcular para ese mismo trial. Es trabajo duplicado; en 2.0 basta con reservar el acumulador en la primera iteración, como ya hace `wavelet_promedio`.

### 5.6 Chebyshev II contra Butterworth

El plugin `filter` de 2.0 usa Butterworth con `sosfiltfilt`. PAC en 1.0 usa Chebyshev II con orden calculado automáticamente por `cheb2ord` (Rp = 0,5 dB, Rs = 100 dB, bordes de banda de rechazo a ±0,5 Hz de la banda de paso, escalados para frecuencias por debajo de 1 Hz).

Reutilizar el filtro existente es más barato pero **cambia el resultado** respecto a la referencia. Y aun usando Chebyshev II, `sosfiltfilt` no es numéricamente idéntico al flip-filter manual de MATLAB, porque trata los transitorios de borde de otra manera. **No se debe esperar igualdad bit a bit con MATLAB en PAC**, a diferencia de lo que se logró con otros plugins.

---

## 6. La interfaz de 2.0 está incompleta

Es el hallazgo más concreto del análisis. El panel de parámetros de `pac_plugin_ui.py` tiene exactamente tres secciones:

| Sección | Controles | Corresponde a |
|---|---|---|
| Sample density | `sampleDensitySpinBox` (Hz) | el factor `srt` |
| Phase Band | `lowFrequencySpinBox` (F1), `highFrequencySpinBox` (F2) | `P1`, `P2` |
| Trial Mode | `trialModeComboBox` | single / average |

**Falta la banda de amplitud.** Los parámetros `A1` y `A2` no tienen dónde escribirse, y los necesitan tanto el algoritmo como la descripción del `properties.yml`. En la app de MATLAB esos campos existen (`A1EditField`, `A2EditField`).

Hay que agregar una sección «Amplitude Band» con dos campos más, calcada de la de fase. Sin eso no se puede probar nada.

---

## 7. Estructura propuesta para la implementación

Siguiendo el patrón que la Fase 3 ya validó contra dos plugins reales:

```
plugins/analysis/time_frequency/pac/
├── compute.py          NUEVO: todo el calculo, puro, sin Qt
│   ├── morse_tf(...)              la transformada
│   ├── fase_instantanea(...)      Chebyshev II + filtfilt + hilbert
│   ├── pac_un_trial(ctx, ...)     los pasos 1 a 8
│   └── pac_promedio(ctx, ...)     acumulador sobre trials
├── pac_plugin.py       lee la UI, submit(), dibuja en el slot de finished
├── pac_plugin_ui.py    agregar la seccion Amplitude Band
└── properties.yml      ya esta
```

`compute.py` recibe NumPy y devuelve NumPy: no toca widgets ni el `DataStore`. Las dos funciones de alto nivel llevan `ctx` para reportar avance por trial y responder a la cancelación, igual que `wavelet_promedio`.

El plugin queda con el mismo esqueleto de cuatro conexiones que usa hoy el promedio de wavelet:

```python
handle = tasks.submit(cw.pac_promedio, owner=self.meta.id, ...)
handle.progress.connect(partial(self._on_pac_progress, handle))
handle.finished.connect(partial(self._on_pac_done, handle))
handle.failed.connect(partial(self._on_pac_failed, handle))
handle.cancelled.connect(partial(self._on_pac_cancelled, handle))
```

Así se cumple lo que el UC-01 ya da por sentado: el plugin delega el cómputo al orquestador en vez de instanciar hilos propios. Y la prueba `ningun_plugin_crea_hilos_propios` avisa si alguien le pone un `QThread`.

### Orden de trabajo

1. **Agregar los campos de banda de amplitud a la interfaz.** Sin ellos no hay nada que probar.
2. **`morse_tf` sola, verificada contra MATLAB.** Es la pieza con más riesgo numérico y la única sin equivalente en ninguna librería. Conviene exportar desde MATLAB una matriz de referencia y compararla, como se hizo con el wavelet.
3. **`fase_instantanea`**, con la decisión del punto 5.6 ya tomada.
4. **`pac_un_trial`**, que compone las dos anteriores con el agrupado por bins de fase.
5. **`pac_promedio`**, con el acumulador y el `ctx`.
6. **El plugin**: leer la interfaz, `submit()`, y los tres dibujos en el slot de `finished` — mapa, histograma y vector medio.

---

## 8. Decisiones pendientes

Dos, y las dos son previas a escribir código:

| # | Decisión | Opciones |
|---|---|---|
| **a** | Los problemas 5.3 y 5.4 | Reproducir el comportamiento de 1.0 tal cual, o corregirlos (y documentar que 2.0 difiere a propósito) |
| **b** | El filtro de la banda de fase | Chebyshev II, para acercarse a la referencia; o Butterworth, para reutilizar lo que ya existe en el plugin `filter` |

Conviene cerrar la **(a)** con la directora, porque es una decisión científica del mismo tipo que la del problema nº 2.

---

## 9. Estado actual del plugin en 2.0

| Archivo | Estado |
|---|---|
| `pac_plugin_ui.py` | Interfaz completa (~10,8 KB), **falta la banda de amplitud** |
| `pac_plugin.py` | 18 líneas: `process()` y `stop()` los dos en `pass` |
| `properties.yml` | Completo, y define el alcance del plugin |
| `compute.py` | No existe |

El esqueleto y la interfaz están; la lógica no existe. No hay nada que migrar y todo por escribir, que es justamente lo que hace de PAC el caso ideal para nacer ya orquestado: es el primer consumidor **nuevo** del `TaskService`.
