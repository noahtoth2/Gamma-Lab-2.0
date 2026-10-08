# Plan de implementación de PAC

*6 de octubre de 2026. Fases y lista de verificación para llevar las cuatro operaciones de PAC del MATLAB de `BOARD_FTD_PACC` a Gamma Lab 2.0.*

El análisis del algoritmo está en [`analisis-pac.md`](analisis-pac.md). Este documento es el plan de trabajo: qué hay hecho, qué falta y en qué orden.

> ## Estado al 6 de octubre de 2026
>
> | Fase | Estado |
> |---|---|
> | **1 — Piezas de cálculo** | ✅ **Hecha.** `core/filters/iir.py` y `plugins/.../pac/compute.py`. 41 pruebas |
> | **2 — PAC** | ✅ **Hecha.** `pac_un_trial`, los ocho pasos |
> | **3 — PAC Average** | ✅ **Hecha.** `pac_promedio`, con acumulador |
> | **4 — MI (comodulograma)** | ✅ **Hecha.** Cálculo, interfaz completa y plugin. 23 escenarios. El `178` se replicó tal cual, a la espera de la decisión |
> | **5 — PAC Psel** | ⬜ **Falta.** La más grande: Gabor y detección de picos |
> | **6 — Integración con el orquestador** | ✅ **Hecha.** Selector de trial con flechas, `submit()` + 4 slots, 4 salidas apiladas y deslizables. 28 escenarios |
> | **7 — Verificación** | ⬜ **Bloqueada** por la referencia de MATLAB (sección 8 bis) |
>
> Suite completa: **262 pasan, 5 fallan** (los cinco fallos MATLAB ya conocidos, ajenos a PAC).
>
> **Lo que se decidió sobre el dibujo**, al compararlo con lo que produce MATLAB:
>
> - El histograma **no arranca en cero**: se acerca al rango de los datos con un 10 % de margen, como hace `set(gca,'YLim',...)`. Sin eso la variación se aplasta y parece plano.
> - El mapa usa **`jet`**, el mismo mapa de colores de `f_ImageMatrix`.
> - Los cuatro paneles de señal **comparten el eje de tiempo**, como el `linkaxes(ax,'x')`.
> - Las seis salidas van **apiladas y deslizables** en un `QScrollArea`, cada una con altura fija. Repartir el alto entre seis gráficos —uno de ellos cuadrado— los dejaba ilegibles.
>
> **Dos erratas de MATLAB que NO se copiaron**, las dos de etiquetas:
>
> - El `ylabel` del mapa dice «Frequency (Hz) - **Log**», pero el eje es **lineal**: `f_Phase_PAC` llama a `f_ImageMatrix` con 6 argumentos, así que entra por la rama de `imagesc`, que reparte linealmente; y el eje de la Morse también es lineal porque `ps_DyadicScale` no se pasa.
> - El tercer panel de señal dice «Filtered PHASE», igual que el segundo, cuando muestra la fase instantánea en radianes.
>
> > **Ojo para la Fase 5:** `f_Phase_PAC_Pdetect` **sí** llama a `f_ImageMatrix` con 10 argumentos y activa `ps_NonEquAxis`, que usa `pcolor` y respeta espaciados no uniformes. Ahí el eje puede no ser lineal y hay que tratarlo distinto.

> **Criterio de este plan: paridad con MATLAB.** La referencia del proyecto es el MATLAB de `BOARD_FTD_PACC`, no Gamma Lab 1.0, así que el objetivo es reproducir sus funciones, sus parámetros y sus salidas. Donde el MATLAB tiene un defecto, este documento lo señala y lo deja como decisión explícita en vez de corregirlo en silencio.

---

## 1. Estado actual

El commit `355f0ae` («pac y MI interfaz») dejó las dos interfaces construidas.

| Pieza | Estado |
|---|---|
| `pac` — interfaz | ✅ Combo (PAC / PAC Average / PAC Psel), Sample Fq, P1, P2, **A1, A2**, Clear, Generate |
| `pac` — cálculo | ❌ `process()` y `stop()` en `pass`; no hay `compute.py` |
| `modulation_index` — interfaz | ✅ Plugin aparte: Fq P1, Fq P2, Pstep, Fq A1, Fq A2, Astep, Clear, Generate |
| `modulation_index` — cálculo | ❌ igual, sin `compute.py` |

Los valores por defecto coinciden con los del MATLAB:

| Plugin | Defectos |
|---|---|
| `pac` | `sample_fq=2000`, `p1=3`, `p2=8`, `a1=25`, `a2=500` |
| `modulation_index` | `fq_p1=0,1`, `fq_p2=10`, `p_step=0,1`, `fq_a1=10`, `fq_a2=500`, `a_step=0,5` |

Que MI haya quedado como **plugin separado** es lo correcto: no comparte ni un parámetro con la familia PAC y no usa wavelet, sino filtros IIR.

> **Falta un campo en `modulation_index`.** No tiene frecuencia de muestreo: sus etiquetas son solo *Parameters, Generate, Phase Band, Fq P1, Fq P2, P step, Amplitude Band, Fq A1, Fq A2, A step, Hz*. En el MATLAB, MI lee `app.ResampleFr` —que vive en el panel *Frequency*, con valor 1000—, **no** el `ResamplePAC` de 2000 que aparece dibujado al lado del botón MI. **Decidido:** MI lleva campo propio en 2.0; no se replica esa confusión.

