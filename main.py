import sys
from PyQt6.QtWidgets import QApplication
from core.database import init_db
from ui.main_window import MainWindow



def main():
    # Inicializar tablas si no existen
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("Sistema Contable")
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
