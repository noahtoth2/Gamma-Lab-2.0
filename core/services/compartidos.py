"""Registro de los servicios compartidos del núcleo (R69).

Los servicios de ajustes, exportación y medición se crean aquí, una sola vez, y los módulos los piden al
Kernel con sus claves. Ningún otro módulo los construye: lo comprueba `test_servicios_compartidos`.
"""
from core.services.export_service import ExportService
from core.services.measurement_service import MeasurementService
from core.services.settings_service import SettingsService


def registrar_servicios_compartidos(kernel):
    """Registra "Settings", "Export" y "Measurement". El "DataStore" tiene que estar registrado antes."""
    ajustes = SettingsService()
    almacen = kernel.get_service("DataStore")
    kernel.register_service("Settings", ajustes)
    kernel.register_service("Export", ExportService(ajustes, almacen))
    kernel.register_service("Measurement", MeasurementService(almacen))
