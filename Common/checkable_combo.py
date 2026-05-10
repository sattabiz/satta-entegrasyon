from Common.qt_compat import Qt, QComboBox, QStyledItemDelegate
import sys

class CheckableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Make the combobox editable so we can display custom text
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        
        # Connect the view's pressed signal to our handler
        self.view().pressed.connect(self.handle_item_pressed)
        
        # We need a standard item delegate to show checkboxes
        self.setItemDelegate(QStyledItemDelegate(self))
        self._changed = False

    def handle_item_pressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            item.setCheckState(Qt.Checked)
        self._changed = True
        self.update_text()

    def hidePopup(self):
        # Prevent popup from closing when an item is toggled
        if not self._changed:
            super().hidePopup()
            self.update_text()
        self._changed = False

    def addItem(self, text, userData=None):
        super().addItem(text, userData)
        # Set the newly added item to be checkable
        item = self.model().item(self.count() - 1, self.modelColumn())
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Unchecked)
        self.update_text()

    def clear(self):
        super().clear()
        self.update_text()

    def item_checked(self, index):
        item = self.model().item(index, self.modelColumn())
        if item:
            return item.checkState() == Qt.Checked
        return False

    def checkedItems(self):
        # Returns a list of dictionaries containing text and data of checked items
        items = []
        for i in range(self.count()):
            if self.item_checked(i):
                items.append({
                    "text": self.itemText(i),
                    "data": self.itemData(i)
                })
        return items

    def update_text(self, *args):
        texts = []
        for i in range(self.count()):
            if self.item_checked(i):
                texts.append(self.itemText(i))
                
        if not texts:
            display_text = "Masraf Merkezi Seçiniz..."
        else:
            display_text = f"{len(texts)} Merkez Seçili ({', '.join(texts[:2])}{'...' if len(texts) > 2 else ''})"
            
        self.lineEdit().blockSignals(True)
        self.lineEdit().setText(display_text)
        self.lineEdit().blockSignals(False)