> **Falta el selector de trial en las dos interfaces.** Ni `pac` ni `modulation_index` tienen con qué elegir el trial, y la directora pidió explícitamente poder navegar entre ellos. Hace falta en las operaciones que trabajan sobre **un** trial.

### Qué operación necesita selector de trial

| Operación | Qué trials usa en MATLAB | ¿Selector? |
|---|---|---|
| **PAC** | `v_Data(:,Tr)` — uno solo | **Sí** |
| **MI** | `v_Data(:,Tr)` — uno solo | **Sí** |
| PAC Average | `v_Data` completo — todos | No |
| PAC Psel | concatena todos en una señal continua | No |

### Quién usa qué campo, en el MATLAB

| Campo | Lo usa |
|---|---|
| `Fq P1`, `Fq P2`, `Pstep`, `Fq A1`, `Fq A2`, `Astep` | **solo MI** (`f_PAC_sing`) |
| `P1`, `P2`, `A1`, `A2` | **PAC, PAC Average y PAC Psel**, los tres igual |
| `ResamplePAC` (2000) | PAC, PAC Average y PAC Psel |
| `ResampleFr` (1000) | MI |

Verificado con `grep`: `astep` no aparece en ninguno de los cuatro archivos `f_Phase_PAC*.m`.

---

## 2. Decisiones previas — bloquean el trabajo

Van con la directora, salvo la última.

- [x] **Filtro de la banda de fase: Chebyshev II, igual que MATLAB.** *(Decidido el 6 de octubre de 2026.)* El criterio del proyecto es parecerse lo más posible a la referencia, así que se replica `f_GetIIRFilter` en lugar de reutilizar el Butterworth del plugin `filter`. El detalle de cómo portarlo está en la sección 3.
- [ ] **El `178` fijo de MI.** Se reproduce o se corrige. Con los valores por defecto, el comodulograma sale con **solo el 18,1 % de sus filas con datos reales** (ver sección 6). *No bloquea las fases 1 a 3.*
- [x] **Las divisiones por cero: se replica el `NaN` de MATLAB, sin guardas.** *(Decidido el 6 de octubre de 2026.)*

  Al revisarlo con cuidado resultó que **MATLAB produce `NaN`, no `Inf`**, en los tres sitios donde divide sin comprobar — porque en los tres el **numerador también vale cero**:

  | Caso | Qué pasa | Resultado |
  |---|---|---|
  | Bin de fase vacío | no se le sumó nada, y la cuenta es 0 → `0/0` | `NaN` en esa columna |
  | Fila constante en el z-score | el valor menos la media es 0, y la desviación es 0 → `0/0` | `NaN` en esa fila |
  | Fila de MI nunca filtrada (el `178`) | `sum(a)=0` y `sum(amp)=0` → `0/0` | `MI = 0`, pero **`MInorm = NaN`** |

  Verificado numéricamente. NumPy hace lo mismo que MATLAB, así que **no hay que programar nada**: basta con silenciar el aviso con `np.errstate`.

  Lo que sí hay que atender es el **dibujo**, y eso no es apartarse de la referencia: asegurarse de que el `NaN` no arruine la escala de color ni reviente el render. Es lo mismo que ya hace `preparar_mapa_calor` de `erp`, que calcula los percentiles solo sobre los puntos finitos.

  > **Consecuencia para el `178`:** las filas que MI no calcula no salen en cero, salen **sin dato**. Con los valores por defecto eso es el **81,9 %** del comodulograma en `NaN`, que al dibujarse se ve como un bloque en blanco de 99 a 500 Hz.

### Decisiones ya tomadas (6 de octubre de 2026)

- [x] **Visualización: apilar las salidas en el `plotArea`**, como hace `open_signal` con sus canales (`_relayout_charts`, hasta 3 gráficos en una vista VTK). No se abren ventanas aparte como en MATLAB.
- [x] **El modo «sin estimulación» (`GF`) no se implementa.** Se asume que siempre hay trials. El `NoStimCheckBox` de MATLAB y la rama `if GF==1 → Tr=1` no tienen equivalente en 2.0.
- [x] **Selector de trial: sí, con navegación y por plugin.** Lo pidió la directora: *«tenemos que poder navegar entre los trials»* y *«además de los rangos de frecuencia, el trial»*. No basta con fijar el trial 0 como hace el wavelet individual.

  **Cómo lo hace MATLAB, y en qué nos apartamos.** `SingleTrialEditField` es una casilla numérica («Single Trial», valor por defecto 1) que vive en el `BasicInformationPanel` y que leen **15 callbacks distintos**: PAC, PAC Average, MI, TF, TF Average, FFT, PSD, RMS… Es decir, **un solo campo global para toda la aplicación**, y sin navegación: se escribe el número y se vuelve a presionar el botón.

  En 2.0 se hace **distinto a propósito**, en dos puntos:

  | | MATLAB | Gamma Lab 2.0 |
  |---|---|---|
  | Forma | casilla numérica sola | casilla **+ flechas de navegación** |
  | Alcance | un campo global, 15 análisis | **uno por plugin** |

  - **Las flechas** son lo que pidió la directora; una casilla sola no es «navegar». La casilla se conserva para poder escribir el número directo, así que es un superconjunto de lo que hace MATLAB.
  - **Por plugin y no global** porque hoy ningún plugin de 2.0 lee los widgets de otro, y el proyecto guarda los parámetros **por plugin** (`get_analysis_params`). Un campo compartido por 15 análisis necesitaría un «trial activo» en el `DataStore`, que no existe, y obligaría a tocar plugins ya terminados y verificados.

  Aspecto propuesto:

  ```
  Trial   [ ◄ ]  [  3  ]  [ ► ]   de 60
  ```

  > **Ojo con el índice:** MATLAB cuenta desde **1** y Python desde **0**. La casilla debe mostrar 1 para el primer trial —igual que MATLAB— y restar uno internamente.
