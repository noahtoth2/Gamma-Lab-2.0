"""Plugin de PPC: orquesta el cálculo y dibuja el mapa.

**Lo que hace este archivo y lo que no.** Lee los parámetros del panel, pide
los trials de **dos** canales, comprueba que estén alineados, encola el cálculo
en el orquestador, recoge el resultado y lo dibuja (`render_resultado`). No
calcula nada: eso es `compute.py`.

El patrón es el mismo de PAC, y las cuatro guardas `if handle is not
self._handle` no son decorativas: al cambiar un parámetro se encola otra tarea
y la anterior puede seguir viva un instante. Sin la guarda, su resultado
sobreescribe el nuevo.
"""
from functools import partial

import numpy as np
import vtk
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util import numpy_support

from core.filters.trials import cut_trials_single_channel
from core.plugins.interfaces import IPlugin
from core.utils.vtk_context_menu import VTKContextMenu
from plugins.analysis.connectivity.ppc import compute as cp
from plugins.analysis.connectivity.ppc.ppc_plugin_ui import Ui_Ppc
from plugins.analysis.time_frequency.pac.compute import remuestrear_en_log


class Ppc_plugin(IPlugin):
    """Consistencia de fase por pares entre dos canales."""

    # Los del panel *Inter Channel* del MATLAB, salvo los dos que el plan
    # cambió: `wd` pasa a ser la ventana mínima y `ciclos` es nuevo (decisiones
    # 9 y 11). Los valores son los mismos que trae el .mlapp.
    DEFECTOS = {
        "remuestreo_hz": 2000,
        "f_min_hz": 0.1,
        "f_max_hz": 500.0,
        "ventana_min_s": cp.VENTANA_MINIMA_S,
        "ciclos": cp.CICLOS_PPC,
    }

    def __init__(self, meta):
        super().__init__(meta)
        self.ui = None
        self._handle = None
        self._calculando = False
        self._ultimo = None            # {"parametros": ..., "resultado": ...}
        self._params_en_curso = {}
        self._restaurando = False        # apply_analysis_params recalcula al abrir un proyecto
        self._corrida_restaura = False   # la ejecución en curso viene de una restauración
        self.vtk_widget = None
        self.vtk_menu = None
        self._context_view = None
        self._chart = None
        self._avisos_label = None

    # =====================================================
    # === Ciclo de vida
    # =====================================================
    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_Ppc()
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self._valores_por_defecto()
            self.ui.clearButton.clicked.connect(self._valores_por_defecto)
            self.ui.createPpcButton.clicked.connect(self.on_create_ppc)
            self._llenar_canales()
        else:
            self.widget.setParent(parent)
        return self.widget

    def start(self, kernel):
        super().start(kernel)
        self._llenar_canales()

    def stop(self):
        """Al salir de la pestaña: la tarea en vuelo se descarta.

        Sin esto el cálculo sigue corriendo contra una interfaz que ya no se ve
        y, cuando termina, intenta dibujar sobre widgets ocultos.
        """
        tareas = self.kernel.get_service("TaskService") if self.kernel else None
        if tareas is not None:
            tareas.cancel_all_from(self.meta.id)
        self._terminar_calculo()

    def process(self, data):
        # Se llama cada vez que se abre la pestaña. Nadie emite `trials_changed`,
        # así que los canales con trials se releen aquí: sin esto los combos
        # quedan vacíos si los trials se generaron antes de abrir PPC.
        self._llenar_canales()
        return None

    def on_kernel_event(self, topic, payload):
        super().on_kernel_event(topic, payload)
        if topic in ("signal_active_changed", "signal_added", "trials_changed"):
            self._llenar_canales()

    # =====================================================
    # === El panel
    # =====================================================
    def _valores_por_defecto(self):
        if self.ui is None:
            return
        self.ui.sampleDensitySpinBox.setValue(self.DEFECTOS["remuestreo_hz"])
        self.ui.lowFrequencySpinBox.setValue(self.DEFECTOS["f_min_hz"])
        self.ui.highFrequencySpinBox.setValue(self.DEFECTOS["f_max_hz"])
        self.ui.windowSpinBox.setValue(self.DEFECTOS["ventana_min_s"])
        self.ui.cyclesSpinBox.setValue(self.DEFECTOS["ciclos"])

    def _canales_disponibles(self):
        """Todos los canales de la señal activa, en el orden del archivo.

        Antes solo se ofrecían los que ya tenían trials, y con uno solo cortado
        el segundo combo no tenía nada que elegir. Los trials del otro canal se
        generan al calcular, con la misma receta (`_asegurar_trials`).
        """
        senal = self.get_active_signal(silent=True)
        if senal is None:
            return []
        return list(getattr(senal, "channel_names", None) or [])

    def _asegurar_trials(self, senal, canal):
        """Los trials de `canal`; si no existen, los corta con la receta del otro.

        PPC exige que los dos canales salgan del **mismo corte**: mismos onsets,
        `t0`/`t1` y umbral, cambiando solo el canal. La receta de un canal ya
        cortado vive en `metadata["generation_params"]`, así que cortar el otro
        con ella es exactamente lo que el usuario haría a mano en Trials.
        Devuelve None, avisando, si no hay ninguna receta de donde partir.
        """
        td = senal.get_active_trials(senal.name, canal)
        if td is not None and np.asarray(td.trials).size:
            return td

        receta = None
        for otro in senal.get_all_trials_datasets():
            receta = (otro.metadata or {}).get("generation_params")
            if receta:
                break
        if not receta:
            self.alerts.warning(
                f"El canal '{canal}' no tiene trials y no hay ningún corte de otro canal "
                f"del que copiar los parámetros. Genera los trials en Trials primero.")
            return None
        try:
            nombres = list(senal.channel_names)
            params = dict(receta, channel=nombres.index(canal))
            td = cut_trials_single_channel(ds=senal, **params, debug=False)
            td.metadata["generation_params"] = params
            senal.add_trial_dataset(td)
            return td
        except Exception as e:
            self.alerts.error(f"No se pudieron generar los trials del canal '{canal}': {e}")
            return None

    def _llenar_canales(self):
        if self.ui is None:
            return
        canales = self._canales_disponibles()
        for i, combo in enumerate((self.ui.channel1ComboBox, self.ui.channel2ComboBox)):
            previo = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(canales)
            if previo in canales:
                combo.setCurrentText(previo)
            elif len(canales) > i:
                # Por omisión, cada combo apunta a uno distinto: el PPC de un
                # canal consigo mismo vale 1 y no mide nada.
                combo.setCurrentIndex(i)
            combo.blockSignals(False)

    # =====================================================
    # === Lógica principal
    # =====================================================
    def on_create_ppc(self):
        self._corrida_restaura, self._restaurando = self._restaurando, False
        tareas = self.kernel.get_service("TaskService") if self.kernel else None
        if tareas is None:
            self.alerts.error("El servicio de tareas no está disponible.")
            return
        if self.get_active_signal() is None:
            return

        canal_1 = self.ui.channel1ComboBox.currentText()
        canal_2 = self.ui.channel2ComboBox.currentText()
        if not canal_1 or not canal_2 or canal_1 == canal_2:
            # Se rechaza **antes** de encolar, no después. El PPC de un canal
            # consigo mismo vale 1 en todas las celdas, así que calcularlo son
            # varios segundos de espera para acabar enseñando un mapa entero de
            # unos. `compute.avisos` también lo dice, por si alguien llama al
            # cálculo desde un script, pero por la interfaz no se llega ahí.
            self.alerts.warning(
                "Hacen falta dos canales **distintos**. El PPC de un canal consigo "
                "mismo vale 1 en todo el mapa y no mide nada.")
            return

        senal_activa = self.get_active_signal()
        td1 = self._asegurar_trials(senal_activa, canal_1)
        td2 = self._asegurar_trials(senal_activa, canal_2)
        if td1 is None or td2 is None:
            return

        try:
            cp.validar_alineacion(td1, td2)
        except ValueError as e:
            self.alerts.error(str(e))
            return

        t = td1.time_rel
        if t is None or len(t) < 2:
            self.alerts.error("No hay suficiente información de tiempo en la señal activa.")
            return

        fs_calculado = round(1.0 / (t[1] - t[0]), 3)
        fs = float(self.ui.sampleDensitySpinBox.value())
        f_min = float(self.ui.lowFrequencySpinBox.value())
        f_max = float(self.ui.highFrequencySpinBox.value())
        wd = float(self.ui.windowSpinBox.value())
        ciclos = float(self.ui.cyclesSpinBox.value())

        senal = self.get_active_signal()
        self._params_en_curso = {
            "señal": getattr(senal, "name", ""),
            "canal_1": canal_1, "canal_2": canal_2,
            "remuestreo_hz": fs,
            "f_min_hz": f_min, "f_max_hz": f_max,
            "ventana_min_s": wd, "ciclos": ciclos,
            "n_trials": int(np.asarray(td1.trials).shape[1]),
        }

        tareas.cancel_all_from(self.meta.id)
        self._terminar_calculo()

        self._calculando = True
        self.ui.createPpcButton.setEnabled(False)
        self.ui.createPpcButton.setText("Computing...")

        handle = tareas.submit(
            cp.ppc_mapa, owner=self.meta.id,
            trials_1=np.asarray(td1.trials, dtype=np.float64),
            trials_2=np.asarray(td2.trials, dtype=np.float64),
            fs_calculado=fs_calculado, fs=fs, fmin=f_min, fmax=f_max,
            wd=wd, ciclos=ciclos, t0=float(t[0]),
            canal_1=canal_1, canal_2=canal_2)

        self._handle = handle
        handle.progress.connect(partial(self._on_ppc_progress, handle))
        handle.finished.connect(partial(self._on_ppc_done, handle))
        handle.failed.connect(partial(self._on_ppc_failed, handle))
        handle.cancelled.connect(partial(self._on_ppc_cancelled, handle))

    def _terminar_calculo(self):
        self._calculando = False
        self._handle = None
        if self.ui is not None:
            self.ui.createPpcButton.setEnabled(True)
            self.ui.createPpcButton.setText("Generate")

    # =====================================================
    # === Los cuatro slots del orquestador
    # =====================================================
    # La guarda de cada uno descarta lo que llegue de una tarea que ya no es la
    # vigente. Pasa de verdad: al cambiar un parámetro se encola otra y la
    # anterior puede seguir viva un instante.

    def _on_ppc_progress(self, handle, porcentaje, mensaje):
        if handle is not self._handle:
            return
        self._notify(f"{mensaje} ({porcentaje}%)")

    def _on_ppc_failed(self, handle, mensaje):
        if handle is not self._handle:
            return
        self._terminar_calculo()
        self.alerts.error(f"No se pudo calcular el PPC: {mensaje}")

    def _on_ppc_cancelled(self, handle):
        if handle is not self._handle:
            return
        self._terminar_calculo()

    def _on_ppc_done(self, handle, resultado):
        """Ya en el hilo de la interfaz: aquí se dibuja."""
        if handle is not self._handle:
            return
        try:
            if self.ui is None or resultado is None:
                return
            self.ensure_vtk()
            self._ultimo = {"parametros": self._params_en_curso, "resultado": resultado}
            self.render_resultado(resultado)
            avisos = cp.avisos(resultado)
            for aviso in avisos:
                self._log(aviso)
            self._mostrar_avisos(avisos)
            self._actualizar_menu()
            self._notify(
                f"PPC {resultado.canal_1} ↔ {resultado.canal_2}: "
                f"{resultado.frecuencias.size} frecuencias × "
                f"{resultado.tiempos.size} ventanas, {resultado.n_trials} trial(s)")
            if not self._corrida_restaura:
                self.mark_project_dirty()
        except Exception as e:
            self._log("render_resultado:", e)
            self.alerts.error(f"No se pudo dibujar el PPC: {e}")
        finally:
            self._terminar_calculo()

    # =====================================================
    # === VTK
    # =====================================================
    FONDO = (0.98, 0.98, 0.98)
    # Como el MATLAB: `clim [0 0.5]`, una marca cada 0,5 en log10 etiquetada con
    # `round(10.^v)` (0, 0, 1, 3, 10, 32, 100, 316 Hz) y los mismos títulos.
    LIMITE_COLOR = 0.5
    PASO_MARCA_LOG = 0.5

    def ensure_vtk(self):
        if self.vtk_widget is not None and self._context_view is not None:
            return
        contenedor = self.ui.plotArea
        if contenedor.layout() is None:
            lay = QVBoxLayout(contenedor)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

        self.vtk_widget = QVTKRenderWindowInteractor(contenedor)
        contenedor.layout().addWidget(self.vtk_widget, 1)

        # Los avisos van bajo el gráfico, nunca en un diálogo: un modal abre un
        # bucle de eventos anidado y el temporizador de VTK sigue disparando
        # dentro de él (problema nº 24 de problemas-encontrados.md).
        self._avisos_label = QLabel(contenedor)
        self._avisos_label.setWordWrap(True)
        self._avisos_label.setTextFormat(Qt.PlainText)
        self._avisos_label.setContentsMargins(8, 4, 8, 4)
        self._avisos_label.setStyleSheet("color: #8a5a00; background: #fff6e0;")
        self._avisos_label.setVisible(False)
        contenedor.layout().addWidget(self._avisos_label, 0)

        self._context_view = vtk.vtkContextView()
        self._context_view.SetRenderWindow(self.vtk_widget.GetRenderWindow())
        self._context_view.GetRenderer().SetBackground(*self.FONDO)
        self.vtk_widget.Initialize()
        self.vtk_widget.Start()

        self.vtk_menu = VTKContextMenu(
            chart=[], vtk_widget=self.vtk_widget, plugin_name="PPC",
            measurements_enabled=False, parent=self.widget)
        self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))
        for fmt in ("csv", "xlsx", "json"):
            self.vtk_menu.add_action(f"Export PPC results ({fmt})", partial(self.exportar_resultados, fmt))

    def _mostrar_avisos(self, avisos):
        if self._avisos_label is None:
            return
        self._avisos_label.setText("\n\n".join(avisos))
        self._avisos_label.setVisible(bool(avisos))

    def render_resultado(self, r):
        """Un mapa de frecuencia logarítmica contra tiempo, con barra de color.

        Las celdas que no se pudieron medir (NaN) van **transparentes**, como
        en el índice de modulación: pintarlas con un color de la escala las
        disfrazaría de «sin acoplamiento» cuando lo que pasa es que ahí no hay
        medida. El remuestreo a eje logarítmico es el mismo de PAC.
        """
        escena = self._context_view.GetScene()
        escena.ClearItems()

        mapa = np.asarray(r.mapa, dtype=np.float64)
        datos, log_min, log_max = remuestrear_en_log(mapa, r.frecuencias)
        datos = np.ascontiguousarray(datos, dtype=np.float32)
        n_freq, n_t = datos.shape

        t = np.asarray(r.tiempos, dtype=np.float64)
        paso_t = (t[-1] - t[0]) / max(1, n_t - 1) if n_t > 1 else 1.0
        paso_y = (log_max - log_min) / max(1, n_freq - 1)

        img = vtk.vtkImageData()
        img.SetDimensions(n_t, n_freq, 1)
        img.SetSpacing(paso_t, paso_y, 1.0)
        img.SetOrigin(float(t[0]), log_min, 0.0)
        img.GetPointData().SetScalars(numpy_support.numpy_to_vtk(
            datos.ravel(), deep=True, array_type=vtk.VTK_FLOAT))
        img.Modified()

        vmin, vmax = 0.0, self.LIMITE_COLOR
        lut = vtk.vtkColorTransferFunction()
        for fraccion, (rr, gg, bb) in zip(
                (0.0, 0.125, 0.375, 0.625, 0.875, 1.0),
                ((0.0, 0.0, 0.5), (0.0, 0.0, 1.0), (0.0, 1.0, 1.0),
                 (1.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 0.0))):
            lut.AddRGBPoint(vmin + fraccion * (vmax - vmin), rr, gg, bb)
        lut.SetNanColor(*self.FONDO)
        lut.SetNanOpacity(0.0)

        chart = vtk.vtkChartHistogram2D()
        chart.SetInputData(img, 0)
        chart.SetTransferFunction(lut)
        chart.SetTitle("Phase Coherence")
        eje_x = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        eje_x.SetTitle("Time(s)")
        eje_x.SetBehavior(vtk.vtkAxis.FIXED)
        eje_x.SetRange(float(t[0]), float(t[-1] + paso_t))
        eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
        eje_y.SetTitle("Frequency (Hz) - Log")
        eje_y.SetBehavior(vtk.vtkAxis.FIXED)
        eje_y.SetRange(log_min, log_max)

        posiciones = vtk.vtkDoubleArray()
        etiquetas = vtk.vtkStringArray()
        v = np.ceil(log_min / self.PASO_MARCA_LOG - 1e-9) * self.PASO_MARCA_LOG
        while v <= log_max + 1e-9:
            posiciones.InsertNextValue(float(v))
            etiquetas.InsertNextValue(str(int(round(10 ** v))))
            v += self.PASO_MARCA_LOG
        if posiciones.GetNumberOfTuples():
            eje_y.SetCustomTickPositions(posiciones, etiquetas)

        chart.SetAutoSize(True)
        escena.AddItem(chart)
        self._chart = chart
        self._context_view.GetRenderWindow().Render()

    # =====================================================
    # === Exportación
    # =====================================================
    def _actualizar_menu(self):
        """Apunta el menú contextual al gráfico y a la señal actuales."""
        if self.vtk_menu is None:
            return
        self.vtk_menu.set_chart([self._chart] if self._chart is not None else [])
        params = (self._ultimo or {}).get("parametros") or {}
        self.vtk_menu.set_signal_name(params.get("señal") or "signal")
        self.vtk_menu.set_channel_name(None)

    @staticmethod
    def _num(x):
        """float para exportar; NaN e infinitos salen vacíos (JSON no los admite)."""
        x = float(x)
        return x if np.isfinite(x) else None

    def _secciones_resultado(self) -> dict:
        """Parámetros, resumen, avisos, ventana por frecuencia y mapa."""
        r = self._ultimo["resultado"]
        p = self._ultimo["parametros"]
        n = self._num

        resumen = [["canal_1", r.canal_1], ["canal_2", r.canal_2],
                   ["n_trials", int(r.n_trials)],
                   ["fs_efectiva_hz", n(r.fs_efectiva)], ["fs_pedida_hz", n(r.fs_pedida)],
                   ["solape", n(r.solape)], ["n_objetivo", int(r.n_objetivo)],
                   ["filas_sin_resolver", int(r.filas_sin_resolver)]]
        por_fila = [[n(f), n(w), int(m)] for f, w, m in
                    zip(r.frecuencias, r.ventanas_s, r.n_muestras)]
        encabezado = ["frecuencia_hz"] + [f"t_{t:.4f}s" for t in r.tiempos]
        filas = [[n(f)] + [n(v) for v in fila] for f, fila in zip(r.frecuencias, r.mapa)]
        secciones = {
            "Parametros": (["parametro", "valor"], [[k, v] for k, v in p.items()]),
            "Resumen": (["medida", "valor"], resumen),
            "Ventanas": (["frecuencia_hz", "ventana_s", "n_muestras"], por_fila),
            "Mapa": (encabezado, filas),
        }
        avisos = cp.avisos(r)
        if avisos:
            secciones["Avisos"] = (["aviso"], [[a] for a in avisos])
        return secciones

    def exportar_resultados(self, fmt: str):
        """Exporta los números de la última ejecución, con los parámetros que la produjeron."""
        if not self._ultimo or self.vtk_menu is None:
            self.alerts.info("Primero genera un PPC para poder exportar sus resultados.")
            return
        self.vtk_menu.export_service.export_sections(self._secciones_resultado(), fmt)

    # =====================================================
    # === Guardar y restaurar el análisis en el proyecto
    # =====================================================
    def get_analysis_params(self) -> dict:
        return {
            "channel_1": self.ui.channel1ComboBox.currentText(),
            "channel_2": self.ui.channel2ComboBox.currentText(),
            "sample_fq": self.ui.sampleDensitySpinBox.value(),
            "f_min": self.ui.lowFrequencySpinBox.value(),
            "f_max": self.ui.highFrequencySpinBox.value(),
            "window": self.ui.windowSpinBox.value(),
            "cycles": self.ui.cyclesSpinBox.value(),
        }

    def apply_analysis_params(self, params: dict):
        d = self.DEFECTOS
        self._llenar_canales()
        for combo, clave in ((self.ui.channel1ComboBox, "channel_1"),
                             (self.ui.channel2ComboBox, "channel_2")):
            idx = combo.findText(params.get(clave, ""))
            if idx >= 0:
                combo.setCurrentIndex(idx)
        self.ui.sampleDensitySpinBox.setValue(params.get("sample_fq", d["remuestreo_hz"]))
        self.ui.lowFrequencySpinBox.setValue(params.get("f_min", d["f_min_hz"]))
        self.ui.highFrequencySpinBox.setValue(params.get("f_max", d["f_max_hz"]))
        self.ui.windowSpinBox.setValue(params.get("window", d["ventana_min_s"]))
        self.ui.cyclesSpinBox.setValue(params.get("cycles", d["ciclos"]))
        self._restaurando = True
        self.on_create_ppc()
