

import logging
from typing import Any, Dict, List, Optional

from Invoice.logo_bridge_runner import LogoBridgeRunner
from Invoice.logo_payload_builder import LogoPayloadBuilder

logger = logging.getLogger(__name__)


class LogoTransferService:
    def __init__(self, logo_settings: Dict[str, Any], bridge_runner: Optional[LogoBridgeRunner] = None):
        self.logo_settings = logo_settings or {}
        self.payload_builder = LogoPayloadBuilder(self.logo_settings)
        self.bridge_runner = bridge_runner or LogoBridgeRunner()

    def transfer_invoices(self, raw_invoices: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not isinstance(raw_invoices, list):
            raise ValueError("Aktarılacak faturalar liste tipinde olmalıdır.")

        successful_invoice_ids: List[int] = []
        successful_invoice_nos: List[str] = []
        failed_results: List[str] = []
        bridge_results: List[Dict[str, Any]] = []

        payloads = []
        invoice_info_list = []

        for raw_invoice in raw_invoices:
            if not isinstance(raw_invoice, dict):
                failed_results.append("Bilinmeyen fatura: Ham veri sözlük tipinde değil.")
                continue

            invoice_id = self._to_int(raw_invoice.get("invoice_id"))
            invoice_no = self._safe_text(raw_invoice.get("invoice_no"), default="-")

            try:
                payload = self.payload_builder.build_invoice_payload(raw_invoice)
                payloads.append(payload)
                invoice_info_list.append({"id": invoice_id, "no": invoice_no})
            except Exception as exc:
                failed_results.append(f"{invoice_no}: Payload hazırlanamadı - {exc}")

        if not payloads:
            return {
                "successful_invoice_ids": successful_invoice_ids,
                "successful_invoice_nos": successful_invoice_nos,
                "failed_results": failed_results,
                "bridge_results": bridge_results,
            }

        try:
            batch_results = self.bridge_runner.run_batch_invoice_transfer(payloads)
        except Exception as exc:
            failed_results.append(f"Toplu Bridge çalıştırılamadı - {exc}")
            return {
                "successful_invoice_ids": successful_invoice_ids,
                "successful_invoice_nos": successful_invoice_nos,
                "failed_results": failed_results,
                "bridge_results": bridge_results,
            }

        successful_invoices: List[Dict[str, Any]] = []

        for info, bridge_result in zip(invoice_info_list, batch_results):
            invoice_id = info["id"]
            invoice_no = info["no"]

            bridge_results.append({
                "invoice_id": invoice_id,
                "invoice_no": invoice_no,
                "result": bridge_result,
            })

            is_success = bool(bridge_result.get("is_success"))
            message = self._safe_text(bridge_result.get("message"), default="Logo aktarımı başarısız.")
            
            details = bridge_result.get("details", {})
            if isinstance(details, dict):
                specific_error = (
                    details.get("post_error_desc") or 
                    details.get("line_mapping_error") or 
                    details.get("header_mapping_error") or 
                    details.get("error") or
                    details.get("stderr") or
                    details.get("stdout")
                )
                if specific_error:
                    message += f"\n\nHata Detayı: {specific_error}"

            if is_success:
                erp_ref = self._to_int(bridge_result.get("logical_ref")) or 0
                self._post_process_einvoice(erp_ref, details, invoice_no)
                successful_invoices.append({"id": invoice_id, "no": invoice_no})
                if invoice_id is not None:
                    successful_invoice_ids.append(invoice_id)
                successful_invoice_nos.append(invoice_no)
            else:
                failed_results.append(f"{invoice_no}: {message}")

        # Aktarılan faturaları Connect APPROVAL tablosunda otomatik senkronize et
        if successful_invoices:
            try:
                from Invoice.logo_connect_reader import LogoConnectReader
                reader = LogoConnectReader(self.logo_settings)
                period_no = self._to_int(self.logo_settings.get("period_no")) or 1
                reader.auto_sync_transferred_invoices(period_no=period_no)
            except Exception as sync_exc:
                logger.debug("Toplu aktarım sonrası Connect otomatik senkronizasyon hatası: %s", sync_exc)

        return {
            "successful_invoices": successful_invoices,
            "successful_invoice_ids": successful_invoice_ids,
            "successful_invoice_nos": successful_invoice_nos,
            "failed_results": failed_results,
            "bridge_results": bridge_results,
        }

    def _post_process_einvoice(
        self, erp_logical_ref: int, details: Dict[str, Any], invoice_no: str = ""
    ) -> None:
        if not isinstance(details, dict):
            return

        is_e_invoice = (
            str(details.get("is_e_invoice", "")).lower() in ("true", "1")
            or bool(details.get("is_e_invoice"))
        )
        guid = str(details.get("guid") or "").strip()
        profile_id = self._to_int(details.get("profile_id")) or 1
        connect_logical_ref = self._to_int(details.get("connect_logical_ref")) or 0
        doc_no = str(details.get("invoice_number") or invoice_no or "").strip()

        if guid:
            is_e_invoice = True

        # Eğer erp_logical_ref 0 geldiyse, Tiger DB INVOICE tablosundan faturayı sorgulayarak LOGICALREF'i bul
        if erp_logical_ref <= 0 and (doc_no or guid):
            try:
                import pyodbc
                server = str(self.logo_settings.get("server", "")).strip()
                database = str(self.logo_settings.get("database", "")).strip()
                username = str(self.logo_settings.get("db_username", "")).strip()
                password = str(self.logo_settings.get("db_password", "")).strip()
                firm_no = self._to_int(self.logo_settings.get("firm_no")) or 1
                period_no = self._to_int(self.logo_settings.get("period_no")) or 1

                if server and database:
                    if username:
                        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};"
                    else:
                        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

                    table_name = f"LG_{firm_no:03d}_{period_no:02d}_INVOICE"
                    with pyodbc.connect(conn_str, timeout=5) as conn:
                        cursor = conn.cursor()
                        if doc_no and guid:
                            cursor.execute(
                                f"SELECT TOP 1 LOGICALREF FROM [{table_name}] WITH (NOLOCK) WHERE FICHENO = ? OR GUID = ? ORDER BY LOGICALREF DESC",
                                (doc_no, guid),
                            )
                        elif doc_no:
                            cursor.execute(
                                f"SELECT TOP 1 LOGICALREF FROM [{table_name}] WITH (NOLOCK) WHERE FICHENO = ? ORDER BY LOGICALREF DESC",
                                (doc_no,),
                            )
                        elif guid:
                            cursor.execute(
                                f"SELECT TOP 1 LOGICALREF FROM [{table_name}] WITH (NOLOCK) WHERE GUID = ? ORDER BY LOGICALREF DESC",
                                (guid,),
                            )
                        row = cursor.fetchone()
                        if row and row[0]:
                            erp_logical_ref = int(row[0])
            except Exception as exc:
                logger.warning("Tiger INVOICE tablosundan LOGICALREF sorgulanamadı: %s", exc)

        if erp_logical_ref <= 0:
            return

        # 1. Tiger DB INVOICE tablosunda EINVOICE ve GUID alanlarını garantiye al
        if is_e_invoice and guid:
            try:
                import pyodbc
                server = str(self.logo_settings.get("server", "")).strip()
                database = str(self.logo_settings.get("database", "")).strip()
                username = str(self.logo_settings.get("db_username", "")).strip()
                password = str(self.logo_settings.get("db_password", "")).strip()
                firm_no = self._to_int(self.logo_settings.get("firm_no")) or 1
                period_no = self._to_int(self.logo_settings.get("period_no")) or 1

                if server and database:
                    if username:
                        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password};"
                    else:
                        conn_str = f"DRIVER={{SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"

                    table_name = f"LG_{firm_no:03d}_{period_no:02d}_INVOICE"
                    update_query = f"""
                    UPDATE {table_name}
                    SET EINVOICE = 1,
                        GUID = ?,
                        PROFILE_ID = ?,
                        ESTATUS = 12
                    WHERE LOGICALREF = ?
                    """
                    with pyodbc.connect(conn_str, timeout=5) as conn:
                        cursor = conn.cursor()
                        cursor.execute(update_query, (guid, profile_id, erp_logical_ref))
                        conn.commit()
            except Exception as exc:
                logger.warning("Tiger INVOICE tablosu post_process güncellenemedi: %s", exc)

        # 2. Connect APPROVAL tablosunda DOCREF ve STATUS=3 güncelle
        if connect_logical_ref > 0 or (is_e_invoice and doc_no):
            try:
                from Invoice.logo_connect_reader import LogoConnectReader
                reader = LogoConnectReader(self.logo_settings)
                success = reader.mark_as_transferred(connect_logical_ref, erp_logical_ref, doc_no)
                if not success:
                    logger.warning(
                        "Connect APPROVAL tablosu güncellenemedi (ConnectRef: %s, FaturaNo: %s, ERPRef: %s)",
                        connect_logical_ref, doc_no, erp_logical_ref
                    )
            except Exception as exc:
                logger.warning("Connect APPROVAL post_process hatası: %s", exc)

    @staticmethod
    def _safe_text(value: Any, default: str = "") -> str:
        if value is None:
            return default

        text = str(value).strip()
        if not text:
            return default

        return text

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            if value is None or str(value).strip() == "":
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None