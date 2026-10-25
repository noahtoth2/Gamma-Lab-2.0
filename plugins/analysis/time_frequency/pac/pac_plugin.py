from functools import partial

import numpy as np
import vtk
from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util import numpy_support

from core.utils.emf_writer import anotar_mapa
from core.plugins.interfaces import IPlugin
from core.utils.vtk_context_menu import VTKContextMenu
from core.utils.trial_labels import trials_used
from plugins.analysis.time_frequency.pac import compute as cp
from plugins.analysis.time_frequency.pac.pac_plugin_ui import Ui_Pac


# ===========================================================
# === La brujula polar, como la `compass` de MATLAB
# ===========================================================
# VTK no trae grafico polar: `vtkChartXY` solo sabe de ejes cartesianos.
# Antes la brujula se dibujaba encima de uno —dos circulos, una cruz y la
# flecha—, lo que daba la forma pero no el instrumento: los ejes mostraban
# numeros de abscisa y ordenada, y el angulo solo salia en el titulo, y en
# RADIANES. MATLAB dibuja radios cada 30 grados rotulados en GRADOS, anillos
# de magnitud con su valor, y ningun eje cartesiano a la vista.
#
# Aqui se pinta a mano con el `painter` de VTK a traves de `vtkPythonItem`,
# que es la via que la libreria ofrece para dibujo propio dentro de la escena.
# El gris de la rejilla y el azul de la flecha, los mismos que ya usaba el resto
GRIS_REJILLA = (205, 205, 205)
GRIS_TEXTO = (0.35, 0.35, 0.35)
AZUL = (40, 90, 190)
AZUL_TENUE = (90, 150, 230)

ANILLOS_OBJETIVO = 4      # cuantos anillos de magnitud se buscan
PASO_GRADOS = 30          # un radio cada 30 grados, como MATLAB


def pasos_de_magnitud(rmax, objetivo=ANILLOS_OBJETIVO):
    """Los valores donde van los anillos, redondeados a algo legible.

    Elige el paso entre 1, 2, 2,5 y 5 por una potencia de diez, que es lo que
    hace cualquier eje decente y lo que se ve en MATLAB: con un máximo de 0,6
    salen los anillos en 0,2, 0,4 y 0,6.

    **El último anillo queda por encima del máximo, no por debajo.** Es lo que
    hace MATLAB y no es un detalle estético: el anillo exterior es el borde del
    instrumento, así que si se quedara corto la flecha saldría del círculo y
    parecería un error de dibujo. En una `compass` con el vector en 1,6 los
    anillos van a 0,5, 1, 1,5 y **2**.
    """
    if not np.isfinite(rmax) or rmax <= 0:
        return [1.0]
    bruto = rmax / objetivo
    exponente = np.floor(np.log10(bruto))
    base = bruto / 10.0 ** exponente
    for candidato in (1.0, 2.0, 2.5, 5.0, 10.0):
        if base <= candidato:
            paso = candidato * 10.0 ** exponente
            break
    n = int(np.ceil(rmax / paso - 1e-9))
    return [paso * k for k in range(1, max(n, 1) + 1)]


class BrujulaPolar:
    """Dibuja el vector medio sobre una rejilla polar.

    Se comporta como un gráfico para `_reacomodar` —entiende `SetAutoSize` y
    `SetSize`— pero lo que se añade a la escena es `self.item`.
    """

    def __init__(self, vector, extra=None, titulo=""):
        self.vector = complex(vector)
        self.extra = (np.asarray(extra, dtype=np.complex128).ravel()
                      if extra is not None else np.empty(0, dtype=np.complex128))
        self.titulo = titulo
        self._rect = (0.0, 0.0, 1.0, 1.0)

        self.item = vtk.vtkPythonItem()
        self.item.SetPythonObject(self)

    # --- lo que `_reacomodar` necesita, para tratarla como a los demas graficos
    def SetAutoSize(self, _valor):
        return None

    def SetSize(self, rectf):
        self._rect = (rectf.GetX(), rectf.GetY(), rectf.GetWidth(), rectf.GetHeight())

    def GetTitle(self):
        return self.titulo

    # --- el radio de la rejilla
    def radio(self):
        """El mayor entre |parte real| y |parte imaginaria|, como MATLAB.

        Es para lo que allá sirven las cuatro flechas invisibles de `x_fake` e
        `y_fake`: forzar la escala. **La flecha puede sobresalir del anillo
        exterior**, y en MATLAB también lo hace: un vector a 45° mide
        `max_lim·√2`.
        """
        candidatos = [abs(self.vector.real), abs(self.vector.imag)]
        if self.extra.size:
            candidatos += [float(np.abs(self.extra.real).max()),
                           float(np.abs(self.extra.imag).max())]
        r = max(candidatos)
        return r if np.isfinite(r) and r > 0 else 1.0

    # --- la interfaz de vtkPythonItem
    def Initialize(self, _vtk_self):
        return True

    def Paint(self, _vtk_self, painter):
        try:
            self._pintar(painter)
        except Exception:
            # Una excepcion dentro del Paint de VTK no tiene a donde propagarse:
            # dejaria la escena a medias o tumbaria el proceso. Mejor no dibujar.
            return True
        return True

    # ------------------------------------------------------------------ dibujo
    def _pintar(self, painter):
        x0, y0, ancho, alto = self._rect
        if ancho <= 1 or alto <= 1:
            return
        cx, cy = x0 + ancho / 2.0, y0 + alto / 2.0
        # Se deja margen para las etiquetas de grados, que van por fuera
        lado = min(ancho, alto) / 2.0 * 0.78
        rmax = self.radio()
        escala = lado / rmax

        pluma = painter.GetPen()
        painter.GetBrush().SetOpacity(0)

        # --- anillos de magnitud
        magnitudes = pasos_de_magnitud(rmax)
        pluma.SetColor(*GRIS_REJILLA)
        pluma.SetWidth(1.0)
        angulos = np.linspace(0.0, 2.0 * np.pi, 181)
        for m in magnitudes:
            r = m * escala
            self._poli(painter, cx + r * np.cos(angulos), cy + r * np.sin(angulos))

        # --- radios cada 30 grados
        borde = magnitudes[-1] * escala
        for grados in range(0, 360, PASO_GRADOS):
            rad = np.deg2rad(grados)
            self._poli(painter, [cx, cx + borde * np.cos(rad)],
                       [cy, cy + borde * np.sin(rad)])

        # --- las etiquetas
        texto = painter.GetTextProp()
        texto.SetColor(*GRIS_TEXTO)
        texto.SetFontSize(12)
        texto.SetJustificationToCentered()
        texto.SetVerticalJustificationToCentered()
        for grados in range(0, 360, PASO_GRADOS):
            rad = np.deg2rad(grados)
            painter.DrawString(float(cx + borde * 1.12 * np.cos(rad)),
                               float(cy + borde * 1.12 * np.sin(rad)), str(grados))

        # Los valores de magnitud, entre el radio de 60 y el de 90 como MATLAB
        texto.SetFontSize(11)
        rad_etiqueta = np.deg2rad(75)
        for m in magnitudes:
            r = m * escala
            painter.DrawString(float(cx + r * np.cos(rad_etiqueta)),
                               float(cy + r * np.sin(rad_etiqueta)), f"{m:g}")

        # --- los vectores por grupo, detras y mas tenues
        pluma.SetWidth(1.4)
        for w in self.extra:
            if np.isfinite(w.real) and np.isfinite(w.imag):
                pluma.SetColor(*AZUL_TENUE)
                pluma.SetOpacity(160)
                self._poli(painter, [cx, cx + w.real * escala], [cy, cy + w.imag * escala])
        pluma.SetOpacity(255)

        # --- la flecha
        v = self.vector
        if np.isfinite(v.real) and np.isfinite(v.imag):
            pluma.SetColor(*AZUL)
            pluma.SetWidth(2.5)
            px, py = cx + v.real * escala, cy + v.imag * escala
            self._poli(painter, [cx, px], [cy, py])
            theta = np.angle(v)
            largo = 0.12 * lado
            for desvio in (+2.6, -2.6):      # ~150 grados a cada lado del eje
                self._poli(painter, [px, px + largo * np.cos(theta + desvio)],
                           [py, py + largo * np.sin(theta + desvio)])

        # --- el titulo, arriba del todo
        if self.titulo:
            texto.SetFontSize(13)
            texto.SetColor(0.15, 0.15, 0.15)
            painter.DrawString(float(cx), float(y0 + alto - 10.0), self.titulo)

    @staticmethod
    def _poli(painter, xs, ys):
        puntos = np.empty(2 * len(xs), dtype=np.float64)
        puntos[0::2] = xs
        puntos[1::2] = ys
        painter.DrawPoly(puntos.tolist(), len(xs))


