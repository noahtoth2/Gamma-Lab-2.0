"""Observadores de VTK que se retiran al salir de un modulo (R58).

Los plugins guardan su widget VTK vivo al cambiar de seccion, asi que sus
observadores seguirian atados al interactor aunque nadie mire el grafico.
`observar` los registra en el propio widget; la ventana principal llama a
`retirar_observadores` al salir del modulo y a `reponer_observadores` al volver.
"""

_ATTR = "_gamma_observadores"


def _estado(vtk_widget):
    estado = getattr(vtk_widget, _ATTR, None)
    if estado is None:
        estado = {"items": [], "activos": True}
        setattr(vtk_widget, _ATTR, estado)
    return estado


def _interactor(vtk_widget):
    return vtk_widget.GetRenderWindow().GetInteractor()


def observar(vtk_widget, evento, callback, prioridad=0.0):
    """Como `interactor.AddObserver`, pero recordado para poder retirarlo."""
    estado = _estado(vtk_widget)
    item = {"evento": evento, "callback": callback, "prioridad": prioridad, "id": None}
    if estado["activos"]:
        item["id"] = _interactor(vtk_widget).AddObserver(evento, callback, prioridad)
    estado["items"].append(item)
    return item


def retirar_observadores(vtk_widget):
    """Quita del interactor todos los observadores registrados. Devuelve cuántos."""
    estado = _estado(vtk_widget)
    if not estado["activos"]:
        return 0
    iren = _interactor(vtk_widget)
    n = 0
    for item in estado["items"]:
        if item["id"] is not None:
            iren.RemoveObserver(item["id"])
            item["id"] = None
            n += 1
    estado["activos"] = False
    return n


def reponer_observadores(vtk_widget):
    """Vuelve a poner los observadores retirados. Devuelve cuántos."""
    estado = _estado(vtk_widget)
    if estado["activos"]:
        return 0
    iren = _interactor(vtk_widget)
    for item in estado["items"]:
        item["id"] = iren.AddObserver(item["evento"], item["callback"], item["prioridad"])
    estado["activos"] = True
    return len(estado["items"])


def contar_observadores(vtk_widget):
    """Observadores actualmente atados al interactor."""
    estado = getattr(vtk_widget, _ATTR, None)
    if not estado or not estado["activos"]:
        return 0
    return sum(1 for i in estado["items"] if i["id"] is not None)


def widgets_vtk(contenedor):
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    return contenedor.findChildren(QVTKRenderWindowInteractor)


def retirar_de(contenedor):
    """Retira los observadores de todos los widgets VTK dentro de `contenedor`."""
    return sum(retirar_observadores(w) for w in widgets_vtk(contenedor) if hasattr(w, _ATTR))


def reponer_en(contenedor):
    """Repone los observadores de todos los widgets VTK dentro de `contenedor`."""
    return sum(reponer_observadores(w) for w in widgets_vtk(contenedor) if hasattr(w, _ATTR))
