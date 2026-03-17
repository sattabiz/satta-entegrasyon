import json
import requests
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from Common.path_helper import project_path


InvoiceUiRow = Tuple[str, str, str, str, str, str, str, str]
InvoiceDetailRow = Tuple[str, str, str, str, str, str]


## TODO: Dinamik buton adları hazırlanacak 

@dataclass
class SattaInvoiceConfig:
    use_mock_data: bool = True
    base_url: str = "https://test.satta.biz"
    username: str = ""
    password: str = ""
    token: str = ""
    token_storage_file: str = "satta_session.json"

class SattaInvoiceConnector:
    def __init__(self, config: SattaInvoiceConfig | None = None):
        self.config = config or SattaInvoiceConfig()

    def get_invoices_for_ui(self) -> Tuple[List[InvoiceUiRow], Dict[str, List[InvoiceDetailRow]], Dict[str, int]]:
        response = self._read_invoice_response()
        invoices = response.get("invoices", [])

        invoice_rows: List[InvoiceUiRow] = []
        invoice_details: Dict[str, List[InvoiceDetailRow]] = {}
        invoice_id_map: Dict[str, int] = {}

        for invoice in invoices:
            if not isinstance(invoice, dict):
                continue
            invoice_row = self._map_invoice_row(invoice)
            invoice_rows.append(invoice_row)
            invoice_details[invoice_row[0]] = self._map_invoice_details(invoice)

            invoice_id = self._normalize_invoice_id(invoice.get("invoice_id"))
            if invoice_id is not None:
                invoice_id_map[invoice_row[0]] = invoice_id

        return invoice_rows, invoice_details, invoice_id_map

    def ensure_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            current_token = self.get_saved_token()
            if current_token:
                return current_token

        new_token = self.login_and_get_token()
        self.save_token(new_token)
        return new_token

    def get_saved_token(self) -> str:
        if self.config.token:
            return self.config.token.strip()

        session_data = self._read_session_file()
        username = self._normalized_username()
        saved_token = self._safe_text(session_data.get(username, {}).get("token"))

        if saved_token:
            self.config.token = saved_token

        return saved_token

    def save_token(self, token: str) -> None:
        clean_token = self._safe_text(token)
        if not clean_token:
            return

        session_data = self._read_session_file()
        username = self._normalized_username()
        session_data[username] = {
            "token": clean_token,
            "base_url": self.config.base_url,
            "username": self.config.username,
            "saved_at": datetime.now().isoformat(),
        }

        session_path = self._session_file_path()
        session_path.parent.mkdir(parents=True, exist_ok=True)
        session_path.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.config.token = clean_token

    def clear_saved_token(self) -> None:
        session_data = self._read_session_file()
        username = self._normalized_username()
        if username in session_data:
            del session_data[username]
            session_path = self._session_file_path()
            session_path.parent.mkdir(parents=True, exist_ok=True)
            session_path.write_text(json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8")
        self.config.token = ""

    def login_and_get_token(self) -> str:
        if self.config.use_mock_data:
            return self._mock_token_for_user()

        username = self._safe_text(self.config.username)
        password = self._safe_text(self.config.password)

        if not username or not password:
            raise ValueError("Satta e-posta ve şifre zorunludur.")

        auth_url = self._build_auth_url()
        timeout_seconds = 30

        payload = {
            "api_user": {
                "email": username,
                "password": password,
            }
        }

        try:
            response = requests.post(
                auth_url,
                json=payload,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Satta login isteği başarısız oldu: {exc}") from exc

        response_json = self._safe_json(response)
        token = self._extract_token_from_response(response_json)

        if response.ok and token:
            return token

        message = self._extract_error_message(response_json)
        if not message:
            message = response.text.strip()

        raise RuntimeError(
            f"Satta login başarısız oldu. HTTP {response.status_code}. {message}"
        )

    def build_invoice_request(self) -> Dict[str, Any]:
        token = self.ensure_token()
        return {
            "url": self._build_invoice_list_url(),
            "headers": self._build_auth_headers(token),
            "params": {
                "state": '"invoice_approved","invoice_pending"',
                "saved_to_erp": "false",
            },
        }

    def _read_invoice_response(self) -> Dict[str, Any]:
        if self.config.use_mock_data:
            return self._read_mock_response()

        request_payload = self.build_invoice_request()
        timeout_seconds = 30

        try:
            response = requests.get(
                request_payload["url"],
                headers=request_payload["headers"],
                params=request_payload["params"],
                timeout=timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Satta fatura isteği başarısız oldu: {exc}") from exc

        if response.status_code in (401, 403):
            refreshed_token = self.ensure_token(force_refresh=True)
            try:
                response = requests.get(
                    request_payload["url"],
                    headers=self._build_auth_headers(refreshed_token),
                    params=request_payload["params"],
                    timeout=timeout_seconds,
                )
            except requests.RequestException as exc:
                raise RuntimeError(f"Satta fatura isteği başarısız oldu: {exc}") from exc

        response_json = self._safe_json(response)

        if not response.ok:
            message = self._extract_error_message(response_json)
            if not message:
                message = response.text.strip()
            raise RuntimeError(
                f"Satta faturaları alınamadı. HTTP {response.status_code}. {message}"
            )

        invoices = response_json.get("invoices")
        if invoices is None:
            response_json["invoices"] = []
        elif not isinstance(invoices, list):
            response_json["invoices"] = []

        return response_json

    def _read_mock_response(self) -> Dict[str, Any]:
        return {
            "status": 200,
            "response_message": "Müşteri faturaları başarıyla yüklendi.",
            "request_id": "ca08c6fabc500b9a7be9197d89db9bcb",
            "invoices": [
                {
                    "invoice_id": 710,
                    "invoice_no": "ssj4332123",
                    "order_id": None,
                    "invoice_date": "2024-12-27T00:00:00.000+03:00",
                    "payment_date": "2025-01-27T03:00:00.000+03:00",
                    "payment_type": "",
                    "state": "invoice_approved",
                    "note": None,
                    "dbs": False,
                    "price_without_vat": 1050.0,
                    "invoice_vat_total": 210.0,
                    "total_tl_price": 1260.0,
                    "payment_due_date_in_days": 30,
                    "seller_name": "Üçmetal Çelik Sanayi Tic. Ltd. Şti",
                    "seller_erp_id": "4343234234324",
                    "currency_rates": {
                        "USD": 35.2001,
                        "EUR": 36.6794,
                        "GBP": 44.1777,
                    },
                    "reference_no": None,
                    "products": [
                        {
                            "line_index": None,
                            "order_id": 1140,
                            "order_po_no": None,
                            "products_proposal_id": 8263,
                            "name": "STRECH 17 mic. - 50 cm - 300 mt.",
                            "category_id": 609,
                            "category_erp_id": "AS01",
                            "cost_center_name": "2 Kısa Elyaf",
                            "cost_center_erp_id": "3",
                            "description": "El TİPİ (MANUEL",
                            "shipped_amount": 10.5,
                            "unit": "KG",
                            "price": 100.0,
                            "price_in_tl": 100.0,
                            "line_total_without_tax": 1050.0,
                            "line_total_with_tax": 1260.0,
                            "line_tax_total": 210.0,
                            "applied_vat_rate": 20,
                            "currency_code": "TRY",
                            "erp_id": None,
                            "company_product_erp_code": "AS01002",
                            "company_product_erp_id": "51997",
                            "product_erp_id": None,
                            "proposal_note": None,
                        }
                    ],
                },
                {
                    "invoice_id": 536,
                    "invoice_no": "132",
                    "order_id": None,
                    "invoice_date": "2024-02-20T00:00:00.000+03:00",
                    "payment_date": None,
                    "payment_type": "",
                    "state": "invoice_approved",
                    "note": None,
                    "dbs": False,
                    "price_without_vat": 12.0,
                    "invoice_vat_total": 2.4,
                    "total_tl_price": 14.4,
                    "payment_due_date_in_days": 30,
                    "seller_name": "Tedarik Test",
                    "seller_erp_id": "tedarik_erp",
                    "currency_rates": {
                        "USD": 30.8944,
                        "EUR": 33.3239,
                        "GBP": 38.9773,
                    },
                    "reference_no": None,
                    "products": [
                        {
                            "line_index": None,
                            "order_id": 645,
                            "order_po_no": None,
                            "products_proposal_id": 5821,
                            "name": "sdf",
                            "category_id": 175,
                            "category_erp_id": None,
                            "cost_center_name": None,
                            "cost_center_erp_id": None,
                            "description": None,
                            "shipped_amount": 1.0,
                            "unit": "ADET",
                            "price": 12.0,
                            "price_in_tl": 12.0,
                            "line_total_without_tax": 12.0,
                            "line_total_with_tax": 14.4,
                            "line_tax_total": 2.4,
                            "applied_vat_rate": 20,
                            "currency_code": "TRY",
                            "erp_id": None,
                            "company_product_erp_code": None,
                            "company_product_erp_id": None,
                            "product_erp_id": None,
                            "proposal_note": None,
                        }
                    ],
                },
            ],
        }

    def _map_invoice_row(self, invoice: Dict[str, Any]) -> InvoiceUiRow:
        invoice_no = self._safe_text(invoice.get("invoice_no"), "-")
        seller_name = self._safe_text(invoice.get("seller_name"), "-")
        invoice_date = self._format_date(invoice.get("invoice_date"))
        payment_date = self._format_date(invoice.get("payment_date"))
        currency_code = self._resolve_invoice_currency(invoice)
        price_without_vat = self._format_money(invoice.get("price_without_vat"))
        price_with_vat = self._format_money(
            self._to_float(invoice.get("price_without_vat")) + self._to_float(invoice.get("invoice_vat_total"))
        )
        total_tl_price = self._format_money(invoice.get("total_tl_price"))

        return (
            invoice_no,
            seller_name,
            invoice_date,
            payment_date,
            currency_code,
            price_without_vat,
            price_with_vat,
            total_tl_price,
        )

    def _map_invoice_details(self, invoice: Dict[str, Any]) -> List[InvoiceDetailRow]:
        detail_rows: List[InvoiceDetailRow] = []

        for product in invoice.get("products") or []:
            if not isinstance(product, dict):
                continue
            product_code = self._safe_text(product.get("company_product_erp_code"))
            if not product_code:
                product_code = self._safe_text(product.get("product_erp_id"))
            if not product_code:
                product_code = self._safe_text(product.get("products_proposal_id"), "-")

            product_name = self._safe_text(product.get("name"), "-")
            description = self._safe_text(product.get("description"))
            if not description:
                description = self._safe_text(product.get("proposal_note"))
            if not description:
                description = "-"

            unit = self._safe_text(product.get("unit"), "-")

            detail_rows.append(
                (
                    product_code,
                    product_name,
                    description,
                    self._format_quantity(product.get("shipped_amount")),
                    unit,
                    self._format_money(product.get("price")),
                )
            )

        return detail_rows

    def _build_auth_headers(self, token: str) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": token,
            "Content-Type": "application/json",
        }

    def _build_invoice_list_url(self) -> str:
        base_url = self._safe_text(self.config.base_url).rstrip("/")
        return f"{base_url}/api/v1/buyer_invoice_list.json"

    def _build_auth_url(self) -> str:
        base_url = self._safe_text(self.config.base_url).rstrip("/")
        return f"{base_url}/api/v1/login.json"

    def _session_file_path(self) -> Path:
        return project_path("Settings", self.config.token_storage_file)

    def _read_session_file(self) -> Dict[str, Any]:
        session_path = self._session_file_path()
        if not session_path.exists():
            return {}

        try:
            return json.loads(session_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _normalized_username(self) -> str:
        username = self._safe_text(self.config.username).lower()
        return username or "default_user"

    def _mock_token_for_user(self) -> str:
        username = self._normalized_username().replace("@", "_").replace(".", "_")
        return f"mock_token_{username}"

    def _normalize_invoice_id(self, value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _resolve_invoice_currency(self, invoice: Dict[str, Any]) -> str:
        products = invoice.get("products") or []
        if products and isinstance(products[0], dict):
            currency_code = self._safe_text(products[0].get("currency_code"))
            if currency_code:
                return currency_code
        return "TRY"

    def _format_date(self, value: Any) -> str:
        text = self._safe_text(value)
        if not text:
            return "-"

        try:
            normalized_text = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized_text)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            return text[:10] if text else "-"

    def _format_money(self, value: Any) -> str:
        if value is None:
            return "0.00"
        amount = self._to_float(value)
        return f"{amount:.2f}"

    def _format_quantity(self, value: Any) -> str:
        if value is None:
            return "0"
        amount = self._to_float(value)
        return f"{amount:.2f}".rstrip("0").rstrip(".")

    def _to_float(self, value: Any) -> float:
        try:
            if value is None:
                return 0.0
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _safe_text(value: Any, default: str = "") -> str:
        if value is None:
            return default

        text = str(value).strip()
        if not text:
            return default

        return text

    def _safe_json(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}
        except ValueError:
            return {}

    def _extract_token_from_response(self, response_json: Dict[str, Any]) -> str:
        direct_keys = [
            "jwt",
            "token",
            "access_token",
            "auth_token",
            "id_token",
        ]
        for key in direct_keys:
            token = self._safe_text(response_json.get(key))
            if token:
                return token

        nested_keys = ["data", "result", "response", "session", "user"]
        for container_key in nested_keys:
            container_value = response_json.get(container_key)
            if isinstance(container_value, dict):
                for key in direct_keys:
                    token = self._safe_text(container_value.get(key))
                    if token:
                        return token

        return ""

    def _extract_error_message(self, response_json: Dict[str, Any]) -> str:
        message_keys = [
            "response_message",
            "message",
            "error",
            "error_message",
            "detail",
        ]
        for key in message_keys:
            value = response_json.get(key)
            if isinstance(value, str):
                clean_value = value.strip()
                if clean_value:
                    return clean_value

        errors_value = response_json.get("errors")
        if isinstance(errors_value, list):
            joined_errors = ", ".join(self._safe_text(item) for item in errors_value if self._safe_text(item))
            if joined_errors:
                return joined_errors
        if isinstance(errors_value, dict):
            collected_messages: List[str] = []
            for item in errors_value.values():
                if isinstance(item, list):
                    collected_messages.extend(self._safe_text(entry) for entry in item if self._safe_text(entry))
                else:
                    clean_item = self._safe_text(item)
                    if clean_item:
                        collected_messages.append(clean_item)
            if collected_messages:
                return ", ".join(collected_messages)

        return ""