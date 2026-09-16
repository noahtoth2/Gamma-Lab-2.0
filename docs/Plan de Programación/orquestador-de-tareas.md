# El orquestador de tareas de GammaLab

*Una propuesta de diseño para la versión 2*

---

## De qué va esto

Hoy GammaLab hace las cuentas en el mismo hilo que dibuja la ventana. Cuando el investigador pide un wavelet, la aplicación se queda congelada hasta que termina: no responde, no se puede cancelar, no dice cuánto falta. La justificación del R55 lo resume mejor que yo: *"la interfaz se congela y el usuario cree que el programa falló"*.

No es que nadie lo haya intentado. De los 17 plugins, dos sí usan hilos —`wavelet_average` y `artifact_remove`—, pero cada uno resolvió el problema a su manera, ninguno tiene progreso real y ninguno se puede cancelar de verdad. Los otros quince no hacen nada.

La idea es dejar de resolver esto quince veces y resolverlo una sola. Eso es el orquestador: **un servicio que recibe los cálculos, los pone en cola, los ejecuta fuera del hilo de la interfaz, informa del progreso y los cancela cuando hace falta**. El CU-020 ya lo describe; esto es cómo lo construiríamos.

Y una aclaración desde el principio, porque es fácil confundirse: el objetivo no es que los cálculos vayan más rápido. Es que **la ventana no se congele** y que **la aplicación no reviente en equipos modestos**. Que algo vaya más rápido es un tercer objetivo, aparte, y solo se consigue en cuatro sitios muy concretos — de eso va la última sección.

---

## 1. Qué opciones hay en Python, y cuál elegimos

Lo primero es quitarse de encima un mito. Todo el mundo dice que en Python los hilos no sirven por el GIL. Es verdad a medias: **el GIL se libera dentro del código C de NumPy y SciPy**. Cuando llamas a `np.fft.rfft`, Python suelta el candado, se mete en C, hace la transformada y vuelve. Durante todo ese rato otro hilo puede estar trabajando.

Como aquí el 95 % del tiempo se pasa dentro de NumPy, SciPy y PyWavelets, los hilos son mucho más útiles de lo que sugiere el eslogan.

Con eso en mente, hay tres familias:

### Familia A — Hilos

`QThread`, `QThreadPool`, `threading`, `ThreadPoolExecutor`. Todos los hilos comparten la memoria del proceso: **los arrays no se copian**. Arrancar un hilo cuesta microsegundos.

**Es la que proponemos**, y hay un argumento que no es técnico sino práctico: **ya se usa en el código actual**. `wavelet_average_plugin.py:554` tiene un `QThread` y `artifact_remove_plugin.py:299` usa `moveToThread`. No estaríamos introduciendo tecnología nueva; estaríamos unificando lo que ya hay, que hoy son dos soluciones distintas para el mismo problema.

### Familia B — Procesos

`multiprocessing`, `ProcessPoolExecutor`, `joblib`. Esquivan el GIL por completo, pero se paga caro en este caso concreto:

- En Windows cada proceso arranca por `spawn`, que tarda entre medio segundo y dos segundos y vuelve a importar los módulos.
- Los argumentos se copian. Un escalograma son 32 MB, y hay que mandarlo de ida y de vuelta.
- Cuatro procesos trabajando en un wavelet son unos 400 MB solo en buffers. En un portátil de 8 GB con Windows, VTK y la señal ya cargada, eso no cabe.

O sea: la familia que parece más potente es justamente la que choca de frente con la restricción de que los equipos del laboratorio son modestos.

### Familia C — Las que descartamos

- **`asyncio`**: sirve para esperar muchas cosas a la vez, no para calcular. Aquí el I/O es un solo archivo. No aplica.
- **Dask, Ray, Celery**: están pensadas para repartir trabajo entre varias máquinas. Añaden peso de arranque y de memoria a una aplicación que ya va justa. Van en contra del objetivo.
- **El Python sin GIL de la 3.13**: académicamente es la respuesta elegante, pero no existen versiones de PyQt5 ni de VTK compiladas para eso. Hoy es inviable.

**Conclusión: hilos.** Es lo que ya funciona en el código, lo que menos memoria consume y lo único compatible con un ejecutable instalable.

---

## 2. Qué organiza el orquestador

Aquí está la pregunta de fondo: ¿el orquestador gestiona **plugins** o gestiona otra cosa?

