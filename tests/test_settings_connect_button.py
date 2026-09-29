import sys
import unittest
from unittest.mock import patch

from Common.qt_compat import QApplication
app = QApplication.instance() or QApplication(sys.argv or [""])

from Settings.settings import SettingsTab


class TestSettingsConnectButton(unittest.TestCase):
    def setUp(self):
        self.tab = SettingsTab()

    def test_connect_button_hidden_when_connect_disabled(self):
        self.tab.use_logo_connect_checkbox.setChecked(False)
        self.tab.update_connect_test_button_visibility()
        self.assertTrue(self.tab.connect_test_button.isHidden())

    def test_connect_button_visible_when_connect_enabled_unverified(self):
        self.tab.use_logo_connect_checkbox.setChecked(True)
        # Mock load_existing_settings to return empty verified config
        with patch.object(self.tab, "load_existing_settings", return_value={"logo": {}}):
            self.tab.update_connect_test_button_visibility()
            self.assertFalse(self.tab.connect_test_button.isHidden())

    def test_connect_button_hidden_when_verified_matches(self):
        self.tab.use_logo_connect_checkbox.setChecked(True)
        self.tab.logo_server_input.setText("192.168.1.50")
        self.tab.logo_database_input.setText("TIGERDB")
        self.tab.logo_connect_database_input.setText("CONNECTDB")
        self.tab.logo_db_username_input.setText("sa")
        self.tab.logo_db_password_input.setText("Secret123")
        self.tab.logo_connect_firm_no_input.setValue(1)

        verified = {
            "server": "192.168.1.50",
            "database": "TIGERDB",
            "connect_database": "CONNECTDB",
            "db_username": "sa",
            "db_password": "Secret123",
            "connect_firm_no": 1,
        }
        with patch.object(self.tab, "load_existing_settings", return_value={"logo": {"connect_connection_verified_config": verified}}):
            self.tab.update_connect_test_button_visibility()
            self.assertTrue(self.tab.connect_test_button.isHidden())

            # Change server
            self.tab.logo_server_input.setText("192.168.1.99")
            self.assertFalse(self.tab.connect_test_button.isHidden())

            # Revert server
            self.tab.logo_server_input.setText("192.168.1.50")
            self.assertTrue(self.tab.connect_test_button.isHidden())

            # Change firm_no
            self.tab.logo_connect_firm_no_input.setValue(2)
            self.assertFalse(self.tab.connect_test_button.isHidden())

            # Revert firm_no
            self.tab.logo_connect_firm_no_input.setValue(1)
            self.assertTrue(self.tab.connect_test_button.isHidden())

            # Change connect database
            self.tab.logo_connect_database_input.setText("OTHER_CONNECT")
            self.assertFalse(self.tab.connect_test_button.isHidden())

            # Revert connect database
            self.tab.logo_connect_database_input.setText("CONNECTDB")
            self.assertTrue(self.tab.connect_test_button.isHidden())

    def test_save_settings_success_feedback(self):
        with patch("pathlib.Path.write_text") as mock_write, \
             patch("Settings.settings.QMessageBox.information") as mock_info:
            self.tab.handle_save_settings()
            mock_write.assert_called_once()
            mock_info.assert_called_once()
            self.assertIn("✓ Ayarlar Başarıyla Kaydedildi", self.tab.save_button.text())

    def test_save_settings_error_feedback(self):
        with patch("pathlib.Path.write_text", side_effect=OSError("Disk full")), \
             patch("Settings.settings.QMessageBox.critical") as mock_crit:
            self.tab.handle_save_settings()
            mock_crit.assert_called_once()
            self.assertIn("✕ Kayıt Başarısız", self.tab.save_button.text())


if __name__ == "__main__":
    unittest.main()