- [x] **MI lleva su propio campo de frecuencia de muestreo.** Hoy no tiene ninguno. No se replica la rareza de MATLAB, donde MI lee el campo del panel *Frequency* (1000) mientras que el que aparece dibujado a su lado es el de PAC (2000).
- [x] **El submuestreo sin antialias.** Ya decidido para el wavelet —se conserva, para coincidir con MATLAB— y el mismo criterio aplica aquí, porque el MATLAB de PAC también usa `downsample`. Queda anotado, no hay que volver a decidirlo.

> **Sobre la igualdad numérica con MATLAB.** Replicando el flip-filter literal (sección 3) el resultado queda **mucho más cerca** que usando `sosfiltfilt`, pero seguirá sin ser bit a bit: `cheb2ord` y `cheby2` no están implementados igual en MATLAB y en SciPy, y el orden que calculan puede diferir en algún caso de frontera. La verificación tiene que ser por correlación y forma, no por igualdad exacta — igual que con el wavelet.

---

## 3. Fase 1 — Las piezas de cálculo

> **Dónde va cada cosa.** El criterio del proyecto es que `core/filters/` guarda únicamente el cálculo que **cruza una frontera de plugin**; lo demás vive en la carpeta de su plugin. Los precedentes: `wavelet.py` lo comparten los dos plugins de wavelet, `artifacts.py` lo comparten `artifact_remove` y el `ProjectService`, y `trials.py` lo comparten `open_signal`, `trials` y dos servicios.
>
> | Módulo | Quién lo usa | Dónde va |
> |---|---|---|
> | Filtros IIR | plugins `pac` **y** `modulation_index` | **`core/filters/iir.py`** |
> | Morse y agrupado por fase | **solo** el plugin `pac` | **`plugins/.../pac/compute.py`** |
>
> **Ojo con un error fácil:** PAC, PAC Average y PAC Psel **son tres modos del mismo plugin** —un combo—, no tres plugins. Compartir código entre ellos no justifica subirlo a `core/`. Lo que sí cruza frontera son los filtros IIR, porque el índice de modulación es un plugin aparte y también los necesita (aunque no use ni la Morse ni los bins de fase).

- [ ] **`morse_tf(sig, fs, fmin, fmax, n_freq, cycles)`** — la transformada de Morse.

  Parecía el obstáculo y no lo es: el MATLAB la calcula **en el dominio de la frecuencia**, así que son unas 30 líneas de NumPy y no hace falta ninguna librería nueva. PyWavelets **no sirve** aquí: tiene 21 wavelets continuas y ninguna Morse.

  ```
  γ = 3                        (valor por defecto)
  β = (cycles·π)² / γ          con cycles = 1  →  β ≈ 3,2899
  pico = (β/γ)^(1/γ)           ≈ 1,0312
  escala = pico / (2π·f)

  Ψ(ω) = 2 · exp[ (β/γ)·((1 + ln γ) − ln β) + β·ln(ω·escala) − (ω·escala)^γ ]

  coef = IFFT( FFT(señal) · Ψ )
  ```

  Detalles del original que hay que respetar:
  - [ ] Solo se llena **media ventana** (`1:s_HalfLen`), porque es un wavelet analítico; el resto queda en cero
  - [ ] El eje de frecuencias se construye lineal y después se **invierte**: queda descendente
  - [ ] Si la señal tiene longitud **par**, se descarta la última muestra antes de transformar y se duplica la última columna al final
  - [ ] El eje angular es `v_WAxis = (2π/N)·(0:N−1)·fs`
  - [ ] Devuelve **frecuencia en filas, tiempo en columnas**. La cabecera del `.m` dice lo contrario y **está equivocada**; el código hace `zeros(numel(v_FreqAxis), numel(v_TimeAxis))`

  Como todo son `np.fft.fft`, aritmética vectorial e `np.fft.ifft`, el GIL se libera y encaja bien en el orquestador.

  > **Ventaja de paso:** el problema nº 17 —las franjas falsas de PyWavelets por `precision=12`— **no puede ocurrir aquí**. Ese defecto viene de discretizar la wavelet con una malla fija; la Morse se evalúa directamente sobre el eje de frecuencias, así que no hay malla que se quede corta.