Un plugin no sirve como unidad de trabajo, y la razón es simple: **no empieza ni termina**. Un plugin es una carpeta con su `properties.yml`, una clase y su interfaz gráfica. Se crea cuando arranca la aplicación y vive toda la sesión, con su widget guardado y su estado dentro. No se puede encolar algo así, ni medirle el progreso, ni cancelarlo.

Además, un plugin puede lanzar varios cálculos distintos —`wavelet` hace la transformada, la normalización y el escalado logarítmico— y un mismo cálculo puede servirle a varios plugins: `welch` lo usan `psd`, `psd_average` y `relative_psd`, con el código duplicado tres veces.

Así que la unidad no es el plugin. Es la **Tarea**.

### Qué es una Tarea

> Una **Tarea** es la unidad mínima de cómputo planificable: una función que transforma datos de entrada en datos de salida, sin tocar el estado compartido, interrumpible, y de la que se puede saber cuánto va a costar antes de ejecutarla.

Cinco características, y cada una está ahí porque habilita algo concreto:

**Es pura.** Con los mismos datos de entrada da el mismo resultado. No lee variables globales ni escribe en el `DataStore`.
→ Se puede probar aislada, reintentar y mover de hilo sin miedo.

**Es cerrada.** Recibe todo por parámetros. No alcanza al kernel ni al almacén de datos.
→ Mientras se ejecuta, nadie está escribiendo estado compartido. Es la respuesta al R54.

**Es agnóstica.** No importa PyQt ni VTK.
→ Puede correr en cualquier hilo. VTK y Qt obligan a vivir en el hilo gráfico; una tarea no.

**Es interrumpible.** Consulta de vez en cuando si la han cancelado.
→ Es lo que hace posibles el R46 y el CU-014.

**Declara su coste.** Sabe estimar su tiempo y su pico de memoria **a partir de sus parámetros**.
→ Permite avisar antes de empezar y decidir si cabe en el equipo.

Esta última es la que separa una Tarea de "una función cualquiera". Una función se ejecuta. Una Tarea, además, **se sabe describir antes de ejecutarse**.

### Y lo que no es

- **No es un plugin.** El plugin es el objeto con la interfaz; la tarea es el cálculo que ese objeto pide.
- **No es un proceso del sistema operativo.** El proceso es un mecanismo de ejecución. La misma tarea puede correr en un hilo o en un proceso sin que su definición cambie. Por eso conviene no llamarles "procesos": se confunde con `multiprocessing`.
- **No es una acción del usuario.** Un clic puede generar cero, una o varias tareas.

### La buena noticia

Contando lo que hay en el código, salen **13 cálculos**: cargar ABF, cargar EDF, cortar trials, remover artefacto, filtrar, FFT, FFT promedio, PSD, PSD promedio, PSD relativa, promedio de trials, wavelet y wavelet promedio. Coincide con la lista del R71.

**Once de esas trece ya son funciones puras.** `core/filters/trials.py`, `fileio_service.py`, `artifact_logic.py` y una docena de métodos `_compute_*` dentro de los plugins ya reciben NumPy y devuelven NumPy, sin tocar widgets. Solo dos necesitan trabajo de verdad: `average`, donde el cálculo es una línea suelta metida dentro del botón (`average_plugin.py:66`), y `erp`, que ni siquiera tiene función de cálculo porque el NumPy vive dentro del código que dibuja.

Dicho de otro modo: esto no es una reescritura. Es **formalizar una separación que el código ya insinúa**.

---

## 3. El orquestador no tiene una lista de tareas

Esta es la parte que más se malinterpreta, así que conviene decirla clara:

**El orquestador no conoce ninguna tarea. No detecta nada. No decide nada por su cuenta.**

No hay un archivo en el núcleo con las trece tareas apuntadas. **Todo lo que entra por `submit()` es una tarea, por definición.** Si un plugin no llama a `submit()`, su cálculo sigue corriendo en el hilo de la interfaz y el orquestador ni se entera de que existe.

¿Por qué no un registro central? Porque el **R77** dice que añadir un plugin nuevo no puede obligar a modificar el núcleo. Si existiera esa lista, cada plugin nuevo tendría que editarla, y el requerimiento se rompería. Cuando llegue el plugin de PAC con sus funciones propias, simplemente las manda por `submit()` y **no se toca una sola línea del núcleo**.

Cada llamada a submit() representa una unidad de trabajo que estás entregando al executor para que la ejecute.

### Cómo se enciende

Al arrancar la aplicación, `main.py` lo registra como un servicio más, al lado de los que ya hay:

