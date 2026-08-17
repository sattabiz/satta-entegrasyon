from Common.qt_compat import (
    QApplication,
    QComboBox,
    QKeySequence,
    QMenu,
    QShortcut,
    QTableWidget,
    Qt,
)


def copy_table_selection(table: QTableWidget) -> None:
    if table is None:
        return

    selection_model = table.selectionModel()
    if selection_model is None or not selection_model.hasSelection():
        return

    selected_indexes = table.selectedIndexes()
    if not selected_indexes:
        return

    rows_dict = {}
    for index in selected_indexes:
        row = index.row()
        col = index.column()
        if row not in rows_dict:
            rows_dict[row] = {}

        widget = table.cellWidget(row, col)
        if isinstance(widget, QComboBox):
            cell_text = widget.currentText().strip()
        else:
            item = table.item(row, col)
            cell_text = item.text().strip() if item is not None else ""

        rows_dict[row][col] = cell_text

    sorted_rows = sorted(rows_dict.keys())
    row_strings = []
    for r in sorted_rows:
        cols_in_row = rows_dict[r]
        sorted_cols = sorted(cols_in_row.keys())

        # If col 0 is empty (e.g. checkbox column) and other columns are selected in that row, omit col 0
        if len(sorted_cols) > 1 and 0 in sorted_cols and cols_in_row[0] == "":
            sorted_cols.remove(0)

        row_str = "\t".join(cols_in_row[c] for c in sorted_cols)
        row_strings.append(row_str)

    clipboard_text = "\n".join(row_strings)
    if clipboard_text:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(clipboard_text)


def paste_table_selection(table: QTableWidget) -> None:
    if table is None:
        return

    clipboard = QApplication.clipboard()
    if clipboard is None:
        return

    text = clipboard.text()
    if not text:
        return

    selected_indexes = table.selectedIndexes()
    if not selected_indexes:
        return

    lines = text.splitlines()

    table.blockSignals(True)
    affected_items = []
    try:
        if len(selected_indexes) == 1 or len(lines) <= 1:
            paste_val = lines[0].strip() if lines else text.strip()
            for index in selected_indexes:
                item = table.item(index.row(), index.column())
                if item is not None and (item.flags() & Qt.ItemIsEditable):
                    item.setText(paste_val)
                    affected_items.append(item)
        else:
            min_row = min(idx.row() for idx in selected_indexes)
            min_col = min(idx.column() for idx in selected_indexes)
            for r_idx, line in enumerate(lines):
                target_row = min_row + r_idx
                if target_row >= table.rowCount():
                    break
                cols = line.split("\t")
                for c_idx, val in enumerate(cols):
                    target_col = min_col + c_idx
                    if target_col >= table.columnCount():
                        break
                    item = table.item(target_row, target_col)
                    if item is not None and (item.flags() & Qt.ItemIsEditable):
                        item.setText(val.strip())
                        affected_items.append(item)
    finally:
        table.blockSignals(False)

    # Emit itemChanged signal for all edited items so handlers update raw data
    for item in affected_items:
        table.itemChanged.emit(item)


def show_table_context_menu(table: QTableWidget, pos) -> None:
    if table is None:
        return
    menu = QMenu(table)
    copy_action = menu.addAction("Kopyala")
    copy_action.setShortcut(QKeySequence.Copy)

    selected_indexes = table.selectedIndexes()
    has_editable = any(
        (table.item(idx.row(), idx.column()).flags() & Qt.ItemIsEditable)
        if table.item(idx.row(), idx.column()) is not None else False
        for idx in selected_indexes
    )

    paste_action = menu.addAction("Yapıştır")
    paste_action.setShortcut(QKeySequence.Paste)
    paste_action.setEnabled(has_editable)

    action = menu.exec(table.viewport().mapToGlobal(pos))
    if action == copy_action:
        copy_table_selection(table)
    elif action == paste_action:
        paste_table_selection(table)


def enable_table_copy(table: QTableWidget) -> None:
    if table is None:
        return

    # Setup Copy shortcuts (Ctrl+C, Ctrl+Ins)
    shortcut_copy = QShortcut(QKeySequence.Copy, table)
    shortcut_copy.activated.connect(lambda t=table: copy_table_selection(t))

    shortcut_copy_ins = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Insert), table)
    shortcut_copy_ins.activated.connect(lambda t=table: copy_table_selection(t))

    # Setup Paste shortcuts (Ctrl+V, Shift+Ins)
    shortcut_paste = QShortcut(QKeySequence.Paste, table)
    shortcut_paste.activated.connect(lambda t=table: paste_table_selection(t))

    shortcut_paste_ins = QShortcut(QKeySequence(Qt.SHIFT | Qt.Key_Insert), table)
    shortcut_paste_ins.activated.connect(lambda t=table: paste_table_selection(t))

    # Setup Right-Click context menu
    table.setContextMenuPolicy(Qt.CustomContextMenu)
    table.customContextMenuRequested.connect(
        lambda pos, t=table: show_table_context_menu(t, pos)
    )
