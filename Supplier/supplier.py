from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from Connectors.logo_connector import LogoConnectionConfig, LogoConnector
from Supplier.push_suppliers import SattaSupplierPushConnector


class SupplierSendTab(QWidget):
    def __init__(self):
        super().__init__()

        root_layout = QVBoxLayout(self)

        title_label = QLabel("Tedarikçi Gönderim Ekranı")
        root_layout.addWidget(title_label)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(36)
        self.search_input.setMinimumWidth(320)
        self.search_input.setPlaceholderText("Tedarikçi kodu veya adı")

        self.search_button = QPushButton("🔍")
        self.search_button.setMinimumHeight(36)
        self.search_button.setMinimumWidth(44)

        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_button)

        root_layout.addLayout(search_row)

        button_layout = QHBoxLayout()
        self.load_button = QPushButton("Tedarikçileri Al")
        self.send_button = QPushButton("Seçili Tedarikçileri Satta'ya Gönder")
        self.edit_table_checkbox = QCheckBox("Tabloyu düzenlenebilir yap")
        self.edit_table_checkbox.toggled.connect(self.toggle_table_edit_mode)
        self.load_button.clicked.connect(self.load_suppliers)
        self.send_button.clicked.connect(self.send_selected_suppliers)
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.edit_table_checkbox)
        root_layout.addLayout(button_layout)

        self.supplier_table = QTableWidget(0, 7)
        self.supplier_table.setHorizontalHeaderLabels([
            "Seç",
            "Kod",
            "Tedarikçi Adı",
            "İlgili Kişi",
            "Telefon Numarası",
            "E-posta Adresi",
            "Vergi No",
        ])
        self.supplier_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        supplier_header = self.supplier_table.horizontalHeader()
        supplier_header.setSectionResizeMode(QHeaderView.Interactive)

        self.supplier_table.setColumnWidth(0, 44)
        self.supplier_table.setColumnWidth(1, 110)
        self.supplier_table.setColumnWidth(2, 220)
        self.supplier_table.setColumnWidth(3, 160)
        self.supplier_table.setColumnWidth(4, 140)
        self.supplier_table.setColumnWidth(5, 220)
        self.supplier_table.setColumnWidth(6, 130)
        self.supplier_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        root_layout.addWidget(self.supplier_table)

        status_info_layout = QHBoxLayout()

        self.selected_info_label = QLabel("Seçili tedarikçi sayısı: 0")

        status_info_layout.addWidget(self.selected_info_label)

        root_layout.addLayout(status_info_layout)

        self.all_suppliers = []
        self.search_button.clicked.connect(self.filter_suppliers)
        self.search_input.returnPressed.connect(self.filter_suppliers)
        self.search_input.textChanged.connect(self.filter_suppliers)
        self.load_suppliers()

    def fetch_suppliers(self):
        connector = LogoConnector(
            LogoConnectionConfig(
                use_mock_data=True,
            )
        )
        return [row[:6] for row in connector.get_suppliers_for_ui()]

    def apply_supplier_data(self, rows):
        self.all_suppliers = rows
        self.populate_supplier_table(self.all_suppliers)

        try:
            self.supplier_table.itemChanged.disconnect(self.update_selected_count)
        except RuntimeError:
            pass
        except TypeError:
            pass

        self.supplier_table.itemChanged.connect(self.update_selected_count)
        self.update_status_summary()

        if self.supplier_table.rowCount() > 0:
            self.supplier_table.selectRow(0)

    def load_suppliers(self):
        supplier_rows = self.fetch_suppliers()
        self.apply_supplier_data(supplier_rows)

    def populate_supplier_table(self, rows):
        self.supplier_table.setRowCount(0)
        for row_data in rows:
            row_index = self.supplier_table.rowCount()
            self.supplier_table.insertRow(row_index)

            select_item = QTableWidgetItem()
            select_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            select_item.setCheckState(Qt.Unchecked)
            select_item.setText("")
            self.supplier_table.setItem(row_index, 0, select_item)

            for col_index, value in enumerate(row_data, start=1):
                item = QTableWidgetItem(value)
                if not self.edit_table_checkbox.isChecked() or col_index == 1:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.supplier_table.setItem(row_index, col_index, item)

    def filter_suppliers(self):
        search_text = self.search_input.text().strip().lower()

        if not search_text:
            self.populate_supplier_table(self.all_suppliers)
            self.update_status_summary()
            if self.supplier_table.rowCount() > 0:
                self.supplier_table.selectRow(0)
            return

        filtered_rows = []
        for row in self.all_suppliers:
            supplier_code = str(row[0]).lower()
            supplier_name = str(row[1]).lower()

            if search_text in supplier_code or search_text in supplier_name:
                filtered_rows.append(row)

        self.populate_supplier_table(filtered_rows)
        self.update_status_summary()

        if self.supplier_table.rowCount() > 0:
            self.supplier_table.selectRow(0)
        elif search_text:
            QMessageBox.information(self, "Arama Sonucu", "Aramaya uygun tedarikçi bulunamadı.")

    def get_selected_suppliers(self):
        selected_suppliers = []
        invalid_suppliers = []

        for row in range(self.supplier_table.rowCount()):
            check_item = self.supplier_table.item(row, 0)
            if check_item is None or check_item.checkState() != Qt.Checked:
                continue

            code_item = self.supplier_table.item(row, 1)
            name_item = self.supplier_table.item(row, 2)
            person_item = self.supplier_table.item(row, 3)
            phone_item = self.supplier_table.item(row, 4)
            email_item = self.supplier_table.item(row, 5)
            tax_id_item = self.supplier_table.item(row, 6)

            supplier_code = code_item.text().strip() if code_item else ""
            supplier_name = name_item.text().strip() if name_item else ""
            invited_person = person_item.text().strip() if person_item else ""
            phone = phone_item.text().strip() if phone_item else ""
            invited_email = email_item.text().strip() if email_item else ""
            tax_id = tax_id_item.text().strip() if tax_id_item else ""

            missing_fields = []
            if not supplier_name:
                missing_fields.append("Tedarikçi Adı")
            if not invited_person:
                missing_fields.append("İlgili Kişi")
            if not invited_email:
                missing_fields.append("E-posta Adresi")
            if not tax_id:
                missing_fields.append("Vergi No")
            if not supplier_code:
                missing_fields.append("Kod")
            if not phone:
                missing_fields.append("Telefon")

            if missing_fields:
                supplier_label = supplier_name or supplier_code or f"Satır {row + 1}"
                invalid_suppliers.append(f"{supplier_label} -> Eksik alanlar: {', '.join(missing_fields)}")
                continue

            selected_suppliers.append(
                {
                    "name": supplier_name,
                    "invited_person": invited_person,
                    "phone": phone,
                    "invited_email": invited_email,
                    "tax_id": tax_id,
                    "erp_id": supplier_code,
                }
            )

        return selected_suppliers, invalid_suppliers

    def send_selected_suppliers(self):
        selected_suppliers, invalid_suppliers = self.get_selected_suppliers()

        if invalid_suppliers:
            missing_text = "\n".join(invalid_suppliers)
            QMessageBox.warning(
                self,
                "Eksik Zorunlu Alan",
                f"Aşağıdaki tedarikçiler gönderilmedi çünkü zorunlu alanlar boş:\n{missing_text}",
            )

        if not selected_suppliers:
            QMessageBox.warning(self, "Seçim Yok", "Gönderilecek geçerli tedarikçi bulunamadı.")
            return

        connector = SattaSupplierPushConnector()

        try:
            connector.push_suppliers(selected_suppliers)
        except Exception as exc:
            QMessageBox.critical(self, "Aktarım Hatası", f"Seçili tedarikçiler Satta'ya gönderilemedi:\n{exc}")
            return

        QMessageBox.information(
            self,
            "Aktarım Tamamlandı",
            f"Seçili {len(selected_suppliers)} tedarikçi Satta'ya gönderildi.",
        )
    def update_selected_count(self):
        selected_count = 0
        for row in range(self.supplier_table.rowCount()):
            item = self.supplier_table.item(row, 0)
            if item is not None and item.checkState() == Qt.Checked:
                selected_count += 1

        self.selected_info_label.setText(f"Seçili tedarikçi sayısı: {selected_count}")

    def update_status_summary(self):
        self.update_selected_count()

    def toggle_table_edit_mode(self, checked):
        if checked:
            self.supplier_table.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.SelectedClicked
            )
        else:
            self.supplier_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        current_rows = []
        for row in range(self.supplier_table.rowCount()):
            row_data = []
            for col in range(1, self.supplier_table.columnCount()):
                item = self.supplier_table.item(row, col)
                row_data.append(item.text() if item else "")
            current_rows.append(tuple(row_data))

        self.populate_supplier_table(current_rows)