```python
kernel.register_service("DataStore", DataStore())
kernel.register_service("FileIO", FileIOService())
kernel.register_service("TaskService", TaskService())   # ← lo nuevo
```

Y ya está. Levanta su pool de hilos y se queda **vivo y ocioso**. Se activa cuando alguien le pide algo.

### Cómo cambia un plugin

Así se calcula la FFT hoy, dentro del botón:

```python
def _on_calculate_clicked(self):
    X, fs, target = self._read_params()
    freq, mag, fs_eff = self._compute_fft(X, fs, target)   # ← aquí se congela
    self._plot_fft(freq, mag)
```

Y así quedaría:

```python
def _on_calculate_clicked(self):
    X, fs, target = self._read_params()
    h = self.tasks.submit(compute_fft, owner=self.meta.id,
                          X=X, fs=fs, target_fs=target)
    h.finished.connect(self._on_fft_done)

def _on_fft_done(self, result):
    freq, mag, fs_eff = result
    self._plot_fft(freq, mag)                              # ya existe
```

Es partir el botón en dos: lo que pide y lo que dibuja cuando llega la respuesta. La función `_compute_fft` se mueve tal cual a un archivo `compute.py` en la carpeta del plugin, sin cambiarle nada.

---

## 4. Las colas

### Dos filas, como dos cajas de supermercado

Una fila, una persona atendida a la vez, los demás esperan en orden de llegada.

- **Fila de cálculo**: wavelet, FFT, filtrar, promediar.
- **Fila de archivo**: abrir una señal del disco.

**Una sola a la vez en cada fila**, porque el CU-020 lo pide y porque dos wavelets simultáneos no caben en un portátil de 8 GB.

**Dos filas y no una**, porque calcular usa la CPU y abrir un archivo usa el disco: no compiten. Si fueran una sola, abrir un archivo tendría que esperar diez segundos a que terminara un wavelet, sin ningún motivo.

> **Desviación que hay que anotar:** el R71 lista la carga de señal como operación pesada, y el CU-020 dice que solo puede haber una pesada a la vez. Con dos filas eso se matiza a *"una operación pesada **de cómputo** a la vez"*. Conviene actualizar el texto del caso de uso para que diseño y requerimientos queden alineados.

### Un ejemplo

1. Pulsas **Wavelet**. La fila de cálculo está vacía, arranca. Aparece el progreso.
2. Sin esperar, pulsas **FFT**. La fila está ocupada, así que espera. La barra dice *"1 en cola"*.
3. Sin esperar, abres un **archivo**. Es la otra fila, está libre: arranca de inmediato, en paralelo con el wavelet.
4. Termina el wavelet, se dibuja el escalograma y la FFT arranca sola.

Durante todo eso la ventana sigue respondiendo. Hoy nada de esto es posible.

### Los estados

```
Encolada ──> Ejecutando ──> Completada
    │            │      └──> Fallida
    │            │      └──> Cancelada
    └──> Descartada
```

La diferencia entre **Descartada** y **Cancelada** no es un capricho: es literalmente la alternativa 1a del CU-014. Si la tarea todavía está esperando en la fila, se borra y ya — no hay ningún hilo que detener. Si ya arrancó, hay que avisarle y esperar a que se entere. Son dos cosas distintas y el diseño necesita distinguirlas.

### Dos reglas

**Reemplazo.** Pulsas Calcular, te arrepientes, cambias un parámetro y vuelves a pulsar. La primera solicitud sigue esperando en la fila y su resultado ya no le sirve a nadie: se descarta y entra la nueva. Sin esto la cola se llena de cálculos obsoletos.

**Cancelar al salir.** Te cansas de esperar y te vas a otro módulo. Al cambiar de módulo se cancelan todas las tareas de ese plugin, estén corriendo o esperando. Es el R46, y lo bonito es que el plugin no necesita saber que existen hilos: solo pone su nombre en cada solicitud y el orquestador se encarga.

### Lo justo del contrato

`submit()` devuelve un manejador con cuatro señales —`progress`, `finished`, `failed`, `cancelled`— y un `cancel()`. Nada más.