- [ ] **`filtro_iir(fs, f1, f2)`** — réplica de `f_GetIIRFilter` con `cheby2` y orden automático. Son **dos** cosas que hay que copiar, el diseño y la forma de aplicarlo.

  **El diseño**, tal como lo hace el MATLAB con sus valores por defecto:

  ```python
  nyq = fs / 2
  rp, rs, espacio = 0.5, 100.0, 0.5        # los del original
  # los bordes de la banda de rechazo van a +-0,5 Hz, escalados si la
  # frecuencia es menor que 1 Hz (el bucle `while s_LowFreq < 1` del .m)
  f_baja = f1 - espacio * 10 ** (-escala(f1))
  f_alta = f2 + espacio * 10 ** (-escala(f2))
  orden, wst = cheb2ord([f1/nyq, f2/nyq], [f_baja/nyq, f_alta/nyq], rp, rs)
  sos = cheby2(orden, rs, wst, btype="band", output="sos")
  ```

  > El MATLAB usa `zp2sos` + `dfilt.df2sos`, o sea secciones de segundo orden. Hay que usar `output="sos"` en SciPy por lo mismo: con `Rs = 100 dB` y la banda de rechazo a solo 0,5 Hz, los órdenes salen **altos** —26 para la banda 3-8 Hz y 155 para 25-250 Hz—, y en forma de coeficientes `b, a` eso sería numéricamente inestable.

- [ ] **`bifiltro(sos, sig)`** — réplica de `f_IIRBiFilter`. **No usar `sosfiltfilt`.**

  ```python
  y = sosfilt(sos, sig)
  y = sosfilt(sos, y[::-1])
  return y[::-1]
  ```

  `f_IIRBiFilter` hace exactamente eso: filtra hacia adelante, voltea, vuelve a filtrar y desvoltea, sin ningún relleno. `scipy.signal.sosfiltfilt` hace lo mismo **pero rellenando los bordes** (`padtype='odd'`), que es mejor práctica de procesamiento de señales pero **no es lo que hace la referencia**.

  Medido sobre una señal de prueba de 4 s a 1.000 Hz:

  | Banda | Orden | Correlación entre ambos | max&nbsp;&#124;dif&#124; |
  |---|---:|---:|---:|
  | 3-8 Hz (fase, defecto de PAC) | 26 | **0,9806** | 0,544 |
  | 25-250 Hz (amplitud) | 155 | 0,9960 | 0,568 |

  La diferencia en la banda de fase **no se concentra en los bordes**: está repartida por toda la señal. Y como ese filtro es el que produce la fase instantánea, y la fase decide en qué bin de los 100 cae cada muestra, usar `sosfiltfilt` cambiaría el agrupado de forma visible. Por eso se replica el flip-filter literal.

- [ ] **`fase_instantanea(sig, fs, f1, f2)`** — compone las dos anteriores y aplica `np.angle(scipy.signal.hilbert(·))`.
- [ ] **`agrupar_por_fase(tf, fase, nbins=100)`** — devuelve `(m_phase_av, v_phase_num)`. Por cada uno de los 100 bins entre −π y π, suma las columnas de la matriz tiempo-frecuencia cuyo instante cae dentro, y cuenta cuántas eran.
- [ ] **Reusar `tasa_efectiva()`** de `core/filters/wavelet.py`. Ya existe y resuelve el `srt`: el MATLAB calcula `srate/srt`, que es exactamente lo que hace esa función.
- [ ] Guardas contra bin vacío y contra desviación cero en el z-score.

---

## 4. Fase 2 — PAC, en `plugins/analysis/time_frequency/pac/compute.py`

Corresponde a `f_Phase_PAC` (164 líneas).

- [ ] **`pac_un_trial(ctx, sig, fs_calculado, fs, p1, p2, a1, a2)`** — recibe **un** trial ya elegido; quién lo elige es el plugin, según el selector. En este orden:
  1. [ ] Submuestrear con `tasa_efectiva`, sin antialias
  2. [ ] Fase instantánea en `[P1, P2]`
  3. [ ] `morse_tf` sobre `[A1, A2]` con **`n_freq = 4·(A2 − A1)`** y `cycles = 1`, devolviendo magnitudes
  4. [ ] Agrupar por los 100 bins de fase
  5. [ ] `m_phase_av = suma / cuenta`
  6. [ ] `hist = m_phase_av.sum(axis=0)` — un valor por bin
  7. [ ] **Z-score de cada fila** a lo largo de los bins → es lo que se dibuja como mapa
  8. [ ] Vector medio de acoplamiento: `mean(hist · e^{i·bins})` → magnitud y ángulo

### Salidas que hay que dibujar

El MATLAB abre **cuatro ventanas**. En 2.0 van **apiladas en el `plotArea`**, siguiendo el patrón de `open_signal` (`_relayout_charts`, varios gráficos en una sola vista VTK con los ejes de tiempo sincronizados). Hacen falta las cuatro:

