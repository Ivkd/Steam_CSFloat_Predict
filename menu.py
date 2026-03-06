import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtGui import QAction


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple menu (PyQt6)")
        self.resize(700, 450)

        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setStatusTip("Open something")
        open_action.triggered.connect(self.on_open)

        exit_action = QAction("E&xit", self)
        exit_action.setStatusTip("Quit application")
        exit_action.triggered.connect(self.close)

        file_menu.addAction(open_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.on_about)
        help_menu.addAction(about_action)

        self.statusBar().showMessage("Ready")

    def on_open(self):
        self.statusBar().showMessage("Open clicked")

    def on_about(self):
        QMessageBox.information(self, "About", "Demo меню на PyQt6")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
