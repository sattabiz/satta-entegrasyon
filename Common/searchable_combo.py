from Common.qt_compat import (
    Qt,
    QComboBox,
    QLineEdit,
    QSortFilterProxyModel,
    QStandardItemModel,
    QStandardItem,
    QEvent,
)

class SearchableComboBox(QComboBox):
    """
    A QComboBox subclass with an integrated dynamic search bar displayed
    at the top of the dropdown popup. Typing filters the visual list without
    automatically committing the selection until the user clicks an item
    or presses Enter.
    """
    def __init__(self, parent=None, placeholder_text="Kategori Ara..."):
        super().__init__(parent)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(placeholder_text)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #007acc;
                border-radius: 3px;
                padding: 4px 6px;
                margin: 4px;
                background-color: #ffffff;
                color: #333333;
                font-size: 12px;
            }
        """)

        self._source_model = QStandardItemModel(self)
        self._proxy_model = QSortFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)
        self._proxy_model.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)

        super().setModel(self._proxy_model)

        self.search_input.installEventFilter(self)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        
        # Connect view item selection events (mouse click, press, activated)
        self.view().pressed.connect(self._on_view_pressed)
        self.view().clicked.connect(self._on_view_pressed)
        self.activated.connect(self._on_activated)

        self._initial_source_index = -1
        self._selected_source_index = -1
        self._user_selected = False

    def addItem(self, text, userData=None):
        item = QStandardItem(str(text) if text is not None else "")
        item.setData(userData, Qt.UserRole)
        self._source_model.appendRow(item)

    def addItems(self, texts):
        for text in texts:
            self.addItem(text)

    def clear(self):
        self._source_model.clear()
        self._proxy_model.setFilterFixedString("")

    def showPopup(self):
        self._user_selected = False
        self._initial_source_index = self.currentIndex()
        self._selected_source_index = self.currentIndex()

        # Block combobox signals while popup is open to prevent intermediate typing selection events
        self.blockSignals(True)

        self.search_input.blockSignals(True)
        self.search_input.setText("")
        self.search_input.blockSignals(False)
        
        self._proxy_model.setFilterFixedString("")

        super().showPopup()

        popup = self.view().window()
        layout = popup.layout()
        if layout:
            if layout.indexOf(self.search_input) == -1:
                layout.insertWidget(0, self.search_input)
            self.search_input.show()
            self.search_input.setFocus()

    def hidePopup(self):
        self.search_input.hide()
        self._proxy_model.setFilterFixedString("")

        target_idx = self._selected_source_index if self._user_selected else self._initial_source_index

        super().hidePopup()

        # Unblock signals now that popup interaction is finished
        self.blockSignals(False)

        if target_idx < 0 or target_idx >= self._source_model.rowCount():
            target_idx = 0

        current_before = self.currentIndex()

        if not self._user_selected:
            # Quietly restore initial selection
            self.blockSignals(True)
            self.setCurrentIndex(target_idx)
            self.blockSignals(False)
        else:
            # Explicit user selection
            if current_before != target_idx:
                self.setCurrentIndex(target_idx)
            else:
                self.currentIndexChanged.emit(target_idx)

    def _on_view_pressed(self, proxy_index):
        if proxy_index.isValid():
            source_index = self._proxy_model.mapToSource(proxy_index)
            if source_index.isValid():
                self._selected_source_index = source_index.row()
                self._user_selected = True

    def _on_activated(self, proxy_idx_row):
        if isinstance(proxy_idx_row, int) and proxy_idx_row >= 0:
            proxy_index = self._proxy_model.index(proxy_idx_row, 0)
            if proxy_index.isValid():
                source_index = self._proxy_model.mapToSource(proxy_index)
                if source_index.isValid():
                    self._selected_source_index = source_index.row()
                    self._user_selected = True

    def _on_search_text_changed(self, text):
        self._proxy_model.setFilterFixedString(text.strip())

    def eventFilter(self, watched, event):
        if watched == self.search_input and event.type() == QEvent.KeyPress:
            if event.key() in (Qt.Key_Down, Qt.Key_Up):
                self.view().setFocus()
                return True
            elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self._proxy_model.rowCount() > 0:
                    current_idx = self.view().currentIndex()
                    if not current_idx.isValid():
                        current_idx = self._proxy_model.index(0, 0)
                    if current_idx.isValid():
                        source_idx = self._proxy_model.mapToSource(current_idx)
                        if source_idx.isValid():
                            self._selected_source_index = source_idx.row()
                            self._user_selected = True
                self.hidePopup()
                return True
            elif event.key() == Qt.Key_Escape:
                self.hidePopup()
                return True
        return super().eventFilter(watched, event)