De ahí sale una consecuencia que vale la pena entender porque simplifica mucho el diseño. Las señales de Qt entre hilos se entregan al hilo de la interfaz. Si establecemos que **el único sitio donde se escribe en el `DataStore` es el slot de `finished`**, entonces todo se escribe siempre desde el mismo hilo. Eso cumple el R54 —*"un solo propietario escribe cada dato"*— **sin un solo cerrojo ni mutex**. Y de regalo: una tarea cancelada nunca emite `finished`, así que el *"descarta el resultado parcial sin escribirlo en el estado compartido"* del CU-014 sale gratis, sin código que lo implemente.

La fila misma, por cierto, tampoco necesita cerrojos: se manipula desde los botones, que viven en el hilo de la interfaz. Nadie más la toca.

### Un límite que hay que decir

Solo 4 de las 13 tareas tienen un bucle por dentro, y solo esas se pueden cancelar a mitad. Las otras nueve entran de un salto en código C —`np.fft.rfft`, `welch`— y no vuelven hasta terminar: solo se pueden descartar mientras esperan en la fila. En la práctica da igual, porque esas nueve tardan milisegundos, pero el CU-014 no hace esa distinción y el diseño sí debería.

---

## 5. Cuando no hay memoria suficiente

Esta sección es la que conecta todo con la realidad de los equipos del laboratorio.

### El problema, con números

Los valores por defecto del wavelet son `fmin=1, fmax=500`, lo que da **998 escalas**. Con un trial de 4050 muestras, PyWavelets reserva una matriz compleja de 998 × 4050, a 16 bytes por elemento: **65 MB**. Más el módulo, otros 32 MB. En total unos **100 MB para un solo trial**. Tolerable.

Pero `wavelet_average` hace eso mismo una vez por trial y **guarda todos los resultados en una lista**, y al final llama a `np.stack`, que copia el conjunto entero:

| Trials | En la lista | La copia | Pico |
|---|---|---|---|
| 10 | 323 MB | 323 MB | ~710 MB |
| 30 | 970 MB | 970 MB | **~2 GB** |
| 100 | 3,2 GB | 3,2 GB | revienta |

Y si el usuario sube `fmax` a 2000, un solo trial ya son 259 MB.

Este es, hoy, el problema más grave de la aplicación. Y no es de velocidad.

### Primera mitad: gastar menos

Cambiar *"guardar todo y luego apilar"* por *"ir sumando"*:

```python
acumulador += escalograma        # en vez de lista.append(escalograma)
```

Con eso el pico deja de depender del número de trials. Da igual si son 10 o 200: siempre ~100 MB. **De 2 GB a 100 MB**, y no tiene nada que ver con concurrencia.

Por eso conviene que la reducción incremental sea parte del **contrato** de las tareas que promedian, no una optimización que alguien recuerde aplicar.

### Segunda mitad: avisar antes

Cada tarea sabe estimar su pico a partir de sus propios parámetros. Para el wavelet es una multiplicación: número de escalas × muestras × 24 bytes.

Antes de encolar nada, el orquestador mira cuánta RAM hay libre (con `psutil`) y decide:

- **Cabe holgado** → arranca sin decir nada.
- **Va justo** → arranca, pero avisa en la barra de estado.
- **No cabe** → **no arranca**, y dice por qué.

Y lo importante es que el aviso sea útil, no genérico. Como el pico es proporcional al número de escalas, el mensaje puede ser exacto:

> *Este cálculo necesita 2,1 GB y hay 1,8 GB disponibles. Con fmax = 250 en lugar de 500 bajaría a 1,0 GB.*

La alternativa es que el investigador espere cuarenta segundos para encontrarse un `MemoryError` que se lleva por delante la sesión de trabajo. Un aviso en el segundo cero es infinitamente mejor.

> **Hueco que hay que cerrar:** esto no tiene requerimiento que lo respalde. El R11, el R45 y el R52 hablan de *liberar* memoria; ninguno de *negarse a empezar*. Haría falta uno nuevo, algo como: *"El sistema debe estimar la memoria requerida por una operación antes de ejecutarla y rechazarla cuando exceda la memoria disponible, indicando qué parámetro reducir"*. Tipo confiabilidad, prioridad alta.

---

## 6. Paralelismo dentro de una tarea

Hasta aquí todo iba de **no bloquear la ventana**, y eso aplica a las trece tareas. Esta última sección va de otra cosa: de **ir más rápido**, y eso solo aplica a cuatro.

El resto son llamadas únicas a NumPy o SciPy que ya están optimizadas en C. Repartirlas cuesta más de lo que ahorra.

Los cuatro sitios donde sí rinde:

