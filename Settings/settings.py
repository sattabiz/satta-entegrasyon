import json

from Common.qt_compat import (
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


RUNTIME_CONFIG_FILE = user_data_path("runtime_config.json")


CONNECTOR_DISPLAY_NAMES = {
    "logo": "Logo",
    "sap": "SAP",
    "canias": "Canias",
}


class SettingsTab(QWidget):
    SETTINGS_FILE = user_data_path("app_settings.json")

    def __init__(self):
        super().__init__()

        self.active_connector = self.load_active_connector()

        root_layout = QVBoxLayout(self)

        title_label = QLabel("Ayarlar")
        root_layout.addWidget(title_label)

        content_row = QHBoxLayout()

        satta_group = self.build_satta_group()
        connector_group = self.build_connector_group()

        content_row.addWidget(satta_group)
        content_row.addWidget(connector_group)

        root_layout.addLayout(content_row)

        self.save_button = QPushButton("Ayarları Kaydet")
        root_layout.addWidget(self.save_button)

        self.satta_login_button.clicked.connect(self.handle_satta_login)
        self.satta_test_button.clicked.connect(self.handle_satta_test)
        self.connector_test_button.clicked.connect(self.handle_connector_test)
        self.save_button.clicked.connect(self.save_settings)

        self.load_settings()

    def load_active_connector(self) -> str:
        if not RUNTIME_CONFIG_FILE.exists():
            return "logo"

        try:
            runtime_config = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return "logo"

        active_connector = str(runtime_config.get("active_connector", "")).strip().lower()
        if active_connector in CONNECTOR_DISPLAY_NAMES:
            return active_connector
        return "logo"

    def get_connector_display_name(self) -> str:
        return CONNECTOR_DISPLAY_NAMES.get(self.active_connector, "Hedef Sistem")

    def build_satta_group(self) -> QGroupBox:
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
        return satta_group

    def build_connector_group(self) -> QGroupBox:
        if self.active_connector == "logo":
            return self.build_logo_group()
        if self.active_connector == "sap":
            return self.build_sap_group()
        if self.active_connector == "canias":
            return self.build_canias_group()
        return self.build_empty_connector_group()

    def build_logo_group(self) -> QGroupBox:
        connector_group = QGroupBox("Logo Bağlantı Ayarları")
        connector_form = QFormLayout(connector_group)

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

        self.connector_test_button = QPushButton("Logo Bağlantısını Test Et")

        connector_form.addRow("SQL Server", self.logo_server_input)
        connector_form.addRow("Database", self.logo_database_input)
        connector_form.addRow("Kullanıcı", self.logo_username_input)
        connector_form.addRow("Şifre", self.logo_password_input)
        connector_form.addRow("Firma No", self.logo_firm_no_input)
        connector_form.addRow("Dönem No", self.logo_period_no_input)
        connector_form.addRow("", self.connector_test_button)

        return connector_group

    def build_sap_group(self) -> QGroupBox:
        connector_group = QGroupBox("SAP Bağlantı Ayarları")
        connector_form = QFormLayout(connector_group)

        self.sap_host_input = QLineEdit()
        self.sap_host_input.setPlaceholderText("sap.example.local")

        self.sap_system_number_input = QLineEdit()
        self.sap_system_number_input.setPlaceholderText("00")

        self.sap_client_input = QLineEdit()
        self.sap_client_input.setPlaceholderText("100")

        self.sap_username_input = QLineEdit()
        self.sap_username_input.setPlaceholderText("SAP kullanıcı")

        self.sap_password_input = QLineEdit()
        self.sap_password_input.setPlaceholderText("SAP şifre")
        self.sap_password_input.setEchoMode(QLineEdit.Password)

        self.sap_language_input = QLineEdit()
        self.sap_language_input.setPlaceholderText("TR")

        self.connector_test_button = QPushButton("SAP Bağlantısını Test Et")

        connector_form.addRow("Host", self.sap_host_input)
        connector_form.addRow("System Number", self.sap_system_number_input)
        connector_form.addRow("Client", self.sap_client_input)
        connector_form.addRow("Kullanıcı", self.sap_username_input)
        connector_form.addRow("Şifre", self.sap_password_input)
        connector_form.addRow("Dil", self.sap_language_input)
        connector_form.addRow("", self.connector_test_button)

        return connector_group

    def build_canias_group(self) -> QGroupBox:
        connector_group = QGroupBox("Canias Bağlantı Ayarları")
        connector_form = QFormLayout(connector_group)

        self.canias_host_input = QLineEdit()
        self.canias_host_input.setPlaceholderText("canias.example.local")

        self.canias_tenant_input = QLineEdit()
        self.canias_tenant_input.setPlaceholderText("Tenant / Firma")

        self.canias_username_input = QLineEdit()
        self.canias_username_input.setPlaceholderText("Canias kullanıcı")

        self.canias_password_input = QLineEdit()
        self.canias_password_input.setPlaceholderText("Canias şifre")
        self.canias_password_input.setEchoMode(QLineEdit.Password)

        self.connector_test_button = QPushButton("Canias Bağlantısını Test Et")

        connector_form.addRow("Host", self.canias_host_input)
        connector_form.addRow("Tenant / Firma", self.canias_tenant_input)
        connector_form.addRow("Kullanıcı", self.canias_username_input)
        connector_form.addRow("Şifre", self.canias_password_input)
        connector_form.addRow("", self.connector_test_button)

        return connector_group

    def build_empty_connector_group(self) -> QGroupBox:
        connector_group = QGroupBox("Bağlantı Ayarları")
        connector_layout = QVBoxLayout(connector_group)

        info_label = QLabel("Aktif connector seçilmedi. Kurulum sihirbazından bir connector seçerek devam et.")
        connector_layout.addWidget(info_label)

        self.connector_test_button = QPushButton("Bağlantı Testi Hazır Değil")
        self.connector_test_button.setEnabled(False)
        connector_layout.addWidget(self.connector_test_button)

        return connector_group

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

    def handle_connector_test(self) -> None:
        if self.active_connector == "logo":
            self.handle_logo_test()
            return
        if self.active_connector == "sap":
            self.handle_sap_test()
            return
        if self.active_connector == "canias":
            self.handle_canias_test()
            return

        QMessageBox.warning(self, "Connector Yok", "Aktif connector bilgisi bulunamadı.")

    def handle_logo_test(self) -> None:
        if not self.logo_server_input.text().strip() or not self.logo_database_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Logo SQL Server ve Database alanlarını doldur.")
            return

        QMessageBox.information(
            self,
            "Logo Bağlantısı",
            "Logo bağlantı testi için bilgiler hazır. SQL test akışı daha sonra eklenecek.",
        )

    def handle_sap_test(self) -> None:
        if not self.sap_host_input.text().strip() or not self.sap_client_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "SAP Host ve Client alanlarını doldur.")
            return

        QMessageBox.information(
            self,
            "SAP Bağlantısı",
            "SAP bağlantı testi için bilgiler hazır. Gerçek bağlantı testi daha sonra eklenecek.",
        )

    def handle_canias_test(self) -> None:
        if not self.canias_host_input.text().strip() or not self.canias_tenant_input.text().strip():
            QMessageBox.warning(self, "Eksik Bilgi", "Canias Host ve Tenant / Firma alanlarını doldur.")
            return

        QMessageBox.information(
            self,
            "Canias Bağlantısı",
            "Canias bağlantı testi için bilgiler hazır. Gerçek bağlantı testi daha sonra eklenecek.",
        )

    def get_default_settings(self) -> dict:
        return {
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
        }

    def load_existing_settings(self) -> dict:
        settings_data = self.get_default_settings()

        if not self.SETTINGS_FILE.exists():
            return settings_data

        try:
            file_data = json.loads(self.SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return settings_data

        for section_name, defaults in settings_data.items():
            existing_section = file_data.get(section_name, {})
            if isinstance(defaults, dict) and isinstance(existing_section, dict):
                merged_section = dict(defaults)
                merged_section.update(existing_section)
                settings_data[section_name] = merged_section
            elif section_name in file_data:
                settings_data[section_name] = file_data[section_name]

        return settings_data

    def collect_active_connector_settings(self) -> dict:
        if self.active_connector == "logo":
            return {
                "server": self.logo_server_input.text().strip(),
                "database": self.logo_database_input.text().strip(),
                "username": self.logo_username_input.text().strip(),
                "password": self.logo_password_input.text().strip(),
                "firm_no": self.logo_firm_no_input.value(),
                "period_no": self.logo_period_no_input.value(),
            }

        if self.active_connector == "sap":
            return {
                "host": self.sap_host_input.text().strip(),
                "system_number": self.sap_system_number_input.text().strip(),
                "client": self.sap_client_input.text().strip(),
                "username": self.sap_username_input.text().strip(),
                "password": self.sap_password_input.text().strip(),
                "language": self.sap_language_input.text().strip(),
            }

        if self.active_connector == "canias":
            return {
                "host": self.canias_host_input.text().strip(),
                "tenant": self.canias_tenant_input.text().strip(),
                "username": self.canias_username_input.text().strip(),
                "password": self.canias_password_input.text().strip(),
            }

        return {}

    def save_settings(self, show_message: bool = True) -> None:
        settings_data = self.load_existing_settings()

        settings_data["satta"] = {
            "base_url": self.satta_base_url_input.text().strip(),
            "username": self.satta_username_input.text().strip(),
            "password": self.satta_password_input.text().strip(),
            "token": self.satta_token_input.text().strip(),
        }

        if self.active_connector in {"logo", "sap", "canias"}:
            settings_data[self.active_connector] = self.collect_active_connector_settings()

        try:
            ensure_parent_directory(self.SETTINGS_FILE)
            self.SETTINGS_FILE.write_text(
                json.dumps(settings_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            QMessageBox.critical(self, "Kayıt Hatası", f"Ayarlar kaydedilemedi:\n{exc}")
            return

        if show_message:
            QMessageBox.information(self, "Ayarlar", "Ayarlar kaydedildi.")

    def load_settings(self) -> None:
        settings_data = self.load_existing_settings()

        satta_settings = settings_data.get("satta", {})
        self.satta_base_url_input.setText(str(satta_settings.get("base_url", "")))
        self.satta_username_input.setText(str(satta_settings.get("username", "")))
        self.satta_password_input.setText(str(satta_settings.get("password", "")))
        self.satta_token_input.setText(str(satta_settings.get("token", "")))

        if self.active_connector == "logo":
            logo_settings = settings_data.get("logo", {})
            self.logo_server_input.setText(str(logo_settings.get("server", "")))
            self.logo_database_input.setText(str(logo_settings.get("database", "")))
            self.logo_username_input.setText(str(logo_settings.get("username", "")))
            self.logo_password_input.setText(str(logo_settings.get("password", "")))
            self.logo_firm_no_input.setValue(int(logo_settings.get("firm_no", 1) or 1))
            self.logo_period_no_input.setValue(int(logo_settings.get("period_no", 1) or 1))
            return

        if self.active_connector == "sap":
            sap_settings = settings_data.get("sap", {})
            self.sap_host_input.setText(str(sap_settings.get("host", "")))
            self.sap_system_number_input.setText(str(sap_settings.get("system_number", "")))
            self.sap_client_input.setText(str(sap_settings.get("client", "")))
            self.sap_username_input.setText(str(sap_settings.get("username", "")))
            self.sap_password_input.setText(str(sap_settings.get("password", "")))
            self.sap_language_input.setText(str(sap_settings.get("language", "TR")))
            return

        if self.active_connector == "canias":
            canias_settings = settings_data.get("canias", {})
            self.canias_host_input.setText(str(canias_settings.get("host", "")))
            self.canias_tenant_input.setText(str(canias_settings.get("tenant", "")))
            self.canias_username_input.setText(str(canias_settings.get("username", "")))
            self.canias_password_input.setText(str(canias_settings.get("password", "")))