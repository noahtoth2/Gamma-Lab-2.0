from functools import partial

import numpy as np
import vtk
from PyQt5.QtWidgets import QScrollArea, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util import numpy_support

from core.plugins.interfaces import IPlugin
from plugins.analysis.time_frequency.modulation_index import compute as cm
from plugins.analysis.time_frequency.modulation_index.modulation_index_plugin_ui import (
    Ui_ModulationIndex)


class Modulation_index_plugin(IPlugin):
    DEFAULTS = {
        "sample_fq": 1000,     # en MATLAB MI lee ResampleFr, que vale 1000
        "fq_p1": 0.1,
        "fq_p2": 10.0,
        "p_step": 0.1,
        "fq_a1": 10.0,
        "fq_a2": 500.0,
        "a_step": 0.5,
    }

    ALTO_COMODULOGRAMA = 420
    # El fondo del lienzo. Se usa dos veces: al pintar el renderizador y como
    # color de los NaN, que van transparentes y por tanto lo dejan ver.
    FONDO = (0.98, 0.98, 0.98)

    def __init__(self, meta):
        super().__init__(meta)
        self.vtk_widget = None
        self._context_view = None
        self._charts = []
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
            self.ui = Ui_ModulationIndex()
            self.ui.setupUi(self.widget)
            self.alerts.parent = self.widget
            self._init_controls()
            self.ui.clearButton.clicked.connect(self._on_clear_clicked)
            self.ui.generateButton.clicked.connect(self.on_create_mi)
            self.ui.prevTrialButton.clicked.connect(partial(self._mover_trial, -1))
            self.ui.nextTrialButton.clicked.connect(partial(self._mover_trial, +1))
        else:
            self.widget.setParent(parent)
        return self.widget

    def _init_controls(self):
        self.ui.sampleFqSpinBox.setRange(0, 1_000_000)
        self.ui.sampleFqSpinBox.setSingleStep(100)
        for spin in (self.ui.fqP1SpinBox, self.ui.fqP2SpinBox,
                     self.ui.fqA1SpinBox, self.ui.fqA2SpinBox):
            spin.setDecimals(2)
            spin.setRange(0.0, 100000.0)
            spin.setSingleStep(1.0)
        for spin in (self.ui.pStepSpinBox, self.ui.aStepSpinBox):
            spin.setDecimals(2)
            spin.setRange(0.0, 100000.0)
            spin.setSingleStep(0.1)
        self._on_clear_clicked()

    def _on_clear_clicked(self):
        if self._calculando:
            self.alerts.info("Hay un cálculo del índice de modulación en curso; "
                             "espera a que termine.")
            return
        d = self.DEFAULTS
        self.ui.sampleFqSpinBox.setValue(d["sample_fq"])
        self.ui.fqP1SpinBox.setValue(d["fq_p1"])
        self.ui.fqP2SpinBox.setValue(d["fq_p2"])
        self.ui.pStepSpinBox.setValue(d["p_step"])
        self.ui.fqA1SpinBox.setValue(d["fq_a1"])
        self.ui.fqA2SpinBox.setValue(d["fq_a2"])
        self.ui.aStepSpinBox.setValue(d["a_step"])
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

    def _actualizar_selector_trial(self):
        if self.ui is None:
            return
        n = self._n_trials()
        self.ui.trialSpinBox.setEnabled(n > 0)
        self.ui.prevTrialButton.setEnabled(n > 0)
        self.ui.nextTrialButton.setEnabled(n > 0)
        self.ui.trialSpinBox.setMaximum(max(1, n))
        if self.ui.trialSpinBox.value() > max(1, n):
            self.ui.trialSpinBox.setValue(1)
        self.ui.trialTotalLabel.setText(f"de {n}" if n else "sin trials")

    def _mover_trial(self, paso: int):
        if not self.ui.trialSpinBox.isEnabled():
            return
        nuevo = self.ui.trialSpinBox.value() + paso
        if self.ui.trialSpinBox.minimum() <= nuevo <= self.ui.trialSpinBox.maximum():
            self.ui.trialSpinBox.setValue(nuevo)
            self.on_create_mi()

    # =====================================================
    # === Lógica principal
    # =====================================================
    def on_create_mi(self):
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
        indice = self.ui.trialSpinBox.value() - 1
        if not (0 <= indice < datos.shape[1]):
            self.alerts.error(f"El trial {indice + 1} no existe; hay {datos.shape[1]}.")
            return

        tasks.cancel_all_from(self.meta.id)
        self._terminar_calculo()
        self.stop()

        self._calculando = True
        self.ui.generateButton.setEnabled(False)
        self.ui.generateButton.setText("Computing...")

        handle = tasks.submit(
            cm.comodulograma, owner=self.meta.id,
            sig=datos[:, indice],
            fs_calculado=round(1.0 / (t[1] - t[0]), 3),
            fs=float(self.ui.sampleFqSpinBox.value()),
            p_ini=float(self.ui.fqP1SpinBox.value()),
            p_fin=float(self.ui.fqP2SpinBox.value()),
            pstep=float(self.ui.pStepSpinBox.value()),
            a_ini=float(self.ui.fqA1SpinBox.value()),
            a_fin=float(self.ui.fqA2SpinBox.value()),
            astep=float(self.ui.aStepSpinBox.value()),
        )
        self._handle = handle
        handle.progress.connect(partial(self._on_mi_progress, handle))
        handle.finished.connect(partial(self._on_mi_done, handle, indice))
        handle.failed.connect(partial(self._on_mi_failed, handle))
        handle.cancelled.connect(partial(self._on_mi_cancelled, handle))

    def _terminar_calculo(self):
        self._calculando = False
        self._handle = None
        if self.ui is not None:
            self.ui.generateButton.setEnabled(True)
            self.ui.generateButton.setText("Generate")

    def _on_mi_progress(self, handle, percent, message):
        if handle is not self._handle:
            return
        self._log(f"{message} ({percent}%)")
        self._notify(f"{message} ({percent}%)")

    def _on_mi_failed(self, handle, message):
        if handle is not self._handle:
            return
        self._terminar_calculo()
        self.alerts.error(f"No se pudo calcular el índice de modulación: {message}")

    def _on_mi_cancelled(self, handle):
        if handle is not self._handle:
            return
        self._terminar_calculo()

    def _on_mi_done(self, handle, indice, resultado):
        """Ya en el hilo de la interfaz: aquí se dibuja."""
        if handle is not self._handle:
            return
        try:
            if self.ui is None or resultado is None:
                return
            self.ensure_vtk()
            self.render_resultado(resultado, indice)

            self._avisar_de_los_limites(resultado)
            self.mark_project_dirty()
        except Exception as e:
            self._log("render_resultado:", e)
            self.alerts.error(f"No se pudo dibujar el comodulograma: {e}")
        finally:
            self._terminar_calculo()
            self.process("Done")

    def _avisar_de_los_limites(self, r):
        """Un solo diálogo con todo lo que el usuario necesita saber del gráfico.

        Son dos avisos distintos y encadenar dos ventanas modales seguidas
        molesta, así que se juntan. Si hay alguno grave el diálogo sube a
        advertencia; si no, queda en informativo.
        """
        avisos, grave = [], False

        sin_datos = r.frecuencias_amplitud.size - r.bandas_calculadas
        if sin_datos > 0:
            # No es un fallo: es el limite fijo de 178 que trae f_PAC_sing.
            avisos.append(
                f"El cálculo solo cubre las primeras {r.bandas_calculadas} "
                f"frecuencias de amplitud, hasta "
                f"{r.frecuencias_amplitud[r.bandas_calculadas - 1]:g} Hz. "
                f"Las otras {sin_datos} quedan sin datos: es el límite fijo que trae "
                f"el cálculo original de MATLAB. En el gráfico salen en blanco.")

        if r.ciclos_banda_lenta < cm.CICLOS_MINIMOS_FASE:
            # MATLAB no avisa de esto; es un anadido para no leer ruido como
            # acoplamiento. El calculo no cambia.
            grave = True
            p_minima = cm.CICLOS_MINIMOS_FASE / r.duracion_s if r.duracion_s > 0 else 0.0
            avisos.append(
                f"El trial dura {r.duracion_s:.2f} s y la frecuencia de fase más baja "
                f"es {r.frecuencias_fase[0]:g} Hz, así que de esa banda solo caben "
                f"{r.ciclos_banda_lenta:.1f} ciclos. Hacen falta al menos "
                f"{cm.CICLOS_MINIMOS_FASE:g} para que el índice sea fiable: por debajo "
                f"de eso sale alto por azar y aparenta un acoplamiento que no existe. "
                f"Sube «Fq P1» a {p_minima:.1f} Hz o usa trials más largos.")

        if avisos:
            texto = '\n\n'.join(avisos)
            if grave:
                self.alerts.warning(texto)
            else:
                self.alerts.info(texto)

    # =====================================================
    # === VTK
    # =====================================================
    def ensure_vtk(self):
        if self.vtk_widget is not None and self._context_view is not None:
            return
        contenedor = self.ui.plotArea
        if contenedor.layout() is None:
            lay = QVBoxLayout(contenedor)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setSpacing(0)

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
        self.vtk_widget.Initialize()
        self.vtk_widget.Start()

    def render_resultado(self, r, indice=0):
        escena = self._context_view.GetScene()
        escena.ClearItems()
        self._charts = [self._grafico_comodulograma(r, indice)]
        for chart in self._charts:
            escena.AddItem(chart)
        self.vtk_widget.setMinimumHeight(self.ALTO_COMODULOGRAMA + 40)
        self._reacomodar()
        self._context_view.GetRenderWindow().Render()

    def _grafico_comodulograma(self, r, indice):
        """`f_ImageMatrix(MInorm, fp, fm, [], 'jet', 256)`: fase en la x,
        amplitud en la y."""
        datos = np.asarray(r.mi_norm, dtype=np.float32)
        finitos = datos[np.isfinite(datos)]
        # Los NaN se quedan como NaN: mas abajo la tabla de color los pinta
        # transparentes y dejan ver el fondo. Es lo que hace `imagesc` en
        # f_ImageMatrix, y la diferencia no es estetica: rellenarlos con el
        # minimo los disfrazaba de "acoplamiento bajo" cuando lo que pasa es
        # que ahi no se calculo nada. Con los valores por defecto eso son 803
        # de las 981 filas, el 82 % del grafico.
        vmin = float(finitos.min()) if finitos.size else 0.0
        vmax = float(finitos.max()) if finitos.size else 1.0
        if vmax <= vmin:
            vmax = vmin + 1.0

        n_amp, n_fase = datos.shape
        fp, fa = r.frecuencias_fase, r.frecuencias_amplitud
        paso_x = (fp[-1] - fp[0]) / max(1, n_fase - 1) if n_fase > 1 else 1.0
        paso_y = (fa[-1] - fa[0]) / max(1, n_amp - 1) if n_amp > 1 else 1.0

        img = vtk.vtkImageData()
        img.SetDimensions(n_fase, n_amp, 1)
        img.SetSpacing(paso_x, paso_y, 1.0)
        img.SetOrigin(float(fp[0]), float(fa[0]), 0.0)
        # La fila 0 es la frecuencia de amplitud mas baja y VTK dibuja de abajo
        # hacia arriba, asi que no hay que voltear nada.
        img.GetPointData().SetScalars(numpy_support.numpy_to_vtk(
            np.ascontiguousarray(datos).ravel(), deep=True, array_type=vtk.VTK_FLOAT))
        img.Modified()

        # `jet`, el mismo mapa de colores que usa f_ImageMatrix
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
        chart.SetTitle(f"Índice de modulación — trial {indice + 1}")
        eje_x = chart.GetAxis(vtk.vtkAxis.BOTTOM)
        eje_x.SetTitle("Frecuencia de fase (Hz)")
        eje_x.SetBehavior(vtk.vtkAxis.FIXED)
        eje_x.SetRange(float(fp[0]), float(fp[-1] + paso_x))
        eje_y = chart.GetAxis(vtk.vtkAxis.LEFT)
        eje_y.SetTitle("Frecuencia de amplitud (Hz)")
        eje_y.SetBehavior(vtk.vtkAxis.FIXED)
        eje_y.SetRange(float(fa[0]), float(fa[-1] + paso_y))
        return chart

    def _reacomodar(self):
        if not self._context_view or not self._charts:
            return
        ancho, alto = self._context_view.GetRenderWindow().GetSize()
        if ancho <= 0 or alto <= 0:
            return
        margen = 14
        self._charts[0].SetAutoSize(False)
        self._charts[0].SetSize(vtk.vtkRectf(
            float(margen), float(alto - margen - self.ALTO_COMODULOGRAMA),
            float(ancho - 2 * margen), float(self.ALTO_COMODULOGRAMA)))

    # =====================================================
    # === Guardar y restaurar el análisis en el proyecto
    # =====================================================
    def get_analysis_params(self) -> dict:
        return {
            "sample_fq": self.ui.sampleFqSpinBox.value(),
            "fq_p1": self.ui.fqP1SpinBox.value(),
            "fq_p2": self.ui.fqP2SpinBox.value(),
            "p_step": self.ui.pStepSpinBox.value(),
            "fq_a1": self.ui.fqA1SpinBox.value(),
            "fq_a2": self.ui.fqA2SpinBox.value(),
            "a_step": self.ui.aStepSpinBox.value(),
            "trial": self.ui.trialSpinBox.value(),
        }

    def apply_analysis_params(self, params: dict):
        d = self.DEFAULTS
        self.ui.sampleFqSpinBox.setValue(params.get("sample_fq", d["sample_fq"]))
        self.ui.fqP1SpinBox.setValue(params.get("fq_p1", d["fq_p1"]))
        self.ui.fqP2SpinBox.setValue(params.get("fq_p2", d["fq_p2"]))
        self.ui.pStepSpinBox.setValue(params.get("p_step", d["p_step"]))
        self.ui.fqA1SpinBox.setValue(params.get("fq_a1", d["fq_a1"]))
        self.ui.fqA2SpinBox.setValue(params.get("fq_a2", d["fq_a2"]))
        self.ui.aStepSpinBox.setValue(params.get("a_step", d["a_step"]))
        self._actualizar_selector_trial()
        self.ui.trialSpinBox.setValue(params.get("trial", 1))
        self.on_create_mi()
