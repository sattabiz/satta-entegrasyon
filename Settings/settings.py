import json

from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from Invoice.get_invoice import SattaInvoiceConfig, SattaInvoiceConnector
from Common.path_helper import ensure_parent_directory, user_data_path


class SettingsTab(QWidget):
    SETTINGS_FILE = user_data_path("app_settings.json")

    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout(self)

        title_label = QLabel("Ayarlar")
        root_layout.addWidget(title_label)

        content_row = QHBoxLayout()

        satta_group = QGroupBox("Satta Kullanıcı Girişi ve API Ayarları")
        satta_layout = QVBoxLayout(satta_group)

        satta_login_frame = QFrame()
        satta_login_form = QFormLayout(satta_login_frame)

        self.satta_base_url_input = QLineEdit()
        self.satta_base_url_input.setPlaceholderText("https://test.satta.biz")

        self.satta_username_input = QLineEdit()
        self.satta_username_input.setPlaceholderText("Satta e-posta")

        self.satta_password_input = QLineEdit()
        self.satta_password_input.setPlaceholderText("Satta şifre")
        self.satta_password_input.setEchoMode(QLineEdit.Password)

        self.satta_token_input = QLineEdit()
        self.satta_token_input.setPlaceholderText("Login sonrası alınan token")
        self.satta_token_input.setReadOnly(True)

        self.satta_login_button = QPushButton("Satta'ya Giriş Yap")
        self.satta_test_button = QPushButton("Satta Bağlantısını Test Et")

        satta_login_form.addRow("Base URL", self.satta_base_url_input)
        satta_login_form.addRow("E-posta", self.satta_username_input)
        satta_login_form.addRow("Şifre", self.satta_password_input)
        satta_login_form.addRow("Token", self.satta_token_input)
        satta_login_form.addRow("", self.satta_login_button)
        satta_login_form.addRow("", self.satta_test_button)

        satta_layout.addWidget(satta_login_frame)

        logo_group = QGroupBox("Logo Bağlantı Ayarları")
        logo_form = QFormLayout(logo_group)

        self.logo_server_input = QLineEdit()
        self.logo_server_input.setPlaceholderText("127.0.0.1")

        self.logo_database_input = QLineEdit()
        self.logo_database_input.setPlaceholderText("TIGERDB")

        self.logo_username_input = QLineEdit()
        self.logo_username_input.setPlaceholderText("sa")

        self.logo_password_input = QLineEdit()
        self.logo_password_input.setPlaceholderText("SQL şifre")
        self.logo_password_input.setEchoMode(QLineEdit.Password)

        self.logo_firm_no_input = QSpinBox()
        self.logo_firm_no_input.setRange(1, 999)
        self.logo_firm_no_input.setValue(1)

        self.logo_period_no_input = QSpinBox()
        self.logo_period_no_input.setRange(1, 99)
        self.logo_period_no_input.setValue(1)

        self.logo_test_button = QPushButton("Logo Bağlantısını Test Et")

        logo_form.addRow("SQL Server", self.logo_server_input)
        logo_form.addRow("Database", self.logo_database_input)
        logo_form.addRow("Kullanıcı", self.logo_username_input)
        logo_form.addRow("Şifre", self.logo_password_input)
        logo_form.addRow("Firma No", self.logo_firm_no_input)
        logo_form.addRow("Dönem No", self.logo_period_no_input)
        logo_form.addRow("", self.logo_test_button)

        content_row.addWidget(satta_group)
        content_row.addWidget(logo_group)

        root_layout.addLayout(content_row)

        self.save_button = QPushButton("Ayarları Kaydet")
        root_layout.addWidget(self.save_button)

        self.satta_login_button.clicked.connect(self.handle_satta_login)
        self.satta_test_button.clicked.connect(self.handle_satta_test)
        self.logo_test_button.clicked.connect(self.handle_logo_test)
        self.save_button.clicked.connect(self.save_settings)

        self.load_settings()

    def create_satta_config(self) -> SattaInvoiceConfig:
        return SattaInvoiceConfig(
            use_mock_data=False,
            base_url=self.satta_base_url_input.text().strip(),
            username=self.satta_username_input.text().strip(),
            password=self.satta_password_input.text().strip(),
            token=self.satta_token_input.text().strip(),
        )

    def handle_satta_login(self) -> None:
        if not self.satta_username_input.text().strip() or not self.satta_password_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Satta e-posta ve şifre alanlarını doldur.")
            return

        connector = SattaInvoiceConnector(self.create_satta_config())

        try:
            token = connector.ensure_token(force_refresh=True)
        except Exception as exc:
            QMessageBox.critical(self, "Satta Giriş Hatası", f"Satta token alınamadı:\n{exc}")
            return

        self.satta_token_input.setText(token)
        self.save_settings(show_message=False)
        QMessageBox.information(self, "Satta Giriş", "Satta token başarıyla alındı ve kaydedildi.")

    def handle_satta_test(self) -> None:
        connector = SattaInvoiceConnector(self.create_satta_config())

        try:
            token = connector.ensure_token(force_refresh=False)
        except Exception as exc:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Satta bağlantısı doğrulanamadı:\n{exc}")
            return

        if not token:
            QMessageBox.warning(self, "Token Yok", "Önce Satta'ya giriş yapıp token al.")
            return

        self.satta_token_input.setText(token)
        QMessageBox.information(self, "Satta Bağlantısı", "Satta bağlantısı ve token bilgisi hazır görünüyor.")

    def handle_logo_test(self) -> None:
        if not self.logo_server_input.text().strip() or not self.logo_database_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Logo SQL Server ve Database alanlarını doldur.")
            return

        QMessageBox.information(
            self,
            "Logo Bağlantısı",
            "Logo bağlantı testi için bilgiler hazır. SQL test akışı daha sonra eklenecek.",
        )

    def save_settings(self, show_message: bool = True) -> None:
        settings_data = {
            "satta": {
                "base_url": self.satta_base_url_input.text().strip(),
                "username": self.satta_username_input.text().strip(),
                "password": self.satta_password_input.text().strip(),
                "token": self.satta_token_input.text().strip(),
            },
            "logo": {
                "server": self.logo_server_input.text().strip(),
                "database": self.logo_database_input.text().strip(),
                "username": self.logo_username_input.text().strip(),
                "password": self.logo_password_input.text().strip(),
                "firm_no": self.logo_firm_no_input.value(),
                "period_no": self.logo_period_no_input.value(),
            },
        }

        ensure_parent_directory(self.SETTINGS_FILE)
        self.SETTINGS_FILE.write_text(
            json.dumps(settings_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if show_message:
            QMessageBox.information(self, "Ayarlar", "Ayarlar kaydedildi.")

    def load_settings(self) -> None:
        if not self.SETTINGS_FILE.exists():
            return

        try:
            settings_data = json.loads(self.SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        satta_settings = settings_data.get("satta", {})
        self.satta_base_url_input.setText(str(satta_settings.get("base_url", "")))
        self.satta_username_input.setText(str(satta_settings.get("username", "")))
        self.satta_password_input.setText(str(satta_settings.get("password", "")))
        self.satta_token_input.setText(str(satta_settings.get("token", "")))

        logo_settings = settings_data.get("logo", {})
        self.logo_server_input.setText(str(logo_settings.get("server", "")))
        self.logo_database_input.setText(str(logo_settings.get("database", "")))
        self.logo_username_input.setText(str(logo_settings.get("username", "")))
        self.logo_password_input.setText(str(logo_settings.get("password", "")))
        self.logo_firm_no_input.setValue(int(logo_settings.get("firm_no", 1) or 1))
        self.logo_period_no_input.setValue(int(logo_settings.get("period_no", 1) or 1))