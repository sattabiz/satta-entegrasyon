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

        if not invoice_id:
            raise ValueError("invoice_id bulunamadı.")

        if not invoice_no:
            raise ValueError("invoice_no bulunamadı.")

        if not seller_erp_id:
            raise ValueError("seller_erp_id bulunamadı. Cari hesap eşlemesi yapılamaz.")

        if not invoice_date:
            raise ValueError("invoice_date bulunamadı.")

        is_service_invoice = any(
            str(p.get("category_type")).lower().strip() == "service"
            for p in invoice.get("products") or []
            if isinstance(p, dict)
        )

        payload = {
            "firm_no": self._to_int(self.logo_settings.get("firm_no"), default=1),
            "period_no": self._to_int(self.logo_settings.get("period_no"), default=1),
            "logo_user": self._safe_text(self.logo_settings.get("logo_user")),
            "logo_password": self._safe_text(self.logo_settings.get("logo_password")),
            "logo_company_code": self._safe_text(self.logo_settings.get("database")),
            "logo_working_year": self._resolve_logo_working_year(invoice),
            "invoice_type": "purchase",
            "logo_invoice_type": 4 if is_service_invoice else 1,
            "document_number": invoice_no,
            "document_date": invoice_date,
            "document_time": self._resolve_document_time(invoice.get("invoice_date")),
            "arp_code": seller_erp_id,
            "invoice_number": invoice_no,
            "group_code": "1",
            "do_code": "~",
            "description": "",
            "auxiliary_code": "",
            "authorization_code": "",
            "trading_group": "",
            "division": self._to_int(self.logo_settings.get("division"), default=0),
            "department": self._to_int(self.logo_settings.get("department"), default=0),
            "source_index": self._to_int(self.logo_settings.get("source_index"), default=0),
            "factory_nr": self._to_int(self.logo_settings.get("factory_nr"), default=0),
            "warehouse_nr": self._to_int(self.logo_settings.get("warehouse_nr"), default=0),
            "currency_code": self._resolve_invoice_currency(invoice),
            "exchange_rate": self._resolve_exchange_rate(invoice),
            "transaction_currency_id": self._resolve_currency_id(self._resolve_invoice_currency(invoice)),
            "transaction_currency_rate": self._resolve_exchange_rate(invoice),
            "usd_rate": self._resolve_line_exchange_rate(invoice, "USD"),
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
                # Eşleşmeyen (ERP kodu olmayan) kalemleri faturaya yazmamak için atla
                continue

            quantity = self._to_float(product.get("shipped_amount"))
            if quantity <= 0:
                raise ValueError(f"{index}. satır için shipped_amount 0'dan büyük olmalıdır.")

            raw_price = self._to_float(product.get("price"))
            tl_price = self._to_float(product.get("price_in_tl"))
            line_total = self._to_float(product.get("line_total_without_tax"))

            # Cari'den tespit edilen ana fatura dövizini kullanıyoruz (Satırın kendi döviz kodunu eziyoruz)
            line_currency_code = self._resolve_invoice_currency(invoice)
            currency_id = self._resolve_currency_id(line_currency_code)
            currency_rate = self._resolve_line_exchange_rate(invoice, line_currency_code)

            # Satta'daki net tutar (line_total_without_tax) daima Yerel Para Birimi (TL) cinsindedir.
            # Faturada kuruş ve kur kaymasını engellemek için yüksek hassasiyetli TL birim fiyatı türetilir:
            if line_total > 0 and quantity > 0:
                derived_tl_price = round(line_total / quantity, 6)
            elif tl_price > 0:
                derived_tl_price = tl_price
            elif currency_rate > 0 and currency_id != 0:
                derived_tl_price = round(raw_price * currency_rate, 6)
            else:
                derived_tl_price = raw_price

            if currency_id != 0:
                # Dövizli fatura:
                # Logo'da PRICE = Yerel Para Birimi (TL) birim fiyatı
                # Logo'da FC_PRICE / EDT_PRICE / PC_PRICE = İşlem Dövizi (EUR/USD vb.) birim fiyatı
                unit_price = derived_tl_price
                if raw_price > 0:
                    foreign_price = raw_price
                elif currency_rate > 0 and unit_price > 0:
                    foreign_price = round(unit_price / currency_rate, 6)
                else:
                    foreign_price = 0.0
            else:
                # TL fatura:
                unit_price = derived_tl_price
                foreign_price = 0.0

            vat_rate = self._to_float(product.get("applied_vat_rate"))
            
            product_category_type = str(product.get("category_type")).lower().strip()
            is_service = product_category_type == "service"

            line_payload = {
                "master_code": product_code,
                "line_type": 4 if is_service else 0,
                "description": self._build_line_description(product),
                "description2": self._safe_text(product.get("description")),
                "quantity": quantity,
                "unit_code": self._safe_text(product.get("unit")),
                "unit_price": unit_price,
                "foreign_currency_price": foreign_price,
                "vat_rate": vat_rate,
                "currency_code": line_currency_code,
                "exchange_rate": currency_rate,
                "currency_id": currency_id,
                "currency_rate": currency_rate,
                "warehouse_nr": self._to_int(self.logo_settings.get("warehouse_nr"), default=1),
                "source_index": self._to_int(self.logo_settings.get("source_index"), default=0),
                "division": self._to_int(self.logo_settings.get("division"), default=0),
                "department": self._to_int(self.logo_settings.get("department"), default=0),
                "auxiliary_code": self._safe_text(product.get("category_erp_id")),
                "project_code": "",
                "cost_center_code": self._safe_text(product.get("cost_center_erp_id")),
                "variant_code": "",
            }
            lines.append(line_payload)

        # Boş (0 satırlı) faturaya izin vermek için satır kontrolü kaldırıldı
        # if not lines:
        #     raise ValueError("Fatura içinde aktarılacak ürün satırı bulunamadı.")

        return lines

    def _resolve_product_code(self, product: Dict[str, Any]) -> str:
        if product.get("category_manually_changed"):
            return self._safe_text(product.get("category_erp_code"))

        product_code = self._safe_text(product.get("company_product_erp_id"))
        
        # İstek: Eğer kod "SAT-" ile başlıyorsa veya boşsa (null ise), öncelikli olarak category_erp_code kullan
        if not product_code or product_code.startswith("SAT-"):
            category_code = self._safe_text(product.get("category_erp_code"))
            if category_code:
                return category_code

        if product_code and not product_code.startswith("SAT-"):
            return product_code

        return ""

    def _resolve_invoice_currency(self, invoice: Dict[str, Any]) -> str:
        seller_erp_id = self._safe_text(invoice.get("seller_erp_id")).upper()
        if seller_erp_id.endswith(".€"):
            return "EUR"
        if seller_erp_id.endswith(".$"):
            return "USD"
        if seller_erp_id.endswith(".£"):
            return "GBP"

        products = invoice.get("products") or []
        for product in products:
            if not isinstance(product, dict):
                continue
            currency_code = self._safe_text(product.get("currency_code"))
            if currency_code and currency_code.upper() != "TRY":
                return currency_code
        return "TRY"

    def _resolve_currency_id(self, currency_code: str) -> int:
        code = self._safe_text(currency_code).upper()
        mapping = {
            "TRY": 0,
            "TL": 0,
            "USD": 1,
            "EUR": 20,
            "GBP": 17,
            "CHF": 11,
            "CAD": 19,
            "RUB": 58,
            "JPY": 18
        }
        return mapping.get(code, 0)

    def _resolve_exchange_rate(self, invoice: Dict[str, Any]) -> float:
        currency_code = self._resolve_invoice_currency(invoice)
        return self._resolve_line_exchange_rate(invoice, currency_code)

    def _resolve_line_exchange_rate(self, invoice: Dict[str, Any], currency_code: str) -> float:
        normalized_currency = self._safe_text(currency_code, default="TRY").upper()
        if not normalized_currency or normalized_currency == "TRY":
            return 0.0

        currency_rates = invoice.get("currency_rates") or {}
        if not isinstance(currency_rates, dict):
            return 0.0

        return self._to_float(currency_rates.get(normalized_currency), default=0.0)

    def _resolve_logo_working_year(self, invoice: Dict[str, Any]) -> str:
        configured_year = self._safe_text(self.logo_settings.get("logo_working_year"))
        if configured_year:
            return configured_year

        invoice_date = self._safe_text(invoice.get("invoice_date"))
        if not invoice_date:
            return str(self._to_int(self.logo_settings.get("period_no"), default=1))

        try:
            normalized_text = invoice_date.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized_text)
            return str(parsed.year)
        except ValueError:
            return str(self._to_int(self.logo_settings.get("period_no"), default=1))

    def _resolve_document_time(self, value: Any) -> str:
        text = self._safe_text(value)
        if not text:
            return "00:00:00"

        try:
            normalized_text = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized_text)
            return parsed.strftime("%H:%M:%S")
        except ValueError:
            return "00:00:00"

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
