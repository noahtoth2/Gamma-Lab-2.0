"""Prueba corta del programa congelado (R39): arranca, abre un .glab, calcula un FFT y abre la ayuda.

Uso:  python installer/prueba_congelado.py [--dev | ruta/a/GammaLab.exe]
Sin argumentos prueba installer/dist/GammaLab/GammaLab.exe; con --dev, `python main.py`.
Lanza el programa desde otra carpeta y con APPDATA temporal, como haría el doble clic.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MUESTRA = RAIZ / "17309009_full.mat"
TIEMPO_MAXIMO_S = 240


def preparar_proyecto(carpeta: Path) -> Path:
    shutil.copy(MUESTRA, carpeta / MUESTRA.name)
    glab = carpeta / "p.glab"
    glab.write_text(json.dumps({
        "schema_version": 1, "project_name": "p_prueba",
        "signal": {"filename": MUESTRA.name, "format": "mat", "name": MUESTRA.name,
                   "sampling_rate": 10000.0, "sampling_rate_source": "manual"},
        "measurements": [], "analysis": {},
        "trials": [{"generation_params": {"channel": 0, "stim_channel": 1, "threshold": 1.0, "t0": 0.0,
                                          "t1": 0.1, "end_mode": "fixed", "stim_expected": None,
                                          "inter_stim_time": None}, "discarded_indices": []}],
    }), encoding="utf-8")
    return glab


def main(argumentos):
    if argumentos[:1] == ["--dev"]:
        orden = [sys.executable, str(RAIZ / "main.py")]
    else:
        exe = Path(argumentos[0]) if argumentos else RAIZ / "installer" / "dist" / "GammaLab" / "GammaLab.exe"
        if not exe.exists():
            print(f"No existe {exe}")
            return 1
        orden = [str(exe)]

    esperados = len(list((RAIZ / "plugins").rglob("properties.yml")))
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        glab = preparar_proyecto(tmp)
        salida = tmp / "resultado.json"
        entorno = dict(os.environ, APPDATA=str(tmp / "appdata"), GAMMALAB_AUTOPRUEBA=str(salida),
                       PYTHONIOENCODING="utf-8")
        try:
            subprocess.run(orden + [str(glab)], cwd=tmp, env=entorno, timeout=TIEMPO_MAXIMO_S,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            print(f"FALLO: el programa no terminó en {TIEMPO_MAXIMO_S} s")
            return 1
        if not salida.exists():
            print("FALLO: el programa terminó sin escribir el resultado")
            return 1
        r = json.loads(salida.read_text(encoding="utf-8"))
        ajustes = tmp / "appdata" / "GammaLab" / "gamma_lab_settings.json"
        comprobaciones = {
            f"plugins cargados ({len(r['plugins'])} de {esperados})": len(r["plugins"]) >= esperados - 1,
            "proyecto abierto desde el argumento": r.get("proyecto") == "p_prueba",
            "señal activa": r.get("senal") == MUESTRA.name,
            "FFT calculado": r.get("fft") is True,
            "ventana de ayuda": r.get("ayuda") is True,
            "ajustes en la carpeta del usuario": ajustes.exists(),
        }
        for texto, ok in comprobaciones.items():
            print(("OK    " if ok else "FALLO ") + texto)
        for clave in ("fft_error", "ayuda_error"):
            if clave in r:
                print(f"   {clave}: {r[clave]}")
        if len(r["plugins"]) < esperados:
            print("   (plugins:", r["plugins"], ")")
        return 0 if all(comprobaciones.values()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