- [ ] **Mapa fase-frecuencia** (el z-scoreado), eje Y «Frequency (Hz) - Log», eje X «Phase (rad)»
- [ ] **Histograma** de barras sobre los 100 bins
- [ ] **Vector medio tipo brújula**, con su magnitud y su ángulo
- [ ] **Figura de 4 paneles**: señal original, filtrada en fase, fase instantánea, filtrada en amplitud

> **Un defecto del MATLAB que no hay que replicar.** En la figura de 4 paneles, las líneas 126 y 134 hacen `fliplr` sobre un vector columna, que **no hace nada**. El filtrado que pretende ser de fase cero aplica en realidad el filtro dos veces hacia adelante y acumula retardo. Afecta solo a esa figura, no al cálculo de PAC. `f_IIRBiFilter`, que sí se usa para el cálculo, emplea `flipud` correctamente.

---

## 5. Fase 3 — PAC Average

Corresponde a `f_Phase_PAC_Average` (119 líneas). Es **idéntico** a PAC salvo en un punto.

- [ ] **`pac_promedio(ctx, data, ...)`** — acumula `m_phase` y `v_phase_num` sobre **todos** los trials y divide una sola vez al final. Es el mismo patrón de acumulador incremental de `wavelet_promedio`.
- [ ] `ctx.progress` por trial, y `ctx.cancelled` entre trial y trial
- [ ] **Corregir de paso:** el MATLAB calcula la transformada del trial 1 **dos veces** (en la línea 52, solo para conocer la forma de la matriz, y otra vez dentro del bucle). En 2.0 basta con reservar el acumulador en la primera iteración.

### Salidas

- [ ] Mapa fase-frecuencia + un subgráfico con `cos(bins)` debajo
- [ ] Histograma de barras
- [ ] Vector medio tipo brújula
- [ ] **Sin** la figura de 4 paneles — esa solo la tiene PAC

---

## 6. Fase 4 — MI (comodulograma), en `modulation_index/compute.py`

Corresponde a `f_PAC_sing` (90 líneas). Es **otro algoritmo**: barre una rejilla con filtros IIR y no usa wavelet.

- [ ] Añadirle a la interfaz el campo de frecuencia de muestreo que le falta
- [ ] **`comodulograma(ctx, sig, fs, p_ini, p_fin, pstep, a_ini, a_fin, astep)`**:
  - [ ] `phase_range = p_ini : pstep : p_fin`; cada frecuencia filtrada en **`[f, f+1]`** → Hilbert → `angle`
  - [ ] `amp_range = a_ini : astep : a_fin`; cada frecuencia filtrada en **`[f, f+10]`** → Hilbert → `abs` (envolvente)
  - [ ] `MI = |mean(amp · e^{iφ})|` — índice de Canolty
  - [ ] `MInorm = |Σ(amp · e^{iφ}) / Σ amp|` — variante de Özkurt
  - [ ] **Solo `MInorm` se dibuja.** `MI` se calcula y no se usa
- [ ] Salida: imagen de `MInorm`, eje Y «Freq Amplitude», eje X «Freq Phase»

### Dos trampas de MI

**Los anchos de banda son fijos.** `pstep` y `astep` solo mueven **dónde** se centra cada banda, no cuán ancha es: la de fase siempre mide 1 Hz y la de amplitud siempre 10 Hz. Si `astep < 10`, las bandas de amplitud **se solapan** y el comodulograma sale suavizado; lo mismo con `pstep < 1`.

**El bucle del filtrado de amplitud corre `1:178`, fijo**, ignorando el tamaño real del barrido:

```matlab
%for counta = 1:(size(amp_range,2)     <- el correcto, comentado y con un parentesis de menos
    for counta = 1:178                 <- lo que se ejecuta
```

Consecuencias:

- Si el barrido da **menos** de 178 frecuencias, `amp_range(counta)` se sale del arreglo y **MATLAB lanza un error de índice**
- Si da **más**, solo se filtran las primeras 178; el resto de `m_amp` se queda con los ceros de la preasignación, y después el cálculo del MI recorre el rango completo leyendo esos ceros

Con los valores por defecto de la interfaz:

| | |
|---|---|
| `phase_range = 0,1 : 0,1 : 10` | 100 frecuencias de fase |
| `amp_range = 10 : 0,5 : 500` | 981 frecuencias de amplitud |
| El bucle filtra | solo las primeras **178**, hasta **98,5 Hz** |
| Quedan sin calcular | **803 filas**, de 99 a 500 Hz, que salen en cero |

El comodulograma sería de 981 × 100, pero **solo el 18,1 % de sus filas tiene datos reales**. El eje dice que llega a 500 Hz y en realidad se acaba en 98,5.

En la práctica eso obliga a que `a_fin − a_ini ≥ 177 × astep`. Es la decisión pendiente de la sección 2.

En 2.0 se replicó tal cual: si el barrido da menos de 178 frecuencias se lanza un error **en español** explicando la condición, en vez del error de índice de MATLAB; y si da más, las filas que sobran quedan en `NaN` y el plugin **avisa** cuántas frecuencias quedaron sin datos y hasta dónde llegó el cálculo. Corregirlo es poner `LIMITE_BANDAS_AMPLITUD = None`.

### Dos límites del algoritmo que aparecieron al verificarlo

