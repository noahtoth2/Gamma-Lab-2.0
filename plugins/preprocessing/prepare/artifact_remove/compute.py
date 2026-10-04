# plugins/preprocessing/prepare/artifact_remove/compute.py
"""Cálculo puro de la modificación de artefactos.

Es lo que corre dentro del orquestador (TaskService): recibe arreglos de NumPy
y devuelve arreglos de NumPy. No toca el Kernel, el DataStore ni ningún widget;
la lectura y la escritura de los trials viven en artifact_logic.py y corren en
el hilo de la interfaz.

La implementación está en core/filters/artifacts.py porque ProjectService
también la necesita, para reaplicar las modificaciones al abrir un proyecto.
"""
from core.filters.artifacts import (  # noqa: F401
    calcular_modificacion,
    columnas_activas,
    reaplicar_modificaciones,
    receta,
)
