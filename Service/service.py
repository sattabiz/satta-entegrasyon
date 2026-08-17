import json
from Common.qt_compat import Qt
from Common.path_helper import user_data_path
from Common.qt_compat import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from Service.get_categories import SattaServiceCategoryConnector
from Service.get_cost_center import SattaServiceCostCenterConnector
from Service.push_services import SattaServicePushConnector
from Service.services_reader import ServiceReader, ServiceReaderConfig
from Common.checkable_combo import CheckableComboBox
from Common.table_utils import enable_table_copy

SETTINGS_FILE = user_data_path("app_settings.json")


class ServiceTab(QWidget):
    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout(self)

        title_label = QLabel("Hizmet Listesi")

        title_row = QHBoxLayout()
        title_row.addWidget(title_label)
        title_row.addStretch()

        top_form_layout = QVBoxLayout()

        self.source_combo = CheckableComboBox()
        self.source_combo.addItem("Masraf merkezi yüklenmedi")

        self.target_combo = QComboBox()
        self.target_combo.addItem("Kategori yüklenmedi")

        combo_row = QHBoxLayout()

        source_layout = QVBoxLayout()
        source_label = QLabel("Masraf Merkezi")
        source_layout.addWidget(source_label)
        source_layout.addWidget(self.source_combo)

        target_layout = QVBoxLayout()
        target_label = QLabel("Kategori")
        target_layout.addWidget(target_label)
        target_layout.addWidget(self.target_combo)

        combo_row.addLayout(source_layout)
        combo_row.addLayout(target_layout)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(36)
        self.search_input.setMinimumWidth(320)
        self.search_input.setPlaceholderText("Hizmet kodu, hizmet adı veya tipi")

        self.search_button = QPushButton("🔍")
        self.search_button.setMinimumHeight(36)
        self.search_button.setMinimumWidth(44)

        search_row = QHBoxLayout()
        search_label = QLabel("Ara")
        search_row.addWidget(search_label)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)

        top_form_layout.addLayout(combo_row)

        root_layout.addLayout(top_form_layout)

        self.load_button = QPushButton("Masraf Merkezi ve Kategorileri Al")
        self.load_services_button = QPushButton("Hizmetleri Al")
        self.transfer_button = QPushButton("Seçili Hizmetleri Satta'ya Gönder")
        self.select_all_button = QPushButton("Tümünü Seç / Temizle")

        title_row.addWidget(self.load_button)
        title_row.addWidget(self.load_services_button)
        title_row.addWidget(self.transfer_button)
        title_row.addWidget(self.select_all_button)
        root_layout.addLayout(title_row)
        root_layout.addLayout(search_row)

        self.service_table = QTableWidget(0, 1)
        self.service_table.setHorizontalHeaderLabels(["Seç"])
        self.service_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.service_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.service_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.service_table.setColumnWidth(0, 36)
        self.service_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.service_table.horizontalHeader().setStretchLastSection(False)
        self.service_table.setWordWrap(True)
        self.service_table.setTextElideMode(Qt.ElideRight)
        enable_table_copy(self.service_table)
        
        self.current_headers = []

        root_layout.addWidget(self.service_table)

        status_info_layout = QHBoxLayout()
        self.selected_info_label = QLabel("Seçili hizmet sayısı: 0")
        self.ready_info_label = QLabel("Kullanımda durumundaki hizmet sayısı: 0")
        self.error_info_label = QLabel("Diğer durumdaki hizmet sayısı: 0")
        status_info_layout.addWidget(self.selected_info_label)
        status_info_layout.addWidget(self.ready_info_label)
        status_info_layout.addWidget(self.error_info_label)
        root_layout.addLayout(status_info_layout)

        self.all_services = []
        self.search_button.clicked.connect(self.run_search_with_feedback)
        self.search_input.returnPressed.connect(self.run_search_with_feedback)
        
        self.load_button.clicked.connect(self.load_cost_centers_and_categories)
        self.load_services_button.clicked.connect(self.load_services)
        self.transfer_button.clicked.connect(self.transfer_selected_services)
        self.select_all_button.clicked.connect(self.toggle_select_all)
        
        self.service_table.itemChanged.connect(self.handle_table_item_changed)
        
    def get_col_idx(self, name):
        if not self.current_headers:
            return -1
        try:
            return self.current_headers.index(name) + 1
        except ValueError:
            return -1

    def load_services(self):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as settings_file:
                settings = json.load(settings_file)
        except FileNotFoundError:
            QMessageBox.warning(self, "Ayar Bulunamadı", "Önce Ayarlar ekranından Logo bağlantı bilgilerini kaydet.")
            return
        except (json.JSONDecodeError, OSError) as exc:
            QMessageBox.critical(self, "Ayar Okuma Hatası", f"Ayar dosyası okunamadı:\n{exc}")
            return

        logo_settings = settings.get("logo", {})

        try:
            config = ServiceReaderConfig(
                server=logo_settings.get("server", ""),
                database=logo_settings.get("database", ""),
                db_username=logo_settings.get("db_username", ""),
                db_password=logo_settings.get("db_password", ""),
                username=logo_settings.get("username", ""),
                password=logo_settings.get("password", ""),
                firm_no=logo_settings.get("firm_no", 1),
                period_no=logo_settings.get("period_no", 1),
            )
            reader = ServiceReader(config)
            headers, services = reader.read_services()
        except Exception as exc:
            QMessageBox.critical(self, "Logo Hatası", f"Hizmetler alınamadı:\n{exc}")
            return

        self.apply_service_data(headers, services)

    def apply_service_data(self, headers, rows):
        self.current_headers = headers
        self.all_services = [tuple(str(value) if value is not None else "" for value in row) for row in rows]

        try:
            self.service_table.itemChanged.disconnect(self.handle_table_item_changed)
        except (RuntimeError, TypeError):
            pass

        self.service_table.setUpdatesEnabled(False)
        self.service_table.blockSignals(True)
        try:
            self.service_table.setColumnCount(len(headers) + 1)
            self.service_table.setHorizontalHeaderLabels(["Seç"] + headers)
            self.configure_table_columns()
            self.populate_service_table(self.all_services)
        finally:
            self.service_table.blockSignals(False)
            self.service_table.setUpdatesEnabled(True)

        self.service_table.itemChanged.connect(self.handle_table_item_changed)
        self.update_status_summary()
        self.update_edit_button_text()

        if self.service_table.rowCount() > 0:
            self.service_table.selectRow(0)

    def run_search_with_feedback(self):
        self.filter_services(show_no_results_message=True)

    def load_cost_centers_and_categories(self):
        cost_center_connector = SattaServiceCostCenterConnector()
        category_connector = SattaServiceCategoryConnector()

        try:
            cost_centers = cost_center_connector.get_cost_centers()
            categories = category_connector.get_categories()
        except Exception as exc:
            QMessageBox.critical(self, "Satta Hatası", f"Masraf merkezi ve kategoriler alınamadı:\n{exc}")
            return

        self.populate_dropdowns(cost_centers, categories)

    def populate_dropdowns(self, cost_centers, categories):
        self.source_combo.blockSignals(True)
        self.target_combo.blockSignals(True)

        self.source_combo.clear()
        self.target_combo.clear()

        if cost_centers:
            for cost_center in cost_centers:
                if not isinstance(cost_center, dict):
                    continue
                name = str(cost_center.get("name", "")).strip()
                erp_id = str(cost_center.get("erp_id", "")).strip()
                if not name:
                    continue
                self.source_combo.addItem(name, erp_id)

            if self.source_combo.count() == 0:
                self.source_combo.addItem("Masraf merkezi bulunamadı", "")
        else:
            self.source_combo.addItem("Masraf merkezi bulunamadı", "")

        if categories:
            self.target_combo.addItems(categories)
        else:
            self.target_combo.addItem("Kategori bulunamadı")

        self.source_combo.blockSignals(False)
        self.target_combo.blockSignals(False)

    def configure_table_columns(self):
        default_width = 120
        header = self.service_table.horizontalHeader()

        for column_index in range(self.service_table.columnCount()):
            header.setSectionResizeMode(column_index, QHeaderView.Interactive)
            self.service_table.setColumnWidth(column_index, default_width)

        self.service_table.setColumnWidth(0, 36)
        
        name_idx = self.get_col_idx("Hizmet Açıklaması")
        if name_idx == -1: name_idx = self.get_col_idx("Hizmet Adı")
        if name_idx > 0:
            self.service_table.setColumnWidth(name_idx, 250)

    def populate_service_table(self, rows):
        self.service_table.setRowCount(0)
        code_idx = self.get_col_idx("Hizmet Kodu")
        
        for row_data in rows:
            row_index = self.service_table.rowCount()
            self.service_table.insertRow(row_index)

            select_item = QTableWidgetItem()
            select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            select_item.setCheckState(Qt.Unchecked)
            select_item.setText("")
            self.service_table.setItem(row_index, 0, select_item)

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.service_table.setItem(row_index, col_index, item)

    def toggle_select_all(self):
        all_checked = True
        for row in range(self.service_table.rowCount()):
            item = self.service_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Unchecked:
                all_checked = False
                break
        
        new_state = Qt.Unchecked if all_checked else Qt.Checked
        
        self.service_table.blockSignals(True)
        for row in range(self.service_table.rowCount()):
            item = self.service_table.item(row, 0)
            if item is not None:
                item.setCheckState(new_state)
        self.service_table.blockSignals(False)
        self.update_selected_count()

    def handle_table_item_changed(self, item):
        if item is None:
            return

        if item.column() == 0:
            self.update_selected_count()

    def filter_services(self, *_args, show_no_results_message=False):
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            filtered_rows = self.all_services
        else:
            filtered_rows = []
            for row in self.all_services:
                if any(search_text in str(cell).lower() for cell in row):
                    filtered_rows.append(row)

        self.service_table.setUpdatesEnabled(False)
        self.service_table.blockSignals(True)
        try:
            self.populate_service_table(filtered_rows)
        finally:
            self.service_table.blockSignals(False)
            self.service_table.setUpdatesEnabled(True)

        self.update_status_summary()

        if self.service_table.rowCount() > 0:
            self.service_table.selectRow(0)
        elif search_text and show_no_results_message:
            QMessageBox.information(self, "Arama Sonucu", "Aramaya uygun hizmet bulunamadı.")

    def parse_tax_rate(self, value):
        text = str(value).strip().replace("%", "").replace(",", ".")
        try:
            return int(float(text))
        except (TypeError, ValueError):
            return 0

    def parse_number(self, value):
        text = str(value).strip().replace(",", ".")
        try:
            return float(text)
        except (TypeError, ValueError):
            return 0

    def get_selected_services(self):
        selected_services = []
        invalid_services = []

        checked_cost_centers = self.source_combo.checkedItems()
        selected_cost_center_erp_ids = [str(item["data"]).strip() for item in checked_cost_centers if item["data"]]

        selected_category = self.target_combo.currentText().strip()
        invalid_category_values = {"", "Kategori yüklenmedi", "Kategori bulunamadı"}

        code_idx = self.get_col_idx("Hizmet Kodu")
        name_idx = self.get_col_idx("Hizmet Açıklaması")
        if name_idx == -1: name_idx = self.get_col_idx("Hizmet Adı")
        unit_idx = self.get_col_idx("Birim")
        tax_idx = self.get_col_idx("KDV Oranı")
        
        for row in range(self.service_table.rowCount()):
            check_item = self.service_table.item(row, 0)
            if check_item is None or check_item.checkState() != Qt.Checked:
                continue

            service_code = self.service_table.item(row, code_idx).text().strip() if code_idx > 0 and self.service_table.item(row, code_idx) else ""
            service_name = self.service_table.item(row, name_idx).text().strip() if name_idx > 0 and self.service_table.item(row, name_idx) else "-"
            unit_text = self.service_table.item(row, unit_idx).text().strip() if unit_idx > 0 and self.service_table.item(row, unit_idx) else ""
            tax_text = self.service_table.item(row, tax_idx).text() if tax_idx > 0 and self.service_table.item(row, tax_idx) else "0"
            
            if not unit_text:
                service_label = service_code or service_name
                invalid_services.append(f"{service_label} -> Eksik alan: Birim")
                continue

            category_text = selected_category if selected_category not in invalid_category_values else ""
            cost_center_ids = selected_cost_center_erp_ids.copy()

            service_data = {
                "product_name": service_name,
                "description": "",
                "category_text": category_text,
                "erp_id": service_code,
                "unit": unit_text,
                "tax_rate": self.parse_tax_rate(tax_text),
                "price": 0.0,
                "currency": "TRY",
                "max_quantity": None,
                "min_quantity": None,
                "quantity_tolerance": None,
                "notes": "",
                "cost_center_erp_ids": cost_center_ids,
                "un_no": "",
                "erp_code": service_code,
            }
            selected_services.append(service_data)

        return selected_services, invalid_services

    def transfer_selected_services(self):
        selected_services, invalid_services = self.get_selected_services()

        if invalid_services:
            missing_text = "\n".join(invalid_services)
            QMessageBox.warning(
                self,
                "Eksik Zorunlu Alan",
                f"Aşağıdaki hizmetler aktarılmadı çünkü Birim bilgileri Logo'da eksik (veya tabloda boş):\n\n{missing_text}\n\nLütfen Logo ERP veya tablo üzerinden boş olan birimleri düzeltip tekrar deneyin.",
            )
            return

        if not selected_services:
            QMessageBox.warning(self, "Seçim Yok", "Önce aktarılacak (ve birimi girilmiş) hizmetleri seçin.")
            return

        connector = SattaServicePushConnector()

        try:
            connector.push_services(selected_services)
        except Exception as exc:
            QMessageBox.critical(self, "Aktarım Hatası", f"Seçili hizmetler Satta'ya gönderilemedi:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Aktarım Tamamlandı",
            f"Seçili {len(selected_services)} hizmet Satta'ya başarıyla gönderildi."
        )

    def update_selected_count(self):
        selected_count = 0
        for row in range(self.service_table.rowCount()):
            item = self.service_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected_count += 1

        self.selected_info_label.setText(f"Seçili hizmet sayısı: {selected_count}")

    def update_status_summary(self):
        self.update_selected_count()

        ready_count = 0
        error_count = 0
        
        status_idx = self.get_col_idx("Kullanım Durumu")
        if status_idx == -1: status_idx = self.get_col_idx("Durum")

        if status_idx > 0:
            for row in range(self.service_table.rowCount()):
                status_item = self.service_table.item(row, status_idx)
                if status_item is None:
                    continue

                status_text = status_item.text().strip().lower()
                if status_text in ("kullanımda", "hazır"):
                    ready_count += 1
                else:
                    error_count += 1

        self.ready_info_label.setText(f"Kullanımda durumundaki hizmet sayısı: {ready_count}")
        self.error_info_label.setText(f"Diğer durumdaki hizmet sayısı: {error_count}")
