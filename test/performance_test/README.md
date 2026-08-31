# Suite de benchmarks de rendimiento

Mide, con datos reales (`test/data/17308005.abf`) y el código real de la
aplicación (nada mockeado), el tiempo de las operaciones que más le hacen
esperar al usuario en Gamma Lab: desde el arranque del kernel y la carga de
archivos, hasta el cómputo de cada plugin de análisis y el renderizado VTK de
los mapas 2D.

Esta suite está pensada para durar más que esta versión de la app: el objetivo
es correr exactamente los mismos benchmarks contra **Gamma Lab 2.0** cuando
esté lista, y comparar ambas corridas con `compare_report.py`. Ver
`docs/informe_rendimiento.tex` para el análisis completo de resultados y la
metodología de comparación.

## Estructura

| Archivo | Qué mide |
|---|---|
| `bench_common.py` | Infraestructura compartida: cronometraje, guardado de resultados, snapshot del entorno. No es un archivo de test. |
| `test_kernel_bench.py` | Arranque del kernel: descubrimiento de plugins, `PluginManager.load_all()`, `Kernel.register_plugin()`. |
| `test_io_bench.py` | Carga de archivos (`FileIOService.load_abf`), corte de trials (`cut_trials_single_channel`), `DataStore`. |
| `test_preprocessing_bench.py` | Filtro pasa-banda Butterworth (`Filter_plugin.run_filter`). |
| `test_compute_bench.py` | Cómputo numérico de los plugins de análisis: FFT, PSD (Welch), Wavelet (CWT). |
| `test_render_bench.py` | Renderizado VTK "lento" (bucle de Python píxel a píxel) de wavelet/wavelet_average/erp. |
| `test_vtk_adapters_bench.py` | Renderizado VTK "rápido" (vectorizado con `numpy_to_vtk`) de `core/utils/adapters.py`, más un micro-benchmark sintético que compara ambos patrones de forma aislada. |
| `compare_report.py` | Script standalone: imprime la tabla antes/después entre dos etiquetas. |
| `results/perf_results.json` | Resultados acumulados de todas las corridas, uno por etiqueta. |

## Uso

1. Correr contra el código actual y ponerle una etiqueta al run:

   ```powershell
   $env:GAMMA_PERF_LABEL = "gammalab_v1_baseline"
   pytest test/performance_test -s
   ```

2. (Este mes) Migrar/reescribir a Gamma Lab 2.0.

3. Correr la MISMA suite contra el código de 2.0, con otra etiqueta:

   ```powershell
   $env:GAMMA_PERF_LABEL = "gammalab_v2_baseline"
   pytest test/performance_test -s
   ```

   Si en 2.0 cambian nombres de módulos/funciones, los imports de cada
   `test_*.py` son el único lugar que hay que actualizar -- el resto
   (`time_block`, `record`, el formato de `results/perf_results.json`,
   `compare_report.py`) no depende de la versión de la app.

4. Comparar:

   ```powershell
   python test/performance_test/compare_report.py gammalab_v1_baseline gammalab_v2_baseline
   ```

Cada corrida se agrega a `results/perf_results.json` bajo su etiqueta --
correr con la misma etiqueta dos veces sobrescribe esa etiqueta, no las demás.
Si no se define `GAMMA_PERF_LABEL`, se usa `"baseline"`.

Cada corrida también guarda un snapshot del entorno (SO, CPU, versión de
Python/VTK/numpy/scipy) bajo la clave `"_entorno"` de su etiqueta -- los
tiempos de un benchmark solo son comparables si además se sabe si cambió la
máquina o las versiones de las librerías entre una corrida y otra.

## Notas

- `test_render_bench.py` y `test_vtk_adapters_bench.py` crean ventanas VTK
  reales en modo offscreen (`vtkRenderWindow.SetOffScreenRendering(1)`) -- no
  necesitan mostrar nada en pantalla, pero sí un stack gráfico/VTK funcional.
  En un entorno sin GPU/sin drivers gráficos puede tardar bastante en el
  primer render; en la máquina donde normalmente corre Gamma Lab funciona con
  normalidad.
- Los benchmarks de `wavelet_average` y `erp` recortan a 10-20 trials o al
  tope de downsampling que ya trae el propio plugin, para que la suite corra
  en segundos y no minutos -- son proporcionales, no absolutos, así que siguen
  sirviendo para comparar antes/después.
- `test_kernel_bench.py` NO benchmarkea la construcción de `MainWindow`
  (requiere una `QApplication` con event loop completo, no solo un stack VTK
  offscreen) -- solo el arranque del kernel y los plugins hasta el punto justo
  antes de crear la ventana principal. Es una limitación conocida, documentada
  también en `docs/informe_rendimiento.tex`.
- `test_io_bench.py` no cubre `FileIOService.load_edf`/`load_mat` porque
  `test/data/` no tiene ningún archivo `.edf`/`.mat` de referencia. Agregar
  uno es la forma más directa de extender esta cobertura.