def titulo_de(vector, n_extra=0):
    """El rótulo del gráfico, con el ángulo **en grados**.

    MATLAB imprime `radtodeg(angle(v_pha_av_pre1))` por consola, así que grados
    es lo fiel; y además es lo que dicen las etiquetas del círculo, de modo que
    el título y la rejilla hablan el mismo idioma.
    """
    v = complex(vector)
    grados = np.rad2deg(np.angle(v)) % 360.0
    sufijo = f" + {n_extra} por grupo" if n_extra else ""
    return f"Vector medio{sufijo} — magnitud {abs(v):.4f}, fase {grados:.1f}°"


class Pac_plugin(IPlugin):
    PAC_TYPES = ["PAC", "PAC Average", "PAC Psel"]
    DEFAULTS = {
        "sample_fq": 2000,
        "p1": 3.0,
        "p2": 8.0,
        "a1": 25.0,
        "a2": 500.0,
    }

    def __init__(self, meta):
        super().__init__(meta)
        self.vtk_widget = None
        self._context_view = None
        self._charts = []
        self._altos = []          # la altura de cada grafico, en el mismo orden
        self._cuadrados = []      # los que hay que dibujar cuadrados (las brujulas)
        self._brujula = None
        self._mapa_chart = None
        self._histograma_chart = None
        self._charts_senal = []
        self._sincronizando = False
        self._scroll = None
        self._handle = None
        self._calculando = False
        self.vtk_menu = None
        self._params_en_curso = None
        self._restaurando = False        # apply_analysis_params recalcula al abrir un proyecto
        self._corrida_restaura = False   # la ejecucion en curso viene de una restauracion
        self._ultimo = None      # parametros + resultado de la ultima ejecucion

    # =====================================================
    # === Ciclo de vida
    # =====================================================
    def process(self, data):
        if self.vtk_widget and self.vtk_widget.GetRenderWindow():
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor:
                interactor.Enable()

    def stop(self):
        if self.vtk_widget and self.vtk_widget.GetRenderWindow():
            interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
            if interactor:
                interactor.Disable()

    def get_widget(self, parent=None):
        if self.widget is None:
            self.widget = QWidget(parent)
            self.ui = Ui_Pac()
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self.ui.pacTypeComboBox.addItems(self.PAC_TYPES)
            self._init_controls()
            self.ui.clearButton.clicked.connect(self._on_clear_clicked)
            self.ui.createPacButton.clicked.connect(self.on_create_pac)
            self.ui.prevTrialButton.clicked.connect(partial(self._mover_trial, -1))
            self.ui.nextTrialButton.clicked.connect(partial(self._mover_trial, +1))
            self.ui.pacTypeComboBox.currentIndexChanged.connect(self._actualizar_selector_trial)
            self.ui.pacTypeComboBox.currentIndexChanged.connect(lambda _: self.publish_current_trial())
            self.ui.trialSpinBox.valueChanged.connect(lambda _: self.publish_current_trial())
        else:
            self.widget.setParent(parent)
        return self.widget

    def _init_controls(self):
        self.ui.sampleDensitySpinBox.setRange(0, 1_000_000)
        self.ui.sampleDensitySpinBox.setSingleStep(100)
        for spin in (self.ui.lowFrequencySpinBox, self.ui.highFrequencySpinBox,
                     self.ui.ampLowFrequencySpinBox, self.ui.ampHighFrequencySpinBox):
            spin.setDecimals(2)
            spin.setRange(0.0, 100000.0)
            spin.setSingleStep(1.0)
        self._on_clear_clicked()

    def _on_clear_clicked(self):
        if self._calculando:
            self.alerts.warning("Hay un cálculo de PAC en curso; espera a que termine.")
            return
        d = self.DEFAULTS
        self.ui.pacTypeComboBox.setCurrentIndex(0)
        self.ui.sampleDensitySpinBox.setValue(d["sample_fq"])
        self.ui.lowFrequencySpinBox.setValue(d["p1"])
        self.ui.highFrequencySpinBox.setValue(d["p2"])
        self.ui.ampLowFrequencySpinBox.setValue(d["a1"])
        self.ui.ampHighFrequencySpinBox.setValue(d["a2"])
        self._actualizar_selector_trial()

    # =====================================================
    # === Selector de trial
    # =====================================================
    def _n_trials(self) -> int:
        try:
            trials = self.get_active_trials()
            return int(trials.trials.shape[1]) if trials is not None else 0
        except Exception:
            return 0

    def _usa_un_solo_trial(self) -> bool:
        """Solo PAC trabaja sobre un trial. Average los promedia todos y Psel
        los concatena, así que para esos dos el selector no aplica."""
        return self.ui.pacTypeComboBox.currentText() == "PAC"

    def _actualizar_selector_trial(self):
        """Ajusta el rango y el texto «de N» a los trials que haya cargados."""
        if self.ui is None:
            return
        n = self._n_trials()
        habilitado = self._usa_un_solo_trial() and n > 0

        self.ui.trialSpinBox.setEnabled(habilitado)
        self.ui.prevTrialButton.setEnabled(habilitado)
        self.ui.nextTrialButton.setEnabled(habilitado)
        self.ui.trialSpinBox.setMaximum(max(1, n))
        if self.ui.trialSpinBox.value() > max(1, n):
            self.ui.trialSpinBox.setValue(1)

        if not self._usa_un_solo_trial():
            self.ui.trialTotalLabel.setText(f"todos ({n})" if n else "todos")
        else:
            self.ui.trialTotalLabel.setText(f"de {n}" if n else "sin trials")

    def _trials_de_la_corrida(self, n: int) -> dict:
        """Que trials entran en el calculo con el tipo elegido."""
        tipo = self.ui.pacTypeComboBox.currentText()
        if self._usa_un_solo_trial():
            return trials_used([self.ui.trialSpinBox.value()], n, "single")
        if tipo == "PAC Average":
            return trials_used(None, n, "average")
        return trials_used(None, n, "all")   # Psel concatena todos

    def current_trial_state(self):
        _, td = self._active_trials_quiet()
        if td is None or self.ui is None:
            return None
        n = int(td.trials.shape[1])
        tipo = self.ui.pacTypeComboBox.currentText()
        if self._usa_un_solo_trial():
            return self.build_trial_state("single", position=self.ui.trialSpinBox.value(),
                                          total=n, channel=td.channel_name)
        if tipo == "PAC Average":
            return self.build_trial_state("average", total=n, channel=td.channel_name)
        return self.build_trial_state("all", total=n, channel=td.channel_name,
                                      note="concatenados (Psel)")

    def _mover_trial(self, paso: int):
        """Las flechas: avanzar o retroceder sin salirse del rango."""
        if not self.ui.trialSpinBox.isEnabled():
            return
        nuevo = self.ui.trialSpinBox.value() + paso
        if self.ui.trialSpinBox.minimum() <= nuevo <= self.ui.trialSpinBox.maximum():
            self.ui.trialSpinBox.setValue(nuevo)
            self.on_create_pac()

    # =====================================================
    # === Lógica principal
    # =====================================================
    def on_create_pac(self):
        self._corrida_restaura, self._restaurando = self._restaurando, False
        tasks = self.kernel.get_service("TaskService") if self.kernel else None
        if tasks is None:
            self.alerts.error("El servicio de tareas no está disponible.")
            return

        if self.get_active_signal() is None:
            return
        trials = self.get_active_trials()
        if trials is None:
            return

        t = trials.time_rel
        if t is None or len(t) < 2:
            self.alerts.error("No hay suficiente información de tiempo en la señal activa.")
            return

        try:
            datos = np.asarray(trials.trials, dtype=np.float64)
            if datos.ndim == 1:
                datos = datos[:, None]
        except Exception as e:
            self.alerts.error(f"No se pudo obtener la matriz de trials: {e}")
            return

        self._actualizar_selector_trial()

        fs_calculado = round(1.0 / (t[1] - t[0]), 3)
        fs = float(self.ui.sampleDensitySpinBox.value())
        p1 = float(self.ui.lowFrequencySpinBox.value())
        p2 = float(self.ui.highFrequencySpinBox.value())
        a1 = float(self.ui.ampLowFrequencySpinBox.value())
        a2 = float(self.ui.ampHighFrequencySpinBox.value())
        tipo = self.ui.pacTypeComboBox.currentText()

        # La casilla muestra 1 para el primer trial, como MATLAB; aquí se resta
        # uno porque Python indexa desde cero.
        indice = self.ui.trialSpinBox.value() - 1
        if self._usa_un_solo_trial() and not (0 <= indice < datos.shape[1]):
            self.alerts.warning(f"El trial {indice + 1} no existe; hay {datos.shape[1]}.")
            return

        senal = self.get_active_signal()
        self._params_en_curso = {
            "señal": getattr(senal, "name", ""),
            "canal": getattr(trials, "channel_name", ""),
            "tipo": tipo,
            "sample_fq_hz": fs,
            "p1_hz": p1, "p2_hz": p2,
            "a1_hz": a1, "a2_hz": a2,
            "trial": (indice + 1) if self._usa_un_solo_trial() else "todos",
        }
        self._trials_en_curso = self._trials_de_la_corrida(datos.shape[1])
        # Texto legible en la exportacion (una fila por parametro)
        self._params_en_curso["trials_usados"] = self._trials_en_curso["label"]

        tasks.cancel_all_from(self.meta.id)
        self._terminar_calculo()
        self.stop()

        self._calculando = True
        self.ui.createPacButton.setEnabled(False)
        self.ui.createPacButton.setText("Computing...")

        comun = dict(fs_calculado=fs_calculado, fs=fs, p1=p1, p2=p2, a1=a1, a2=a2)
        if tipo == "PAC Psel":
            # Psel concatena todos los trials, asi que recibe la matriz entera
            handle = tasks.submit(cp.pac_psel, owner=self.meta.id, data=datos, **comun)
        elif self._usa_un_solo_trial():
            handle = tasks.submit(cp.pac_un_trial, owner=self.meta.id,
                                  sig=datos[:, indice], **comun)
        else:
            handle = tasks.submit(cp.pac_promedio, owner=self.meta.id,
                                  data=datos, **comun)

        self._handle = handle
        handle.progress.connect(partial(self._on_pac_progress, handle))
        handle.finished.connect(partial(self._on_pac_done, handle, tipo))
        handle.failed.connect(partial(self._on_pac_failed, handle))
        handle.cancelled.connect(partial(self._on_pac_cancelled, handle))

    def _terminar_calculo(self):
        self._calculando = False
        self._handle = None
        if self.ui is not None:
            self.ui.createPacButton.setEnabled(True)
            self.ui.createPacButton.setText("Generate")

    def _on_pac_progress(self, handle, percent, message):
        if handle is not self._handle:
            return
        self._log(f"{message} ({percent}%)")
        self._notify(f"{message} ({percent}%)")

    def _on_pac_failed(self, handle, message):
        if handle is not self._handle:
            return
        self._terminar_calculo()
        self.alerts.error(f"No se pudo calcular PAC: {message}")

    def _on_pac_cancelled(self, handle):
        if handle is not self._handle:
            return
        self._terminar_calculo()

    def _on_pac_done(self, handle, tipo, resultado):
        """Ya en el hilo de la interfaz: aquí se dibuja."""
        if handle is not self._handle:
            return
        try:
            if self.ui is None or resultado is None:
                return
            self.ensure_vtk()
            usados = getattr(self, "_trials_en_curso", None) or {}
            etiqueta_trials = usados.get("label", "")
            if tipo == "PAC Psel":
                self.render_psel(resultado)
                detalle = f"{resultado.n_ciclos} ciclo(s)"
                if resultado.ciclos_descartados:
                    detalle += (f", {resultado.ciclos_descartados} omitido(s) por "
                                f"quedar pegados al borde de la señal")
            else:
                self.render_resultado(
                    resultado, f"{tipo} — {etiqueta_trials}" if etiqueta_trials else tipo)
                detalle = f"{resultado.n_trials} trial(s)"
            self._ultimo = {"parametros": self._params_en_curso, "resultado": resultado}
            self._trials_used = usados or None
            self._actualizar_menu()
            self._notify(
                f"{tipo} con {etiqueta_trials}: acoplamiento {abs(resultado.vector):.4f} "
                f"en la fase {np.rad2deg(np.angle(resultado.vector)) % 360.0:.1f}° "
                f"({detalle})")
            if not self._corrida_restaura:
                self.mark_project_dirty()
        except Exception as e:
            self._log("render_resultado:", e)
            self.alerts.error(f"No se pudo dibujar PAC: {e}")
        finally:
            self._terminar_calculo()
            self.process("Done")

    # =====================================================
    # === VTK
    # =====================================================
    # Alturas en pixeles de cada grafico. Son seis y no caben en el panel, asi
    # que el area de dibujo va dentro de un QScrollArea y se desliza.
    ALTO_MAPA = 300
    ALTO_HISTOGRAMA = 170
    LADO_BRUJULA = 320        # cuadrado: si no, los circulos salen elipses
    ALTO_SENAL = 150
    ALTO_CICLOS = 180         # las pilas de ciclos de PAC Psel
    HUECO = 52
    # Cuantas trazas individuales se dibujan en las pilas de ciclos. Con datos
    # reales salen cientos y un vtkChartXY con cientos de series deja la
    # interfaz inservible; el promedio se calcula sobre todas.
    MAX_TRAZAS_CICLOS = 100
    # Las marcas del eje logaritmico, las mismas del MATLAB: `v_YTick = [1.5,
    # 2, 2.5]` etiquetadas con `round(10.^v_YTick)` -> 32, 100 y 316 Hz.
    MARCAS_LOG = (1.5, 2.0, 2.5)
    FONDO = (0.98, 0.98, 0.98)

    def ensure_vtk(self):
        if self.vtk_widget is not None and self._context_view is not None:
            return
        contenedor = self.ui.plotArea
        if contenedor.layout() is None:
            lay = QVBoxLayout(contenedor)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

        # Seis graficos apilados no caben en la altura del panel. En vez de
        # encogerlos hasta volverlos ilegibles, el area de dibujo crece y se
        # desliza: cada grafico conserva su altura util.
        self._scroll = QScrollArea(contenedor)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        contenedor.layout().addWidget(self._scroll)

        self.vtk_widget = QVTKRenderWindowInteractor(self._scroll)
        self._scroll.setWidget(self.vtk_widget)

        original_resize = self.vtk_widget.resizeEvent

        def _al_cambiar_tamano(ev):
            original_resize(ev)
            self._reacomodar()

        self.vtk_widget.resizeEvent = _al_cambiar_tamano

        self._context_view = vtk.vtkContextView()
        self._context_view.SetRenderWindow(self.vtk_widget.GetRenderWindow())
        self._context_view.GetRenderer().SetBackground(*self.FONDO)
        self.vtk_widget.AddObserver(vtk.vtkCommand.EndInteractionEvent,
                                    self._sincronizar_eje_de_tiempo)
        self.vtk_widget.Initialize()
        self.vtk_widget.Start()

        self.vtk_menu = VTKContextMenu(
            chart=[], vtk_widget=self.vtk_widget, plugin_name="PAC",
            measurements_enabled=False, parent=self.widget)
        self.vtk_menu.set_datastore(self.kernel.get_service("DataStore"))
        for fmt in ("csv", "xlsx", "json"):
            self.vtk_menu.add_action(f"Export PAC results ({fmt})", partial(self.exportar_resultados, fmt))

    def _sincronizar_eje_de_tiempo(self, *_):
        """Hace que los cuatro paneles de señal compartan el eje de tiempo.

        Es el `linkaxes(ax,'x')` de MATLAB: al hacer zoom en uno, los demás lo
        siguen. Solo aplica a esos cuatro — el mapa y el histograma llevan fase
        en la x, y la brújula no tiene eje de tiempo.
        """
        if self._sincronizando or len(self._charts_senal) < 2:
            return
        self._sincronizando = True
        try:
            rango = [0.0, 0.0]
            self._charts_senal[0].GetAxis(vtk.vtkAxis.BOTTOM).GetRange(rango)
            x0, x1 = rango
            for chart in self._charts_senal[1:]:
                eje = chart.GetAxis(vtk.vtkAxis.BOTTOM)
                actual = [0.0, 0.0]
                eje.GetRange(actual)
                if abs(actual[0] - x0) > 1e-9 or abs(actual[1] - x1) > 1e-9:
                    eje.SetRange(x0, x1)
                    eje.SetBehavior(vtk.vtkAxis.FIXED)
            self._context_view.GetRenderWindow().Render()
        except Exception as e:
            self._log("sincronizar eje de tiempo:", e)
        finally:
            self._sincronizando = False

    def render_resultado(self, r, titulo="PAC"):
        """Dibuja las salidas apiladas, como hace open_signal con sus canales."""
        escena = self._context_view.GetScene()
        escena.ClearItems()
        self._charts = []

        self._mapa_chart = self._grafico_mapa(r, titulo)
        self._histograma_chart = self._grafico_histograma(r)
        self._brujula = self._grafico_brujula(r)
        self._charts = [self._mapa_chart, self._histograma_chart, self._brujula]
        self._altos = [self.ALTO_MAPA, self.ALTO_HISTOGRAMA, self.LADO_BRUJULA]
        self._cuadrados = [self._brujula]

        self._charts_senal = []
        if r.n_trials > 1:
            # PAC Average: `f_Phase_PAC_Average` pone bajo el mapa un
            # `plot(cos(index_pi))` como referencia de fase, y **no dibuja
            # ninguna senal**. Antes aqui salian los cuatro paneles del PRIMER
            # trial bajo un titulo que decia "promedio", lo que invita a leer
            # como promediado algo que no lo es.
            grados_ref = self._fase_en_grados(r.fases)[0]
            chart = self._grafico_senal(grados_ref, np.cos(np.deg2rad(grados_ref)),
                                        "Referencia: cos(fase)", "cos")
            self._charts.append(chart)
            self._altos.append(self.ALTO_SENAL)
        else:
            # PAC de un trial: los cuatro paneles comparten el eje de tiempo,
            # como el `linkaxes(ax,'x')` de MATLAB.
            # La fase instantánea se dibuja en grados de 0 a 360, igual que el
            # histograma, la brújula y los mapas. Es la misma serie: `angle` la
            # devuelve en radianes de −π a π y aquí solo se reexpresa, así que
            # el diente de sierra salta ahora en el pico del ritmo lento (0°) y
            # no en el valle.
            for etiqueta, unidad, serie in (
                    ("Original", "Amplitud", r.senal),
                    ("Filtrada en fase", "Amplitud", r.banda_fase),
                    ("Fase instantánea", "°", np.rad2deg(r.fase) % 360.0),
                    ("Filtrada en amplitud", "Amplitud", r.banda_amplitud)):
                chart = self._grafico_senal(r.tiempo, serie, etiqueta, unidad)
                self._charts_senal.append(chart)
                self._charts.append(chart)
                self._altos.append(self.ALTO_SENAL)

        for chart in self._charts:
            # La brujula es un `vtkPythonItem` envuelto en una clase de Python
            # que entiende SetSize: a la escena va el item, no el envoltorio.
            escena.AddItem(getattr(chart, "item", chart))
        self._ajustar_alto_del_lienzo()
        self._reacomodar()
        self._context_view.GetRenderWindow().Render()

    def render_psel(self, r):
        """Los 13 paneles de PAC Psel, apilados y deslizables.

        MATLAB abre **12 ventanas sueltas**, varias con dos `subplot` dentro —
        unos 15 paneles repartidos por la pantalla—. Aquí van en una sola
        columna, igual que ya se hizo con las 4 ventanas de PAC: doce ventanas
        flotantes en una aplicación con pestañas no tienen sentido.

        De los 15 paneles del original se quitan **dos duplicados exactos**: la
        figura de la línea 252 es copia literal de la 245 (mismos datos, mismo
        color, mismo grosor) y la de la 506 repite el mapa de la 398 sin el
        coseno de abajo. Dibujar dos veces lo mismo no aporta nada.
        """
        escena = self._context_view.GetScene()
        escena.ClearItems()
        self._charts, self._altos, self._cuadrados = [], [], []
        self._charts_senal = []
        self._mapa_chart = self._histograma_chart = self._brujula = None

        def agregar(chart, alto, cuadrado=False, es_senal=False):
            self._charts.append(chart)
            self._altos.append(alto)
            if cuadrado:
                self._cuadrados.append(chart)
            if es_senal:
                self._charts_senal.append(chart)
            return chart

        # 1-2. La señal concatenada y su banda de fase, con el eje compartido
        for etiqueta, serie in (("Original", r.senal),
                                ("Filtrada en fase", r.senal_filtrada)):
            agregar(self._grafico_senal(r.tiempo, serie, etiqueta),
                    self.ALTO_SENAL, es_senal=True)

        # 3-5. Las tres pilas de ciclos con su promedio encima
        for etiqueta, pila, promedio, color in (
                ("Ciclos en la banda de fase", r.ciclos_theta, r.promedio_theta, (200, 30, 30)),
                ("Ciclos sin filtrar", r.ciclos_full, r.promedio_full, (200, 30, 30)),
                ("Ciclos en gamma (25-129 Hz)", r.ciclos_gamma, None, (20, 20, 20))):
            agregar(self._grafico_ciclos(pila, promedio, etiqueta, color), self.ALTO_CICLOS)

        # 6-7. El mapa fase/frecuencia en escala logarítmica, y debajo el coseno
        # de referencia que el MATLAB dibuja para situar la fase
        grados_psel, mapa_psel = self._fase_en_grados(r.fases, r.mapa)
        self._mapa_chart = agregar(
            self._grafico_mapa_log(mapa_psel, r.frecuencias, grados_psel,
                                   "PAC Psel — mapa fase/frecuencia", "Fase (°)"),
            self.ALTO_MAPA)
        agregar(self._grafico_senal(grados_psel, np.cos(np.deg2rad(grados_psel)),
                                    "Referencia: cos(fase)", "cos"),
                self.ALTO_SENAL)

        # 8-9. El tiempo-frecuencia promedio y el promedio del ritmo lento debajo
        agregar(self._grafico_mapa_log(r.mapa_tf, r.frecuencias, r.tiempo_tf,
                                       "Tiempo/frecuencia promedio", "Tiempo (s)"),
                self.ALTO_MAPA)
        agregar(self._grafico_senal(r.tiempo_tf, r.promedio_theta,
                                    "Promedio del ritmo lento"), self.ALTO_SENAL)

        # 10. El histograma
        self._histograma_chart = agregar(self._grafico_histograma(r), self.ALTO_HISTOGRAMA)

        # 11. La brújula del vector medio
        self._brujula = agregar(self._grafico_brujula(r), self.LADO_BRUJULA, cuadrado=True)

        # 12. El promedio sin filtrar, que el MATLAB dibuja aparte
        agregar(self._grafico_senal(np.arange(r.promedio_full.size) / r.fs_efectiva,
                                    r.promedio_full, "Promedio sin filtrar"),
                self.ALTO_SENAL)

        # 13. La brújula con los 16 vectores por grupo de bins, más el medio
        agregar(self._grafico_brujula(r, extra=r.vectores_por_grupo),
                self.LADO_BRUJULA, cuadrado=True)

        for chart in self._charts:
            # La brujula es un `vtkPythonItem` envuelto en una clase de Python
            # que entiende SetSize: a la escena va el item, no el envoltorio.
            escena.AddItem(getattr(chart, "item", chart))
        self._ajustar_alto_del_lienzo()
        self._reacomodar()
        self._context_view.GetRenderWindow().Render()

    def _grafico_ciclos(self, pila, promedio, etiqueta, color_promedio):
        """Los ciclos detectados, uno encima de otro, con su promedio marcado.

        Réplica de los `plot(m_lows_*)` con el `hold on` y el promedio grueso.

        > **Se dibujan como mucho `MAX_TRAZAS_CICLOS` ciclos**, repartidos por
        > toda la pila. Con datos reales —60 trials de 3 s y un ritmo de 5 Hz—
        > salen unos 900 ciclos, y 900 series en un `vtkChartXY` dejan la
        > interfaz inservible. El promedio, que es lo que se lee, se calcula
        > **sobre todos**; el número real aparece en el título.
        """
        pila = np.asarray(pila, dtype=np.float64)
        n_muestras, n_ciclos = pila.shape if pila.ndim == 2 else (pila.size, 0)
        chart = vtk.vtkChartXY()
        chart.SetShowLegend(False)
        if n_ciclos == 0:
            chart.SetTitle(f"{etiqueta} — sin ciclos")
            return chart

        x = np.arange(n_muestras, dtype=np.float64)
        if n_ciclos <= self.MAX_TRAZAS_CICLOS:
            columnas = np.arange(n_ciclos)
        else:
            columnas = np.unique(np.linspace(0, n_ciclos - 1,
                                             self.MAX_TRAZAS_CICLOS).astype(int))

        for c in columnas:
            tabla = vtk.vtkTable()
            tabla.AddColumn(self._columna(x, "Muestra"))
            tabla.AddColumn(self._columna(np.nan_to_num(pila[:, c]), f"c{c}"))
            linea = chart.AddPlot(vtk.vtkChart.LINE)
            linea.SetInputData(tabla, 0, 1)
            linea.SetWidth(0.6)
            linea.SetColor(150, 170, 200, 70)      # tenue: son el fondo
            linea.LegendVisibilityOff()

        if promedio is not None:
            prom = np.nan_to_num(np.asarray(promedio, dtype=np.float64))
            tabla = vtk.vtkTable()
            tabla.AddColumn(self._columna(np.arange(prom.size, dtype=np.float64), "Muestra"))
            tabla.AddColumn(self._columna(prom, "Promedio"))
            linea = chart.AddPlot(vtk.vtkChart.LINE)
            linea.SetInputData(tabla, 0, 1)
            linea.SetWidth(2.5)
            linea.SetColor(*color_promedio, 255)
            linea.LegendVisibilityOff()

        mostrados = len(columnas)
        sufijo = "" if mostrados == n_ciclos else f", se dibujan {mostrados}"
        chart.SetTitle(f"{etiqueta} — {n_ciclos} ciclos{sufijo}")
        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Muestra dentro de la ventana")
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle("Amplitud")
        return chart

    def _grafico_mapa_log(self, matriz, frecuencias, eje_x, titulo, etiqueta_x):
        """Un mapa con el eje de frecuencias en escala logarítmica.

        **No puede usar el mismo código que `_grafico_mapa`.** Aquel reparte las
        filas a intervalos iguales, que es lo que hace `imagesc` y lo correcto
        para el eje lineal de PAC. Aquí el MATLAB pasa por `pcolor` y además
        convierte el eje a `log10`, así que las filas van a alturas desiguales:
        hay que remuestrear primero (`remuestrear_en_log`).

        Las marcas del eje son las del original —1,5, 2 y 2,5 en logaritmo,
        etiquetadas con `round(10^v)`: 32, 100 y 316 Hz— y solo se ponen las que
        caen dentro del rango.
        """
        datos, log_min, log_max = cp.remuestrear_en_log(
            np.nan_to_num(np.asarray(matriz, dtype=np.float64),
                          nan=0.0, posinf=0.0, neginf=0.0),
            frecuencias)
        datos = datos.astype(np.float32)
        n_freq, n_x = datos.shape

        x = np.asarray(eje_x, dtype=np.float64)
        paso_x = (x[-1] - x[0]) / max(1, n_x - 1)
        paso_y = (log_max - log_min) / max(1, n_freq - 1)

        img = vtk.vtkImageData()
        img.SetDimensions(n_x, n_freq, 1)
        img.SetSpacing(paso_x, paso_y, 1.0)
        img.SetOrigin(float(x[0]), log_min, 0.0)
        # `remuestrear_en_log` ya devuelve la fila 0 en la frecuencia mas baja,
        # que es como VTK dibuja hacia arriba: aqui no hay que voltear nada.
        img.GetPointData().SetScalars(numpy_support.numpy_to_vtk(
            np.ascontiguousarray(datos).ravel(), deep=True, array_type=vtk.VTK_FLOAT))
        img.Modified()

        finitos = datos[np.isfinite(datos)]
        vmin, vmax = (float(finitos.min()), float(finitos.max())) if finitos.size else (0.0, 1.0)
        if vmax <= vmin:
            vmax = vmin + 1.0

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
        anotar_mapa(chart, img, lut)
        chart.SetTitle(titulo)
        eje_horizontal = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        eje_horizontal.SetTitle(etiqueta_x)
        eje_horizontal.SetBehavior(vtk.vtkAxis.FIXED)
        eje_horizontal.SetRange(float(x[0]), float(x[-1] + paso_x))

        eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
        eje_y.SetTitle("Frecuencia (Hz) — log")
        eje_y.SetBehavior(vtk.vtkAxis.FIXED)
        eje_y.SetRange(log_min, log_max)

        posiciones = vtk.vtkDoubleArray()
        etiquetas = vtk.vtkStringArray()
        for v in self.MARCAS_LOG:
            if log_min <= v <= log_max:
                posiciones.InsertNextValue(v)
                etiquetas.InsertNextValue(str(int(round(10 ** v))))
        if posiciones.GetNumberOfTuples():
            eje_y.SetCustomTickPositions(posiciones, etiquetas)
        return chart

    def _grafico_mapa(self, r, titulo):
        """El mapa fase-frecuencia, con el mismo patrón vectorizado del wavelet."""
        fases, mapa = self._fase_en_grados(
            r.fases, np.nan_to_num(np.asarray(r.mapa, dtype=np.float32),
                                   nan=0.0, posinf=0.0, neginf=0.0))
        n_freq, n_fase = mapa.shape
        frecuencias = r.frecuencias

        paso_fase = (fases[-1] - fases[0]) / max(1, n_fase - 1)
        f_min, f_max = float(np.min(frecuencias)), float(np.max(frecuencias))
        paso_freq = (f_max - f_min) / max(1, n_freq - 1)

        img = vtk.vtkImageData()
        img.SetDimensions(n_fase, n_freq, 1)
        img.SetSpacing(paso_fase, paso_freq, 1.0)
        img.SetOrigin(float(fases[0]), f_min, 0.0)

        # La fila 0 del mapa es la frecuencia mas alta (el eje viene descendente);
        # se voltea para que el dibujo crezca hacia arriba.
        plano = np.ascontiguousarray(mapa[::-1, :]).ravel()
        img.GetPointData().SetScalars(
            numpy_support.numpy_to_vtk(plano, deep=True, array_type=vtk.VTK_FLOAT))
        img.Modified()

        finitos = mapa[np.isfinite(mapa)]
        vmin, vmax = (float(finitos.min()), float(finitos.max())) if finitos.size else (0.0, 1.0)
        if vmax <= vmin:
            vmax = vmin + 1.0

        # `jet`, el mismo mapa de colores que pasa f_Phase_PAC a f_ImageMatrix.
        # Para un mapa z-scoreado un divergente seria mejor practica —el blanco
        # marcaria el cero—, pero el criterio es parecerse a la referencia.
        lut = vtk.vtkColorTransferFunction()
        for fraccion, (rr, gg, bb) in zip(
                (0.0, 0.125, 0.375, 0.625, 0.875, 1.0),
                ((0.0, 0.0, 0.5), (0.0, 0.0, 1.0), (0.0, 1.0, 1.0),
                 (1.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.0, 0.0))):
            lut.AddRGBPoint(vmin + fraccion * (vmax - vmin), rr, gg, bb)

        chart = vtk.vtkChartHistogram2D()
        chart.SetInputData(img, 0)
        chart.SetTransferFunction(lut)
        anotar_mapa(chart, img, lut)
        chart.SetTitle(f"{titulo} — mapa fase/frecuencia")
        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Fase (°)")
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle("Frecuencia (Hz)")
        # FIXED: si no, VTK redondea el rango hacia afuera y deja franjas vacias
        # a los lados —el eje llegaba a 400 grados cuando los datos terminan en
        # 360, y a 600 Hz cuando llegan a 500—.
        eje_x = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        eje_x.SetBehavior(vtk.vtkAxis.FIXED)
        eje_x.SetRange(float(fases[0]), float(fases[-1] + paso_fase))
        eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
        eje_y.SetBehavior(vtk.vtkAxis.FIXED)
        eje_y.SetRange(f_min, f_max)
        return chart

    @staticmethod
    def _fase_en_grados(fases_rad, *matrices, eje=-1):
        """Pasa el eje de fase a grados de 0 a 360 y rota los datos con él.

        **Por qué grados y no radianes.** La brújula marca 0-360, porque es la
        convención de un instrumento polar y es lo que hace la `compass` de
        MATLAB. El histograma y los mapas venían en radianes de −π a π, que es
        lo que hace el `bar(index_pi, ...)` del original. En MATLAB eso no
        molesta porque son ventanas separadas; aquí van apilados uno encima de
        otro, y un acoplamiento que la brújula sitúa en 280,6° aparecía en el
        histograma como −79,4°. Mismo dato, dos lecturas.

        **Por qué hay que rotar y no basta con reetiquetar.** Los bins empiezan
        en −π. Al pasarlos a 0-360 el que estaba en −180 se convierte en 180, o
        sea salta al final: el eje dejaría de ir en orden. Rotar los datos la
        misma cantidad los deja alineados. La fase es circular, así que rotar
        no pierde nada — pero **la forma del histograma cambia** respecto al de
        MATLAB, que arranca en −180.

        El cálculo sigue en radianes de principio a fin; esto es solo el dibujo.
        """
        grados = np.rad2deg(np.asarray(fases_rad, dtype=np.float64)) % 360.0
        # El modulo deja basura de coma flotante donde tendria que haber un cero
        # clavado, porque −π y π son el mismo punto del circulo: 2,5e−14 grados.
        # No afecta al dibujo, pero sale escrita en el CSV.
        grados[np.isclose(grados, 0.0, atol=1e-9) | np.isclose(grados, 360.0, atol=1e-9)] = 0.0
        corte = int(np.argmin(grados))          # donde queda el 0 tras envolver
        rotadas = tuple(np.roll(np.asarray(m), -corte, axis=eje) for m in matrices)
        return (np.roll(grados, -corte),) + rotadas

    def _grafico_histograma(self, r):
        grados, valores = self._fase_en_grados(
            r.fases, np.nan_to_num(np.asarray(r.histograma, dtype=np.float64)))
        tabla = vtk.vtkTable()
        tabla.AddColumn(self._columna(grados, "Fase"))
        tabla.AddColumn(self._columna(valores, "Energía"))

        chart = vtk.vtkChartXY()
        barras = chart.AddPlot(vtk.vtkChart.BAR)
        barras.SetInputData(tabla, 0, 1)
        barras.SetColor(70, 110, 190, 255)
        barras.LegendVisibilityOff()
        chart.SetTitle("Histograma por fase")
        chart.SetShowLegend(False)
        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Fase (°)")

        # MATLAB acerca el eje Y al rango de los datos con un 10% de margen, en
        # vez de arrancar en cero:
        #     set(gca,'YLim',[(minh1 - dis1*0.1) (maxh1 + dis1*0.1)])
        # Importa: con estos valores —de ~19 a ~46— dibujar desde cero aplasta
        # la variacion y el histograma parece plano.
        finitos = valores[np.isfinite(valores)]
        if finitos.size:
            minimo, maximo = float(finitos.min()), float(finitos.max())
            margen = (maximo - minimo) * 0.1 or (abs(maximo) * 0.1 or 1.0)
            eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
            eje_y.SetBehavior(vtk.vtkAxis.FIXED)
            eje_y.SetRange(minimo - margen, maximo + margen)
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle("Energía")
        return chart

    def _grafico_brujula(self, r, extra=None):
        """El vector medio de acoplamiento, como la `compass` de MATLAB.

        Antes se dibujaba encima de un `vtkChartXY`: daba la forma, pero los ejes
        mostraban números de abscisa y ordenada, y el ángulo solo salía en el
        título **en radianes**. MATLAB dibuja un instrumento polar: radios cada
        30° rotulados en **grados**, anillos de magnitud con su valor y ningún
        eje cartesiano. Eso es lo que hace ahora `BrujulaPolar`.

        Con `extra` añade esos vectores en azul claro detrás del principal: es el
        segundo `compass` de `f_Phase_PAC_Pdetect`, que superpone los 16 vectores
        por grupo de bins y encima el vector medio.
        """
        n_extra = 0 if extra is None else len(np.asarray(extra).ravel())
        return BrujulaPolar(r.vector, extra=extra,
                            titulo=titulo_de(r.vector, n_extra))

    def _grafico_senal(self, tiempo, serie, etiqueta, unidad="Amplitud"):
        n = min(len(tiempo), len(serie))
        tabla = vtk.vtkTable()
        tabla.AddColumn(self._columna(np.asarray(tiempo[:n]), "Tiempo"))
        tabla.AddColumn(self._columna(np.nan_to_num(np.asarray(serie[:n])), etiqueta))

        chart = vtk.vtkChartXY()
        linea = chart.AddPlot(vtk.vtkChart.LINE)
        linea.SetInputData(tabla, 0, 1)
        linea.SetWidth(1.0)
        linea.SetColor(40, 90, 190, 255)
        linea.LegendVisibilityOff()
        chart.SetTitle(etiqueta)
        chart.SetShowLegend(False)
        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Tiempo (s)")
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle(unidad)
        return chart

    @staticmethod
    def _columna(datos, nombre):
        arr = numpy_support.numpy_to_vtk(
            np.ascontiguousarray(datos, dtype=np.float64), deep=True,
            array_type=vtk.VTK_DOUBLE)
        arr.SetName(nombre)
        return arr

    def _alturas(self):
        """La altura en píxeles de cada gráfico, en el orden en que se apilan.

        La lista la llena quien dibuja. Antes se deducía comparando cada gráfico
        contra `self._mapa_chart` y compañía, lo que bastaba con los seis de PAC
        pero no con los trece de Psel, donde hay dos mapas, dos brújulas y tres
        pilas de ciclos.
        """
        if len(self._altos) == len(self._charts):
            return list(self._altos)
        return [self.ALTO_SENAL] * len(self._charts)

    def _ajustar_alto_del_lienzo(self):
        """Hace el lienzo tan alto como la pila necesite; el resto lo desliza
        el QScrollArea."""
        if self.vtk_widget is None or not self._charts:
            return
        total = sum(self._alturas()) + self.HUECO * (len(self._charts) - 1) + 40
        if self.vtk_widget.minimumHeight() != total:
            self.vtk_widget.setMinimumHeight(int(total))

    def _reacomodar(self):
        """Reparte los gráficos en vertical, con altura fija cada uno.

        A diferencia de `_relayout_charts` de `open_signal`, aquí **no** se
        reparte el alto disponible entre los gráficos: cada uno conserva su
        altura útil y el lienzo crece hacia abajo. Con seis gráficos —y uno de
        ellos cuadrado— repartir dejaba la brújula minúscula y los paneles de
        señal ilegibles.
        """
        if not self._context_view or not self._charts:
            return
        ancho, alto = self._context_view.GetRenderWindow().GetSize()
        if ancho <= 0 or alto <= 0:
            return

        margen_x, margen_arriba = 12, 16
        y = float(alto - margen_arriba)
        for chart, h in zip(self._charts, self._alturas()):
            y -= h
            chart.SetAutoSize(False)
            if chart in self._cuadrados:
                # Cuadrada y centrada: con el ancho completo los circulos
                # saldrian como elipses y la flecha apuntaria a un angulo falso.
                lado = float(min(h, ancho - 2 * margen_x))
                chart.SetSize(vtk.vtkRectf(float((ancho - lado) / 2), float(y), lado, lado))
            else:
                chart.SetSize(vtk.vtkRectf(float(margen_x), float(y),
                                           float(ancho - 2 * margen_x), float(h)))
            y -= self.HUECO

    # =====================================================
    # === Exportación
    # =====================================================
    def _actualizar_menu(self):
        """Apunta el menú contextual a los gráficos y al canal actuales."""
        if self.vtk_menu is None:
            return
        self.vtk_menu.set_chart([c for c in self._charts if isinstance(c, vtk.vtkChart)])
        params = (self._ultimo or {}).get("parametros") or {}
        self.vtk_menu.set_signal_name(params.get("señal") or "signal")
        self.vtk_menu.set_channel_name(params.get("canal") or None)

    @staticmethod
    def _num(x):
        """float para exportar; NaN e infinitos salen vacíos (JSON no los admite)."""
        x = float(x)
        return x if np.isfinite(x) else None

    def _secciones_resultado(self) -> dict:
        """Parámetros, resumen, histograma de fase y mapa de la última ejecución."""
        r = self._ultimo["resultado"]
        p = self._ultimo["parametros"]
        n = self._num

        # Los ángulos se exportan en grados de 0 a 360, los mismos que se ven en
        # pantalla: si el histograma dibuja una barra en 280° y el CSV la pone en
        # −1,39, parecen dos corridas distintas.
        grados, histograma = self._fase_en_grados(r.fases, r.histograma)
        _, mapa = self._fase_en_grados(r.fases, r.mapa)

        resumen = [["magnitud_vector_medio", n(abs(r.vector))],
                   ["angulo_vector_medio_grados", n(np.rad2deg(np.angle(r.vector)) % 360.0)],
                   ["fs_efectiva_hz", n(r.fs_efectiva)]]
        if hasattr(r, "n_ciclos"):
            resumen += [["n_ciclos", int(r.n_ciclos)],
                        ["ciclos_descartados", int(r.ciclos_descartados)],
                        ["vpp", n(r.vpp)], ["vpp_full", n(r.vpp_full)], ["vrms", n(r.vrms)]]
        else:
            resumen += [["n_trials", int(r.n_trials)]]

        encabezado_mapa = ["frecuencia_hz"] + [f"fase_{g:.1f}deg" for g in grados]
        filas_mapa = [[n(fr)] + [n(v) for v in fila] for fr, fila in zip(r.frecuencias, mapa)]
        return {
            "Parametros": (["parametro", "valor"], [[k, v] for k, v in p.items()]),
            "Resumen": (["medida", "valor"], resumen),
            "Histograma": (["fase_grados", "valor"],
                           [[n(g), n(v)] for g, v in zip(grados, histograma)]),
            "Mapa": (encabezado_mapa, filas_mapa),
        }

    def exportar_resultados(self, fmt: str):
        """Exporta los números de la última ejecución, con los parámetros que la produjeron."""
        if not self._ultimo or self.vtk_menu is None:
            self.alerts.warning("Primero ejecuta un análisis PAC para poder exportar sus resultados.")
            return
        self.vtk_menu.export_service.export_sections(self._secciones_resultado(), fmt)

    # =====================================================
    # === Guardar y restaurar el análisis en el proyecto
    # =====================================================
    def get_analysis_params(self) -> dict:
        return {
            "pac_type": self.ui.pacTypeComboBox.currentText(),
            "sample_fq": self.ui.sampleDensitySpinBox.value(),
            "p1": self.ui.lowFrequencySpinBox.value(),
            "p2": self.ui.highFrequencySpinBox.value(),
            "a1": self.ui.ampLowFrequencySpinBox.value(),
            "a2": self.ui.ampHighFrequencySpinBox.value(),
            "trial": self.ui.trialSpinBox.value(),
            "trials_used": self._trials_used,
        }

    def apply_analysis_params(self, params: dict):
        idx = self.ui.pacTypeComboBox.findText(params.get("pac_type", ""))
        if idx >= 0:
            self.ui.pacTypeComboBox.setCurrentIndex(idx)
        d = self.DEFAULTS
        self.ui.sampleDensitySpinBox.setValue(params.get("sample_fq", d["sample_fq"]))
        self.ui.lowFrequencySpinBox.setValue(params.get("p1", d["p1"]))
        self.ui.highFrequencySpinBox.setValue(params.get("p2", d["p2"]))
        self.ui.ampLowFrequencySpinBox.setValue(params.get("a1", d["a1"]))
        self.ui.ampHighFrequencySpinBox.setValue(params.get("a2", d["a2"]))
        self._actualizar_selector_trial()
        self.ui.trialSpinBox.setValue(params.get("trial", 1))
        self._restaurando = True
        self.on_create_pac()