No son defectos de la implementación: son propiedades de `f_PAC_sing` que MATLAB tiene igual, y que conviene conocer antes de interpretar un comodulograma.

**1. Con bandas de amplitud de 10 Hz, solo se detectan fases por debajo de 5 Hz.**

Una modulación a `f_fase` crea bandas laterales a **±f_fase** de la portadora. Para que el filtro de amplitud las capture, su ancho tiene que ser de al menos `2 × f_fase`. Con los 10 Hz fijos de `f_PAC_sing`, el techo son **5 Hz de fase**.

Medido: correlación entre la envolvente que mide el algoritmo y el modulador real, para una portadora de 75 Hz en la banda `[70, 80]`:

| f_fase | Laterales | ¿Caben? | Correlación |
|---:|---|---|---:|
| 1,0 Hz | 74 / 76 | sí | **+1,0000** |
| 3,0 Hz | 72 / 78 | sí | **+1,0000** |
| 4,5 Hz | 70,5 / 79,5 | sí | +0,9998 |
| 5,0 Hz | 70 / 80 | justo | +0,9953 |
| **6,5 Hz** | 68,5 / 81,5 | **no** | **−0,0176** |
| **8,0 Hz** | 67 / 83 | no | +0,0059 |

El corte es nítido. **Importa para la tesis** porque los valores por defecto piden fases de 0,1 a 10 Hz: la mitad de ese rango no puede detectar nada. Y theta está entre 4 y 8 Hz, justo a caballo del límite — un acoplamiento theta-gamma a 7 Hz sería invisible para MI, aunque **PAC sí lo vería**, porque usa la wavelet sobre todo el rango de amplitud en vez de bandas fijas de 10 Hz.

**2. `MInorm` se sesga al alza cuando hay pocos ciclos del ritmo lento.**

Es el sesgo conocido de las medidas de longitud de vector medio con pocas muestras independientes. Medido con un acoplamiento construido en amplitud 75 Hz y fase 3,5 Hz:

| Duración | Fase más baja | Ciclos | ¿Encuentra el máximo donde debe? |
|---:|---:|---:|---|
| 3 s | 1 Hz | 3 | ❌ lo pone en (41,5 Hz · 1,0 Hz) |
| 3 s | 2 Hz | 6 | ✅ |
| 8 s | 1 Hz | 8 | ✅ |
| 8 s | 2 Hz | 16 | ✅ |
| 12 s | 2 Hz | 24 | ✅ |

Con tres ciclos el máximo sale en cualquier parte. A partir de unos seis es fiable. Con los valores por defecto —`Fq P1 = 0,1 Hz`— un trial de 3 segundos da **0,3 ciclos**, así que esa esquina del comodulograma no significa nada.

### Lo que se corrigió al probarlo en la aplicación (7 de octubre de 2026)

Tres cosas que solo salieron al abrir GammaLab y darle a *Generate*, no con la suite.

**1. La guarda de Nyquist rechazaba los valores por defecto.** ✅ corregido

Comprobaba la **última frecuencia del barrido** en vez de la última banda que se calcula de verdad:

```python
if rango_amplitud[-1] + ANCHO_BANDA_AMPLITUD >= nyquist:   # 500 + 10 = 510 > 500 -> error
```

Con los valores de fábrica —idénticos a los de MATLAB: `A 10:0,5:500`, remuestreo 1000— eso daba 510 Hz contra un Nyquist de 500 y abortaba el cálculo entero. Pero esa banda **nunca se filtra**: el tope de 178 corta en la banda `98,5–108,5 Hz`, y MATLAB tampoco le diseña filtro a nada por encima. La guarda ahora mira `rango_amplitud[n_calculadas - 1]`.

Sigue haciendo falta: con `A step = 3` la banda nº 178 llega a 551 Hz y ahí el filtro sí revienta.

> Por qué no lo vio la suite: los 23 escenarios de MI usaban un barrido corto para correr rápido y **ninguno probaba los valores con los que arranca el panel**. Además MI no tenía pruebas de núcleo, solo de interfaz. Se creó `test/plugins_test/test_modulation_index_core.py`, y la primera prueba es exactamente ese caso.

**2. Los `NaN` se dibujaban rellenos con el mínimo.** ✅ corregido

Las filas que el tope de 178 deja fuera se pintaban del color más bajo de la escala, así que el 82 % del comodulograma parecía «acoplamiento bajo» cuando en realidad ahí no se calculó nada. Se notaba en el tooltip: en `(3,6 Hz, 478,5 Hz)` mostraba `0.00200125`, que es el mínimo de la escala, no una medida.

MATLAB no hace eso. `f_ImageMatrix` dibuja con `imagesc` (línea 133), e `imagesc` deja los `NaN` **transparentes**: se ven del color del fondo. Ahora se replica con `SetNanColor` + `SetNanOpacity(0)`. Verificado leyendo los píxeles del render, no a ojo: la zona `NaN` pasó de `(0, 0, 128)` a `(250, 250, 250)`, que es el fondo exacto.

Además de ser fiel, hace evidente de un vistazo cuánto del gráfico está vacío por el tope de 178 — justo el dato que hay que tener delante para decidir qué hacer con ese número.

