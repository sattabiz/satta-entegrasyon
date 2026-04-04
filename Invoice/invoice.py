import json
from Common.path_helper import user_data_path
from Common.qt_compat import Qt
from Common.qt_compat import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView
)
from Invoice.get_invoice import SattaInvoiceConfig, SattaInvoiceConnector
from Invoice.push_invoice import SattaInvoicePushConnector

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

        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Faturaları Satta'dan Al")
        self.transfer_button = QPushButton(f"Faturaları {connector_display_name}'a Aktar")
        self.edit_invoice_table_checkbox = QCheckBox("Fatura tablosunu düzenlenebilir yap")
        self.edit_invoice_table_checkbox.toggled.connect(self.toggle_invoice_table_edit_mode)
        self.load_button.clicked.connect(self.load_invoices)
        self.transfer_button.clicked.connect(self.transfer_selected_invoices)
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.transfer_button)
        button_layout.addWidget(self.edit_invoice_table_checkbox)
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
        self.invoice_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.invoice_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.invoice_table.setColumnWidth(0, 36)
        self.invoice_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root_layout.addWidget(self.invoice_table)

        self.detail_container = QWidget()
        detail_layout = QVBoxLayout(self.detail_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self.detail_title_label = QLabel("Seçili fatura kalemleri")
        detail_layout.addWidget(self.detail_title_label)

        self.detail_table = QTableWidget(0, 6)
        self.detail_table.setHorizontalHeaderLabels([
            "Ürün Kodu",
            "Ürün Bilgisi",
            "Açıklama",
            "Miktar",
            "Birim",
            "Birim Fiyat",
        ])
        detail_layout.addWidget(self.detail_table)
        self.detail_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail_container.setVisible(True)
        root_layout.addWidget(self.detail_container)

        status_info_layout = QHBoxLayout()

        self.selected_info_label = QLabel("Seçili fatura sayısı: 0")

        status_info_layout.addWidget(self.selected_info_label)

        root_layout.addLayout(status_info_layout)

        self.all_invoices = []
        self.invoice_details = {}
        self.invoice_id_map = {}
        self.invoice_raw_map = {}
        self.search_button.clicked.connect(self.run_search_with_feedback)
        self.search_input.returnPressed.connect(self.run_search_with_feedback)
        self.search_input.textChanged.connect(self.filter_invoices)
        self.invoice_table.itemSelectionChanged.connect(self.load_selected_invoice_details)


    def load_active_connector(self):
        if not RUNTIME_CONFIG_FILE.exists():
            return ""

        try:
            runtime_config = json.loads(RUNTIME_CONFIG_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ""

        return str(runtime_config.get("active_connector", "")).strip().lower()

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

    def load_satta_settings(self):
        if not SETTINGS_FILE.exists():
            return {}

        try:
            settings_data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        return settings_data.get("satta", {})

    def apply_invoice_data(self, invoice_rows, invoice_details, invoice_id_map, invoice_raw_map):
        self.all_invoices = invoice_rows
        self.invoice_details = invoice_details
        self.invoice_id_map = invoice_id_map
        self.invoice_raw_map = invoice_raw_map

        self.populate_invoice_table(self.all_invoices)

        try:
            self.invoice_table.itemChanged.disconnect(self.update_selected_count)
        except RuntimeError:
            pass
        except TypeError:
            pass

        self.invoice_table.itemChanged.connect(self.update_selected_count)
        self.update_status_summary()

        if self.invoice_table.rowCount() > 0:
            self.invoice_table.selectRow(0)
            self.load_selected_invoice_details()
        else:
            self.detail_table.setRowCount(0)
            self.detail_title_label.setText("Seçili fatura kalemleri")

    def load_invoices(self):
        invoice_rows, invoice_details, invoice_id_map, invoice_raw_map = self.fetch_invoices()
        self.apply_invoice_data(invoice_rows, invoice_details, invoice_id_map, invoice_raw_map)

    def populate_invoice_table(self, rows):
        self.invoice_table.setRowCount(0)
        for row_data in rows:
            row_index = self.invoice_table.rowCount()
            self.invoice_table.insertRow(row_index)

            select_item = QTableWidgetItem()
            select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            select_item.setCheckState(Qt.Unchecked)
            select_item.setText("")
            self.invoice_table.setItem(row_index, 0, select_item)

            invoice_no = str(row_data[0]).strip() if row_data else ""
            invoice_id = self.invoice_id_map.get(invoice_no)

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                if col_index == 1:
                    item.setData(Qt.UserRole, invoice_id)
                if not self.edit_invoice_table_checkbox.isChecked() or col_index == 1:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.invoice_table.setItem(row_index, col_index, item)

            invoice_id_text = str(invoice_id) if invoice_id is not None else "-"
            invoice_id_item = QTableWidgetItem(invoice_id_text)
            invoice_id_item.setFlags(invoice_id_item.flags() & ~Qt.ItemIsEditable)
            self.invoice_table.setItem(row_index, 9, invoice_id_item)

    def populate_detail_table(self, invoice_no):
        details = self.invoice_details.get(invoice_no, [])
        self.detail_table.setRowCount(0)

        for row_data in details:
            row_index = self.detail_table.rowCount()
            self.detail_table.insertRow(row_index)
            for col_index, value in enumerate(row_data):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.detail_table.setItem(row_index, col_index, item)

        if details:
            self.detail_title_label.setText(f"Seçili fatura kalemleri: {invoice_no}")
        else:
            self.detail_title_label.setText(f"Seçili fatura kalemleri: {invoice_no} için detay bulunamadı")

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

    def toggle_invoice_table_edit_mode(self, checked):
        if checked:
            self.invoice_table.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.SelectedClicked
            )
        else:
            self.invoice_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        current_rows = []
        for row in range(self.invoice_table.rowCount()):
            row_data = []
            for col in range(1, self.invoice_table.columnCount() - 1):
                item = self.invoice_table.item(row, col)
                row_data.append(item.text() if item else "")
            current_rows.append(tuple(row_data))

        self.populate_invoice_table(current_rows)
        if self.invoice_table.rowCount() > 0:
            self.invoice_table.selectRow(0)
            self.load_selected_invoice_details()

    def filter_invoices(self, *_args, show_no_results_message=False):
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            self.populate_invoice_table(self.all_invoices)
            self.update_status_summary()
            if self.invoice_table.rowCount() > 0:
                self.invoice_table.selectRow(0)
                self.load_selected_invoice_details()
            else:
                self.detail_table.setRowCount(0)
                self.detail_title_label.setText("Seçili fatura kalemleri")
            return

        filtered_rows = []
        for row in self.all_invoices:
            invoice_no = str(row[0]).lower()
            supplier_name = str(row[1]).lower()

            if search_text in invoice_no or search_text in supplier_name:
                filtered_rows.append(row)

        self.populate_invoice_table(filtered_rows)
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

    def build_logo_transfer_payloads(self, selected_raw_invoices):
        logo_settings = self.load_logo_settings()
        payload_builder = LogoPayloadBuilder(logo_settings)
        payloads = []

        for raw_invoice in selected_raw_invoices:
            payloads.append(payload_builder.build_invoice_payload(raw_invoice))

        return payloads

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

        try:
            payloads = self.build_logo_transfer_payloads(selected_raw_invoices)
        except Exception as exc:
            QMessageBox.critical(self, "Payload Hatası", f"Logo aktarım payload'ı hazırlanamadı:\n{exc}")
            return

        bridge_runner = LogoBridgeRunner()
        successful_invoice_ids = []
        failed_results = []

        for invoice_id, invoice_no, payload in zip(selected_invoice_ids, selected_invoice_nos, payloads):
            try:
                bridge_result = bridge_runner.run_invoice_transfer(payload)
            except Exception as exc:
                failed_results.append(f"{invoice_no}: Bridge çalıştırılamadı - {exc}")
                continue

            is_success = bool(bridge_result.get("is_success"))
            message = str(bridge_result.get("message", "")).strip()

            if is_success:
                successful_invoice_ids.append(invoice_id)
            else:
                failed_results.append(f"{invoice_no}: {message or 'Logo aktarımı başarısız.'}")

        if not successful_invoice_ids:
            error_text = "\n".join(failed_results) if failed_results else "Logo'ya aktarılabilecek fatura bulunamadı."
            QMessageBox.critical(self, "Aktarım Hatası", error_text)
            return

        connector = SattaInvoicePushConnector()
        try:
            connector.mark_invoices_saved(successful_invoice_ids)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Satta Güncelleme Hatası",
                f"Logo'ya aktarılan faturalar Satta üzerinde işaretlenemedi:\n{exc}",
            )
            return

        successful_invoice_no_set = {
            invoice_no
            for invoice_id, invoice_no in zip(selected_invoice_ids, selected_invoice_nos)
            if invoice_id in successful_invoice_ids
        }
        self.remove_transferred_invoices_from_ui(list(successful_invoice_no_set))

        success_message = f"{len(successful_invoice_ids)} fatura Logo'ya aktarıldı ve Satta üzerinde işaretlendi."
        if failed_results:
            success_message += "\n\nAktarılamayan faturalar:\n" + "\n".join(failed_results)

        QMessageBox.information(self, "Aktarım Sonucu", success_message)

    def update_selected_count(self):
        selected_count = 0
        for row in range(self.invoice_table.rowCount()):
            item = self.invoice_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected_count += 1

        self.selected_info_label.setText(f"Seçili fatura sayısı: {selected_count}")

    def update_status_summary(self):
        self.update_selected_count()