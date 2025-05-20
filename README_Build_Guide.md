# 🔧 Google Drive Image Sync - EXE Build Instructions

This guide explains how to create a lightweight standalone `.exe` from `main.py` using PyInstaller without bundling unnecessary packages.

## ✅ Prerequisites

- Windows OS
- Python 3.10 or later (recommended: 3.10–3.11 for PyInstaller compatibility)
- Git installed (optional)
- Basic command line knowledge

---

## 📦 Step-by-Step Build Instructions

### 1. Prepare a Clean Folder

Create a clean directory for building:
```
C:\Users\<YourName>\Desktop\CleanBuild
```

Copy the following files into it:
- `main.py`
- `image_sync-icon.ico`

---

### 2. Set Up a Virtual Environment

Open Command Prompt and run:

```bash
cd C:\Users\<YourName>\Desktop\CleanBuild
python -m venv venv
venv\Scripts\activate
```

This creates an isolated Python environment to avoid bundling global packages.

---

### 3. Install Only Required Packages

Install minimal dependencies:

```bash
pip install pillow tqdm google-auth google-auth-oauthlib google-api-python-client pyinstaller
```

---

### 4. Create the Executable

Run the PyInstaller command:

```bash
pyinstaller --noconfirm --clean --onefile --icon=image_sync-icon.ico main.py
```

This will generate:
```
dist\main.exe
```

✅ Final `.exe` size should be ~25–40 MB.

---

## ⚠️ Common Pitfalls

- **Don't use global Python**: Avoid running PyInstaller from a globally installed Python with many packages (like `torch`, `tensorflow`, `matplotlib`, etc.).
- **Don't keep logs, token.json, or large folders like `Computers_Drive` in the build directory.**
- **Avoid Python 3.13**: PyInstaller support may be unstable or cause bloat.

---

## 🧹 Optional Cleanup

To clean previous build artifacts:

```bash
rmdir /s /q build
rmdir /s /q __pycache__
del /f /q main.spec
```

---

## 📁 Output Structure

```
CleanBuild/
├── dist/
│   └── main.exe        ← Your final lightweight EXE
├── build/              ← Can be deleted after build
├── main.spec           ← Can be customized (optional)
├── main.py
├── image_sync-icon.ico
└── venv/               ← Your virtual environment
```

---

## 💡 Tip

Want to automate the build process? Create a `build.bat` file:
```bat
@echo off
python -m venv venv
call venv\Scripts\activate
pip install pillow tqdm google-auth google-auth-oauthlib google-api-python-client pyinstaller
pyinstaller --noconfirm --clean --onefile --icon=image_sync-icon.ico main.py
pause
```

---

### 🔁 Rebuilding?

Simply delete the `build/`, `dist/`, and `main.spec`, then repeat the above steps.

---

Happy coding! 🚀