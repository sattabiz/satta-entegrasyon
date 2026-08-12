import json
from Common.path_helper import user_data_path
from Common.qt_compat import Qt
from Common.qt_compat import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox,
    QTabWidget
)
from Invoice.get_invoice import SattaInvoiceConfig, SattaInvoiceConnector, is_token_expired
from Invoice.push_invoice import SattaInvoicePushConnector
try:
    from PySide6.QtGui import QColor
except ImportError:
    from PySide2.QtGui import QColor
from Invoice.logo_transfer_service import LogoTransferService

SETTINGS_FILE = user_data_path("app_settings.json")

RUNTIME_CONFIG_FILE = user_data_path("runtime_config.json")


CONNECTOR_DISPLAY_NAMES = {
    "logo": "Logo",
    "sap": "SAP",
    "canias": "Canias",
}

class InvoiceTransferTab(QWidget):
    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout(self)

        self.active_connector = self.load_active_connector()
        connector_display_name = self.get_connector_display_name()

        title_label = QLabel(f"Fatura Aktarımı - {connector_display_name}")
        root_layout.addWidget(title_label)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(36)
        self.search_input.setMinimumWidth(320)
        self.search_input.setPlaceholderText("Fatura no veya tedarikçi / cari adı")

        self.search_button = QPushButton("🔍")
        self.search_button.setMinimumHeight(36)
        self.search_button.setMinimumWidth(44)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)

        root_layout.addLayout(search_row)

        options_row = QHBoxLayout()
        warehouse_label = QLabel("Aktarım Ambarı:")
        self.warehouse_dropdown = QComboBox()
        self.warehouse_dropdown.setMinimumHeight(32)
        self.warehouse_dropdown.setMinimumWidth(200)
        self.refresh_warehouses_button = QPushButton("Ambarları Al")
        self.refresh_warehouses_button.setMinimumHeight(32)
        self.refresh_warehouses_button.clicked.connect(self.fetch_and_save_warehouses)
        options_row.addWidget(warehouse_label)
        options_row.addWidget(self.warehouse_dropdown)
        options_row.addWidget(self.refresh_warehouses_button)
        options_row.addStretch()
        root_layout.addLayout(options_row)

        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Faturaları Satta'dan Al")
        self.transfer_button = QPushButton(f"Faturaları {connector_display_name}'a Aktar")
        self.edit_selected_button = QPushButton("Seçili Satırları Düzenle")
        self.load_button.clicked.connect(self.load_invoices)
        self.transfer_button.clicked.connect(self.transfer_selected_invoices)
        self.edit_selected_button.clicked.connect(self.enable_selected_rows_editing)
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.transfer_button)
        button_layout.addWidget(self.edit_selected_button)
        root_layout.addLayout(button_layout)

        self.invoice_table = QTableWidget(0, 10)
        self.invoice_table.setHorizontalHeaderLabels([
            "Seç",
            "Fatura No",
            "Cari",
            "Fatura Tarihi",
            "Ödeme Tarihi",
            "Döviz Cinsi",
            "KDV Hariç Tutar",
            "KDV Dahil Tutar",
            "Toplam Tutar",
            "Invoice ID",
        ])
        self.invoice_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.invoice_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.invoice_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.invoice_table.setColumnWidth(0, 36)
        self.invoice_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root_layout.addWidget(self.invoice_table)

        self.detail_container = QWidget()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        detail_title_row = QHBoxLayout()
        self.detail_title_label = QLabel("Seçili fatura kalemleri")
        self.edit_detail_row_button = QPushButton("Seçili Kalemi Düzenle")
        self.edit_detail_row_button.setMinimumHeight(28)
        self.edit_detail_row_button.clicked.connect(self.enable_detail_row_editing)
        detail_title_row.addWidget(self.detail_title_label)
        detail_title_row.addStretch()
        detail_title_row.addWidget(self.edit_detail_row_button)
        detail_layout.addLayout(detail_title_row)

        self.detail_table = QTableWidget(0, 9)
        self.detail_table.setHorizontalHeaderLabels([
            "Seç",
            "Ürün Kodu",
            "Ürün Bilgisi",
            "Açıklama",
            "Miktar",
            "Birim",
            "Birim Fiyat",
            "Kategori",
            "Kategori ERP Kodu",
        ])
        self.detail_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.detail_table.setColumnWidth(0, 36)
        detail_layout.addWidget(self.detail_table)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_container.setVisible(True)
        root_layout.addWidget(self.detail_container)

        status_info_layout = QHBoxLayout()

        self.selected_info_label = QLabel("Seçili fatura sayısı: 0")

        status_info_layout.addWidget(self.selected_info_label)

        root_layout.addLayout(status_info_layout)

        self.satta_categories = []
        self.all_invoices = []
        self.invoice_details = {}
        self.invoice_id_map = {}
        self.invoice_raw_map = {}
        self.editable_invoice_ids = set()
        self.search_button.clicked.connect(self.run_search_with_feedback)
        self.search_input.returnPressed.connect(self.run_search_with_feedback)
        self.search_input.textChanged.connect(self.filter_invoices)
        self.invoice_table.itemSelectionChanged.connect(self.load_selected_invoice_details)
        self.invoice_table.itemSelectionChanged.connect(self.update_edit_button_text)
        self.invoice_table.itemChanged.connect(self.handle_table_item_changed)
        self.detail_table.itemChanged.connect(self.handle_detail_item_changed)
        self.update_edit_button_text()

        self.load_cached_warehouses()
        self.select_saved_warehouse()
        self.warehouse_dropdown.currentIndexChanged.connect(self.save_selected_warehouse)


    def load_active_connector(self):
        try:
            from main import load_runtime_config
            runtime_config = load_runtime_config()
            return str(runtime_config.get("active_connector", "logo")).strip().lower()
        except Exception:
            return "logo"

    def get_connector_display_name(self):
        return CONNECTOR_DISPLAY_NAMES.get(self.active_connector, "Hedef Sistem")

    def run_search_with_feedback(self):
        self.filter_invoices(show_no_results_message=True)

    def fetch_invoices(self):
        satta_settings = self.load_satta_settings()

        connector = SattaInvoiceConnector(
            SattaInvoiceConfig(
                use_mock_data=False,
                base_url=satta_settings.get("base_url", "https://test.satta.biz"),
                username=satta_settings.get("username", ""),
                password=satta_settings.get("password", ""),
                token=satta_settings.get("token", ""),
            )
        )
        return connector.get_invoices_for_ui()

    def fetch_categories(self):
        satta_settings = self.load_satta_settings()

        connector = SattaInvoiceConnector(
            SattaInvoiceConfig(
                use_mock_data=False,
                base_url=satta_settings.get("base_url", "https://test.satta.biz"),
                username=satta_settings.get("username", ""),
                password=satta_settings.get("password", ""),
                token=satta_settings.get("token", ""),
            )
        )
        try:
            return connector.get_categories()
        except Exception as exc:
            print(f"Kategoriler yüklenemedi: {exc}")
            return []

    def load_satta_settings(self):
        if not SETTINGS_FILE.exists():
            return {}

        try:
            settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        return settings_data.get("satta", {})

    def load_logo_settings(self):
        if not SETTINGS_FILE.exists():
            return {}

        try:
            settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        return settings_data.get("logo", {})

    def load_cached_warehouses(self):
        self.warehouse_dropdown.clear()
        logo_settings = self.load_logo_settings()
        
        server = str(logo_settings.get("server", "")).strip()
        database = str(logo_settings.get("database", "")).strip()
        firm_no = int(logo_settings.get("firm_no", 1))
        
        cached_config = logo_settings.get("warehouses_connection_config", {})
        cached_server = str(cached_config.get("server", "")).strip()
        cached_database = str(cached_config.get("database", "")).strip()
        cached_firm_no = int(cached_config.get("firm_no", 0))
        
        settings_match = (
            server == cached_server and 
            database == cached_database and 
            firm_no == cached_firm_no and 
            bool(server)
        )
        
        cached_list = logo_settings.get("warehouses_list")
        if settings_match and cached_list and isinstance(cached_list, list):
            for item in cached_list:
                if isinstance(item, dict):
                    nr = item.get("nr")
                    name = item.get("name", "")
                    if nr is not None:
                        self.warehouse_dropdown.addItem(f"{nr:03d}, {name}", nr)
            self.refresh_warehouses_button.setVisible(False)
        else:
            self.refresh_warehouses_button.setVisible(True)
        
        if self.warehouse_dropdown.count() == 0:
            self.warehouse_dropdown.addItem("Ambar Seçiniz", None)

    def fetch_and_save_warehouses(self):
        logo_settings = self.load_logo_settings()
        server = str(logo_settings.get("server", "")).strip()
        database = str(logo_settings.get("database", "")).strip()
        db_username = str(logo_settings.get("db_username", "")).strip()
        db_password = str(logo_settings.get("db_password", ""))
        firm_no = int(logo_settings.get("firm_no", 1))

        if not server or not database:
            QMessageBox.warning(
                self,
                "Bağlantı Ayarı Eksik",
                "Logo veritabanı bağlantı ayarları eksik. Lütfen önce Ayarlar sekmesinden bağlantı bilgilerini doldurun."
            )
            return

        if db_username:
            conn_str = (
                f"DRIVER={{SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={db_username};"
                f"PWD={db_password};"
            )
        else:
            conn_str = (
                f"DRIVER={{SQL Server}};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"Trusted_Connection=yes;"
            )

        import pyodbc
        query = "SELECT NR, NAME FROM L_CAPIWHOUSE WHERE FIRMNR = ? ORDER BY NR"
        
        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(query, (firm_no,))
                rows = cursor.fetchall()
                
                if not rows:
                    QMessageBox.information(
                        self,
                        "Ambar Bulunamadı",
                        f"Logo veritabanında {firm_no} numaralı firma için ambar tanımı bulunamadı."
                    )
                    return
                
                try:
                    self.warehouse_dropdown.currentIndexChanged.disconnect(self.save_selected_warehouse)
                except (TypeError, RuntimeError):
                    pass

                self.warehouse_dropdown.clear()
                warehouses_list = []
                for row in rows:
                    nr = int(row[0])
                    name = str(row[1]).strip()
                    self.warehouse_dropdown.addItem(f"{nr:03d}, {name}", nr)
                    warehouses_list.append({"nr": nr, "name": name})
                
                connection_config = {
                    "server": server,
                    "database": database,
                    "firm_no": firm_no
                }
                self.save_warehouses_list_to_settings(warehouses_list, connection_config)
                self.warehouse_dropdown.setCurrentIndex(0)
                
                self.warehouse_dropdown.currentIndexChanged.connect(self.save_selected_warehouse)
                self.save_selected_warehouse()

                self.refresh_warehouses_button.setVisible(False)

                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"Logo üzerinden {len(warehouses_list)} adet ambar bilgisi başarıyla çekildi ve güncellendi."
                )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Ambar Bilgisi Alınamadı",
                f"Logo ambar bilgileri veri tabanından yüklenirken bir hata oluştu:\n{exc}"
            )

    def save_warehouses_list_to_settings(self, warehouses_list, connection_config):
        try:
            settings_data = {}
            if SETTINGS_FILE.exists():
                settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            
            if "logo" not in settings_data:
                settings_data["logo"] = {}
                
            settings_data["logo"]["warehouses_list"] = warehouses_list
            settings_data["logo"]["warehouses_connection_config"] = connection_config
            
            from Common.path_helper import ensure_parent_directory
            ensure_parent_directory(SETTINGS_FILE)
            SETTINGS_FILE.write_text(json.dumps(settings_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def select_saved_warehouse(self):
        logo_settings = self.load_logo_settings()
        saved_wh = logo_settings.get("last_selected_warehouse")
        if saved_wh is not None:
            try:
                target_wh = int(saved_wh)
                for idx in range(self.warehouse_dropdown.count()):
                    item_val = self.warehouse_dropdown.itemData(idx)
                    if item_val is not None and int(item_val) == target_wh:
                        self.warehouse_dropdown.setCurrentIndex(idx)
                        break
            except (ValueError, TypeError):
                pass

    def save_selected_warehouse(self):
        if self.warehouse_dropdown.count() == 0:
            return
        
        current_data = self.warehouse_dropdown.currentData()
        if current_data is None:
            return
            
        selected_wh = int(current_data)
        
        try:
            settings_data = {}
            if SETTINGS_FILE.exists():
                settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            
            if "logo" not in settings_data:
                settings_data["logo"] = {}
                
            settings_data["logo"]["last_selected_warehouse"] = selected_wh
            
            from Common.path_helper import ensure_parent_directory
            ensure_parent_directory(SETTINGS_FILE)
            SETTINGS_FILE.write_text(json.dumps(settings_data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def apply_invoice_data(self, invoice_rows, invoice_details, invoice_id_map, invoice_raw_map):
        self.all_invoices = [tuple(str(value) if value is not None else "" for value in row) for row in invoice_rows]
        self.invoice_details = invoice_details
        self.invoice_id_map = invoice_id_map
        self.invoice_raw_map = invoice_raw_map

        try:
            self.invoice_table.itemChanged.disconnect(self.handle_table_item_changed)
        except RuntimeError:
            pass
        except TypeError:
            pass

        self.invoice_table.setUpdatesEnabled(False)
        self.invoice_table.blockSignals(True)
        try:
            self.populate_invoice_table(self.all_invoices)
        finally:
            self.invoice_table.blockSignals(False)
            self.invoice_table.setUpdatesEnabled(True)

        self.invoice_table.itemChanged.connect(self.handle_table_item_changed)
        self.update_status_summary()
        self.update_edit_button_text()
        self.load_button.setText("Faturaları Yenile")

        if self.invoice_table.rowCount() > 0:
            self.invoice_table.selectRow(0)
            self.load_selected_invoice_details()
        else:
            self.detail_table.setRowCount(0)
            self.detail_title_label.setText("Seçili fatura kalemleri")

    def load_invoices(self):
        try:
            self.satta_categories = self.fetch_categories()
            invoice_rows, invoice_details, invoice_id_map, invoice_raw_map = self.fetch_invoices()
            self.apply_invoice_data(invoice_rows, invoice_details, invoice_id_map, invoice_raw_map)
        except Exception as exc:
            satta_settings = self.load_satta_settings()
            token = satta_settings.get("token", "")
            username = satta_settings.get("username", "")
            password = satta_settings.get("password", "")

            is_cred_empty = not username or not password

            if is_cred_empty:
                msg = (
                    "Satta e-posta veya şifresi Ayarlar sekmesinde girilmemiş.\n\n"
                )
            elif not token or is_token_expired(token):
                msg = (
                    "Satta oturum süreniz dolmuş veya token bulunamadı. Oturumunuzu yenileyiniz.\n\n"
                )
            else:
                msg = (
                    f"Satta faturaları alınırken bir hata oluştu:\n{exc}\n\n"
                )

            reply = QMessageBox.warning(
                self,
                "Satta Bağlantı Hatası",
                msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.Yes:
                self.switch_to_settings_tab()

    def switch_to_settings_tab(self):
        parent = self.parentWidget()
        while parent is not None:
            if isinstance(parent, QTabWidget):
                for i in range(parent.count()):
                    if parent.tabText(i) == "Ayarlar":
                        parent.setCurrentIndex(i)
                        break
                break
            parent = parent.parentWidget()

    def populate_invoice_table(self, rows):
        self.invoice_table.setRowCount(0)
        for raw_row_data in rows:
            row_data = self.normalize_table_row(raw_row_data)
            row_index = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row_index)

            select_item = QTableWidgetItem()
            select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            select_item.setCheckState(Qt.Unchecked)
            select_item.setText("")
            self.invoice_table.setItem(row_index, 0, select_item)

            invoice_no = str(row_data[0]).strip() if row_data else ""
            invoice_id = self.invoice_id_map.get(invoice_no)
            is_row_editable = invoice_id in self.editable_invoice_ids if invoice_id is not None else False

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                if col_index == 1:
                    item.setData(Qt.UserRole, invoice_id)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                elif is_row_editable:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.invoice_table.setItem(row_index, col_index, item)

            invoice_id_text = str(invoice_id) if invoice_id is not None else "-"
            invoice_id_item = QTableWidgetItem(invoice_id_text)
            invoice_id_item.setFlags(invoice_id_item.flags() & ~Qt.ItemIsEditable)
            self.invoice_table.setItem(row_index, 9, invoice_id_item)

    def normalize_table_row(self, row_data):
        normalized_row = [str(value) if value is not None else "" for value in row_data[:8]]
        while len(normalized_row) < 8:
            normalized_row.append("")
        return tuple(normalized_row)

    def get_selected_row_indexes(self):
        selection_model = self.invoice_table.selectionModel()
        if selection_model is None:
            return []
        return sorted(index.row() for index in selection_model.selectedRows())

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

        self.invoice_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )

        for row in selected_rows:
            invoice_no_item = self.invoice_table.item(row, 1)
            invoice_id = invoice_no_item.data(Qt.UserRole) if invoice_no_item is not None else None
            if invoice_id is not None:
                self.editable_invoice_ids.add(invoice_id)

            for col in range(2, 9):
                item = self.invoice_table.item(row, col)
                if item is None:
                    continue
                item.setFlags(item.flags() | Qt.ItemIsEditable)

        # Enable category dropdowns for currently displayed detail table if it belongs to an edited invoice
        current_invoice_row = self.invoice_table.currentRow()
        if current_invoice_row in selected_rows:
            self.detail_table.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.SelectedClicked
            )
            for row in range(self.detail_table.rowCount()):
                combo = self.detail_table.cellWidget(row, 7)
                if isinstance(combo, QComboBox):
                    combo.setEnabled(True)
                unit_item = self.detail_table.item(row, 5)
                if unit_item:
                    unit_item.setFlags(unit_item.flags() | Qt.ItemIsEditable)
                    unit_item.setBackground(QColor("#fffbe6"))

    def enable_detail_row_editing(self):
        current_invoice_row = self.invoice_table.currentRow()
        if current_invoice_row < 0:
            QMessageBox.warning(self, "Fatura Seçilmedi", "Önce fatura listesinden düzenlemek istediğiniz faturayı seçin.")
            return

        # Find which detail rows are checked in column 0
        checked_rows = []
        for row in range(self.detail_table.rowCount()):
            item = self.detail_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                checked_rows.append(row)

        if not checked_rows:
            QMessageBox.warning(
                self, 
                "Kalem Seçilmedi", 
                "Önce detay tablosundan düzenlemek istediğiniz kalemi (satırı) sol taraftaki kutucuktan seçin."
            )
            return

        invoice_no_item = self.invoice_table.item(current_invoice_row, 1)
        invoice_id = invoice_no_item.data(Qt.UserRole) if invoice_no_item is not None else None
        if invoice_id is None:
            invoice_no = invoice_no_item.text().strip() if invoice_no_item else ""
            invoice_id = self.invoice_id_map.get(invoice_no)

        if invoice_id is not None:
            self.editable_invoice_ids.add(invoice_id)

        self.detail_table.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.EditKeyPressed
            | QAbstractItemView.SelectedClicked
        )

        for row in checked_rows:
            combo = self.detail_table.cellWidget(row, 7)
            if isinstance(combo, QComboBox):
                combo.setEnabled(True)
            unit_item = self.detail_table.item(row, 5)
            if unit_item:
                unit_item.setFlags(unit_item.flags() | Qt.ItemIsEditable)
                unit_item.setBackground(QColor("#fffbe6"))

    def handle_table_item_changed(self, item):
        if item is None:
            return

        if item.column() == 0:
            self.update_selected_count()
            return

        if item.column() in (1, 9):
            return

        invoice_no_item = self.invoice_table.item(item.row(), 1)
        invoice_id = invoice_no_item.data(Qt.UserRole) if invoice_no_item is not None else None
        if invoice_id is None:
            self.update_selected_count()
            return

        invoice_no = invoice_no_item.text().strip() if invoice_no_item else ""
        data_index = item.column() - 1

        updated_rows = []
        for row_data in self.all_invoices:
            normalized_row = list(self.normalize_table_row(row_data))
            current_invoice_no = str(normalized_row[0]).strip()
            current_invoice_id = self.invoice_id_map.get(current_invoice_no)

            if current_invoice_id == invoice_id or (invoice_no and current_invoice_no == invoice_no):
                normalized_row[data_index] = item.text().strip()
                updated_rows.append(tuple(normalized_row))
            else:
                updated_rows.append(tuple(normalized_row))

        self.all_invoices = updated_rows
        self.update_selected_count()

    def populate_detail_table(self, invoice_no):
        self.detail_table.setRowCount(0)
        invoice_id = self.invoice_id_map.get(invoice_no)
        raw_invoice = self.invoice_raw_map.get(invoice_id) if invoice_id is not None else None
        
        if not raw_invoice or not isinstance(raw_invoice, dict):
            details = self.invoice_details.get(invoice_no, [])
            for row_data in details:
                row_index = self.detail_table.rowCount()
                self.detail_table.insertRow(row_index)
                
                # Checkbox at column 0
                select_item = QTableWidgetItem()
                select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                select_item.setCheckState(Qt.Unchecked)
                select_item.setText("")
                self.detail_table.setItem(row_index, 0, select_item)

                for col_index, value in enumerate(row_data, start=1):
                    item = QTableWidgetItem(value)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.detail_table.setItem(row_index, col_index, item)
            self.detail_title_label.setText(f"Seçili fatura kalemleri: {invoice_no} (Detaylar sınırlı)")
            return

        products = raw_invoice.get("products") or []
        self.detail_title_label.setText(f"Seçili fatura kalemleri: {invoice_no}")

        self.detail_table.blockSignals(True)
        try:
            for p_idx, product in enumerate(products):
                if not isinstance(product, dict):
                    continue

                product_code = self._safe_text(product.get("company_product_erp_code"))
                if not product_code:
                    product_code = self._safe_text(product.get("product_erp_id"))
                if not product_code:
                    product_code = self._safe_text(product.get("products_proposal_id"), "-")

                product_name = self._safe_text(product.get("name"), "-")
                description = self._safe_text(product.get("description"))
                if not description:
                    description = self._safe_text(product.get("proposal_note"))
                if not description:
                    description = "-"

                unit = self._safe_text(product.get("unit"), "-")
                shipped_amount = self._format_quantity(product.get("shipped_amount"))
                price = self._format_money(product.get("price"))

                row_index = self.detail_table.rowCount()
                self.detail_table.insertRow(row_index)

                # Checkbox at column 0
                select_item = QTableWidgetItem()
                select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                select_item.setCheckState(Qt.Unchecked)
                select_item.setText("")
                self.detail_table.setItem(row_index, 0, select_item)

                # Product info in columns 1 to 6
                cols = [product_code, product_name, description, shipped_amount, unit, price]
                for col_index, val in enumerate(cols, start=1):
                    item = QTableWidgetItem(val)
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    self.detail_table.setItem(row_index, col_index, item)

                # Column 7: Category (QComboBox)
                category_combo = QComboBox()
                category_combo.setMinimumHeight(28)
                category_combo.addItem("Seçiniz...", None)
                
                curr_cat_id = product.get("category_id")
                curr_cat_erp_code = product.get("category_erp_code")
                curr_cat_erp_id = product.get("category_erp_id")
                
                selected_idx = 0
                for cat_idx, cat in enumerate(self.satta_categories, start=1):
                    cat_name = cat.get('name')
                    category_combo.addItem(cat_name, cat)
                    
                    is_match = False
                    if curr_cat_id is not None and cat.get("id") == curr_cat_id:
                        is_match = True
                    elif curr_cat_erp_code and cat.get("category_erp_code") == curr_cat_erp_code:
                        is_match = True
                    elif curr_cat_erp_id and cat.get("category_erp_code") == curr_cat_erp_id:
                        is_match = True
                        
                    if is_match:
                        selected_idx = cat_idx

                category_combo.setCurrentIndex(selected_idx)
                
                is_editable = (invoice_id in self.editable_invoice_ids)
                category_combo.setEnabled(is_editable)

                # Connect lambda with parameters to ensure we identify the changed line correctly
                category_combo.currentIndexChanged.connect(
                    lambda idx, inv_id=invoice_id, p_idx=p_idx, combo=category_combo: 
                    self.handle_line_category_changed(inv_id, p_idx, combo)
                )

                self.detail_table.setCellWidget(row_index, 7, category_combo)

                # Column 8: Category ERP Code
                current_erp_code = ""
                if selected_idx > 0:
                    current_erp_code = self.satta_categories[selected_idx - 1].get("category_erp_code", "")
                else:
                    current_erp_code = curr_cat_erp_code or curr_cat_erp_id or ""

                erp_item = QTableWidgetItem(str(current_erp_code))
                erp_item.setFlags(erp_item.flags() & ~Qt.ItemIsEditable)
                self.detail_table.setItem(row_index, 8, erp_item)

        finally:
            self.detail_table.blockSignals(False)

    def load_selected_invoice_details(self):
        current_row = self.invoice_table.currentRow()
        if current_row < 0:
            self.detail_table.setRowCount(0)
            self.detail_title_label.setText("Seçili fatura kalemleri")
            return

        invoice_no_item = self.invoice_table.item(current_row, 1)
        if invoice_no_item is None:
            return

        invoice_no = invoice_no_item.text().strip()
        self.populate_detail_table(invoice_no)


    def filter_invoices(self, *_args, show_no_results_message=False):
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            filtered_rows = self.all_invoices
        else:
            filtered_rows = []
            for row in self.all_invoices:
                invoice_no = str(row[0]).lower()
                supplier_name = str(row[1]).lower() if len(row) > 1 else ""

                if search_text in invoice_no or search_text in supplier_name:
                    filtered_rows.append(row)

        self.invoice_table.setUpdatesEnabled(False)
        self.invoice_table.blockSignals(True)
        try:
            self.populate_invoice_table(filtered_rows)
        finally:
            self.invoice_table.blockSignals(False)
            self.invoice_table.setUpdatesEnabled(True)

        self.update_status_summary()

        if self.invoice_table.rowCount() > 0:
            self.invoice_table.selectRow(0)
            self.load_selected_invoice_details()
        else:
            self.detail_table.setRowCount(0)
            self.detail_title_label.setText("Seçili fatura kalemleri")

        if not filtered_rows and show_no_results_message:
            QMessageBox.information(self, "Arama Sonucu", "Aramaya uygun fatura bulunamadı.")

    def get_selected_invoice_ids(self):
        selected_invoice_ids = []

        for row in range(self.invoice_table.rowCount()):
            check_item = self.invoice_table.item(row, 0)
            invoice_no_item = self.invoice_table.item(row, 1)

            if check_item is None or invoice_no_item is None:
                continue

            if check_item.checkState() != Qt.Checked:
                continue

            invoice_id = invoice_no_item.data(Qt.UserRole)
            if invoice_id is None:
                invoice_no = invoice_no_item.text().strip()
                invoice_id = self.invoice_id_map.get(invoice_no)

            if invoice_id is not None:
                selected_invoice_ids.append(invoice_id)

        return selected_invoice_ids

    def get_selected_invoice_nos(self):
        selected_invoice_nos = []

        for row in range(self.invoice_table.rowCount()):
            check_item = self.invoice_table.item(row, 0)
            invoice_no_item = self.invoice_table.item(row, 1)

            if check_item is None or invoice_no_item is None:
                continue

            if check_item.checkState() != Qt.Checked:
                continue

            invoice_no = invoice_no_item.text().strip()
            if invoice_no:
                selected_invoice_nos.append(invoice_no)

        return selected_invoice_nos

    def get_selected_raw_invoices(self):
        selected_raw_invoices = []

        for invoice_id in self.get_selected_invoice_ids():
            raw_invoice = self.invoice_raw_map.get(invoice_id)
            if isinstance(raw_invoice, dict):
                selected_raw_invoices.append(raw_invoice)

        return selected_raw_invoices


    def remove_transferred_invoices_from_ui(self, selected_invoice_nos):
        selected_invoice_no_set = {invoice_no.strip() for invoice_no in selected_invoice_nos if str(invoice_no).strip()}
        if not selected_invoice_no_set:
            return

        self.all_invoices = [
            row for row in self.all_invoices
            if str(row[0]).strip() not in selected_invoice_no_set
        ]

        removed_invoice_ids = []

        for invoice_no in selected_invoice_no_set:
            self.invoice_details.pop(invoice_no, None)
            invoice_id = self.invoice_id_map.pop(invoice_no, None)
            if invoice_id is not None:
                removed_invoice_ids.append(invoice_id)

        for invoice_id in removed_invoice_ids:
            self.invoice_raw_map.pop(invoice_id, None)

        self.populate_invoice_table(self.all_invoices)
        self.update_status_summary()

        if self.invoice_table.rowCount() > 0:
            self.invoice_table.selectRow(0)
            self.load_selected_invoice_details()
        else:
            self.detail_table.setRowCount(0)
            self.detail_title_label.setText("Seçili fatura kalemleri")

    def transfer_selected_invoices(self):
        selected_invoice_ids = self.get_selected_invoice_ids()
        selected_invoice_nos = self.get_selected_invoice_nos()
        selected_raw_invoices = self.get_selected_raw_invoices()

        if not selected_invoice_ids:
            QMessageBox.warning(self, "Seçim Yok", "Önce aktarılacak faturaları seç.")
            return

        if len(selected_raw_invoices) != len(selected_invoice_ids):
            QMessageBox.critical(
                self,
                "Aktarım Hatası",
                "Seçili faturaların ham verileri eksik. Faturaları yeniden yükleyip tekrar dene.",
            )
            return

        if self.active_connector != "logo":
            connector_display_name = self.get_connector_display_name()
            QMessageBox.information(
                self,
                "Bilgi",
                f"Bridge aktarımı şu an yalnızca Logo için hazır. Aktif connector: {connector_display_name}",
            )
            return

        logo_settings = self.load_logo_settings()
        selected_wh_data = self.warehouse_dropdown.currentData()
        if selected_wh_data is None:
            QMessageBox.warning(
                self,
                "Ambar Seçilmedi",
                "Lütfen faturayı aktarmadan önce listeden geçerli bir ambar seçin.\n"
                "Eğer ambar listesi boşsa, önce ambarları güncellemek için 'Ambarları Al' butonuna tıklayın."
            )
            return
            
        logo_settings["warehouse_nr"] = int(selected_wh_data)
        logo_settings["source_index"] = int(selected_wh_data)

        transfer_service = LogoTransferService(logo_settings)

        try:
            transfer_result = transfer_service.transfer_invoices(selected_raw_invoices)
        except Exception as exc:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Aktarım Hatası")
            msg_box.setText(f"<b>Logo aktarım servisi çalıştırılamadı:</b><br>{exc}")
            msg_box.exec()
            return

        successful_invoices = transfer_result.get("successful_invoices", [])
        failed_results = list(transfer_result.get("failed_results", []))

        satta_marked_nos = []
        connector = SattaInvoicePushConnector()

        for item in successful_invoices:
            inv_id = item.get("id")
            inv_no = item.get("no")
            if inv_id is None:
                failed_results.append(f"{inv_no}: Logo'ya aktarıldı fakat Satta invoice_id eksik.")
                continue
            try:
                connector.mark_invoice_saved(inv_id)
                satta_marked_nos.append(inv_no)
            except Exception as exc:
                failed_results.append(f"{inv_no}: Logo'ya aktarıldı fakat Satta üzerinde işaretlenemedi - {exc}")

        if satta_marked_nos:
            self.remove_transferred_invoices_from_ui(satta_marked_nos)

        self._show_transfer_result_dialog(
            success_count=len(satta_marked_nos),
            failed_results=failed_results
        )

    def _show_transfer_result_dialog(self, success_count: int, failed_results: list):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Fatura Aktarım Sonucu")

        if success_count > 0 and not failed_results:
            msg_box.setIcon(QMessageBox.Information)
        elif success_count > 0 and failed_results:
            msg_box.setIcon(QMessageBox.Warning)
        else:
            msg_box.setIcon(QMessageBox.Critical)

        html_parts = []

        if success_count > 0:
            html_parts.append(
                f"<div style='color: #2e7d32; font-size: 13px; font-weight: bold; margin-bottom: 8px;'>"
                f"✓ {success_count} adet fatura başarıyla Logo'ya aktarıldı ve Satta üzerinde işaretlendi."
                f"</div>"
            )

        if failed_results:
            html_parts.append(
                f"<div style='color: #c62828; font-size: 13px; font-weight: bold; margin-top: 10px; margin-bottom: 6px;'>"
                f"⚠️ Aktarılamayan / İşaretlenemeyen Faturalar ({len(failed_results)}):"
                f"</div>"
            )
            html_parts.append("<ul style='margin-top: 4px; margin-bottom: 8px; padding-left: 20px;'>")
            for item in failed_results:
                safe_item = item.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if ":" in safe_item:
                    no_part, err_part = safe_item.split(":", 1)
                    html_parts.append(
                        f"<li style='margin-bottom: 4px;'><b>{no_part.strip()}:</b> "
                        f"<span style='color: #444;'>{err_part.strip()}</span></li>"
                    )
                else:
                    html_parts.append(f"<li style='margin-bottom: 4px;'>{safe_item}</li>")
            html_parts.append("</ul>")
            html_parts.append(
                "<div style='color: #666; font-size: 11px; font-style: italic; margin-top: 6px;'>"
                "Not: Hatalı faturalar listede kalmıştır. Sorunları giderdikten sonra tekrar aktarabilirsiniz."
                "</div>"
            )

        msg_box.setText("".join(html_parts))
        msg_box.setTextFormat(Qt.RichText)
        msg_box.exec()

    def update_selected_count(self):
        selected_count = 0
        for row in range(self.invoice_table.rowCount()):
            item = self.invoice_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected_count += 1

        self.selected_info_label.setText(f"Seçili fatura sayısı: {selected_count}")

    def update_status_summary(self):
        self.update_selected_count()

    def showEvent(self, event):
        super().showEvent(event)
        try:
            self.warehouse_dropdown.currentIndexChanged.disconnect(self.save_selected_warehouse)
        except (TypeError, RuntimeError):
            pass
            
        self.load_cached_warehouses()
        self.select_saved_warehouse()
        self.warehouse_dropdown.currentIndexChanged.connect(self.save_selected_warehouse)

    def handle_line_category_changed(self, invoice_id, product_index, combo_widget):
        cat_data = combo_widget.currentData()
        
        # 1. Update the row cells in detail_table
        target_row = -1
        for row in range(self.detail_table.rowCount()):
            if self.detail_table.cellWidget(row, 7) == combo_widget:
                target_row = row
                break

        if target_row == -1:
            return

        new_erp_code = ""
        new_category_id = None
        new_category_type = "item"

        if isinstance(cat_data, dict):
            new_erp_code = str(cat_data.get("category_erp_code", "")).strip()
            new_category_id = cat_data.get("id")
            new_category_type = str(cat_data.get("category_type", "item")).strip()

        # Update ERP code cell text (read-only) in column 8
        erp_item = self.detail_table.item(target_row, 8)
        if erp_item:
            erp_item.setText(new_erp_code)

        # 2. Update the cache: self.invoice_raw_map
        raw_invoice = self.invoice_raw_map.get(invoice_id)
        if not raw_invoice or not isinstance(raw_invoice, dict):
            return

        products = raw_invoice.get("products") or []
        if product_index < 0 or product_index >= len(products):
            return

        product = products[product_index]
        if not isinstance(product, dict):
            return

        # Update category mapping fields in the raw data
        product["category_id"] = new_category_id
        product["category_erp_id"] = new_erp_code
        product["category_erp_code"] = new_erp_code
        product["category_type"] = new_category_type
        product["category_manually_changed"] = True

    def handle_detail_item_changed(self, item):
        if item is None:
            return

        # Check if the edited column is "Birim" (column 5)
        if item.column() != 5:
            return

        current_invoice_row = self.invoice_table.currentRow()
        if current_invoice_row < 0:
            return

        invoice_no_item = self.invoice_table.item(current_invoice_row, 1)
        if not invoice_no_item:
            return

        invoice_no = invoice_no_item.text().strip()
        invoice_id = self.invoice_id_map.get(invoice_no)
        if invoice_id is None:
            return

        raw_invoice = self.invoice_raw_map.get(invoice_id)
        if not raw_invoice or not isinstance(raw_invoice, dict):
            return

        products = raw_invoice.get("products") or []
        product_index = item.row()
        if product_index < 0 or product_index >= len(products):
            return

        product = products[product_index]
        if isinstance(product, dict):
            product["unit"] = item.text().strip()

    def _format_money(self, value):
        if value is None:
            return "0.00"
        amount = self._to_float(value)
        return f"{amount:.2f}"

    def _format_quantity(self, value):
        if value is None:
            return "0"
        amount = self._to_float(value)
        return f"{amount:.2f}".rstrip("0").rstrip(".")

    def _to_float(self, value):
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_text(value, default=""):
        if value is None:
            return default
        text = str(value).strip()
        if not text:
            return default
        return text