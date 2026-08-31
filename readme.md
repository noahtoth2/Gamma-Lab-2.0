# Gamma Lab – Installation Guide (Windows)

This document explains how to install and run **Gamma Lab** on Windows using Python 3.11, 3.12, or 3.13 and the included `run.bat` launcher.
---

## 📦 Download the latest project release
The easiest way to obtain Gamma Lab is by downloading the compressed package containing the latest stable version from the official repository's Releases section:

🔗 Download latest release (.zip): [releases](https://github.com/GAMMA-BOARD-FTD-PACC/gamma-lab-desktop-app/releases)

# 1. Check your Python version

Before installing anything, verify which Python version you currently have:

```bash
python --version
```
- If Python is 3.11, 3.12, or 3.13. OK
- If Python is older than 3.11. You must install a newer version


## 2. Install Python (Recommended: **Python 3.11, 3.12, or 3.13**)

Gamma Lab is compatible with:

- **Python 3.11** (recommended)
- **Python 3.12**
- **Python 3.13**

These versions ensure compatibility with PyQt5, QtWebEngine, VTK, SciPy, and other scientific libraries.

### Download Python for Windows  
Use:

https://www.python.org/downloads/windows/

Download one of the supported versions:
- Python 3.11.x  
- Python 3.12.x  
- Python 3.13.x  

Choose the *Windows installer (64‑bit)*.

### During installation:
- Check **“Add Python to PATH”**
- Click **Customize Installation**
- Keep all defaults enabled
- Finish installation

Verify installation:

```bash
python --version
```

---

## 3. Running Gamma Lab

Gamma Lab includes a launcher script:

```
gamma_lab.bat
```

You can start the application by either double-clicking it or running:

```bash
.
gamma_lab.bat
```

This script performs all environment preparation automatically:

1. Detects your installed Python version
2. Verifies that `Python 3.11` or newer is installed
3. Automatically installs or updates all dependencies from `requirements.txt`
4. Launches `main.py` with the correct working directory

---

## 4. Create shortcut

If you want to create a desktop shortcut to run Gamma Lab, you can run the following script by double-clicking it.

```bash
create_shortcut.bat
```

A shortcut is automatically created on the desktop with the program's logo and name.

---

## 4. Running Manually
If you prefer to launch Gamma Lab yourself open a new terminal in the project root directory and enter the command:

```bash
pip install -r requirements.txt
python main.py
```
---


## ❗ Troubleshooting


## Install Dependencies

Inside the project folder, run:

```bash
python -m pip install -r requirements.txt
```

If anything fails, update pip:

```bash
python -m pip install --upgrade pip
```

--

### ModuleNotFoundError
```bash
python -m pip install -r requirements.txt
```

### Python not recognized
Reinstall Python ensuring **Add to PATH** is enabled.

### Dependency version mismatch
Some libraries may not support earlier Python versions.
Solution:

- Use **Python 3.11–3.13**
- Ensure pip resolves compatible versions:

```bash
    pip install --upgrade pip
    pip install --force-reinstall -r requirements.txt
```


## Done!

Gamma Lab is now installed and running with Python 3.11 or newer on Windows.