**3. Nada avisaba del sesgo de pocos ciclos.** ✅ añadido

El límite 2 de la sección anterior estaba documentado pero el programa no lo decía, y es el que más fácil lleva a una conclusión falsa: con los valores por defecto la esquina inferior izquierda del comodulograma sale roja y **no significa nada**.

`comodulograma` ahora devuelve `duracion_s` y `ciclos_banda_lenta`, y el plugin advierte cuando caben menos de `CICLOS_MINIMOS_FASE = 6` ciclos de la banda de fase más baja, diciendo a cuánto subir `Fq P1`. El umbral de 6 **es el que se midió** (tabla de arriba: 3 ciclos falla, 6 acierta), no un número redondo.

Esto es un **añadido nuestro**: MATLAB no comprueba nada y entrega un comodulograma que parece correcto. **No cambia el cálculo**, solo advierte. Los dos avisos —el del tope de 178 y el de los ciclos— van en un único diálogo, para no encadenar dos ventanas modales.

Cubierto por 8 pruebas nuevas de núcleo y 7 escenarios de interfaz (secciones J y K).


Las dos merecen ir a la conversación con la directora junto al `178`: la pregunta de fondo es si el ancho de 10 Hz debería ser configurable, y si conviene avisar al usuario cuando los parámetros caen fuera de lo que el algoritmo puede resolver.

---

## 7. Fase 5 — PAC Psel

Corresponde a `f_Phase_PAC_Pdetect` (522 líneas). **Va al final a propósito:** no es una variante de PAC, es otro camino entero y comparte muy poco con las fases 2 y 3.

Lo que lo distingue:

- [ ] Usa **Gabor** (`f_GaborAWTransformMatlab`), **no Morse** → hay que portar una segunda transformada
- [ ] `n_freq = 2·(A2 − A1)`, no 4· como en PAC
- [ ] **Concatena todos los trials** en una sola señal continua, en vez de trabajar por trial
- [ ] La banda gamma está **fija en 25–129 Hz**, ignorando `A1`/`A2`. Esos dos solo controlan el rango de la transformada (`ps_MinFreqHz`, `ps_MaxFreqHz`)
- [ ] Detección de picos y valles con `findpeaks` sobre la señal filtrada, selección de ciclos y alineación por evento
- [ ] Varias figuras, muchas comentadas en el original

> **Dos cosas del original que no hay que replicar.** Antes del `horzcat` hay un `A = 0`, así que la señal concatenada arranca con una muestra espuria en cero. Y la línea 41 llama a `fvtool(st_Filtg)`, que abre la ventana de análisis de filtros de MATLAB: es depuración que quedó en el código.

---

## 8. Fase 6 — Integración con el orquestador

Sigue el patrón validado en la Fase 3 del plan del orquestador.

- [ ] Las funciones de alto nivel llevan `ctx`, para avance y cancelación
- [ ] El plugin lee la interfaz, valida, hace `submit()` y dibuja en el slot de `finished`
- [ ] Los cuatro slots del patrón: `progress`, `finished`, `failed`, `cancelled`, cada uno con la guarda `if handle is not self._handle`
- [ ] El combo de tipo decide a cuál de las tres funciones llamar
- [ ] `get_analysis_params()` / `apply_analysis_params()` para que el proyecto los guarde y los restaure
- [ ] La barra de progreso con botón Cancelar funciona sola: se engancha a `TaskService.task_started` y no hay que hacer nada en el plugin

```python
handle = tasks.submit(cp.pac_promedio, owner=self.meta.id, ...)
handle.progress.connect(partial(self._on_pac_progress, handle))
handle.finished.connect(partial(self._on_pac_done, handle))
handle.failed.connect(partial(self._on_pac_failed, handle))
handle.cancelled.connect(partial(self._on_pac_cancelled, handle))
```

La prueba `ningun_plugin_crea_hilos_propios` avisa si alguien le pone un `QThread` propio.

---

## 8 bis. ⚠️ Tarea pendiente: generar la referencia de MATLAB

> **Esto lo tiene que hacer una persona con MATLAB.** No hay MATLAB ni Octave en el equipo de desarrollo, así que el paso de generar la referencia no se puede automatizar. Y aunque se instalara Octave no serviría: no abre los `.mlapp` de App Designer, le faltan `fdesign.bandpass`, `design()` y `dfilt.df2sos`, y aun arreglándolo el resultado sería *la referencia de Octave*, no la de MATLAB.

En `test/data/` hay ocho referencias (wavelet, FFT, PSD, ERP, promedio) pero **ninguna de PAC**. Sin ella no se puede cerrar la Fase 7.

### Qué hacer

1. Abrir `BOARD_FTD_PACC.mlapp` y cargar **`17308005.abf`**
2. Poner **Single Trial = 1** y los valores por defecto: **Sample Fq 2000, P1 3, P2 8, A1 25, A2 500**
3. Pegar esto en `f_Phase_PAC.m`, justo después de la línea 74 (`m_phase_av_aux_pre = m_phase_av_aux;`):

