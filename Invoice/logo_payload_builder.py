from datetime import datetime
from typing import Any, Dict, List


class LogoPayloadBuilder:
    def __init__(self, logo_settings: Dict[str, Any]):
        self.logo_settings = logo_settings or {}

    def build_invoice_payload(self, invoice: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(invoice, dict):
            raise ValueError("Fatura verisi sözlük tipinde olmalıdır.")

        invoice_id = self._to_int(invoice.get("invoice_id"))
        invoice_no = self._safe_text(invoice.get("invoice_no"))
        seller_erp_id = self._safe_text(invoice.get("seller_erp_id"))
        invoice_date = self._format_datetime(invoice.get("invoice_date"))
        payment_date = self._format_datetime(invoice.get("payment_date"))
        invoice_note = self._safe_text(invoice.get("note"))
        seller_name = self._safe_text(invoice.get("seller_name"))

        if not invoice_id:
            raise ValueError("invoice_id bulunamadı.")

        if not invoice_no:
            raise ValueError("invoice_no bulunamadı.")

        if not seller_erp_id:
            raise ValueError("seller_erp_id bulunamadı. Cari hesap eşlemesi yapılamaz.")

        if not invoice_date:
            raise ValueError("invoice_date bulunamadı.")

        payload = {
            "firm_no": self._to_int(self.logo_settings.get("firm_no"), default=1),
            "period_no": self._to_int(self.logo_settings.get("period_no"), default=1),
            "logo_user": self._safe_text(self.logo_settings.get("username")),
            "logo_password": self._safe_text(self.logo_settings.get("password")),
            "logo_company_code": self._safe_text(self.logo_settings.get("database")),
            "logo_working_year": str(self._to_int(self.logo_settings.get("period_no"), default=1)),
            "invoice_type": "purchase",
            "document_number": invoice_no,
            "document_date": invoice_date,
            "document_time": "00:00:00",
            "arp_code": seller_erp_id,
            "invoice_number": invoice_no,
            "description": seller_name,
            "auxiliary_code": self._safe_text(invoice.get("reference_no")),
            "authorization_code": "",
            "trading_group": "",
            "division": self._to_int(self.logo_settings.get("division"), default=0),
            "department": self._to_int(self.logo_settings.get("department"), default=0),
            "source_index": self._to_int(self.logo_settings.get("source_index"), default=0),
            "factory_nr": self._to_int(self.logo_settings.get("factory_nr"), default=0),
            "warehouse_nr": self._to_int(self.logo_settings.get("warehouse_nr"), default=0),
            "currency_code": self._resolve_invoice_currency(invoice),
            "exchange_rate": 0,
            "notes": self._build_notes(invoice_id, payment_date, invoice_note),
            "lines": self._build_invoice_lines(invoice),
        }

        return payload

    def _build_invoice_lines(self, invoice: Dict[str, Any]) -> List[Dict[str, Any]]:
        lines: List[Dict[str, Any]] = []

        for index, product in enumerate(invoice.get("products") or [], start=1):
            if not isinstance(product, dict):
                continue

            product_code = self._resolve_product_code(product)
            if not product_code:
                raise ValueError(
                    f"{index}. satır için ürün ERP kodu bulunamadı. "
                    "company_product_erp_code veya erp_id alanı gerekli."
                )

            quantity = self._to_float(product.get("shipped_amount"))
            if quantity <= 0:
                raise ValueError(f"{index}. satır için shipped_amount 0'dan büyük olmalıdır.")

            unit_price = self._to_float(product.get("price_in_tl"))
            vat_rate = self._to_float(product.get("applied_vat_rate"))
            total = self._to_float(product.get("line_total_without_tax"))

            line_payload = {
                "master_code": product_code,
                "line_type": 0,
                "description": self._build_line_description(product),
                "quantity": quantity,
                "unit_code": self._safe_text(product.get("unit"), default="ADET"),
                "unit_price": unit_price,
                "vat_rate": vat_rate,
                "total": total,
                "currency_code": self._safe_text(product.get("currency_code"), default="TRY"),
                "exchange_rate": 0,
                "warehouse_nr": self._to_int(self.logo_settings.get("warehouse_nr"), default=0),
                "source_index": self._to_int(self.logo_settings.get("source_index"), default=0),
                "division": self._to_int(self.logo_settings.get("division"), default=0),
                "department": self._to_int(self.logo_settings.get("department"), default=0),
                "auxiliary_code": self._safe_text(product.get("category_erp_id")),
                "project_code": "",
                "cost_center_code": self._safe_text(product.get("cost_center_erp_id")),
                "variant_code": "",
            }
            lines.append(line_payload)

        if not lines:
            raise ValueError("Fatura içinde aktarılacak ürün satırı bulunamadı.")

        return lines

    def _resolve_product_code(self, product: Dict[str, Any]) -> str:
        product_code = self._safe_text(product.get("company_product_erp_code"))
        if product_code:
            return product_code

        product_code = self._safe_text(product.get("erp_id"))
        if product_code:
            return product_code

        product_code = self._safe_text(product.get("product_erp_id"))
        if product_code:
            return product_code

        return ""

    def _resolve_invoice_currency(self, invoice: Dict[str, Any]) -> str:
        products = invoice.get("products") or []
        for product in products:
            if not isinstance(product, dict):
                continue
            currency_code = self._safe_text(product.get("currency_code"))
            if currency_code:
                return currency_code
        return "TRY"

    def _build_notes(self, invoice_id: int, payment_date: str, invoice_note: str) -> List[str]:
        notes = [f"Satta Invoice ID: {invoice_id}"]
        if payment_date:
            notes.append(f"Payment Date: {payment_date}")
        if invoice_note:
            notes.append(f"Note: {invoice_note}")
        return notes

    def _build_line_description(self, product: Dict[str, Any]) -> str:
        description_parts = []

        product_name = self._safe_text(product.get("name"))
        if product_name:
            description_parts.append(product_name)

        description = self._safe_text(product.get("description"))
        if description:
            description_parts.append(description)

        proposal_note = self._safe_text(product.get("proposal_note"))
        if proposal_note:
            description_parts.append(proposal_note)

        return " | ".join(description_parts)

    def _format_datetime(self, value: Any) -> str:
        text = self._safe_text(value)
        if not text:
            return ""

        try:
            normalized_text = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized_text)
            return parsed.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return text

    @staticmethod
    def _safe_text(value: Any, default: str = "") -> str:
        if value is None:
            return default

        text = str(value).strip()
        if not text:
            return default

        return text

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        try:
            if value is None or str(value).strip() == "":
                return default
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or str(value).strip() == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default
