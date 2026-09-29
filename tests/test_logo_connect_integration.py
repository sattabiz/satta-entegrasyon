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

    def test_logo_connect_reader_sql_and_mark_as_transferred(self):
        logo_settings = {
            "firm_no": 11,
            "period_no": 1,
            "server": "localhost",
            "database": "TIGERDB",
            "connect_database": "CONNECTDB",
        }
        reader = LogoConnectReader(logo_settings)
        self.assertEqual(reader.get_approval_table_name(), "LG_011_APPROVAL")

        with patch("pyodbc.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            # 1. By connect_logicalref
            success = reader.mark_as_transferred(connect_logicalref=94421, erp_logicalref=29930)
            self.assertTrue(success)
            executed_sql = mock_cursor.execute.call_args[0][0]
            params = mock_cursor.execute.call_args[0][1]
            self.assertIn("UPDATE LG_011_APPROVAL", executed_sql)
            self.assertIn("STATUS = 3", executed_sql)
            self.assertIn("APPROVED = 0", executed_sql)
            self.assertEqual(params, (29930, 94421))

            # 2. By invoice_no fallback
            success2 = reader.mark_as_transferred(connect_logicalref=0, erp_logicalref=29930, invoice_no="ADN2026000002748")
            self.assertTrue(success2)
            executed_sql2 = mock_cursor.execute.call_args[0][0]
            params2 = mock_cursor.execute.call_args[0][1]
            self.assertIn("WHERE DOCNR = ?", executed_sql2)
            self.assertEqual(params2, (29930, "ADN2026000002748"))

    def test_auto_sync_transferred_invoices_query(self):
        logo_settings = {
            "firm_no": 11,
            "period_no": 1,
            "server": "localhost",
            "database": "TIGERDB",
            "connect_database": "CONNECTDB",
        }
        reader = LogoConnectReader(logo_settings)

        with patch("pyodbc.connect") as mock_conn:
            mock_cursor = MagicMock()
            mock_cursor.rowcount = 2
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor

            synced = reader.auto_sync_transferred_invoices(period_no=1)
            self.assertEqual(synced, 2)
            executed_sql = mock_cursor.execute.call_args[0][0]
            self.assertIn("UPDATE A", executed_sql)
            self.assertIn("A.STATUS = 3", executed_sql)
            self.assertIn("[LG_011_APPROVAL] A", executed_sql)
            self.assertIn("[TIGERDB].dbo.[LG_011_01_INVOICE]", executed_sql)

    def test_post_process_einvoice(self):
        logo_settings = {
            "firm_no": 11,
            "period_no": 1,
            "server": "localhost",
            "database": "TIGERDB",
        }
        service = LogoTransferService(logo_settings)

        with patch("Invoice.logo_connect_reader.LogoConnectReader.mark_as_transferred") as mock_mark:
            with patch("pyodbc.connect"):
                mock_mark.return_value = True
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
                mock_mark.assert_called_once_with(94421, 29930, "ADN2026000002748")


if __name__ == "__main__":
    unittest.main()