| Tarea | Se parte por |
|---|---|
| `wavelet` | escalas de frecuencia |
| `wavelet_average` | trials |
| `artifact_remove` | trials |
| PAC (futuro) | pares de bandas |

### Tres reglas

**No anidar.** `wavelet_average` se puede partir por trials *y* por escalas a la vez. No hay que hacerlo: se parte solo por trials, que cuestan todos lo mismo y reparten bien, y la transformada queda en serie dentro de cada uno. Anidar multiplica la memoria sin ganar nada.

**Repartir intercalado, no por bloques.** La aplicación genera las escalas en orden ascendente, y calcular una escala grande cuesta más que una pequeña. Si partes en cuatro bloques contiguos, el último worker se queda con el grueso del trabajo y los otros tres esperan de brazos cruzados. La solución es dar a cada worker escalas salteadas —una de cada cuatro— para que todos reciban baratas y caras por igual.

**Los hilos salen de la RAM, no de los núcleos.** Aunque los hilos comparten memoria, cada uno reserva su propio buffer de trabajo. Cuatro hilos en el wavelet son 400 MB. Así que el número de hilos es `min(núcleos − 1, RAM libre ÷ coste por trozo)`. **Esta fórmula es la que impide que la propuesta deje el programa más pesado de lo que ya está.**

### Quién parte el trabajo

Lo hace el orquestador. La tarea solo **declara** por qué parámetro se puede dividir y cómo se recombina el resultado: concatenando (wavelet, PAC), promediando (wavelet promedio) o colocando cada trozo en su columna (artifact remove).

La ventaja de centralizarlo es que el límite de hilos por memoria queda impuesto **en un solo sitio**, y no depende de que cada tarea se acuerde de respetarlo. En un proyecto cuyo objetivo declarado es no reventar equipos modestos, eso pesa.

### Dos cosas por medir

Antes de cerrar la decisión conviene tener números reales, porque hay dos incógnitas que cambian conclusiones:

**Una.** Hoy `pywt.cwt` corre en su modo lento sin que nadie lo haya decidido. El valor por defecto es `method='conv'`, con un coste proporcional a escalas × muestras, y ninguno de los dos plugins pasa el parámetro. El otro modo, `method='fft'`, es de orden N·log N. Es **un solo argumento**, y probablemente dé más ganancia que cualquier paralelismo.

**Dos.** Con el modo actual no sabemos si `np.convolve` libera el GIL, y de eso depende que partir el wavelet en hilos sirva de algo o no sirva absolutamente de nada. Con `method='fft'` la duda desaparece, porque `np.fft` sí lo libera. Las dos cosas convergen: cambiar el modo acelera el cálculo **y** hace que los hilos funcionen.

Ambas mediciones son de una tarde.

---

## Una dependencia que no es parte de esto, pero hay que decirla

El orquestador saca los cálculos del hilo de la interfaz. Lo que **no** puede sacar es el dibujo, porque VTK obliga a llenar sus estructuras desde el hilo gráfico.

Y ahí hay un problema serio: el código llena las imágenes de VTK punto por punto desde Python. En el wavelet son **cuatro millones de llamadas**, que son varios segundos de ventana congelada — y en `wavelet_average` eso ocurre *después* del hilo, justo cuando el usuario cree que ya terminó.

El R59 ya exige hacer esas conversiones en bloque, y el proyecto **ya tiene la solución escrita y en uso** en `core/utils/adapters.py`. Pero mientras no se aplique, el investigador va a seguir viendo la aplicación congelada, por mucho orquestador que haya.

No es parte de esta propuesta, pero sí es condición para que se note.

---

## En resumen

- **Hilos**, porque es lo que ya funciona en el código y lo que menos memoria gasta.
- La unidad es la **Tarea**, no el plugin: una función pura que sabe lo que cuesta.
- **No hay lista de tareas**: todo lo que pasa por `submit()` lo es, y así un plugin nuevo no obliga a tocar el núcleo.
- **Dos filas**, una cosa a la vez en cada una, con estados que distinguen descartar de cancelar.
- **Avisar antes** cuando un cálculo no cabe en memoria, en vez de reventar a los cuarenta segundos.
- **Partir el trabajo solo en cuatro sitios**, con el número de hilos atado a la RAM disponible.

Y lo que hay que tener presente todo el tiempo: el orquestador **organiza**. Lo que de verdad **optimiza** son tres cosas concretas — el modo de la transformada wavelet, la suma incremental en vez de apilar, y las conversiones a VTK en bloque. Ninguna de las tres es concurrencia.
