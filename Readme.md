
Comando para compilar el ejecutable standalone

python -m pip install pyinstaller

python -m PyInstaller --onefile --name "ProvisionOnus" --icon=icons/cap.ico --exclude-module tkinter.test --exclude-module tests app.py
