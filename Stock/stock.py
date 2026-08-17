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

from Stock.get_categories import SattaCategoryConnector
from Stock.get_cost_center import SattaCostCenterConnector
from Stock.push_products import SattaProductPushConnector
from Stock.products_reader import ProductReader, ProductReaderConfig
from Common.checkable_combo import CheckableComboBox
from Common.table_utils import enable_table_copy

SETTINGS_FILE = user_data_path("app_settings.json")


class StockTab(QWidget):
    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout(self)

        title_label = QLabel("Ürün Listesi")

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
        self.search_input.setPlaceholderText("Ürün kodu, ürün adı veya kategori")

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
        self.load_products_button = QPushButton("Ürünleri Al")
        self.transfer_button = QPushButton("Seçili Ürünleri Satta'ya Gönder")
        self.select_all_button = QPushButton("Tümünü Seç / Temizle")
        title_row.addWidget(self.load_button)
        title_row.addWidget(self.load_products_button)
        title_row.addWidget(self.transfer_button)
        title_row.addWidget(self.select_all_button)
        root_layout.addLayout(title_row)
        root_layout.addLayout(search_row)

        self.stock_table = QTableWidget(0, 1)
        self.stock_table.setHorizontalHeaderLabels(["Seç"])
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stock_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.stock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.stock_table.setColumnWidth(0, 36)
        self.stock_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stock_table.horizontalHeader().setStretchLastSection(False)
        self.stock_table.setWordWrap(True)
        self.stock_table.setTextElideMode(Qt.ElideRight)
        enable_table_copy(self.stock_table)
        
        self.current_headers = []

        root_layout.addWidget(self.stock_table)

        status_info_layout = QHBoxLayout()
        self.selected_info_label = QLabel("Seçili ürün sayısı: 0")
        self.ready_info_label = QLabel("Kullanımda durumundaki ürün sayısı: 0")
        self.error_info_label = QLabel("Diğer durumdaki ürün sayısı: 0")
        status_info_layout.addWidget(self.selected_info_label)
        status_info_layout.addWidget(self.ready_info_label)
        status_info_layout.addWidget(self.error_info_label)
        root_layout.addLayout(status_info_layout)

        self.all_products = []
        self.search_button.clicked.connect(self.run_search_with_feedback)
        self.search_input.returnPressed.connect(self.run_search_with_feedback)
        self.load_button.clicked.connect(self.load_cost_centers_and_categories)
        self.load_products_button.clicked.connect(self.load_products)
        self.transfer_button.clicked.connect(self.transfer_selected_products)
        self.select_all_button.clicked.connect(self.toggle_select_all)
        self.stock_table.itemChanged.connect(self.handle_table_item_changed)
        
    def get_col_idx(self, name):
        if not self.current_headers:
            return -1
        try:
            return self.current_headers.index(name) + 1
        except ValueError:
            return -1

    def load_products(self):
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
            config = ProductReaderConfig(
                server=logo_settings.get("server", ""),
                database=logo_settings.get("database", ""),
                db_username=logo_settings.get("db_username", ""),
                db_password=logo_settings.get("db_password", ""),
                username=logo_settings.get("username", ""),
                password=logo_settings.get("password", ""),
                firm_no=logo_settings.get("firm_no", 1),
                period_no=logo_settings.get("period_no", 1),
            )
            reader = ProductReader(config)
            headers, products = reader.read_products()
        except Exception as exc:
            QMessageBox.critical(self, "Logo Hatası", f"Ürünler alınamadı:\n{exc}")
            return

        self.apply_product_data(headers, products)

    def apply_product_data(self, headers, rows):
        self.current_headers = headers
        self.all_products = [tuple(str(value) if value is not None else "" for value in row) for row in rows]

        try:
            self.stock_table.itemChanged.disconnect(self.handle_table_item_changed)
        except (RuntimeError, TypeError):
            pass

        self.stock_table.setUpdatesEnabled(False)
        self.stock_table.blockSignals(True)
        try:
            self.stock_table.setColumnCount(len(headers) + 1)
            self.stock_table.setHorizontalHeaderLabels(["Seç"] + headers)
            self.configure_table_columns()
            self.populate_stock_table(self.all_products)
        finally:
            self.stock_table.blockSignals(False)
            self.stock_table.setUpdatesEnabled(True)

        self.stock_table.itemChanged.connect(self.handle_table_item_changed)
        self.update_status_summary()
        self.update_edit_button_text()

        if self.stock_table.rowCount() > 0:
            self.stock_table.selectRow(0)

    def run_search_with_feedback(self):
        self.filter_products(show_no_results_message=True)

    def load_cost_centers_and_categories(self):
        cost_center_connector = SattaCostCenterConnector()
        category_connector = SattaCategoryConnector()

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
        header = self.stock_table.horizontalHeader()

        for column_index in range(self.stock_table.columnCount()):
            header.setSectionResizeMode(column_index, QHeaderView.Interactive)
            self.stock_table.setColumnWidth(column_index, default_width)

        self.stock_table.setColumnWidth(0, 36)
        
        name_idx = self.get_col_idx("Ürün Adı")
        if name_idx > 0:
            self.stock_table.setColumnWidth(name_idx, 250)

    def populate_stock_table(self, rows):
        self.stock_table.setRowCount(0)
        code_idx = self.get_col_idx("Ürün Kodu")
        
        for row_data in rows:
            row_index = self.stock_table.rowCount()
            self.stock_table.insertRow(row_index)

            select_item = QTableWidgetItem()
            select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            select_item.setCheckState(Qt.Unchecked)
            select_item.setText("")
            self.stock_table.setItem(row_index, 0, select_item)

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.stock_table.setItem(row_index, col_index, item)

    def toggle_select_all(self):
        all_checked = True
        for row in range(self.stock_table.rowCount()):
            item = self.stock_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Unchecked:
                all_checked = False
                break
        
        new_state = Qt.Unchecked if all_checked else Qt.Checked
        
        self.stock_table.blockSignals(True)
        for row in range(self.stock_table.rowCount()):
            item = self.stock_table.item(row, 0)
            if item is not None:
                item.setCheckState(new_state)
        self.stock_table.blockSignals(False)
        self.update_selected_count()

    def handle_table_item_changed(self, item):
        if item is None:
            return

        if item.column() == 0:
            self.update_selected_count()

    def filter_products(self, *_args, show_no_results_message=False):
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            filtered_rows = self.all_products
        else:
            filtered_rows = []
            for row in self.all_products:
                if any(search_text in str(cell).lower() for cell in row):
                    filtered_rows.append(row)

        self.stock_table.setUpdatesEnabled(False)
        self.stock_table.blockSignals(True)
        try:
            self.populate_stock_table(filtered_rows)
        finally:
            self.stock_table.blockSignals(False)
            self.stock_table.setUpdatesEnabled(True)

        self.update_status_summary()

        if self.stock_table.rowCount() > 0:
            self.stock_table.selectRow(0)
        elif search_text and show_no_results_message:
            QMessageBox.information(self, "Arama Sonucu", "Aramaya uygun ürün bulunamadı.")

    def get_selected_products(self):
        selected_products = []
        invalid_products = []

        checked_cost_centers = self.source_combo.checkedItems()
        selected_cost_center_erp_ids = [str(item["data"]).strip() for item in checked_cost_centers if item["data"]]

        selected_category = self.target_combo.currentText().strip()

        invalid_category_values = {"", "Kategori yüklenmedi", "Kategori bulunamadı"}
        
        code_idx = self.get_col_idx("Ürün Kodu")
        name_idx = self.get_col_idx("Ürün Adı")
        unit_idx = self.get_col_idx("Birim")
        tax_idx = self.get_col_idx("KDV Oranı")
        price_idx = self.get_col_idx("Birim Fiyat")
        curr_idx = self.get_col_idx("Döviz")
        desc_idx = self.get_col_idx("Açıklama")
        cat_idx = self.get_col_idx("Kategori")

        for row in range(self.stock_table.rowCount()):
            check_item = self.stock_table.item(row, 0)
            if check_item is None or check_item.checkState() != Qt.Checked:
                continue

            product_code = self.stock_table.item(row, code_idx).text().strip() if code_idx > 0 and self.stock_table.item(row, code_idx) else ""
            product_name = self.stock_table.item(row, name_idx).text().strip() if name_idx > 0 and self.stock_table.item(row, name_idx) else "-"
            unit_text = self.stock_table.item(row, unit_idx).text().strip() if unit_idx > 0 and self.stock_table.item(row, unit_idx) else ""
            tax_text = self.stock_table.item(row, tax_idx).text() if tax_idx > 0 and self.stock_table.item(row, tax_idx) else "0"
            price_text = self.stock_table.item(row, price_idx).text() if price_idx > 0 and self.stock_table.item(row, price_idx) else "0"
            curr_text = self.stock_table.item(row, curr_idx).text().strip() if curr_idx > 0 and self.stock_table.item(row, curr_idx) else "TRY"
            desc_text = self.stock_table.item(row, desc_idx).text().strip() if desc_idx > 0 and self.stock_table.item(row, desc_idx) else ""
            
            if not unit_text:
                product_label = product_code or product_name
                invalid_products.append(f"{product_label} -> Eksik alan: Birim")
                continue

            row_category = self.stock_table.item(row, cat_idx).text().strip() if cat_idx > 0 and self.stock_table.item(row, cat_idx) else ""
            category_text = selected_category if selected_category not in invalid_category_values else row_category

            cost_center_ids = selected_cost_center_erp_ids.copy()

            product_data = {
                "product_name": product_name,
                "description": desc_text,
                "category_text": category_text,
                "erp_id": product_code,
                "unit": unit_text,
                "tax_rate": self.parse_tax_rate(tax_text),
                "price": self.parse_number(price_text),
                "currency": curr_text,
                "max_quantity": None,
                "min_quantity": None,
                "quantity_tolerance": None,
                "notes": "",
                "cost_center_erp_ids": cost_center_ids,
                "un_no": "",
                "erp_code": product_code,
            }
            selected_products.append(product_data)

        return selected_products, invalid_products

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

    def transfer_selected_products(self):
        selected_products, invalid_products = self.get_selected_products()

        if invalid_products:
            missing_text = "\n".join(invalid_products)
            QMessageBox.warning(
                self,
                "Eksik Zorunlu Alan",
                f"Aşağıdaki ürünler aktarılmadı çünkü Birim bilgileri Logo'da eksik (veya tabloda boş):\n\n{missing_text}\n\nLütfen Logo ERP veya Satta Entegrasyon tablosu üzerinden boş olan birimleri düzeltip tekrar deneyin.",
            )
            return

        if not selected_products:
            QMessageBox.warning(self, "Seçim Yok", "Önce aktarılacak (ve birimi girilmiş) ürünleri seç.")
            return

        connector = SattaProductPushConnector()

        try:
            connector.push_products(selected_products)
        except Exception as exc:
            QMessageBox.critical(self, "Aktarım Hatası", f"Seçili ürünler Satta'ya gönderilemedi:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Aktarım Tamamlandı",
            f"Seçili {len(selected_products)} ürün Satta'ya gönderildi.",
        )

    def update_selected_count(self):
        selected_count = 0
        for row in range(self.stock_table.rowCount()):
            item = self.stock_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected_count += 1

        self.selected_info_label.setText(f"Seçili ürün sayısı: {selected_count}")

    def update_status_summary(self):
        self.update_selected_count()

        ready_count = 0
        error_count = 0
        
        status_idx = self.get_col_idx("Kullanım Durumu")
        if status_idx == -1:
            status_idx = self.get_col_idx("Durum")

        if status_idx > 0:
            for row in range(self.stock_table.rowCount()):
                status_item = self.stock_table.item(row, status_idx)
                if status_item is None:
                    continue

                status_text = status_item.text().strip().lower()
                if status_text in ("kullanımda", "hazır"):
                    ready_count += 1
                else:
                    error_count += 1

        self.ready_info_label.setText(f"Kullanımda durumundaki ürün sayısı: {ready_count}")
        self.error_info_label.setText(f"Diğer durumdaki ürün sayısı: {error_count}")
