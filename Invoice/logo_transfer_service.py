

from typing import Any, Dict, List, Optional

from Invoice.logo_bridge_runner import LogoBridgeRunner
from Invoice.logo_payload_builder import LogoPayloadBuilder


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
                if invoice_id is not None:
                    successful_invoice_ids.append(invoice_id)
                successful_invoice_nos.append(invoice_no)
            else:
                failed_results.append(f"{invoice_no}: {message}")

        return {
            "successful_invoice_ids": successful_invoice_ids,
            "successful_invoice_nos": successful_invoice_nos,
            "failed_results": failed_results,
            "bridge_results": bridge_results,
        }

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