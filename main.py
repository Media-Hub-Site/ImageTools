import sys
import os
import io
import traceback

# Evitar errores de escritura en librerías como tqdm/pooch/onnxruntime cuando console=False en PyInstaller
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from PyQt6.QtWidgets import QApplication, QMessageBox

from apps.media_converter.ui.image_tools_window import ImageToolsWindow


def global_exception_handler(exc_type, exc_value, exc_traceback):
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    print(err_msg)
    if QApplication.instance():
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Error Fatal")
        msg.setText("Ocurrió un error inesperado.")
        msg.setDetailedText(err_msg)
        msg.exec()


sys.excepthook = global_exception_handler


def main():
    app = QApplication(sys.argv)
    window = ImageToolsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
