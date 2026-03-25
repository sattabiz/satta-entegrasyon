import json
import sys
from Common.path_helper import project_path, ensure_directory, get_user_data_dir, user_data_path
from versiyon import APP_DISPLAY_NAME, APP_VERSION
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap, QIcon
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

CONNECTOR_DISPLAY_NAMES = {
    "logo": "Logo",
    "sap": "SAP",
    "canias": "Canias",
}


def get_connector_display_name(connector_name: str) -> str:
    normalized_name = str(connector_name).strip().lower()
    if not normalized_name:
        return "Bağlayıcı Seçilmedi"
    return CONNECTOR_DISPLAY_NAMES.get(normalized_name, normalized_name.capitalize())


class MainWindow(QMainWindow):
    def __init__(self, runtime_config: dict | None = None):
        super().__init__()
        self.runtime_config = runtime_config or {}
        active_connector = str(self.runtime_config.get("active_connector", "")).strip()
        connector_label = get_connector_display_name(active_connector)
        self.setWindowTitle(f"{APP_DISPLAY_NAME} v{APP_VERSION} - {connector_label}")
        window_icon_path = project_path("App_Icons", "exeIcon.ico")
        if window_icon_path.exists():
            self.setWindowIcon(QIcon(str(window_icon_path)))
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

        home_text_label = QLabel(f"{APP_DISPLAY_NAME} - {connector_label}")
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

        self.tabs.addTab(home_widget, "Ana Sayfa")
        self.tabs.addTab(self.invoice_transfer_tab, "Fatura Aktarımı")
        self.tabs.addTab(self.stock_tab, "Ürünler")
        self.tabs.addTab(self.supplier_send_tab, "Tedarikçi Gönderim")
        self.tabs.addTab(self.settings_tab, "Ayarlar")

        self.setCentralWidget(self.tabs)


def deep_merge_defaults(default_value, existing_value):
    if isinstance(default_value, dict):
        existing_dict = existing_value if isinstance(existing_value, dict) else {}
        merged = {}
        for key, default_item in default_value.items():
            merged[key] = deep_merge_defaults(default_item, existing_dict.get(key))
        for key, value in existing_dict.items():
            if key not in merged:
                merged[key] = value
        return merged

    if existing_value is None:
        return default_value

    return existing_value


DEFAULT_RUNTIME_FILES = {
    "app_settings.json": {
        "satta": {
            "base_url": "",
            "username": "",
            "password": "",
            "token": "",
        },
        "logo": {
            "server": "",
            "database": "",
            "username": "",
            "password": "",
            "firm_no": 1,
            "period_no": 1,
        },
        "sap": {
            "host": "",
            "system_number": "",
            "client": "",
            "username": "",
            "password": "",
            "language": "TR",
        },
        "canias": {
            "host": "",
            "tenant": "",
            "username": "",
            "password": "",
        },
    },
    "satta_session.json": {
        "token": "",
        "refresh_token": "",
        "expires_at": "",
    },
    "runtime_config.json": {
        "active_connector": "",
        "installed_connectors": [],
    },
}


def load_runtime_config() -> dict:
    runtime_config_file = user_data_path("runtime_config.json")
    if not runtime_config_file.exists():
        return dict(DEFAULT_RUNTIME_FILES["runtime_config.json"])

    try:
        runtime_config = json.loads(runtime_config_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULT_RUNTIME_FILES["runtime_config.json"])

    return deep_merge_defaults(DEFAULT_RUNTIME_FILES["runtime_config.json"], runtime_config)


def ensure_runtime_files() -> None:
    user_data_dir = get_user_data_dir()
    ensure_directory(user_data_dir)

    for filename, default_content in DEFAULT_RUNTIME_FILES.items():
        file_path = user_data_path(filename)

        if file_path.exists():
            try:
                existing_content = json.loads(file_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing_content = None
        else:
            existing_content = None

        final_content = deep_merge_defaults(default_content, existing_content)
        file_path.write_text(
            json.dumps(final_content, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def main() -> None:
    ensure_runtime_files()
    runtime_config = load_runtime_config()
    app = QApplication(sys.argv)
    window = MainWindow(runtime_config=runtime_config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()