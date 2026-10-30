# Instructivo del instalador de Gamma Lab

Cómo volver a generar el instalador después de hacer cambios, y cómo entregárselo al cliente.

El resultado es un único archivo, `GammaLab-Setup-X.Y.Z.exe` (unos 230 MB). Instala el programa para todo el equipo en `C:\Program Files\GammaLab` y hace que el doble clic sobre un archivo `.glab` abra la aplicación con ese proyecto. El cliente no necesita tener Python instalado.

---

## 1. Qué necesitas en tu computador (una sola vez)

| Qué | Cómo |
|---|---|
| Windows 10 u 11, 64 bits | (probado en Windows 11) |
| Python 3.12 con las librerías del proyecto | `pip install -r requirements.txt` |
| PyInstaller | `pip install pyinstaller` |
| Inno Setup 6 | `winget install -e --id JRSoftware.InnoSetup` |

Para comprobar que están:

```
python -m PyInstaller --version
"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
```

(si Inno Setup quedó en `C:\Program Files (x86)\Inno Setup 6`, `construir.bat` también lo busca ahí).

No borres el archivo `17309009_full.mat` de la raíz del proyecto: el script lo usa para probar el programa antes de empaquetarlo.

---

## 2. Cómo volver a crear el instalador

1. **Haz tus cambios y pruébalos:** `python -m pytest test -q` (las 3 pruebas de comparación con MATLAB de PSD Average y Wavelet Average ya fallaban antes y no tienen que ver con el instalador).
2. **Sube el número de versión.** Abre `installer\gamma_lab.iss` y cambia la línea:
   ```
   #define VersionApp "2.0.0"
   ```
   por la nueva (por ejemplo `2.0.1`). Es lo que hace que Windows trate el instalador como una actualización. **No cambies el `AppId`**: si lo cambias, el cliente tendría dos copias instaladas.
3. **Cierra Gamma Lab** si lo tienes abierto.
4. **Ejecuta, desde cualquier carpeta:**
   ```
   installer\construir.bat
   ```
   Tarda unos 6 a 8 minutos y hace tres cosas seguidas, deteniéndose si alguna falla:
   - **[1/3] Congela** la aplicación con PyInstaller (es lo más lento).
   - **[2/3] Prueba el ejecutable:** lo arranca, abre un `.glab`, calcula un FFT, abre la ayuda y comprueba los ajustes. Tienen que salir seis líneas `OK`.
   - **[3/3] Empaqueta** con Inno Setup.
5. **El instalador queda en** `installer\salida\GammaLab-Setup-X.Y.Z.exe`.
6. **Pruébalo tú antes de enviarlo** (sección 5).

Las carpetas `installer\build`, `installer\dist` y `installer\salida` se regeneran solas y no se suben a git.

