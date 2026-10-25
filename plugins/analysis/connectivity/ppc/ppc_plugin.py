"""Plugin de PPC — la parte que orquesta.

Fase 5b del plan: `tasks.submit` y los cuatro slots. El dibujo es la Fase 6 y
entra por `render_resultado`, que aquí está declarado y vacío a propósito.

**Lo que hace este archivo y lo que no.** Lee los parámetros del panel, pide
los trials de **dos** canales, comprueba que estén alineados, encola el cálculo
en el orquestador y recoge el resultado. No calcula nada: eso es `compute.py`.
Y no dibuja: eso será `render_resultado`.

El patrón es el mismo de PAC, y las cuatro guardas `if handle is not
self._handle` no son decorativas: al cambiar un parámetro se encola otra tarea
y la anterior puede seguir viva un instante. Sin la guarda, su resultado
sobreescribe el nuevo.
"""
from functools import partial

import numpy as np
from PyQt5.QtWidgets import QWidget

from core.plugins.interfaces import IPlugin
from core.utils.trial_labels import trials_used
from plugins.analysis.connectivity.ppc import compute as cp
from plugins.analysis.connectivity.ppc.ppc_plugin_ui import Ui_Ppc


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

    def _canales_con_trials(self):
        """Los canales que **ya tienen trials generados**, en ese orden.

        No todos los del archivo: el plugin *Trials* corta uno por vez, así que
        ofrecer los demás sería ofrecer algo que todavía no existe.
        """
        senal = self.get_active_signal(silent=True)
        if senal is None:
            return []
        vistos = []
        for td in senal.get_all_trials_datasets():
            if td.channel_name not in vistos:
                vistos.append(td.channel_name)
        return vistos

    def _llenar_canales(self):
        if self.ui is None:
            return
        canales = self._canales_con_trials()
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
                "Hacen falta dos canales **distintos** con trials generados. Genéralos "
                "en Trials: primero uno y después el otro, con los mismos parámetros y "
                "cambiando solo el canal. El PPC de un canal consigo mismo vale 1 en "
                "todo el mapa y no mide nada.")
            return

        td1 = self.get_trials_de_canal(canal_1)
        td2 = self.get_trials_de_canal(canal_2)
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
        # PPC usa todos los trials validos de los dos canales, emparejados
        self._trials_en_curso = trials_used(None, self._params_en_curso["n_trials"], "all",
                                            channel=f"{canal_1} ↔ {canal_2}")
        self._params_en_curso["trials_usados"] = (
            f"{self._trials_en_curso['label']} · {canal_1} y {canal_2}")

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
        """Ya en el hilo de la interfaz. Aquí se dibujará (Fase 6)."""
        if handle is not self._handle:
            return
        try:
            if self.ui is None or resultado is None:
                return
            self._ultimo = {"parametros": self._params_en_curso, "resultado": resultado}
            self.render_resultado(resultado)
            for aviso in cp.avisos(resultado):
                self._log(aviso)
            self._trials_used = getattr(self, "_trials_en_curso", None)
            usados = (self._trials_used or {}).get("label", f"{resultado.n_trials} trial(s)")
            self._notify(
                f"PPC {resultado.canal_1} ↔ {resultado.canal_2}: "
                f"{resultado.frecuencias.size} frecuencias × "
                f"{resultado.tiempos.size} ventanas, trials: {usados}")
            self.publish_current_trial()
            self.mark_project_dirty()
        except Exception as e:
            self._log("render_resultado:", e)
            self.alerts.error(f"No se pudo dibujar el PPC: {e}")
        finally:
            self._terminar_calculo()

    # =====================================================
    # === El dibujo (Fase 6)
    # =====================================================
    def current_trial_state(self):
        """PPC trabaja con dos canales a la vez: se muestran los dos."""
        if self._trials_used:
            return self.trial_state_from_used(self._trials_used)
        return super().current_trial_state()

    def render_resultado(self, resultado):
        """Un mapa de frecuencia logarítmica contra tiempo, con barra de color.

        Vacío a propósito: es la Fase 6. Queda aquí declarado para que el hueco
        se vea y para que `_on_ppc_done` ya tenga su sitio de llamada.

        Lo que necesitará, y que ya existe: `_grafico_mapa_log` de
        `pac_plugin.py` —hace el remuestreo logarítmico y las marcas de
        32/100/316 Hz— y la transparencia de NaN de
        `modulation_index_plugin.py`, que aquí hace falta de verdad porque el
        cono de influencia deja los bordes en blanco.
        """
        return None
