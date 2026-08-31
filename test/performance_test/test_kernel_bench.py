# test/performance_test/test_kernel_bench.py
"""
Benchmarks del "kernel" de Gamma Lab (core/kernel.py) y del sistema de plugins
(core/plugins/loader.py, core/plugins/manager.py) -- es decir, el costo real de
arranque de la aplicación antes de mostrar cualquier ventana.

No se mockea nada: se usan los 16 plugins reales que hoy vive bajo plugins/
(cada uno con su properties.yml) y la secuencia exacta que ejecuta main.py al
iniciar la app:

    1. Kernel()
    2. PluginManager(plugins_dir).load_all()   -> descubre + instancia cada plugin
    3. por cada plugin: kernel.register_plugin(meta.name, plugin)

Lo único que queda fuera (por requerir una QApplication real con un event loop
completo, no solo un stack VTK offscreen) es la construcción de MainWindow --
ver docs para más detalle sobre esa limitación conocida.

Nota sobre repetibilidad: core/plugins/loader.py reimporta el módulo de cada
plugin en cada llamada a discover() (usa spec.loader.exec_module de forma
incondicional, no reutiliza el import cacheado en sys.modules), así que repetir
esta prueba varias veces sigue pagando el costo real de (re)importar cada
plugin, no solo el de instanciar la clase.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from core.kernel import Kernel
from core.plugins.loader import discover
from core.plugins.manager import PluginManager

from bench_common import time_block, record, record_environment

pytestmark = pytest.mark.perf

PLUGINS_DIR = Path(__file__).resolve().parents[2] / "plugins"


def test_bench_00_registrar_entorno():
    """No es un benchmark de tiempo: guarda un snapshot del entorno (SO, CPU,
    versiones de librerías) junto a esta corrida, para poder comparar
    Gamma Lab 1.0 vs 2.0 sabiendo si corrieron en las mismas condiciones."""
    info = record_environment()
    assert "python" in info


def test_bench_plugin_discover():
    """
    Tiempo de core.plugins.loader.discover(plugins_dir): recorre plugins/ en
    busca de carpetas con properties.yml, valida las claves requeridas e importa
    la clase lógica de cada plugin. Es el primer paso del arranque, antes de
    instanciar nada.
    """
    stats = time_block(discover, PLUGINS_DIR, reps=5, warmup=1)
    n_plugins = len(stats["result"])
    record(f"kernel.plugins.discover ({n_plugins} plugins)", stats)
    assert n_plugins > 0


def test_bench_plugin_manager_load_all():
    """
    Tiempo de PluginManager.load_all(): discover() + instanciar PluginCls(meta)
    para cada plugin encontrado. Es exactamente lo que hace main.py en el paso
    "2) Discover and instantiate plugins".
    """
    def run_once():
        pm = PluginManager(PLUGINS_DIR)
        pm.load_all()
        return pm

    stats = time_block(run_once, reps=5, warmup=1)
    n_plugins = len(stats["result"].all())
    record(f"kernel.plugin_manager.load_all ({n_plugins} plugins)", stats)
    assert n_plugins > 0


def test_bench_kernel_bootstrap_completo():
    """
    Arranque completo del kernel tal como lo hace main.py (sin la ventana
    principal): PluginManager.load_all() + registrar cada plugin en un Kernel
    nuevo. register_plugin() además llama a plugin.initialize(kernel), igual
    que en producción -- este número es el proxy más fiel de "cuánto tarda
    Gamma Lab en tener todos los plugins listos" antes de dibujar la UI.
    """
    def run_once():
        pm = PluginManager(PLUGINS_DIR)
        pm.load_all()
        kernel = Kernel()
        for meta, plugin in pm.all():
            kernel.register_plugin(meta.name, plugin)
        return kernel

    stats = time_block(run_once, reps=5, warmup=1)
    n_plugins = len(stats["result"].get_plugins())
    record(f"kernel.bootstrap_completo (discover+load_all+register, {n_plugins} plugins)", stats)
    assert n_plugins > 0


# ---------------------------------------------------------------------
# Overhead propio del Kernel, aislado de la instanciación de cada plugin
# ---------------------------------------------------------------------

class _PluginFalso:
    """
    Doble mínimo de un plugin: solo implementa lo que Kernel.register_plugin()
    necesita (un initialize(kernel) opcional). Sirve para medir el costo propio
    del Kernel (dict + hasattr + señal Qt) sin mezclarlo con el costo de
    construir un plugin real (imports, VTK, etc.), que ya se mide arriba.
    """
    def __init__(self, idx: int):
        self.idx = idx

    def initialize(self, kernel):
        self.kernel = kernel


def test_bench_kernel_register_plugin_overhead():
    """Costo puro de Kernel.register_plugin() para 200 plugins ficticios."""
    n = 200

    def run_once():
        kernel = Kernel()
        for i in range(n):
            kernel.register_plugin(f"plugin_{i}", _PluginFalso(i))
        return kernel

    stats = time_block(run_once, reps=10, warmup=2)
    record(f"kernel.register_plugin (overhead propio, x{n} plugins ficticios)", stats)
