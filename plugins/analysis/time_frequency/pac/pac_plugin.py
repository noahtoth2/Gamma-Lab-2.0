from functools import partial

import numpy as np
import vtk
from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util import numpy_support

from core.plugins.interfaces import IPlugin
from plugins.analysis.time_frequency.pac import compute as cp
from plugins.analysis.time_frequency.pac.pac_plugin_ui import Ui_Pac


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
        self._brujula = None
        self._mapa_chart = None
        self._histograma_chart = None
        self._charts_senal = []
        self._sincronizando = False
        self._scroll = None
        self._handle = None
        self._calculando = False

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
            self.alerts.info("Hay un cálculo de PAC en curso; espera a que termine.")
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

        if tipo == "PAC Psel":
            self.alerts.info("PAC Psel todavía no está implementado.")
            return

        # La casilla muestra 1 para el primer trial, como MATLAB; aquí se resta
        # uno porque Python indexa desde cero.
        indice = self.ui.trialSpinBox.value() - 1
        if self._usa_un_solo_trial() and not (0 <= indice < datos.shape[1]):
            self.alerts.error(f"El trial {indice + 1} no existe; hay {datos.shape[1]}.")
            return

        tasks.cancel_all_from(self.meta.id)
        self._terminar_calculo()
        self.stop()

        self._calculando = True
        self.ui.createPacButton.setEnabled(False)
        self.ui.createPacButton.setText("Computing...")

        comun = dict(fs_calculado=fs_calculado, fs=fs, p1=p1, p2=p2, a1=a1, a2=a2)
        if self._usa_un_solo_trial():
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
            self.render_resultado(resultado, tipo)
            self._notify(
                f"{tipo}: acoplamiento {abs(resultado.vector):.4f} "
                f"en la fase {np.angle(resultado.vector):+.3f} rad "
                f"({resultado.n_trials} trial(s))")
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
    HUECO = 52

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
        self._context_view.GetRenderer().SetBackground(0.98, 0.98, 0.98)
        self.vtk_widget.AddObserver(vtk.vtkCommand.EndInteractionEvent,
                                    self._sincronizar_eje_de_tiempo)
        self.vtk_widget.Initialize()
        self.vtk_widget.Start()

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

        # Los cuatro paneles de senal comparten el eje de tiempo, como el
        # `linkaxes(ax,'x')` de MATLAB: al hacer zoom en uno se mueven todos.
        self._charts_senal = []
        for etiqueta, unidad, serie in (
                ("Original", "Amplitud", r.senal),
                ("Filtrada en fase", "Amplitud", r.banda_fase),
                ("Fase instantánea", "rad", r.fase),
                ("Filtrada en amplitud", "Amplitud", r.banda_amplitud)):
            chart = self._grafico_senal(r.tiempo, serie, etiqueta, unidad)
            self._charts_senal.append(chart)
            self._charts.append(chart)

        for chart in self._charts:
            escena.AddItem(chart)
        self._ajustar_alto_del_lienzo()
        self._reacomodar()
        self._context_view.GetRenderWindow().Render()

    def _grafico_mapa(self, r, titulo):
        """El mapa fase-frecuencia, con el mismo patrón vectorizado del wavelet."""
        mapa = np.nan_to_num(np.asarray(r.mapa, dtype=np.float32),
                             nan=0.0, posinf=0.0, neginf=0.0)
        n_freq, n_fase = mapa.shape
        fases, frecuencias = r.fases, r.frecuencias

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
        chart.SetTitle(f"{titulo} — mapa fase/frecuencia")
        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Fase (rad)")
        chart.GetAxis(vtk.vtkAxis.LEFT).SetTitle("Frecuencia (Hz)")
        # FIXED: si no, VTK redondea el rango hacia afuera y deja franjas vacias
        # a los lados —el eje decia -3,5 a 3,5 cuando los datos llegan a +-pi, y
        # 0 a 600 Hz cuando llegan a 500—.
        eje_x = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        eje_x.SetBehavior(vtk.vtkAxis.FIXED)
        eje_x.SetRange(float(fases[0]), float(fases[-1] + paso_fase))
        eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
        eje_y.SetBehavior(vtk.vtkAxis.FIXED)
        eje_y.SetRange(f_min, f_max)
        return chart

    def _grafico_histograma(self, r):
        valores = np.nan_to_num(np.asarray(r.histograma, dtype=np.float64))
        tabla = vtk.vtkTable()
        tabla.AddColumn(self._columna(r.fases, "Fase"))
        tabla.AddColumn(self._columna(valores, "Energía"))

        chart = vtk.vtkChartXY()
        barras = chart.AddPlot(vtk.vtkChart.BAR)
        barras.SetInputData(tabla, 0, 1)
        barras.SetColor(70, 110, 190, 255)
        barras.LegendVisibilityOff()
        chart.SetTitle("Histograma por fase")
        chart.SetShowLegend(False)
        chart.GetAxis(vtk.vtkAxis.BOTTOM).SetTitle("Fase (rad)")

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

    def _grafico_brujula(self, r):
        """El vector medio de acoplamiento, como la `compass` de MATLAB.

        VTK no trae gráfico polar, así que se dibuja a mano sobre un chart
        normal: dos círculos de referencia, la cruz de los ejes y la flecha.
        El radio sale igual que en MATLAB —el mayor entre |parte real| y
        |parte imaginaria|—, que es para lo que allá sirven las cuatro flechas
        invisibles: forzar la escala y que quede centrado en el origen.

        Para que los círculos no salgan como elipses, `_reacomodar` le da a este
        gráfico un recuadro **cuadrado**, no una franja del ancho completo.
        """
        v = r.vector
        radio = max(abs(v.real), abs(v.imag))
        if not np.isfinite(radio) or radio <= 0:
            radio = 1.0

        chart = vtk.vtkChartXY()
        chart.SetTitle(f"Vector medio — magnitud {abs(v):.4f}, "
                       f"fase {np.angle(v):+.3f} rad")

        def traza(xs, ys, color, grosor):
            tabla = vtk.vtkTable()
            tabla.AddColumn(self._columna(np.asarray(xs, dtype=np.float64), "x"))
            tabla.AddColumn(self._columna(np.asarray(ys, dtype=np.float64), "y"))
            linea = chart.AddPlot(vtk.vtkChart.LINE)
            linea.SetInputData(tabla, 0, 1)
            linea.SetColor(*color)
            linea.SetWidth(grosor)
            linea.LegendVisibilityOff()

        # Círculos de referencia, a la mitad y al borde
        angulos = np.linspace(0.0, 2.0 * np.pi, 181)
        for fraccion in (0.5, 1.0):
            traza(radio * fraccion * np.cos(angulos),
                  radio * fraccion * np.sin(angulos), (205, 205, 205, 255), 1.0)

        # La cruz de los ejes
        traza([-radio, radio], [0.0, 0.0], (170, 170, 170, 255), 1.0)
        traza([0.0, 0.0], [-radio, radio], (170, 170, 170, 255), 1.0)

        # La flecha, con su punta
        traza([0.0, v.real], [0.0, v.imag], (40, 90, 190, 255), 2.5)
        theta, largo = np.angle(v), 0.12 * radio
        for desvio in (+2.6, -2.6):          # ~150 grados a cada lado del eje
            traza([v.real, v.real + largo * np.cos(theta + desvio)],
                  [v.imag, v.imag + largo * np.sin(theta + desvio)],
                  (40, 90, 190, 255), 2.5)

        margen = 1.15 * radio
        for eje in (vtk.vtkAxis.BOTTOM, vtk.vtkAxis.LEFT):
            chart.GetAxis(eje).SetBehavior(vtk.vtkAxis.FIXED)
            chart.GetAxis(eje).SetRange(-margen, margen)
            chart.GetAxis(eje).SetTitle("")
        chart.SetShowLegend(False)
        return chart

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
        """La altura en píxeles de cada gráfico, en el orden en que se apilan."""
        alturas = []
        for chart in self._charts:
            if chart is self._mapa_chart:
                alturas.append(self.ALTO_MAPA)
            elif chart is self._histograma_chart:
                alturas.append(self.ALTO_HISTOGRAMA)
            elif chart is self._brujula:
                alturas.append(self.LADO_BRUJULA)
            else:
                alturas.append(self.ALTO_SENAL)
        return alturas

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
            if chart is self._brujula:
                # Cuadrada y centrada: con el ancho completo los circulos
                # saldrian como elipses y la flecha apuntaria a un angulo falso.
                lado = float(min(h, ancho - 2 * margen_x))
                chart.SetSize(vtk.vtkRectf(float((ancho - lado) / 2), float(y), lado, lado))
            else:
                chart.SetSize(vtk.vtkRectf(float(margen_x), float(y),
                                           float(ancho - 2 * margen_x), float(h)))
            y -= self.HUECO

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
        self.on_create_pac()
