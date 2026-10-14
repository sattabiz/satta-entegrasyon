import unittest
from unittest.mock import MagicMock, patch
from Invoice.invoice_matcher import InvoiceMatcher, InvoiceMatchResult
from Invoice.logo_connect_reader import ConnectInvoiceRecord, LogoConnectReader
from Invoice.logo_transfer_service import LogoTransferService


class TestLogoConnectIntegration(unittest.TestCase):

    def setUp(self):
        self.valid_guid = "A439800C-93C4-4893-9540-0C1EFA02597D"
        self.valid_guid_32 = "A439800C93C4489395400C1EFA02597D"
        self.invalid_guid = "not-a-guid"

        self.sample_connect_record = ConnectInvoiceRecord(
            logical_ref=94421,
            invoice_number="ADN2026000002748",
            ettn_guid=self.valid_guid,
            supplier_vkn="2910099243",
            supplier_name="DEMO TICARET LTD STI",
            total_amount=1500.0,
            status=0,
            approved=0,
            doc_ref=0,
        )

    def test_is_valid_ettn(self):
        self.assertTrue(InvoiceMatcher.is_valid_ettn(self.valid_guid))
        self.assertTrue(InvoiceMatcher.is_valid_ettn(self.valid_guid.lower()))
        self.assertTrue(InvoiceMatcher.is_valid_ettn(f"{{{self.valid_guid}}}"))
        self.assertTrue(InvoiceMatcher.is_valid_ettn(self.valid_guid_32))
        self.assertFalse(InvoiceMatcher.is_valid_ettn(""))
        self.assertFalse(InvoiceMatcher.is_valid_ettn(None))
        self.assertFalse(InvoiceMatcher.is_valid_ettn(self.invalid_guid))
        self.assertFalse(InvoiceMatcher.is_valid_ettn("12345"))

    def test_matcher_ignores_records_without_valid_ettn(self):
        invalid_record = ConnectInvoiceRecord(
            logical_ref=94422,
            invoice_number="ADN2026000002749",
            ettn_guid="invalid-ettn",
            supplier_vkn="2910099243",
            supplier_name="DEMO TICARET",
            total_amount=1500.0,
        )
        matcher = InvoiceMatcher([invalid_record])
        self.assertEqual(len(matcher.valid_records), 0)

        satta_inv = {
            "invoice_number": "ADN2026000002749",
            "vkn": "2910099243",
            "total_price": 1500.0,
        }
        res = matcher.match_satta_invoice(satta_inv)
        self.assertFalse(res.is_matched)

    def test_matcher_exact_invoice_no(self):
        matcher = InvoiceMatcher([self.sample_connect_record])
        satta_inv = {
            "invoice_number": "ADN2026000002748",
            "vkn": "2910099243",
            "total_price": 1500.0,
        }
        res = matcher.match_satta_invoice(satta_inv)
        self.assertTrue(res.is_matched)
        self.assertEqual(res.match_type, "EXACT_NO")
        self.assertEqual(res.connect_record.logical_ref, 94421)
        self.assertIn("ADN2026000002748", res.display_text)

    def test_matcher_vkn_and_amount(self):
        matcher = InvoiceMatcher([self.sample_connect_record])
        satta_inv = {
            "invoice_number": "",
            "vkn": "2910099243",
            "total_price": 1500.0,
            "company_name": "DEMO TICARET",
        }
        res = matcher.match_satta_invoice(satta_inv)
        self.assertTrue(res.is_matched)
        self.assertEqual(res.match_type, "VKN_AMOUNT")
        self.assertEqual(res.display_text, "✓ E-Fatura (ADN2026000002748)")

    def test_logo_connect_reader_sql_is_strictly_read_only(self):
        logo_settings = {
            "firm_no": 11,
            "period_no": 1,
            "server": "localhost",
            "database": "TIGERDB",
            "connect_database": "CONNECTDB",
        }
        reader = LogoConnectReader(logo_settings)
        self.assertEqual(reader.get_approval_table_name(), "LG_011_APPROVAL")
        self.assertFalse(hasattr(reader, "mark_as_transferred"))
        self.assertFalse(hasattr(reader, "auto_sync_transferred_invoices"))

        with patch("pyodbc.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            records = reader.fetch_untransferred_invoices()
            self.assertEqual(records, [])
            executed_sql = mock_cursor.execute.call_args[0][0]
            self.assertIn("SELECT", executed_sql)
            self.assertIn("FROM LG_011_APPROVAL WITH (NOLOCK)", executed_sql)
            self.assertNotIn("UPDATE", executed_sql)
            self.assertNotIn("INSERT", executed_sql)
            self.assertNotIn("DELETE", executed_sql)

    def test_post_process_einvoice_only_updates_erp_never_connect(self):
        logo_settings = {
            "firm_no": 11,
            "period_no": 1,
            "server": "localhost",
            "database": "TIGERDB",
            "use_logo_connect": True,
        }
        service = LogoTransferService(logo_settings)

        with patch("pyodbc.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            details = {
                "is_e_invoice": True,
                "guid": self.valid_guid,
                "connect_logical_ref": 94421,
                "invoice_number": "ADN2026000002748",
            }
            service._post_process_einvoice(
                erp_logical_ref=29930,
                details=details,
                invoice_no="ADN2026000002748",
            )
            executed_sql = mock_cursor.execute.call_args[0][0]
            self.assertIn("UPDATE LG_011_01_INVOICE", executed_sql)
            self.assertNotIn("APPROVAL", executed_sql)

    def test_logo_payload_builder_einvoice_setting(self):
        from Invoice.logo_payload_builder import LogoPayloadBuilder

        sample_inv = {
            "invoice_id": 101,
            "invoice_no": "ADN2026000002748",
            "seller_erp_id": "320.01.001",
            "invoice_date": "2026-09-28T00:00:00",
            "is_e_invoice": True,
            "ettn_guid": self.valid_guid,
            "profile_id": 2,
            "connect_logical_ref": 94421,
            "gib_invoice_no": "ADN2026000002748",
            "products": [],
        }

        # 1. Connect Açıkken:
        builder_on = LogoPayloadBuilder({"use_logo_connect": True})
        payload_on = builder_on.build_invoice_payload(sample_inv)
        self.assertTrue(payload_on["is_e_invoice"])
        self.assertEqual(payload_on["guid"], self.valid_guid)
        self.assertEqual(payload_on["profile_id"], 2)
        self.assertEqual(payload_on["connect_logical_ref"], 94421)

        # 2. Connect Kapalıyken:
        builder_off = LogoPayloadBuilder({"use_logo_connect": False})
        payload_off = builder_off.build_invoice_payload(sample_inv)
        self.assertFalse(payload_off["is_e_invoice"])
        self.assertEqual(payload_off["guid"], "")
        self.assertEqual(payload_off["profile_id"], 1)
        self.assertEqual(payload_off["connect_logical_ref"], 0)

    def test_invoice_table_columns_connect_positioning(self):
        import sys
        from Common.qt_compat import QApplication
        app = QApplication.instance() or QApplication(sys.argv or [""])

        from Invoice.invoice import InvoiceTransferTab
        tab = InvoiceTransferTab()

        # Connect enabled: Column 2 must be 'E-Fatura Durumu' right next to 'Fatura No' (Column 1)
        with patch.object(tab, "load_logo_settings", return_value={"use_logo_connect": True}):
            tab.setup_invoice_table_columns()
            self.assertEqual(tab.invoice_table.columnCount(), 11)
            self.assertEqual(tab.invoice_table.horizontalHeaderItem(1).text(), "Fatura No")
            self.assertEqual(tab.invoice_table.horizontalHeaderItem(2).text(), "E-Fatura Durumu")
            self.assertEqual(tab.invoice_table.horizontalHeaderItem(3).text(), "Cari")

        # Connect disabled: Column 2 is 'Cari', total 10 columns, no 'E-Fatura Durumu'
        with patch.object(tab, "load_logo_settings", return_value={"use_logo_connect": False}):
            tab.setup_invoice_table_columns()
            self.assertEqual(tab.invoice_table.columnCount(), 10)
            self.assertEqual(tab.invoice_table.horizontalHeaderItem(1).text(), "Fatura No")
            self.assertEqual(tab.invoice_table.horizontalHeaderItem(2).text(), "Cari")


if __name__ == "__main__":
    unittest.main()


