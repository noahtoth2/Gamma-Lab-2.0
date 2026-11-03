# Inventario de GammaLab 2.0
85 clases, 184 funciones, 916 métodos

## main.py
  función main()
  función loadStyleSheet()

## app/view/main_window.py
  clase MainWindow
    método __init__()
    método on_plugin_registered()
    método refresh_plugin_search()
    método switch_section()
    método add_plugin_button()
    método _plugin_tooltip() — Rich-text tooltip: bold plugin name, description wrapped into a narrow column.
    método _update_plugin_button_selection() — Check only the ribbon button of the active plugin (outlined via QSS).
    método _build_icon_arrow_pair() — Icon button + a separate small arrow button that opens `menu`, with a real
    método _start_measurement() — Arm interactive 2-point picking on the last chart view visited.
    método _build_measurement_button() — Icon-only button that arms an interactive measurement (click = start
    método _build_slope_button() — Slope icon (click = start a 2-point slope) + arrow (2 trials / all trials).
    método _build_amplitude_button() — Amplitude icon (click = start an amplitude measurement), built like slope.
    método _build_static_tool_button() — Build a ribbon button not backed by a plugin (e.g. delete, zoom).
    método _get_active_measure_service() — MeasurementService of the last chart-bearing view the user visited.
    método _refresh_measurement_tables() — Reload the Slope/Amplitude results tables if they're already built.
    método _on_delete_last_measurement()
    método _on_delete_all_measurements()
    método _on_show_all_measurements()
    método _on_hide_all_measurements()
    método _build_delete_button() — 'delete last / delete all' dropdown for the Measurements group.
    método _build_toggle_overlay_button() — Show/hide measurement overlays.
    método _build_delete_toggle_stack() — Stack 'delete' above 'show/hide', vertically, as a compact pair.
    método _build_zoom_button() — Zoom popup: '100%' field + '+' / '-' / 'restore' controls.
    método clear_plugin_area()
    método _liberar_graficos()
    método _cancel_tasks_of()
    método show_plugin_widget()
    método eventFilter()
    método _position_background_logo() — Center and scale watermark inside the workspace area.
    método _has_any_signal()
    método _has_active_signal()
    método _has_active_trials()
    método _update_background_logo_visibility() — Show watermark when there is no active signal and not in Home.
    método _build_home_welcome_widget() — Build centered Home welcome with big title, small subtitle and a divider line.
    método _update_home_welcome_visibility() — Home welcome is visible only in Home when no plugin UI is active.
    método show_watermark()
    método hide_watermark()
    método _make_translucent() — Return a copy of the pixmap with a global opacity applied.
    método _schedule_watermark_autohide() — Wait for the plugin to create its content (e.g., VTK) and hide the watermark.
    método on_button_click()
    método setup_file_menu() — Build the dropdown menu shown when clicking the 'File' tab.
    método on_save_project_clicked() — File > Save: write the .glab to its existing location (or prompt if new).
    método on_save_project_as_clicked() — File > Save as: always prompt for a location and (re)create the project there.
    método _guardar_proyecto() — R04: copying the signal into the project leaves the UI thread (progress bar
    método _copia_terminada()
    método _terminar_guardado()
    método _guardado_fallido()
    método on_open_project_clicked() — File > Open project: pick a .glab and restore its signal + measurements.
    método abrir_proyecto_desde_ruta()
    método _abrir_proyecto()
    método _finish_open_project()
    método _fail_open_project()
    método liberar_senal_anterior() — Suelta la señal que hay cargada y todo lo que depende de ella (R11, R52).
    método mostrar_bienvenida_inicial() — R10: la primera vez que se ejecuta la aplicación explica las funciones básicas. Devuelve si se mostró.
    método cerrar_proyecto_para_nueva_senal() — Cargar otra señal equivale a cerrar el proyecto abierto (R11, R12): avisa y pide guardar si hay cambios.
    método on_close_project_clicked() — File > Close project: forget the project location and free the active signal.
    método _reset_all_plugin_widgets()
    método _reset_plugin_qt_vtk_state()
    método on_exit_clicked() — File > Exit: same unsaved-changes guard as Close Project, then quit.
    método _on_task_started() — Engancha la barra de progreso a la tarea que acaba de encolarse.
    método _nombre_de_plugin() — El `owner` de una tarea es el id del plugin; para la interfaz se
    método _cancel_all_tasks()
    método _any_background_worker_running()
    método _stop_all_background_workers()
    método _confirm_discard_unsaved_changes() — Ask Save/Don't Save/Cancel if dirty; True means OK to proceed.
    método _on_project_changed() — ProjectService callback: refresh title bar + Explorer after open/save/rename/close.
    método _on_project_name_edited() — User double-clicked the project name in the title bar and typed a new one.
    método _update_title_bar_signal_name() — Reflect the active signal's real file name in the title bar.
    método _update_title_bar_project_name()
    método show_status() — Mensaje en la barra de estado, coloreado por severidad (QSS
    método _on_status_message_changed()
    método _set_severity()
    método _refresh_trial_indicator() — Pide al plugin visible su estado de trial y lo muestra. Sin plugin
    método _default_trial_state()
    método format_trial_state()
    método _update_trial_indicator()
    método on_open_signal_clicked() — File > Open signal: show the channel/signal preview and pop the file picker.
    método on_kernel_event() — Listen to events emitted by the Kernel.
    método setup_sidebar_functionality()
    método toggle_sidebar_collapse()
    método update_signal_list() — Update logo/watermark visibility depending on loaded signals.
    método toggle_results_panel() — Show/hide the bottom Results panel, refreshing its data on open.
    método _ensure_results_tabs() — Embed the real Slope/Amplitude plugin widgets (full table + CSV export) as tabs.
    método refresh_results_panel() — Reload both results tables from DataStore['measurements'].
    método _on_export_results_csv() — '...' menu: export whichever results tab (Slope/Amplitude) is active.
    método _on_export_results_xlsx() — '...' menu: export whichever results tab (Slope/Amplitude) is active to Excel.
    método setup_explorer_section() — Build the Explorer: a real filesystem view rooted at the open project's folder.
    método _on_explorer_double_clicked() — Open a file from the Explorer with whatever app the OS associates with it.
    método _on_explorer_context_menu() — Right-click in the Explorer: item -> Rename/Copy/Paste; empty space -> New Folder.
    método _explorer_copy_path() — Put the file/folder's path on the system clipboard as a file URL.
    método _explorer_delete_path() — Delete a file/folder from the Explorer, after confirmation.
    método _explorer_paste_into() — Copy whatever file/folder is on the clipboard into target_dir.
    método _explorer_create_new_folder() — New Folder in the currently browsed project folder, ready to rename.
    método _explorer_unique_path() — Append ' (2)', ' (3)', ... if `path` already exists.
    método set_explorer_root()
    método _explorer_hide_siblings()
    método _on_explorer_directory_loaded()
    método _on_explorer_rows_inserted()
    método _on_app_about_to_quit() — Shut down plugins and their UI safely. Idempotent.
    método _finalize_all_vtk_render_windows()
    método closeEvent()
    método _get_registered_plugin_names() — Obtiene los nombres de todos los plugins registrados (cualquier categoría).
    método setup_plugin_search() — Configura el autocompletado y la navegación.
    método _open_plugin_from_search() — Abre el plugin seleccionado en las sugerencias.
    método _search_exact_plugin() — Abre el plugin si el texto coincide con su nombre.

## app/view/main_window_ui.py
  clase Ui_MainWindow
    método setupUi()
    método retranslateUi()

## app/view/splash_screen.py
  clase SplashScreen — Startup splash: background image plus a progress bar and status line.
    método __init__()
    método set_progress()
    método drawContents()

## app/view/widgets/editable_label.py
  clase _RenameLineEdit — QLineEdit that reports Escape so the caller can cancel the rename.
    método keyPressEvent()
  clase EditableLabel — QLabel that turns into a QLineEdit on double-click, for inline renaming.
    método __init__()
    método text()
    método setText()
    método setEditableValue()
    método _start_edit()
    método _cancel_edit()
    método _commit_edit()

## core/filters/artifacts.py
  función _time_window_indices() — Return indices [i_a, i_b) for window [a, b] (swap if b<a).
  función _fill_nan_segments() — Replace NaN/Inf segments column-wise using interpolation so downstream analysis
  función medidas_del_segmento() — Medidas del segmento que `calcular_modificacion` va a tocar, sin tocarlo.
  función calcular_modificacion() — Devuelve una copia modificada de `trials` (muestras × trials activos), o None si
  función crear_derivado() — A copy of a TrialDataset that owns its data, to write a preprocessing result into (R79).
  función receta() — Describe una modificación con lo justo para poder repetirla.
  función receta_filtro() — Receta de un filtrado aplicado a los trials (R79): se reaplica igual que las de artefactos.
  función columnas_activas() — Columnas del TrialDataset base que estaban activas con esos descartes.
  función reaplicar_modificaciones() — Reaplica en orden las modificaciones guardadas sobre un TrialDataset.

## core/filters/bandpass.py
  función filtrar_banda() — Butterworth band-pass con `sosfiltfilt` (fase cero). Lanza ValueError con parámetros inválidos.
  función filtrar_columnas() — Filtra cada columna (trial) de una matriz (muestras, trials). Devuelve una copia, o None si se canceló.

## core/filters/gabor.py
  función gabor_tf() — Transformada tiempo-frecuencia con wavelet de Gabor (gaussiana modulada).
  función gabor_en() — La misma transformada, sobre **un eje de frecuencias dado**.

## core/filters/iir.py
  función _escala_decimal() — Cuantos decimales hay que bajar para que `f` llegue a 1.
  función tope_banda_alta() — La frecuencia alta mas grande que `filtro_iir` admite a `fs`.
  función _disenar() — El diseno de verdad. Separado para poder memorizarlo (ver `filtro_iir`).
  función filtro_iir() — Pasa-banda Chebyshev II con orden automatico, como `f_GetIIRFilter`.
  función olvidar_filtros() — Vacia la cache de disenos. Para las pruebas y para liberar memoria.
  función estado_de_la_cache() — Aciertos, fallos y cuantos disenos hay guardados.
  función filtro_butterworth() — Pasa-banda Butterworth de orden fijo, como el que `f_Phase_PAC` usa para
  función bifiltro() — Filtrado bidireccional literal, como `f_IIRBiFilter`.
  función fase_instantanea() — Fase instantánea de la señal dentro de la banda `[f1, f2]`, en radianes.
  función envolvente() — Envolvente de amplitud dentro de la banda `[f1, f2]`.

## core/filters/measurements.py
  función two_point_metrics() — p1, p2: tuples (x, y)
  función _slice_window() — Return (i0, i1) and views xs[i0:i1], ys[i0:i1] with x1<=x<x2.
  función amplitude_in_window() — Peak-to-peak amplitude in [x1, x2].

## core/filters/trials.py
  función mv_to_unit() — Convert a value in mV to `unit` (V, mV, uV/µV, nV).
  función _detect_onsets_abs() — Detect rising edges where |signal| crosses from <= threshold to > threshold.
  función _assemble_trials_general()
  función _group_onsets_indices() — Return 'group_starts': indices (in the onsets list) of the first onset of each group.
  función _compute_windows() — Compute windows [a,b) in sample indices for each trial to extract,
  función _extract_trials_matrix() — Extract each window [a_clip, b_clip) from y_tgt and place it in a padded column.
  función cut_trials_single_channel()

## core/filters/wavelet.py
  función _sin_log()
  función eje_frecuencias() — Lineal: descendente, 2 filas por Hz. Logarítmica: ascendente, VOCES_POR_OCTAVA filas por octava.
  función tasa_efectiva() — La tasa que de verdad queda al submuestrear, y el factor usado.
  función compute_wavelet()
  función normalize_tf()
  función scale_log()

## core/kernel.py
  clase Kernel
    método __init__()
    método register_plugin()
    método get_plugins()
    método get_plugin()
    método get_plugins_by_category()
    método load_and_register() — Dynamically load a plugin from a Python module and register it.
    método stop_plugins()
    método register_service()
    método get_service()
    método emit_event()

## core/model/signal_dataset.py
  clase SignalDataset
    método add_trial_dataset() — Guarda un juego de trials, **reemplazando** el anterior del mismo canal.
    método __olvidar_derivados() — Descartes y cachés de un canal, fuera: ya no corresponden a nada.
    método replace_trial_datasets() — Swap out all TrialDatasets at once (e.g. after regenerating them
    método set_sampling_rate() — Public API to correct the sampling rate (R67): no caller should
    método restore_original_sampling_rate() — Restore the sampling rate auto-detected from the file header at load time.
    método number_of_trials_dataset()
    método get_original_trials() — The cut trials as they were generated, never modified by preprocessing.
    método get_derived_trials() — The derived set of a (file, channel), or None if nothing was derived.
    método register_derived_trials() — Registers the result of a preprocessing operation as the active set of its channel.
    método discard_derived_trials() — Drops the derived set so the original is served again. True if there was one.
    método get_all_trials_datasets() — All generated TrialDatasets, in generation order (for project save/restore).
    método get_discarded_trials_map() — Discarded-trial indices per (source, channel) key (for project save/restore).
    método get_active_trials() — Los trials activos de un archivo y un canal, ya sin los descartados.
    método get_active_trial_indices() — Indices **originales** de los trials que `get_active_trials` devuelve.
    método discard_trial() — Discard a specific trial from the given channel.
    método include_trial() — Re-include a previously discarded trial.
    método clear_discarded_trials() — Clear all discards and cache.
    método is_trial_discarded()
    método __invalidate_cache()

## core/model/trial_dataset.py
  clase TrialDataset
    método __post_init__()

## core/plugins/interfaces.py
  clase IPlugin
    método __init__()
    método olvidar_senal() — Suelta lo que el plugin guardó de la señal que se va (R11, R52): los datasets y el último resultado.
    método name() — Display name for UI (from properties.yml).
    método category() — Plugin category (from properties.yml).
    método subcategory() — Plugin subcategory (from properties.yml).
    método description() — Short help text shown as tooltip (from properties.yml).
    método icon() — Absolute path to the icon (inside the plugin folder).
    método _log()
    método _notify() — Mensaje breve en la barra de estado, coloreado por severidad.
    método crear_selector_de_trials() — Añade al panel de parámetros la lista de trials que participan (R27). Requiere `self.ui.paramsLayout`.
    método elegir_trials() — Aplica la selección de trials a la matriz (muestras, trials).
    método settings() — Servicio de ajustes del núcleo (R69): los módulos lo piden al Kernel, no crean el suyo.
    método get_datastore() — Obtain the DataStore service from the kernel.
    método run_task() — Runs `fn(**kwargs)` in the TaskService and calls `on_done(result)` on the UI thread.
    método mark_project_dirty()
    método get_active_signal()
    método get_active_trials() — Return the active trials for the current signal.
    método get_trials_de_canal() — Los trials de **un canal concreto**, no los del último generado.
    método _active_trials_quiet() — (senal, trials activos) sin avisar al usuario si faltan.
    método build_trial_state() — Estado del trial actual con la numeracion de la aplicacion:
    método publish_current_trial() — Publica en que trial se esta trabajando: lo guarda en el DataStore
    método trial_state_from_used() — Estado del indicador a partir de un registro `trials_used`.
    método current_trial_state() — Lo que el indicador debe mostrar cuando este plugin esta visible.
    método on_kernel_event()
    método initialize()
    método start() — Initialize the plugin with the kernel and register for active-signal change events.
    método stop() — Invoked when the kernel stops plugins.
    método get_widget() — Return the widget associated with the plugin.
    método process() — Process data sent by the kernel or other plugins.

## core/plugins/loader.py
  función _ensure_root_on_path() — Add the project root to sys.path so imports like `interfaces`
  función _load_meta()
  función _import_class_from_dir() — Search for class `class_name` inside the plugin folder without assuming
  función discover() — Recursively walk `plugins_root` and consider a plugin any folder

## core/plugins/manager.py
  clase PluginManager
    método __init__()
    método load_all()
    método all()
    método get()

## core/plugins/meta.py
  clase PluginMeta
    método icon_path()

## core/services/compartidos.py
  función registrar_servicios_compartidos() — Registra "Settings", "Export" y "Measurement". El "DataStore" tiene que estar registrado antes.

## core/services/data_store.py
  clase EscrituraNoPermitida — Alguien que no es el propietario intentó escribir en el DataStore (R54).
  función _escribe() — Marca un método como escritura: exige ser el hilo propietario y toma el candado.
  clase DataStore — Estado compartido de la sesión (R54).
    método __init__()
    método _exigir_propietario()
    método reasignar_propietario() — El hilo que llama pasa a ser el único escritor (p. ej. un DataStore creado en otro hilo).
    método dueno_de()
    método get()
    método has()
    método items()
    método get_signals() — Todas las señales guardadas (instancias de SignalDataset).
    método get_active_signal() — La señal activa (SignalDataset), o None si no hay.
    método get_active_signal_key()
    método is_active_signal()
    método set()
    método remove()
    método add_signal() — Añade una señal con el nombre del archivo (o una clave generada). Devuelve la clave.
    método set_active_signal() — Fija la señal activa. ValueError si la clave no existe o no es una señal.
    método release_signals() — Quita del DataStore las señales (con sus trials y derivados) salvo la de la clave `conservar`.
    método clear_active_signal() — Quita la referencia a la señal activa (no la borra del DataStore).

## core/services/export_service.py
  clase ExportService — Servicio de exportación del núcleo (R69): una sola instancia, registrada en el Kernel.
    método __init__()
    método _proyecto_abierto()
    método carpeta_de_exportacion()
    método recordar_carpeta()
    método para() — El exportador de una ventana gráfica.
  clase Exportador — Image and table export for one VTK view.
    método __init__()
    método export_image() — Export the VTK window to an image (png/jpg/jpeg/bmp/tiff).
    método export_emf() — Export the active chart as an Enhanced Metafile: axes, ticks, labels and
    método export_sections() — Export a result made of several tables (parameters, summary, matrices...).
    método _heatmap_sections() — The matrix behind a heat map: one row per Y value, one column per X value.
    método _export_heatmap_table()
    método _share_x_axis() — One X column plus one Y column per series, if all series share the same X.
    método export_table() — Export data (all series) from the active chart to csv/xlsx/json.

## core/services/fileio_service.py
  clase FileIOService — File readers. Each loader returns a SignalDataset.
    método load_abf()
    método load_edf()
    método load_mat() — Load a MATLAB (.mat) file and convert it into a SignalDataset.

## core/services/measurement_service.py
  clase MeasurementService — Servicio de medición del núcleo (R69): una sola instancia, registrada en el Kernel.
    método __init__()
    método _leer()
    método _escribir()
    método sesion_para() — La sesión de medición de una ventana gráfica; reemplaza a la anterior de esa ventana.
    método sesion_de()
  clase SesionDeMedicion — 2-point measurements for one view, with per-trial persistence and rebuildable overlays.
    método __init__()
    método set_context()
    método _context_matches()
    método clear_visual_overlays() — Clear ONLY visuals (overlays), without touching the datastore.
    método rebuild_overlays_for_current_context() — Rebuild overlays for ALL measurements whose ctx metadata matches
    método _dbg()
    método _notify_change()
    método state()
    método start()
    método cancel()
    método on_left_press()
    método on_left_release()
    método _get_current_ranges() — Always read current chart ranges (after zoom/pan).
    método _vec2_to_xy()
    método _save_axes_ranges()
    método _plot_rect_pixels()
    método _plot_to_screen()
    método _screen_to_plot()
    método _load_reference_data_for_pick()
    método _pick_nearest_data_point()
    método _save_measurement()
    método _finalize()
    método _suspend_left_actions()
    método _vtk_has_set_visible()
    método _set_plot_visible()
    método set_overlay_visible()
    método toggle_overlay()
    método _next_color()
    método _make_table_2pts()
    método _add_overlay_for_points()
    método _detach_overlay()
    método _remove_overlay_by_id()
    método remove_last_measurement()
    método remove_measurement_by_id()
    método clear_all_measurements()
    método on_chart_changed() — Invoked by the menu when the chart is replaced (new trial/view).
    método _dump_chart_state()
    método _compute_amplitude_window() — Use self._ref_data (xs/ys) to compute amplitude in window [x1,x2].
    método _nearest_index()
    método _compute_and_save_slopes_each_trial_by_index()

## core/services/project_service.py
  clase _CopiaCancelada
  clase TrabajoGuardado — Lo que `iniciar_guardado` decidió: la señal, la copia pendiente y dónde estaba el proyecto.
  función _is_system_folder() — True if `folder_str` is a filesystem root or an OS-provided special
  clase ProjectService
    método __init__()
    método default_project_name()
    método set_project_name()
    método mark_dirty() — Flag that something changed (e.g. a measurement) since the last save.
    método is_open()
    método archivos_dir() — Folder where exports should land. Created on demand.
    método _notify()
    método _datastore()
    método save() — Save to the already-known project location, or fall back to Save As.
    método save_as()
    método _guardar_sincrono()
    método iniciar_guardado() — Decide dónde se guarda. Devuelve un `TrabajoGuardado`, o None si el usuario canceló.
    método completar_guardado() — Escribe el manifiesto (rápido, lee el estado de los plugins). Hilo de la interfaz.
    método revertir_guardado() — El guardado se canceló o falló: el proyecto sigue donde estaba.
    método copiar_senal() — Copia por bloques, con progreso y cancelación. Devuelve False si se canceló.
    método _write_manifest()
    método _analysis_to_json()
    método _trials_to_json()
    método _copy_signal_into_project()
    método _copiar_si_cambio()
    método _misma_copia() — El archivo ya está en el proyecto tal cual (copy2 conserva tamaño y fecha): no se vuelve a copiar en cada guar
    método _measurement_to_json()
    método _measurement_from_json()
    método preparar_apertura() — Lee el manifiesto y el archivo de la señal sin tocar el DataStore ni la interfaz.
    método senal_faltante() — Nombre de la señal que el proyecto referencia y no se encontró, o None (R78).
    método open()
    método _leer_senal() — Lee el archivo de la señal. No toca el DataStore, así que puede correr en un hilo.
    método _registrar_senal() — Registra la señal leída en el DataStore y la deja activa (hilo de la interfaz).
    método _restore_trials()
    método _restore_analysis()
    método close()

## core/services/settings_service.py
  clase SettingsService — Simple service to save and load persistent settings in a JSON file.
    método __init__()
    método load() — Load the file if it exists.
    método save() — Persist current settings to the file.
    método get() — Get a stored value.
    método set() — Set a value and persist it.

## core/services/task_service.py
  clase TaskContext
    método __init__()
    método cancelled()
    método progress()
  clase TaskHandle
    método __init__()
    método cancel()
  clase _Task
    método __init__()
  clase _Worker
    método __init__()
    método run()
  clase TaskService
    método __init__()
    método submit()
    método cancel_all_from()
    método has_active_tasks()
    método pending_count()
    método _discard_queued_from()
    método _start_next_if_idle()
    método _release_thread()
    método _cancel()
    método _detach_if_still_running()
    método _on_worker_done()
  función _accepts_ctx()

## core/utils/adapters.py
  función dataset_to_vtk_table() — Convert the dataset to a vtkTable:
  función trials_matrix_to_vtk_table() — Create a vtkTable: col 0 = 'time', cols 1..T = trial_j

## core/utils/assets.py
  función icon_from_plugin()

## core/utils/autoprueba.py
  función programar() — Empieza a comprobar cuando arranca el bucle de eventos.

## core/utils/ayudas.py
  función _controles()
  función _rotulo_previo() — Texto del rótulo que precede al control en su fila, si lo hay.
  función descripcion_de()
  función completar_ayudas() — Pone descripción emergente a los controles de `raiz` que no la tienen. Devuelve cuántos completó.
  función sin_ayuda() — Controles de `raiz` sin descripción emergente.

## core/utils/chart_coords.py
  función _xy()
  función plot_rect_pixels() — Rectangulo del area de trazado (x_min, x_max, y_min, y_max) en pixeles
  función _axis_range()
  función current_ranges() — Rangos visibles de los ejes inferior e izquierdo (tras zoom/pan).
  función _interp()
  función screen_to_plot() — Pixel de la escena -> (x, y) en unidades de los ejes. None si el punto
  función chart_at_pixel() — El grafico cuya area de trazado contiene el pixel (para paneles con
  función axis_titles() — Titulos de los ejes inferior e izquierdo ("" si no tienen).

## core/utils/cursor_readout.py
  función format_value() — Numero corto y legible: 0.2341, -12.08, 1.234e-05.
  función format_readout()
  función punto_mas_cercano() — (x, y) del punto de una curva del grafico que esta mas cerca de (x, y); None si no hay curvas.
  clase CursorReadout
    método attach() — Instala (una sola vez por widget) la lectura del cursor.
    método __init__()
    método _on_mouse_move()
    método eventFilter()
    método _charts()
    método _status_label()
    método _place_overlay() — Esquina superior derecha del area de trazado del grafico bajo el
    método _ensure_overlay()
    método _show()

## core/utils/emf_writer.py
  función _rgb()
  función _pad4()
  función _medidor() — Devuelve `ancho(texto)` en píxeles para Arial de `alto_px`; con PIL si hay
  clase EmfWriter — Acumula registros y los vuelca con la cabecera correcta.
    método __init__()
    método emit()
    método _nuevo_objeto()
    método _seleccionar()
    método pluma()
    método pincel()
    método sin_pincel()
    método liberar()
    método linea()
    método rectangulo()
    método polilinea()
    método _fuente()
    método ancho_texto()
    método texto()
    método imagen() — `rgb`: arreglo (filas, columnas, 3) uint8, la fila 0 arriba.
    método guardar()
  función _marcas_bonitas() — Marcas con un paso de 1, 2 o 5 por una potencia de diez.
  función _formato()
  función _marcas_del_eje() — (posiciones, etiquetas) tal como VTK las dibujaría.
  función _marco() — Dibuja ejes, marcas, rótulos y título. Devuelve el rectángulo del área.
  función _ejes()
  función anotar_mapa() — Deja en la gráfica el mapa y su tabla de color.
  función heatmap_a_emf() — Un `vtkChartHistogram2D` a EMF: bitmap del mapa, resto vectorial.
  función xy_a_emf() — Un `vtkChartXY` con líneas a EMF, todo vectorial.
  función chart_a_emf() — Elige el dibujo según el tipo de gráfica.

## core/utils/heatmap_export.py
  función _num()
  función secciones_de_mapa() — Arma las secciones para `ExportService.export_sections`.

## core/utils/notifications.py
  clase NotificationCard — Una tarjeta de aviso no modal. El color sale del QSS por `severity`.
    método __init__()
    método close_card()
  clase NotificationCenter — Pila de avisos no modales en la esquina inferior izquierda del workspace.
    método __init__()
    método window()
    método show_message()
    método clear()
    método restack() — Vuelve a subir las tarjetas; se llama al mostrar otro plugin, cuyas
    método _arm_timer()
    método _trim()
    método _remove_card()
    método _reposition()
    método eventFilter()

## core/utils/parallel.py
  función memoria_disponible() — Bytes de RAM libres en Windows, o None si no se puede saber.
  función n_hilos() — Hilos a usar: nunca más que items, `max_hilos`, la mitad de los núcleos,
  función map_ordenado() — Aplica `fn` a cada item repartiéndolos entre hilos.

## core/utils/plugin_alerts.py
  clase PluginAlerts — Mensajes al usuario con tres severidades que se presentan distinto:
    método __init__()
    método set_center()
    método __show_message() — Internal helper to show alerts with different levels.
    método error()
    método warning()
    método info()
    método show() — Equivalente a `info`/`warning`/`error` con el nivel como argumento.
    método show_spinner()
    método hide_spinner() — Close the loading spinner if active.

## core/utils/rango_color.py
  función limites_color() — (mínimo, máximo) del color. Un rango manual inválido (máx <= mín) cae al automático.
  función _fila()
  función agregar_rango_color() — Añade al panel "Color range" con casilla y límites Min / Max.
  función mostrar_rango_automatico() — Pone en los cuadros el rango que salió de los datos, para partir de él al fijarlo.
  función leer_rango()
  función guardar_rango()
  función restaurar_rango()

## core/utils/results_tables_widget.py
  clase ResultsTablesWidget — Reusable 'RESULTS' panel: header (title + '...' + 'x') over a slope/amplitude table.
    método __init__()
    método setupUi()
    método set_values() — Fill the table's single value column. Pass None to leave a cell blank.

## core/utils/rutas.py
  función carpeta_del_programa() — Donde están `assets/` y `plugins/`: la carpeta del paquete instalado o la raíz del repositorio.
  función carpeta_inicial() — Carpeta por defecto de los diálogos de archivo: la del usuario, no la desde la que se lanzó el programa.
  función carpeta_de_datos() — La carpeta GammaLab dentro de %APPDATA%, creada si hace falta. Si no se puede crear, la carpeta del código.
  función asegurar_salida_estandar() — Una aplicación sin consola (la instalada) arranca con sys.stdout y sys.stderr en None y
  función ruta_de_proyecto() — El primer argumento que es un archivo `.glab` existente, o None.

## core/utils/selector_trials.py
  clase SelectorDeTrials
    método __init__()
    método _dejar_uno()
    método _marcar()
    método establecer_total() — Reconstruye la lista (todos marcados) si cambió el número de trials válidos.
    método posiciones() — Posiciones base 1 de los trials marcados.
  función columnas_elegidas() — Las columnas (trials) de `X` en las posiciones base 1 dadas; `X` si son todas.

## core/utils/submuestreo.py
  función indices_reducidos() — Índices (ordenados) de a lo sumo ~n_max puntos: mínimo y máximo de cada tramo, más los extremos.
  función _a_vtk()
  función _llenar()
  función recortar() — Puntos a dibujar de (x, y) dentro del rango visible [desde, hasta].
  clase _Serie
    método __init__()
    método actualizar()
  clase _Controlador — Vuelve a reducir las series de un gráfico cuando cambia el rango de su eje X.
    método __init__()
    método _abarca_todo()
    método al_cambiar_eje()
  función agregar_linea() — Añade a `chart` una serie de línea reducida y devuelve el plot.
  función tabla_de() — Tabla con los datos completos del plot (X, Y), no la reducida que se dibuja.
  función agregar_columna() — Serie reducida con la columna 0 de `tabla` como X y `columna` como Y.

## core/utils/task_progress.py
  clase TaskProgressBar — Muestra el avance de la tarea en curso y permite cancelarla.
    método __init__()
    método seguir() — Engancha un TaskHandle y se muestra mientras la tarea viva.
    método ocultar()
    método _titulo_de()
    método _soltar() — Desconecta el handle anterior para que sus señales tardías no muevan
    método _on_cancelar()
    método _on_progress()
    método _on_terminada()

## core/utils/trial_labels.py
  función compress_ranges() — [1, 2, 3, 5, 8, 9] -> "1–3, 5, 8–9" (posiciones base 1).
  función describe_trials() — Describe un conjunto de trials, en posiciones base 1 entre los validos.
  función describe_average() — Un promedio de todos los trials validos.
  función trials_used() — Registro serializable de los trials de una operacion, para

## core/utils/vtk_context_menu.py
  clase VTKContextMenu — General context menu for VTK-based views.
    método __init__()
    método liberar() — Retira del widget los observadores, el menu y la rueda de este menu, para que otro lo reemplace.
    método _log()
    método _get_charts() — Los graficos sobre los que el menu puede actuar.
    método _active_chart()
    método set_signal_name()
    método set_channel_name()
    método set_plugin_name()
    método set_chart()
    método set_datastore() — Inject the DataStore service (dict-like with get/set).
    método set_measurements_enabled()
    método set_measurement_context()
    método _apply_measure_scope_to_service()
    método _install_wheel_shortcuts()
    método add_action()
    método _can_measure_current_chart()
    método show_menu()
    método export_image()
    método export_table()
    método set_zoom_mode()
    método reset_zoom()
    método zoom_by_factor() — Scale the visible X/Y range of every chart around its own center.
    método _install_mouse_observers()
    método _on_left_press()
    método _on_left_release()
    método _on_mouse_move_block_hover()
    método rebuild_measurement_overlays()
    método clear_measurement_overlays()
    método on_view_rebuilt() — Actualizar chart + contexto extendido y reconstruir overlays.

## core/utils/vtk_observers.py
  función _estado()
  función _interactor()
  función observar() — Como `interactor.AddObserver`, pero recordado para poder retirarlo.
  función retirar_observadores() — Quita del interactor todos los observadores registrados. Devuelve cuántos.
  función reponer_observadores() — Vuelve a poner los observadores retirados. Devuelve cuántos.
  función contar_observadores() — Observadores actualmente atados al interactor.
  función widgets_vtk()
  función retirar_de() — Retira los observadores de todos los widgets VTK dentro de `contenedor`.
  función reponer_en() — Repone los observadores de todos los widgets VTK dentro de `contenedor`.

## core/utils/vtk_temporizador.py
  función _timer_event_seguro() — `TimerEvent` con las comprobaciones que le faltan al original.
  función instalar() — Deja puesta la guarda. Se llama una vez, al arrancar la aplicación.
  función desinstalar() — Devuelve el método original. Existe para las pruebas.

## core/utils/vtk_ventanas.py
  función liberar_ventanas() — Finaliza la ventana OpenGL de cada widget VTK dentro de `contenedor`. Devuelve cuantas.

## core/utils/xlsx_writer.py
  función nombre_de_hoja() — Nombre válido para Excel (31 caracteres, sin []:*?/\) y sin repetir.
  función _letra()
  función _celda()
  función _filas()
  función escribir_xlsx() — `secciones`: {nombre de hoja: (encabezados, filas)}. Una hoja por sección.

## plugins/analysis/connectivity/ppc/compute.py
  función filas_por_decada() — Cuántas filas por década de frecuencia tienen sentido.
  función eje_frecuencias() — El eje de frecuencias del mapa, **descendente** como en MATLAB.
  clase ResultadoPPC — El mapa de consistencia de fase entre dos canales, y sus ejes.
  función validar_alineacion() — Los dos canales tienen que venir del **mismo corte**.
  función _unidad() — El coeficiente llevado al círculo unidad: `e^{i·fase}`, sin la magnitud.
  función _trials_planos() — Los trials sin ninguna variación, que no tienen fase que medir.
  función _geometria() — Qué ventana le toca a cada fila, y dónde caen las columnas.
  función ppc_mapa() — El mapa de PPC entre dos canales, frecuencia contra tiempo.
  función avisos() — Lo que condiciona la lectura del mapa, en frases listas para mostrar.

## plugins/analysis/connectivity/ppc/ppc_plugin.py
  función cortar_canales() — Corta los trials de `canales` con la receta de otro canal. Puro: no escribe en `ds`; corre en el servicio de t
  clase Ppc_plugin — Consistencia de fase por pares entre dos canales.
    método __init__()
    método get_widget()
    método start()
    método stop() — Al salir de la pestaña: la tarea en vuelo se descarta.
    método process()
    método on_kernel_event()
    método _valores_por_defecto()
    método _canales_disponibles() — Todos los canales de la señal activa, en el orden del archivo.
    método _trials_de()
    método _receta_de() — La receta de corte de cualquier canal ya cortado, o None.
    método _tras_cortar() — Ya en el hilo de la interfaz: registra los trials recortados y retoma el cálculo.
    método _asegurar_trials() — Los trials de `canal`; si no existen, los corta con la receta del otro.
    método _llenar_canales()
    método on_create_ppc()
    método _terminar_calculo()
    método _on_ppc_progress()
    método _on_ppc_failed()
    método _on_ppc_cancelled()
    método _on_ppc_done() — Ya en el hilo de la interfaz: aquí se dibuja.
    método current_trial_state() — PPC trabaja con dos canales a la vez: se muestran los dos.
    método ensure_vtk()
    método _mostrar_avisos()
    método current_trial_state() — PPC trabaja con dos canales a la vez: se muestran los dos.
    método render_resultado() — Un mapa de frecuencia logarítmica contra tiempo, con barra de color.
    método _actualizar_menu() — Apunta el menú contextual al gráfico y a la señal actuales.
    método _num() — float para exportar; NaN e infinitos salen vacíos (JSON no los admite).
    método _secciones_resultado() — Parámetros, resumen, avisos, ventana por frecuencia y mapa.
    método exportar_resultados() — Exporta los números de la última ejecución, con los parámetros que la produjeron.
    método get_analysis_params()
    método apply_analysis_params()

## plugins/analysis/connectivity/ppc/ppc_plugin_ui.py
  clase Ui_Ppc
    método setupUi()
    método _etiqueta()
    método _combo()
    método _entero()
    método _decimal()
    método retranslateUi()

## plugins/analysis/frequency/fft/fft_plugin.py
  función calcular_fft() — FFT of every trial: returns (freq, mag, fs_eff). Pure, so it can run in the TaskService.
  clase Fft_plugin
    método __init__()
    método stop()
    método process()
    método get_widget()
    método _log_sizes()
    método _wire_ui()
    método _on_clear_clicked()
    método _ensure_vtk()
    método _on_calculate_clicked()
    método _on_fft_done()
    método get_analysis_params()
    método apply_analysis_params()
    método _sync_range()
    método _load_trials_from_store() — Find the active signal in the DataStore and return:
    método _compute_fft() — Returns (freq:(Nf,), mag:(Nf,T), fs_eff:float)
    método _plot_fft() — Build a vtkTable using trials_matrix_to_vtk_table(freq, mag)

## plugins/analysis/frequency/fft/fft_plugin_ui.py
  clase Ui_Fft
    método setupUi()
    método retranslateUi()

## plugins/analysis/frequency/fft_average/fft_average_plugin.py
  función calcular_fft_average() — MATLAB-style FFT, averaged across trials unless `per_trial`. Pure, for the TaskService.
  clase Fft_average_plugin
    método __init__()
    método stop()
    método process()
    método get_widget()
    método _wire_ui()
    método _on_clear_clicked()
    método _on_calculate_clicked()
    método _on_fft_average_done()
    método get_analysis_params()
    método apply_analysis_params()
    método _sync_range()
    método _ensure_vtk()
    método _load_trials_from_store() — Find the active signal in the DataStore and return:
    método _compute_fft_average() — MATLAB-style FFT with optional averaging across trials.
    método _plot_fft_average() — Build a vtkTable using trials_matrix_to_vtk_table(freq, mag)

## plugins/analysis/frequency/fft_average/fft_average_plugin_ui.py
  clase Ui_Fft_Average
    método setupUi()
    método retranslateUi()

## plugins/analysis/frequency/psd/psd_plugin.py
  función calcular_psd() — Welch PSD of every trial: returns (freq, power, fs_eff). Pure, for the TaskService.
  clase Psd_plugin — Power Spectral Density (PSD) plugin with selectable modes:
    método __init__()
    método stop()
    método process()
    método get_widget()
    método _log_sizes()
    método _init_defaults() — Set MATLAB-like defaults and a wide plotting range.
    método _wire_ui()
    método _on_mode_changed() — Show or hide the individual trial selector.
    método current_trial_state()
    método _sync_noverlap() — Set noverlap to half of nperseg by default.
    método _ensure_vtk()
    método _on_calculate_clicked()
    método _on_psd_done()
    método get_analysis_params()
    método apply_analysis_params()
    método _sync_range()
    método _load_trials_from_store()
    método _compute_psd()
    método _plot_psd() — Build a vtkTable and draw power curves.

## plugins/analysis/frequency/psd/psd_plugin_ui.py
  clase Ui_Psd
    método setupUi()
    método retranslateUi()

## plugins/analysis/frequency/psd_average/psd_average_plugin.py
  función calcular_psd() — Welch PSD of every trial: returns (freq, power, fs_eff). Pure, for the TaskService.
  clase Psd_average_plugin — Plugin to compute Average Power Spectral Density (PSD)
    método __init__()
    método start()
    método stop()
    método process()
    método get_widget()
    método _log_sizes()
    método _wire_ui()
    método _on_clear_clicked()
    método _sync_noverlap() — Set noverlap to half of nperseg by default.
    método _ensure_vtk()
    método _on_calculate_clicked()
    método _on_psd_done()
    método get_analysis_params()
    método apply_analysis_params()
    método _sync_range()
    método _load_trials_from_store()
    método _compute_psd()
    método _plot_psd()

## plugins/analysis/frequency/psd_average/psd_average_plugin_ui.py
  clase Ui_Psd_average
    método setupUi()
    método retranslateUi()

## plugins/analysis/frequency/relative_psd/relative_psd_plugin.py
  función calcular_psd() — Welch PSD of every trial: returns (freq, pxx, fs_eff). Pure, for the TaskService.
  clase Relative_psd_plugin — Relative (and absolute) PSD mirroring MATLAB's f_PSD_Relative.
    método __init__()
    método stop()
    método process()
    método get_widget()
    método _crear_area_de_grafica() — La gráfica a la izquierda y los parámetros a la derecha, como en la FFT.
    método _inject_optional_controls() — Inject optional controls without assuming a specific UI layout.
    método _wire_ui()
    método _init_defaults()
    método _sync_noverlap()
    método _sync_range()
    método _on_calculate_clicked()
    método _on_psd_done()
    método get_analysis_params()
    método apply_analysis_params()
    método _band_sum() — Sum power in [lo, hi] with two edge policies:
    método _compute_relative_psd() — Reproduces f_PSD_Relative:
    método _log_bands()
    método _load_trials_from_store()
    método _ensure_vtk()
    método _plot_psd()
    método _fracciones_por_banda()
    método _secciones_resultado()
    método exportar_resultados()
    método _compute_psd()

## plugins/analysis/frequency/relative_psd/relative_psd_plugin_ui.py
  clase Ui_Relative_psd
    método setupUi()
    método retranslateUi()

## plugins/analysis/time/average/average_plugin.py
  clase Average_plugin
    método __init__()
    método process()
    método stop()
    método get_widget()
    método _on_clear_clicked()
    método _ensure_trials_list() — Rebuild the list if empty or out-of-date.
    método _on_calculate_average() — Load the active SignalDataset from the DataStore and use its associated TrialDataset.
    método _collect_selected_indices() — Positions (1-based, among valid trials) according to the selection mode.
    método _sync_range()
    método _apply_filter()
    método _on_average_done()
    método get_analysis_params()
    método apply_analysis_params()
    método render_average() — Render the average using vtkContextView + vtkChartXY
    método ensure_vtk() — Create and initialize VTK widgets and the context view.

## plugins/analysis/time/average/average_plugin_ui.py
  clase Ui_Average
    método setupUi()
    método _wireDefaultState()
    método _onSelectAllToggled()
    método _onSingleToggled()
    método _onRangeToggled()
    método _updateEnabled()
    método retranslateUi()

## plugins/analysis/time/average/compute.py
  función promedio_trials() — Promedio muestra a muestra entre los trials.

## plugins/analysis/time/erp/compute.py
  función preparar_mapa_calor() — Prepara los datos del mapa de calor: submuestreo, rango de color y eje de tiempo.

## plugins/analysis/time/erp/erp_plugin.py
  función calcular_erp() — Selects the trials (1-based `idx`) and prepares the heat map. Pure, for the TaskService.
  clase Erp_plugin
    método __init__()
    método process()
    método stop()
    método get_widget()
    método ensure_vtk()
    método _wire_ui()
    método _on_clear_clicked()
    método _load_trials_from_store() — Find the active signal in the DataStore and return the latest TrialDataset:
    método _collect_selected_indices() — Return indices (1-based) according to selection mode.
    método _sync_range()
    método _select_none()
    método _select_visible()
    método _invert_selection()
    método _apply_filter()
    método _on_plot_clicked()
    método _on_erp_done()
    método get_analysis_params()
    método apply_analysis_params()
    método _ensure_trials_list() — Rebuild the list if empty or out-of-date.
    método cleanup_vtk() — Properly release VTK resources before destroying the widget.
    método _render_butterfly() — Draw lines (1 per trial) with vtkChartXY.
    método _render_heatmap() — 2D heatmap with correct time axes
    método _on_change_lut()
    método _build_lut()

## plugins/analysis/time/erp/erp_plugin_ui.py
  clase Ui_ErpPlot — ERP Plot panel (simplified version):
    método __init__()
    método setupUi()
    método _wireDefaultState()
    método _onSelectAllToggled()
    método _onSingleToggled()
    método _onRangeToggled()
    método _updateEnabled()
    método retranslateUi()

## plugins/analysis/time_frequency/modulation_index/compute.py
  clase ResultadoMI — El comodulograma y sus ejes.
  función eje_barrido() — `inicio:paso:fin` de MATLAB: incluye el extremo si cae justo.
  función comodulograma() — El comodulograma de `f_PAC_sing`.

## plugins/analysis/time_frequency/modulation_index/modulation_index_plugin.py
  clase Modulation_index_plugin
    método __init__()
    método process()
    método stop()
    método get_widget()
    método _init_controls()
    método _on_clear_clicked()
    método _n_trials()
    método _actualizar_selector_trial()
    método current_trial_state()
    método _mover_trial()
    método on_create_mi()
    método _terminar_calculo()
    método _on_mi_progress()
    método _on_mi_failed()
    método _on_mi_cancelled()
    método _on_mi_done() — Ya en el hilo de la interfaz: aquí se dibuja.
    método _avisar_de_los_limites() — Deja constancia en el log de lo que condiciona la lectura del gráfico.
    método ensure_vtk()
    método render_resultado()
    método _grafico_comodulograma() — `f_ImageMatrix(MInorm, fp, fm, [], 'jet', 256)`: fase en la x,
    método _reacomodar()
    método _actualizar_menu()
    método _num()
    método _secciones_resultado()
    método exportar_resultados() — Exporta los números de la última ejecución, con los parámetros que la produjeron.
    método get_analysis_params()
    método apply_analysis_params()

## plugins/analysis/time_frequency/modulation_index/modulation_index_plugin_ui.py
  clase Ui_ModulationIndex
    método setupUi()
    método _section_layout()
    método _add_spin_row()
    método _add_trial_row() — La fila del trial: flecha, casilla, flecha y el «de N».
    método retranslateUi()

## plugins/analysis/time_frequency/pac/compute.py
  función morse_tf() — Transformada tiempo-frecuencia con wavelet de Morse generalizada.
  función detectar_extremos() — Picos y valles de `y`, como los dos `findpeaks` del MATLAB.
  función cruces_por_cero() — Índices donde `y` cambia de signo.
  función seleccionar_valles() — Qué valles del ritmo lento abren un ciclo utilizable.
  función ventanas_por_valle() — Recorta una ventana de `2·semiancho+1` muestras centrada en cada valle.
  función _recorte_por_valles() — Qué tramo del promedio se conserva, según sus valles.
  clase ResultadoPsel — Todo lo que `f_Phase_PAC_Pdetect` calcula y dibuja.
  función pac_psel() — PAC Psel: acoplamiento promediado sobre los ciclos detectados.
  función remuestrear_en_log() — Lleva las filas de `mapa` a una rejilla uniforme en `log10(f)`.
  función bordes_bins() — Los `nbins + 1` bordes que parten el círculo de fase, de −π a π.
  función centros_bins() — El eje que MATLAB usa para dibujar: `index(1:nbins)`, o sea los bordes
  función agrupar_por_fase() — Reordena la energía por posición en el ciclo lento. Es el núcleo de PAC.
  función promediar_bins() — `suma / cuenta`, dejando `NaN` donde el bin quedó vacío.
  función zscore_por_fila() — Z-score de cada frecuencia a lo largo de los bins de fase.
  función vector_medio() — Vector medio circular: `mean(hist · e^{i·ángulo})`.
  clase ResultadoPac — Todo lo que el plugin necesita para dibujar las cuatro salidas.
  función _preparar() — Validaciones y submuestreo, comunes a un trial y al promedio.
  función pac_un_trial() — PAC de un solo trial. Réplica de `f_Phase_PAC`.
  función pac_promedio() — PAC promediado sobre todos los trials. Réplica de `f_Phase_PAC_Average`.

## plugins/analysis/time_frequency/pac/pac_plugin.py
  función pasos_de_magnitud() — Los valores donde van los anillos, redondeados a algo legible.
  clase BrujulaPolar — Dibuja el vector medio sobre una rejilla polar.
    método __init__()
    método SetAutoSize()
    método SetSize()
    método GetTitle()
    método radio() — El mayor entre |parte real| y |parte imaginaria|, como MATLAB.
    método Initialize()
    método Paint()
    método _pintar()
    método _poli()
  función etiquetas_del_circulo() — Los rótulos de los doce radios de la brújula, en la unidad elegida.
  función titulo_de() — El rótulo del gráfico, con el ángulo en la unidad que marque la casilla.
  clase Pac_plugin
    método __init__()
    método process()
    método stop()
    método get_widget()
    método _init_controls()
    método _on_unidades_cambiadas() — Cambiar de unidad **no recalcula**: solo se redibuja.
    método _on_clear_clicked()
    método _n_trials()
    método _usa_un_solo_trial() — Solo PAC trabaja sobre un trial. Average los promedia todos y Psel
    método _es_psel() — Los dos modos Psel dibujan los mismos 13 paneles y van por el mismo
    método _actualizar_selector_canal() — Llena y muestra el selector de canal de amplitud, solo entre canales.
    método _actualizar_selector_trial() — Ajusta el rango y el texto «de N» a los trials que haya cargados.
    método _trials_de_la_corrida() — Que trials entran en el calculo con el tipo elegido.
    método current_trial_state()
    método _mover_trial() — Las flechas: avanzar o retroceder sin salirse del rango.
    método on_create_pac()
    método _preparar_vtk()
    método _terminar_calculo()
    método _on_pac_progress()
    método _on_pac_failed()
    método _on_pac_cancelled()
    método _on_pac_done() — Ya en el hilo de la interfaz: aquí se dibuja.
    método ensure_vtk()
    método _sincronizar_eje_de_tiempo() — Hace que los cuatro paneles de señal compartan el eje de tiempo.
    método render_resultado() — Dibuja las salidas apiladas, como hace open_signal con sus canales.
    método render_psel() — Los 13 paneles de PAC Psel, apilados y deslizables.
    método _grafico_ciclos() — Los ciclos detectados, uno encima de otro, con su promedio marcado.
    método _grafico_mapa_log() — Un mapa con el eje de frecuencias en escala logarítmica.
    método _grafico_mapa() — El mapa fase-frecuencia, con el mismo patrón vectorizado del wavelet.
    método _en_grados() — Si la casilla de unidades está marcada. Por omisión, sí.
    método _unidad_de_fase()
    método _fase_legible() — La fase de un vector, escrita en la unidad elegida.
    método _eje_de_fase() — El eje de fase en la unidad que marque la casilla.
    método _fase_en_grados() — Pasa el eje de fase a grados de 0 a 360 y rota los datos con él.
    método _grafico_histograma()
    método _grafico_brujula() — El vector medio de acoplamiento, como la `compass` de MATLAB.
    método _grafico_senal()
    método _columna()
    método _alturas() — La altura en píxeles de cada gráfico, en el orden en que se apilan.
    método _ajustar_alto_del_lienzo() — Hace el lienzo tan alto como la pila necesite; el resto lo desliza
    método _reacomodar() — Reparte los gráficos en vertical, con altura fija cada uno.
    método _actualizar_menu() — Apunta el menú contextual a los gráficos y al canal actuales.
    método _num() — float para exportar; NaN e infinitos salen vacíos (JSON no los admite).
    método _secciones_resultado() — Parámetros, resumen, histograma de fase y mapa de la última ejecución.
    método exportar_resultados() — Exporta los números de la última ejecución, con los parámetros que la produjeron.
    método get_analysis_params()
    método apply_analysis_params()

## plugins/analysis/time_frequency/pac/pac_plugin_ui.py
  clase Ui_Pac
    método setupUi()
    método retranslateUi()

## plugins/analysis/time_frequency/wavelet/compute.py
  función wavelet_individual()

## plugins/analysis/time_frequency/wavelet/wavelet_plugin.py
  clase Wavelet_plugin — Time-Frequency Analysis Plugin (Wavelet CWT with PyWavelets + VTK Visualization)
    método __init__()
    método process()
    método stop()
    método get_widget()
    método init_controls()
    método _on_clear_clicked()
    método ensure_vtk() — Initialize VTK components for rendering.
    método on_create_wavelet() — Load active signal, compute CWT wavelet and render scalogram in VTK
    método _terminar_calculo()
    método _on_wavelet_progress()
    método _on_wavelet_failed()
    método _on_wavelet_cancelled()
    método _on_wavelet_done() — Se ejecuta ya en el hilo de la interfaz.
    método current_trial_state() — Wavelet siempre calcula sobre el primer trial valido.
    método get_analysis_params()
    método apply_analysis_params()
    método exportar_resultados() — Exporta la matriz de la última ejecución, con los parámetros que la produjeron.
    método compute_wavelet()
    método normalize_tf()
    método _scale_log()
    método _get_log_ticks_coords() — Marcas 1-2-5 de cada década; entradas y posiciones en log10, etiquetas en Hz.
    método _redibujar_color() — R33: aplica el rango de color sin volver a calcular.
    método render_scalogram()
    método _build_lut()
    método _lut_to_ctf()

## plugins/analysis/time_frequency/wavelet/wavelet_plugin_ui.py
  clase Ui_Wavelet
    método setupUi()
    método retranslateUi()

## plugins/analysis/time_frequency/wavelet_average/compute.py
  función wavelet_promedio()

## plugins/analysis/time_frequency/wavelet_average/wavelet_average_plugin.py
  clase Wavelet_average_plugin
    método __init__()
    método process() — Optional hook; show status message if available.
    método stop() — Stop plugin and disable VTK interactor if present.
    método get_widget()
    método _on_clear_clicked()
    método _init_controls()
    método _create_vtk_container()
    método ensure_vtk()
    método on_create_wavelet() — Compute average CWT across all active trials and render the average scalogram.
    método _terminar_calculo()
    método _on_wavelet_progress()
    método _on_wavelet_failed()
    método _on_wavelet_cancelled()
    método _on_wavelet_done() — Callback when the task finishes, already on the UI thread.
    método get_analysis_params()
    método apply_analysis_params()
    método exportar_resultados() — Exporta la matriz de la última ejecución, con los parámetros que la produjeron.
    método compute_wavelet()
    método normalize_tf()
    método _scale_log()
    método _get_log_ticks_coords() — Marcas 1-2-5 de cada década; entradas y posiciones en log10, etiquetas en Hz.
    método _redibujar_color() — R33: aplica el rango de color sin volver a calcular.
    método render_scalogram()
    método _build_lut() — Build a lookup table (similar to 'jet' like mapping).
    método _lut_to_ctf() — Convert a VTK lookup table into a vtkColorTransferFunction.

## plugins/analysis/time_frequency/wavelet_average/wavelet_average_plugin_ui.py
  clase Ui_Wavelet_Average
    método setupUi()
    método retranslateUi()

## plugins/faq/help/help_plugin.py
  clase HelpPlugin
    método __init__()
    método stop()
    método process()
    método get_widget()
    método load_pdf() — Carga el PDF en el QWebEngineView.
    método init_buttons()

## plugins/faq/help/help_ui.py
  clase Ui_FAQ
    método setupUi()
    método retranslateUi()

## plugins/io/open_signal/compute.py
  función cargar_senal() — Lee el archivo de `ruta` y devuelve su SignalDataset, o None si se canceló.

## plugins/io/open_signal/open_signal_plugin.py
  función regenerar_trials() — Vuelve a cortar los conjuntos de trials con la frecuencia corregida. Puro: no escribe en `ds`.
  clase OpenSignalPlugin
    método __init__()
    método stop()
    método process() — Restore rendering and re-enable interaction.
    método get_widget()
    método _ensure_vtk() — Embed a QVTKRenderWindowInteractor and use vtkContextView (charts).
    método _setup_sync_callback() — Configure callback to synchronize X axes across all charts.
    método open_file_dialog() — Public entry point: shows the file picker and loads the selected signal.
    método _terminar_carga()
    método _on_load_progress()
    método _on_load_failed()
    método _on_load_cancelled()
    método _on_load_done() — El archivo ya se leyó; esto corre en el hilo de la interfaz.
    método current_trial_state() — Aqui se ve la senal continua, no trials.
    método _set_dataset()
    método _refresh_sampling_rate_labels()
    método _on_restore_sampling_rate_clicked()
    método _on_clear_clicked() — R25: vuelve a los valores iniciales sin tocar la señal ni sus trials.
    método _on_apply_sampling_rate_clicked()
    método _after_sampling_rate_change()
    método _offer_trials_regeneration()
    método _on_trials_regenerated()
    método _populate_channel_list()
    método _checked_indices()
    método _on_channel_item_changed()
    método _relayout_charts() — Reposition charts with enough spacing so axes are visible.
    método _sync_all_x_axes() — Synchronize all X axes to the same range.
    método _render_selected()
    método _chart_at_pixel() — Return the chart whose rectangle contains point (x, y) in VTK coords.

## plugins/io/open_signal/open_signal_ui.py
  clase Ui_OpenSignal
    método __init__()
    método setupUi()
    método retranslateUi()

## plugins/measure/amplitude/amplitude_plugin.py
  clase AmplitudeTableModel
    método __init__()
    método rowCount()
    método columnCount()
    método headerData()
    método _fmt()
    método _fmt_xy()
    método data()
    método set_rows()
    método get_all_rows()
  clase AmplitudePlugin
    método __init__()
    método initialize()
    método start()
    método stop()
    método process()
    método get_widget()
    método _reload_from_store()
    método _load_amplitude_rows_from_store() — Reads DataStore['measurements'] (also tolerates 'meassurements'),
    método _export_dir() — Default export folder: the open project's 'archivos' folder, else last used dir.
    método _tabla_exportable() — (headers, rows) of the measurements, as CSV and Excel write them.
    método export_csv()
    método export_xlsx()
  función _f()
  función _i()

## plugins/measure/amplitude/amplitude_plugin_ui.py
  clase Ui_Amplitude
    método setupUi()
    método retranslateUi()

## plugins/measure/slope/slope_plugin.py
  clase SlopeTableModel — Table model for slope measurements.
    método __init__()
    método rowCount()
    método columnCount()
    método headerData()
    método _fmt()
    método _fmt_xy()
    método data()
    método set_rows()
    método get_all_rows()
  clase SlopePlugin
    método __init__()
    método stop()
    método process()
    método get_widget()
    método _reload_from_store()
    método _load_slope_rows_from_store() — Reads DataStore['measurements'] (or 'meassurements'),
    método _export_dir() — Default export folder: the open project's 'archivos' folder, else last used dir.
    método _tabla_exportable() — (headers, rows) of the measurements, as CSV and Excel write them.
    método export_csv()
    método export_xlsx()

## plugins/measure/slope/slope_plugin_ui.py
  clase Ui_Slope
    método setupUi()
    método retranslateUi()

## plugins/preprocessing/prepare/artifact_remove/artifact_logic.py
  función _last_trial_dataset() — Último TrialDataset generado, por la API pública de SignalDataset (o None).
  función _get_active_signal_and_name()
  función _get_current_channel_name() — Current channel resolution order:
  función _discarded_for() — Descartes de (archivo, canal); si no hay, prueba con el nombre del archivo sin extensión.
  clase ModificacionPreparada — Lo que se lee en el hilo de la interfaz antes de calcular.
  función preparar_modificacion() — Paso 1, en el hilo de la interfaz: ubica los trials activos y el TrialDataset
  función apply_filter_to_all_valid() — Filtra los trials válidos y registra el resultado como derivado (R79), sin orquestador.
  función descartar_derivado() — Descarta el conjunto derivado del canal activo (R79). Devuelve (archivo, canal, había_derivado).
  función escribir_modificacion() — Paso 3, en el hilo de la interfaz: escribe las columnas modificadas en el
  función apply_modification_to_all_valid() — Los tres pasos seguidos, en el hilo que llama (sin orquestador).

## plugins/preprocessing/prepare/artifact_remove/artifact_remove_plugin.py
  clase _WidgetVisibilityFilter — Listens to show/hide events on the plugin widget to keep the plot in sync.
    método __init__()
    método eventFilter()
  clase ArtifactRemovePlugin
    método __init__()
    método process()
    método _refresh_view_coalesced() — Coalesced refresh: only refresh once for bursty events.
    método start() — Called when the plugin is first loaded.
    método stop() — Called when the plugin closes or is disabled.
    método get_widget() — Return the plugin's main widget to the main window.
    método _force_render() — Force a render if the widget is visible.
    método _wire_controls() — Connect UI signals to slots (no optional guards).
    método _on_clear_params_clicked()
    método _on_mode_changed() — Update Point B visibility depending on mode.
    método _parse_point()
    método _texto_de_medidas()
    método _confirmar_con_medidas() — Muestra las medidas del segmento y pide confirmar antes de modificar nada.
    método _on_apply_changes() — Lee los trials aquí, calcula la modificación en el orquestador y la escribe al volver.
    método _on_restore_original() — R79: drops the derived set of the current channel; the analyses read the original again.
    método _go_to_previous_trial()
    método _go_to_next_trial()
    método _get_active_signal_and_name()
    método _get_current_channel_name() — Return channel name to use with get_active_trials.
    método _fetch_active_trials()
    método _load_and_display_trials() — Load active trials via get_active_trials and show average or individual.
    método current_trial_state() — Lo que se esta viendo: el promedio o un trial valido.
    método _ensure_vtk() — Ensure the interactor and view exist and are added to the layout.
    método _cleanup_vtk_references() — Clean VTK references to avoid memory leaks.
    método _plot_curve() — Draw arrays 't' and 'y' in the VTK chart.
    método _reset_state() — Reset internal plugin state.
    método _clear_render() — Clear the VTK view and optionally show a message.
    método _ensure_visibility_filter() — Install an event filter so we refresh whenever the widget is shown again.
    método _on_widget_shown() — Triggered when the stacked widget makes this plugin visible again.
    método _on_widget_hidden() — Triggered when the plugin is hidden; stop pending refresh.
    método _on_data_updated() — Listen to kernel events and coalesce refreshes to avoid UI lag.
    método _on_apply_progress()
    método _on_apply_finished() — El cálculo terminó: la escritura ocurre aquí, en el hilo de la interfaz.
    método _on_apply_error()
    método _on_apply_cancelled() — Se canceló (por ejemplo, al cambiar de sección): no se escribió nada.
    método _set_apply_busy() — Bloquea o libera los controles mientras se aplica una modificación.
    método _finish_apply() — Libera los controles y vuelve a dibujar los trials, modificados o no.

## plugins/preprocessing/prepare/artifact_remove/artifact_remove_ui.py
  clase Ui_ArtifactRemove
    método setupUi()
    método update_ui_for_mode()
    método retranslateUi()

## plugins/preprocessing/prepare/filter/filter_plugin.py
  función filtrar_vista_previa() — The two traces the preview shows: (filtered signal, filtered first trial).
  clase Filter_plugin — Filter plugin for signal processing
    método __init__()
    método process()
    método stop()
    método get_widget()
    método init_controls()
    método _on_clear_clicked()
    método ensure_vtk() — Initialize VTK components for rendering.
    método on_apply_filter()
    método on_apply_to_trials()
    método _on_trials_filtered()
    método on_restore_original()
    método _on_filter_done()
    método current_trial_state() — La vista previa del filtro usa siempre el primer trial valido.
    método run_filter() — Applies a bandpass filter to the signal.
    método _render_filtered() — Render filtered signal or trial using the correct vtkContextView.

## plugins/preprocessing/prepare/filter/filter_plugin_ui.py
  clase Ui_Filter
    método setupUi()
    método retranslateUi()

## plugins/preprocessing/trials/trial_plugin_ui.py
  clase Ui_Trials
    método __init__()
    método setupUi()
    método retranslateUi()

## plugins/preprocessing/trials/trials_plugin.py
  función cortar_trials() — Cuts the trials of one channel. Reads `ds`, never writes it, so it can run in the TaskService.
  clase TrialsPlugin
    método __init__()
    método stop()
    método process()
    método get_widget()
    método _ensure_vtk()
    método _on_vtk_widget_destroyed()
    método _init_controls()
    método _stim_unit() — Unit of the selected stimulus channel ("" if unknown).
    método _update_threshold_unit() — The threshold is shown in mV and converted to the stimulus channel's
    método _show_recipe_threshold() — Show the stimulus channel and threshold the trials were cut with,
    método _on_clear_params_clicked()
    método on_kernel_event() — Listen to events emitted by the Kernel.
    método _on_stim_count_changed() — Callback when the number of stimuli changes: apply rules to the ISI field.
    método _apply_interstim_ui_rules() — - stim_count <= 1: disable ISI and set it to 0.0
    método _populate_channel_combos() — Fill channelComboBox and stimChannelComboBox with the same names (userData = index).
    método _populate_channels_once() — Try to load the active signal and populate the combo (silent if none).
    método _restore_existing_trials_if_any() — Show the active signal's most recent TrialDataset, if it already has
    método _on_generate_clicked()
    método _on_trials_cut()
    método navigate_trial() — Show next or previous trial according to 'direction'.
    método _on_discard_trial()
    método _update_trial_ui() — Update current trial label/button depending on discard state.
    método current_trial_state() — Trial visible, traducido a la numeracion de la aplicacion (posicion
    método _render_trials()