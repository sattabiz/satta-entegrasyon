import sys

if sys.version_info.major == 3 and sys.version_info.minor <= 9:
    from PySide2.QtCore import Qt, QThread, Signal, QEventLoop, QSortFilterProxyModel, QEvent
    from PySide2.QtGui import QFont, QPixmap, QIcon, QStandardItemModel, QStandardItem
    from PySide2.QtWidgets import (
        QApplication, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
        QAbstractItemView, QCheckBox, QFileDialog, QHeaderView, QHBoxLayout,
        QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
        QProgressDialog, QFormLayout, QComboBox, QGroupBox, QGridLayout,
        QFrame, QSpinBox, QStyledItemDelegate, QListView
    )
else:
    from PySide6.QtCore import Qt, QThread, Signal, QEventLoop, QSortFilterProxyModel, QEvent
    from PySide6.QtGui import QFont, QPixmap, QIcon, QStandardItemModel, QStandardItem
    from PySide6.QtWidgets import (
        QApplication, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget,
        QAbstractItemView, QCheckBox, QFileDialog, QHeaderView, QHBoxLayout,
        QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
        QProgressDialog, QFormLayout, QComboBox, QGroupBox, QGridLayout,
        QFrame, QSpinBox, QStyledItemDelegate, QListView
    )