### Qué no tienes que tocar cuando cambias el programa
- Si agregas un plugin nuevo, o un plugin importa una librería nueva, **no hay que editar nada**: `gamma_lab.spec` lee los imports de todos los plugins.
- Lo mismo vale para los módulos nuevos dentro de `core\` y `app\`.
- Una excepción: una librería nueva tiene que estar instalada en tu Python y, si es muy grande o no se usa, conviene revisar el tamaño final.

---

## 3. Si algo falla

| Síntoma | Qué hacer |
|---|---|
| El paso 1 se queda sin avanzar más de 10 minutos | Se colgó PyInstaller. Ciérralo (`Ctrl+C`), mata los procesos `python.exe` que queden y vuelve a ejecutar `construir.bat`. Si se repite, avísame: la causa conocida es un conflicto de `MSVCP140.dll`, que ya resolvimos con `installer\precarga\sitecustomize.py`. |
| La prueba del paso 2 dice `FALLO plugins cargados (N de 19)` | Falta algún módulo dentro del paquete. Ejecuta `installer\dist\GammaLab\GammaLab.exe` desde una terminal: imprime qué plugin falló y por qué (`No module named ...`). |
| `FALLO: el programa no terminó en 240 s` | El ejecutable no arranca. Ejecútalo desde una terminal para ver el error. |
| El programa instalado no arranca | Mira `%APPDATA%\GammaLab\gamma_lab.log`: guarda lo que el programa escribió en su última ejecución. |
| El instalador no encuentra `ISCC.exe` | Instala Inno Setup (sección 1). |
| Instalas y todo queda igual | Windows cancela en silencio si no aceptas el aviso de administrador. Vuelve a ejecutar el instalador y acepta. |

---

## 4. Cómo enviárselo al cliente

### Qué enviar
**Solo** `installer\salida\GammaLab-Setup-X.Y.Z.exe`. No envíes el proyecto, ni las carpetas `dist` o `build`.

### Cómo enviarlo
El archivo pesa unos 230 MB. Lo normal es que el correo lo rechace, y los correos suelen bloquear los `.exe`. Las opciones, de más a menos cómoda:

1. **Un enlace de descarga** en Google Drive, OneDrive o WeTransfer, y le mandas el enlace por correo o mensaje.
2. **Una memoria USB** o un disco compartido de la institución.
3. **Una página de "Releases" de GitHub** del repositorio. GitHub no deja subir archivos de más de 100 MB al repositorio normal, pero sí como adjunto de una release (hasta 2 GB). **No lo subas con `git add`.**

### Verifica que llegó completo
Antes de enviarlo, calcula su huella y pásasela al cliente junto con el enlace:

```
certutil -hashfile installer\salida\GammaLab-Setup-2.0.0.exe SHA256
```

El cliente puede ejecutar el mismo comando sobre lo que descargó. Si el resultado es idéntico, el archivo llegó íntegro.

### Qué decirle al cliente
Puedes copiar este texto:

> **Instalación de Gamma Lab**
> 1. Descarga `GammaLab-Setup-X.Y.Z.exe`.
> 2. Haz doble clic. Windows pedirá permiso de administrador: acéptalo. El instalador es para todo el equipo, así que alguien con permisos de administrador tiene que instalarlo.
> 3. Sigue los pasos (Siguiente → Instalar → Finalizar). Hay una casilla para crear un acceso en el escritorio.
> 4. Para abrir un proyecto, haz doble clic en cualquier archivo `.glab`, o abre Gamma Lab y usa el menú *File → Open project*.
>
> **Requisitos:** Windows 10 u 11 de 64 bits; unos 700 MB libres en disco; permiso de administrador solo para instalar. No hace falta instalar Python.
>
> **Actualizar:** ejecuta el instalador nuevo sin desinstalar el anterior. Reemplaza la versión instalada y conserva sus ajustes.
>
> **Desinstalar:** *Configuración → Aplicaciones → Gamma Lab → Desinstalar*.
>
> Los ajustes y el registro de errores quedan en `%APPDATA%\GammaLab`. Sus proyectos y señales no se tocan.

Si el cliente tiene un área de TI que instala sin ventanas, el mismo instalador acepta `GammaLab-Setup-X.Y.Z.exe /SILENT` (con permisos de administrador).

### Avisos que pueden aparecer
- **"Windows protegió su PC" (SmartScreen) o "Editor desconocido".** El instalador no está firmado digitalmente, así que Windows desconfía de él. El cliente puede elegir *Más información → Ejecutar de todas formas*. Evitarlo exige un certificado de firma de código, que se compra aparte; si es para entrega formal, vale la pena considerarlo.
- **El antivirus lo marca o lo retrasa.** Es habitual con programas congelados y sin firma. Si pasa, el cliente tiene que permitirlo en su antivirus o pedirle a TI que lo autorice. Tener la huella SHA-256 ayuda a demostrar que es el archivo original.

---

## 5. Lista de comprobación antes de enviar

- [ ] `python -m pytest test -q` sin fallas nuevas.
- [ ] Versión actualizada en `installer\gamma_lab.iss`.
- [ ] `installer\construir.bat` terminó y las seis líneas de la prueba dicen `OK`.
- [ ] Instalaste el `.exe` nuevo en tu equipo, aceptando el aviso de administrador.
- [ ] Hiciste doble clic en un `.glab` y se abrió el proyecto.
- [ ] Probaste al menos un análisis (por ejemplo FFT) y la ayuda.
- [ ] **Idealmente, lo probaste en un computador distinto, sin Python instalado.** Es la única forma de estar seguro de que no depende de nada de tu equipo. (Windows 11 Home no trae "Windows Sandbox"; usa otro computador.)
- [ ] Calculaste el SHA-256 y lo anotaste.
- [ ] Enviaste solo el `Setup`, con el enlace y la huella.

---

## 6. Dónde está cada cosa

| Archivo | Para qué sirve |
|---|---|
| `installer\construir.bat` | El comando que lo hace todo |
| `installer\gamma_lab.spec` | Configuración de PyInstaller (qué se incluye en el programa) |
| `installer\gamma_lab.iss` | Configuración del instalador: versión, ruta de instalación, registro de `.glab`, accesos directos |
| `installer\prueba_congelado.py` | La prueba del paso 2 (se puede ejecutar sola: `python installer\prueba_congelado.py`) |
| `installer\precarga\sitecustomize.py` | Evita el conflicto de `MSVCP140.dll` durante la construcción |
| `core\utils\autoprueba.py` | La autoprueba que usa la prueba anterior (solo actúa si existe la variable de entorno `GAMMALAB_AUTOPRUEBA`) |
| `core\utils\rutas.py` | Rutas del programa instalado: carpeta de datos del usuario, apertura del `.glab` recibido, registro de errores |
