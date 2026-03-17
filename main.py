import sys
from Common.path_helper import project_path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from Settings.settings import SettingsTab
from Supplier.supplier import SupplierSendTab
from Invoice.invoice import InvoiceTransferTab
from Stock.stock import StockTab
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Satta Entegrasyon")
        self.resize(1000, 700)

        self.tabs = QTabWidget()

        home_widget = QWidget()
        home_layout = QVBoxLayout(home_widget)
        home_layout.setAlignment(Qt.AlignCenter)
        home_layout.setSpacing(24)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_path = project_path("App_Icons", "2.png")
        logo_pixmap = QPixmap(str(logo_path))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(
                logo_pixmap.scaledToWidth(220, Qt.SmoothTransformation)
            )

        home_text_label = QLabel("Satta Entegrasyon")
        home_text_font = QFont()
        home_text_font.setPointSize(22)
        home_text_font.setBold(True)
        home_text_label.setFont(home_text_font)
        home_text_label.setAlignment(Qt.AlignCenter)

        home_layout.addWidget(logo_label)
        home_layout.addWidget(home_text_label)

        self.settings_tab = SettingsTab()
        self.supplier_send_tab = SupplierSendTab()
        self.invoice_transfer_tab = InvoiceTransferTab()
        self.stock_tab = StockTab()

        self.tabs.addTab(home_widget, "Ana Sayfa"),
        self.tabs.addTab(self.invoice_transfer_tab, "Fatura Aktarımı")
        self.tabs.addTab(self.stock_tab, "Ürünler")
        self.tabs.addTab(self.supplier_send_tab, "Tedarikçi Gönderim")
        self.tabs.addTab(self.settings_tab, "Ayarlar")

        self.setCentralWidget(self.tabs)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()