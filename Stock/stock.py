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

        self.source_combo = QComboBox()
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
        self.edit_selected_button = QPushButton("Seçili Satırları Düzenle")
        title_row.addWidget(self.load_button)
        title_row.addWidget(self.load_products_button)
        title_row.addWidget(self.transfer_button)
        title_row.addWidget(self.edit_selected_button)
        root_layout.addLayout(title_row)
        root_layout.addLayout(search_row)

        self.stock_table = QTableWidget(0, 14)
        self.stock_table.setHorizontalHeaderLabels([
            "Seç",
            "Ürün Kodu",
            "Ürün Adı",
            "Kategori",
            "Birim",
            "Stok Miktarı",
            "Stok Adedi",
            "KDV Oranı",
            "Birim Fiyat",
            "Döviz",
            "Son Alış Fiyatı",
            "Son Alış Fiyatı Döviz Cinsi",
            "Açıklama",
            "Durum",
        ])
        self.stock_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stock_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.stock_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.stock_table.setColumnWidth(0, 36)
        self.stock_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stock_table.horizontalHeader().setStretchLastSection(False)
        self.stock_table.setWordWrap(True)
        self.stock_table.setTextElideMode(Qt.ElideRight)
        self.configure_table_columns()
        root_layout.addWidget(self.stock_table)

        status_info_layout = QHBoxLayout()
        self.selected_info_label = QLabel("Seçili ürün sayısı: 0")
        self.ready_info_label = QLabel("Hazır durumundaki ürün sayısı: 0")
        self.waiting_info_label = QLabel("Bekliyor durumundaki ürün sayısı: 0")
        self.error_info_label = QLabel("Hata durumundaki ürün sayısı: 0")
        status_info_layout.addWidget(self.selected_info_label)
        status_info_layout.addWidget(self.ready_info_label)
        status_info_layout.addWidget(self.waiting_info_label)
        status_info_layout.addWidget(self.error_info_label)
        root_layout.addLayout(status_info_layout)

        self.all_products = []
        self.editable_product_codes = set()
        self.search_button.clicked.connect(self.run_search_with_feedback)
        self.search_input.returnPressed.connect(self.run_search_with_feedback)
        self.load_button.clicked.connect(self.load_cost_centers_and_categories)
        self.load_products_button.clicked.connect(self.load_products)
        self.transfer_button.clicked.connect(self.transfer_selected_products)
        self.edit_selected_button.clicked.connect(self.enable_selected_rows_editing)
        self.stock_table.itemSelectionChanged.connect(self.update_edit_button_text)
        self.stock_table.itemChanged.connect(self.handle_table_item_changed)
        self.update_edit_button_text()
        
        # self.load_sample_data() # UI ilk açıldığında gösterilen mock (A4 kağıt vb) kapatıldı.

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
                username=logo_settings.get("username", ""),
                password=logo_settings.get("password", ""),
                firm_no=logo_settings.get("firm_no", 1),
                period_no=logo_settings.get("period_no", 1),
                use_mock_data=False,
            )
            reader = ProductReader(config)
            products = reader.read_products()
        except Exception as exc:
            QMessageBox.critical(self, "Logo Hatası", f"Ürünler alınamadı:\n{exc}")
            return

        self.apply_product_data(products)

    def apply_product_data(self, rows):
        self.all_products = [tuple(str(value) if value is not None else "" for value in row) for row in rows]

        try:
            self.stock_table.itemChanged.disconnect(self.handle_table_item_changed)
        except RuntimeError:
            pass
        except TypeError:
            pass

        self.stock_table.setUpdatesEnabled(False)
        self.stock_table.blockSignals(True)
        try:
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

    def load_sample_data(self):
        self.apply_product_data([
            ("STK001", "A4 Kağıt 80gr", "Kırtasiye", "PKT", "250", "250", "%20", "125.00", "TRY", "118.50", "TRY", "Beyaz fotokopi kağıdı", "Hazır"),
            ("STK002", "Mavi Tükenmez Kalem", "Kırtasiye", "ADET", "1200", "1200", "%20", "12.75", "TRY", "11.90", "TRY", "0.7 mm kalem", "Bekliyor"),
            ("STK003", "Lazer Yazıcı Toneri", "Ofis Ekipmanı", "ADET", "45", "45", "%20", "3250.00", "USD", "3100.00", "USD", "Siyah toner kartuşu", "Hata"),
            ("STK004", "Endüstriyel Temizleyici", "Temizlik", "ADET", "80", "80", "%10", "210.00", "TRY", "198.00", "TRY", "Yüzey temizleme ürünü", "Hazır"),
            ("STK005", "Konveyör Rulmanı", "Yedek Parça", "ADET", "18", "18", "%20", "980.00", "EUR", "945.00", "EUR", "Hat bakım yedek parçası", "Bekliyor"),
        ])

    def configure_table_columns(self):
        default_width = 100
        header = self.stock_table.horizontalHeader()

        for column_index in range(self.stock_table.columnCount()):
            header.setSectionResizeMode(column_index, QHeaderView.Interactive)
            self.stock_table.setColumnWidth(column_index, default_width)

        self.stock_table.setColumnWidth(0, 36)

    def normalize_table_row(self, row_data):
        normalized_row = [str(value) if value is not None else "" for value in row_data[:13]]
        while len(normalized_row) < 13:
            normalized_row.append("")
        return tuple(normalized_row)

    def populate_stock_table(self, rows):
        self.stock_table.setRowCount(0)
        for raw_row_data in rows:
            row_data = self.normalize_table_row(raw_row_data)
            product_code = row_data[0].strip()
            is_row_editable = product_code in self.editable_product_codes

            row_index = self.stock_table.rowCount()
            self.stock_table.insertRow(row_index)

            select_item = QTableWidgetItem()
            select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            select_item.setCheckState(Qt.Unchecked)
            select_item.setText("")
            self.stock_table.setItem(row_index, 0, select_item)

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                if col_index == 1:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                elif is_row_editable:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.stock_table.setItem(row_index, col_index, item)

    def get_selected_row_indexes(self):
        return sorted(index.row() for index in self.stock_table.selectionModel().selectedRows())

    def update_edit_button_text(self):
        selected_count = len(self.get_selected_row_indexes())
        if selected_count == 1:
            self.edit_selected_button.setText("Seçili Satırı Düzenle")
        else:
            self.edit_selected_button.setText("Seçili Satırları Düzenle")

    def enable_selected_rows_editing(self):
        selected_rows = self.get_selected_row_indexes()
        if not selected_rows:
            QMessageBox.warning(self, "Satır Seçilmedi", "Önce düzenlemek istediğin satırı veya satırları seç.")
            return

        self.stock_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )

        for row in selected_rows:
            code_item = self.stock_table.item(row, 1)
            product_code = code_item.text().strip() if code_item else ""
            if product_code:
                self.editable_product_codes.add(product_code)

            for col in range(2, self.stock_table.columnCount()):
                item = self.stock_table.item(row, col)
                if item is None:
                    continue
                item.setFlags(item.flags() | Qt.ItemIsEditable)

    def handle_table_item_changed(self, item):
        if item is None:
            return

        if item.column() == 0:
            self.update_selected_count()
            return

        if item.column() == 1:
            return

        code_item = self.stock_table.item(item.row(), 1)
        product_code = code_item.text().strip() if code_item else ""

        if not product_code:
            self.update_selected_count()
            return

        data_index = item.column() - 1

        updated_rows = []
        for row_data in self.all_products:
            normalized_row = list(self.normalize_table_row(row_data))
            if str(normalized_row[0]).strip() == product_code:
                normalized_row[data_index] = item.text().strip()
                updated_rows.append(tuple(normalized_row))
            else:
                updated_rows.append(tuple(normalized_row))

        self.all_products = updated_rows
        self.update_selected_count()

    def filter_products(self, *_args, show_no_results_message=False):
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            filtered_rows = self.all_products
        else:
            filtered_rows = []
            for row in self.all_products:
                product_code = str(row[0]).lower()
                product_name = str(row[1]).lower()
                category = str(row[2]).lower() if len(row) > 2 else ""

                if search_text in product_code or search_text in product_name or search_text in category:
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

        selected_cost_center_erp_id = str(self.source_combo.currentData() or "").strip()
        selected_category = self.target_combo.currentText().strip()

        invalid_category_values = {"", "Kategori yüklenmedi", "Kategori bulunamadı"}

        for row in range(self.stock_table.rowCount()):
            check_item = self.stock_table.item(row, 0)
            if check_item is None or check_item.checkState() != Qt.Checked:
                continue

            product_code_item = self.stock_table.item(row, 1)
            product_name_item = self.stock_table.item(row, 2)
            category_item = self.stock_table.item(row, 3)
            unit_item = self.stock_table.item(row, 4)
            tax_rate_item = self.stock_table.item(row, 7)
            price_item = self.stock_table.item(row, 8)
            currency_item = self.stock_table.item(row, 9)
            description_item = self.stock_table.item(row, 12)

            product_code = product_code_item.text().strip() if product_code_item else ""
            product_name = product_name_item.text().strip() if product_name_item else "-"
            unit_text = unit_item.text().strip() if unit_item else ""

            if not unit_text:
                product_label = product_code or product_name
                invalid_products.append(f"{product_label} -> Eksik alan: Birim")
                continue

            row_category = category_item.text().strip() if category_item else ""
            category_text = selected_category if selected_category not in invalid_category_values else row_category

            cost_center_ids = []
            if selected_cost_center_erp_id:
                cost_center_ids = [selected_cost_center_erp_id]

            product_data = {
                "product_name": product_name,
                "description": description_item.text().strip() if description_item else "",
                "category_text": category_text,
                "erp_id": product_code,
                "unit": unit_text,
                "tax_rate": self.parse_tax_rate(tax_rate_item.text() if tax_rate_item else "0"),
                "price": self.parse_number(price_item.text() if price_item else "0"),
                "currency": currency_item.text().strip() if currency_item else "TRY",
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
        waiting_count = 0
        error_count = 0

        for row in range(self.stock_table.rowCount()):
            status_item = self.stock_table.item(row, 13)
            if status_item is None:
                continue

            status_text = status_item.text().strip().lower()
            if status_text == "hazır":
                ready_count += 1
            elif status_text == "bekliyor":
                waiting_count += 1
            elif status_text == "hata":
                error_count += 1

        self.ready_info_label.setText(f"Hazır durumundaki ürün sayısı: {ready_count}")
        self.waiting_info_label.setText(f"Bekliyor durumundaki ürün sayısı: {waiting_count}")
        self.error_info_label.setText(f"Hata durumundaki ürün sayısı: {error_count}")