```matlab
%% ---- exportar referencia para Gamma Lab 2.0 ----
d = 'C:\Users\noah\Downloads\Gamma-Lab-2.0\test\data\';
writematrix(v_Data,        [d 'pac_entrada_matlab.csv']);
writematrix(srate,         [d 'pac_srate_matlab.csv']);
writematrix(v_Data_phase,  [d 'pac_fase_matlab.csv']);
writematrix(m_phase_av,    [d 'pac_mapa_matlab.csv'], 'Delimiter',';');
writematrix(fr(:),         [d 'pac_frecuencias_matlab.csv']);
writematrix(hist_pre_1(:), [d 'pac_histograma_matlab.csv']);
writematrix([real(v_pha_av_pre1) imag(v_pha_av_pre1)], [d 'pac_vector_matlab.csv']);
%% ------------------------------------------------
```

4. Presionar **PAC**. Quedan siete archivos en `test/data/`.

### Por qué se exporta también la entrada

**`pac_entrada_matlab.csv` es el más importante de los siete.** Es la señal ya submuestreada con la que MATLAB trabajó, y permite alimentar el código de 2.0 con **exactamente** lo mismo. Así, si algo no coincide, solo puede venir del algoritmo — no de que el recorte de trials sea distinto. Sin ella, una discrepancia sería imposible de atribuir.

### Lo que se deja fuera a propósito

La matriz completa de Morse (`m_tf_Data`) pesaría unos **200 MB** en CSV, porque es de 1.900 × 6.101. El mapa (`m_phase_av`) es de 1.900 × 100, unos 3 MB, y ya permite comparar el resultado. Si hace falta aislar la transformada, se pide después.

### Qué se hace con ellos

Una vez estén, se arma `test/plugins_test/test_pac_vs_matlab.py` con el mismo criterio que las pruebas del wavelet: correlación por fila contra el mapa, y comparación directa del histograma y del vector medio. Recordar que **no habrá igualdad bit a bit** (sección 2), así que el criterio es correlación, no igualdad.

---

## 9. Fase 7 — Verificación

- [ ] **Exportar desde MATLAB una matriz de referencia de `morse_tf` sola.** Es la pieza con más riesgo numérico y la única sin equivalente en ninguna librería; conviene verificarla aislada antes de componerla con el resto.
- [ ] Comparar `m_phase_av` y el histograma contra MATLAB con el mismo archivo y los mismos parámetros, por correlación
- [ ] Pruebas de `agrupar_por_fase` con señal sintética: una fase conocida tiene que caer en el bin esperado
- [ ] Pruebas de `morse_tf` con tonos puros: el máximo debe quedar en la frecuencia del tono
- [ ] Escenarios de interfaz como los de wavelet (`escenarios_wavelet.py` sirve de molde): que el cálculo corra fuera del hilo principal, que Cancelar cancele, que cerrar el proyecto a mitad no deje nada colgado, que un resultado tardío sin interfaz se descarte sin error

---

## 10. Orden recomendado y por qué

1. **Fase 1 — piezas compartidas.** Sin la Morse no hay nada que probar.
2. **Fase 2 — PAC.** Es el caso simple donde se valida la Morse contra la referencia.
3. **Fase 3 — PAC Average.** Una vez PAC funciona, es el acumulador y poco más.
4. **Fase 4 — MI.** Independiente: filtros IIR, sin wavelet. Puede ir en paralelo con las anteriores si hay dos personas.
5. **Fase 5 — PAC Psel.** El último: el más grande, con su propia transformada y su propia lógica de detección.

Empezar por Psel obligaría a escribir la Gabor y la detección de picos sin haber podido verificar nada en el caso simple.

---

## 11. Resumen de archivos

| Archivo | Estado |
|---|---|
| `plugins/analysis/time_frequency/pac/compute.py` | **Nuevo.** `morse_tf`, `agrupar_por_fase`, `promediar_bins`, `zscore_por_fila`, `vector_medio` y las funciones de alto nivel |
| `core/filters/iir.py` | **Nuevo.** `filtro_iir`, `bifiltro`, `fase_instantanea`, `envolvente`. En `core/` porque los comparten `pac` y `modulation_index`, que son plugins distintos |
| `plugins/.../pac/gabor.py` | **Nuevo**, solo para la Fase 5. En el plugin, no en `core/`: solo PAC Psel lo usa |
| (las de alto nivel van en el mismo `compute.py`) | `pac_un_trial`, `pac_promedio`, `pac_psel` |
| `plugins/analysis/time_frequency/pac/pac_plugin.py` | `submit()` + los cuatro slots + las cuatro salidas apiladas |
| `plugins/.../pac/pac_plugin_ui.py` | **Agregar el selector de trial con navegación** |
| `plugins/analysis/time_frequency/modulation_index/compute.py` | **Nuevo.** `comodulograma` |
| `plugins/.../modulation_index/modulation_index_plugin.py` | Campo de frecuencia de muestreo + `submit()` + slots |
| `plugins/.../modulation_index/modulation_index_plugin_ui.py` | **Agregar el campo de frecuencia de muestreo y el selector de trial** |
| `test/plugins_test/test_pac_compute.py` | **Nuevo** |
| `test/ui_test/escenarios_pac.py` | **Nuevo** |
