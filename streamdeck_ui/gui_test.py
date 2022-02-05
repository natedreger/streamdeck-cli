import sys

# from PySide2.QtGui import QDrag, QIcon

from PyQt5.QtWidgets import (
    QApplication, QDialog, QMainWindow, QMessageBox, QMenu, QAction, QSystemTrayIcon
)
from PyQt5.QtGui import(QIcon, QDrag)
from PyQt5.uic import loadUi



from config import LOGO
import api
from ui_mainND import Ui_MainWindow


class Window(QMainWindow, Ui_MainWindow):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.setupUi(self)
        self.window_shown: bool = True
        self.connectSignalsSlots()

    def connectSignalsSlots(self):
        self.actionExit.triggered.connect(self.close)

    def systray_clicked(self, _status=None) -> None:
        if self.window_shown:
            self.hide()
            self.window_shown = False
            return
        print('clicked')
        self.bring_to_top()

    def bring_to_top(self):
        self.show()
        self.activateWindow()
        self.raise_()
        self.window_shown = True


def start(_exit: bool = False) -> None:
    show_ui = True
    if "-h" in sys.argv or "--help" in sys.argv:
        print(f"Usage: {os.path.basename(sys.argv[0])}")
        print("Flags:")
        print("  -h, --help\tShow this message")
        print("  -n, --no-ui\tRun the program without showing a UI")
        return
    elif "-n" in sys.argv or "--no-ui" in sys.argv:
        show_ui = False

    ui = main_window.ui
    logo = QIcon(LOGO)
    main_window.setWindowIcon(logo)

    # api.render()

    if show_ui:
        main_window.show()
    # #
    if _exit:
        return
    else:
        app.exec_()
        api.close_decks()
        sys.exit()
    sys.exit(app.exec())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = Window()
    main_window.show()
    start()
    sys.exit(app.exec())
