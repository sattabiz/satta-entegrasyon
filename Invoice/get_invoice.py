import json
import requests
import base64
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
from Common.path_helper import user_data_path


InvoiceUiRow = Tuple[str, str, str, str, str, str, str, str]
InvoiceDetailRow = Tuple[str, str, str, str, str, str, str]
InvoiceRawMap = Dict[int, Dict[str, Any]]


def is_token_expired(token: str) -> bool:
    if not token:
        return True

    try:
        parts = token.split('.')
        if len(parts) != 3:
            return True
        payload_b64 = parts[1]
        payload_b64 += '=' * (4 - len(payload_b64) % 4)
        payload_json = base64.b64decode(payload_b64).decode('utf-8')
        payload = json.loads(payload_json)
        exp = payload.get('exp')
        if exp:
            return time.time() >= exp - 60
    except Exception:
        pass
    return True


@dataclass
class SattaInvoiceConfig:
    base_url: str = ""
    username: str = ""
    password: str = ""
    token: str = ""
    token_storage_file: str = "satta_session.json"

class SattaInvoiceConnector:
    def __init__(self, config: Optional[SattaInvoiceConfig] = None):
        self.config = config or SattaInvoiceConfig()

    def get_invoices_for_ui(self) -> Tuple[List[InvoiceUiRow], Dict[str, List[InvoiceDetailRow]], Dict[str, int], InvoiceRawMap]:
        response = self._read_invoice_response()
        invoices = response.get("invoices", [])

        invoice_rows: List[InvoiceUiRow] = []
        invoice_details: Dict[str, List[InvoiceDetailRow]] = {}
        invoice_id_map: Dict[str, int] = {}
        invoice_raw_map: InvoiceRawMap = {}

        for invoice in invoices:
            if not isinstance(invoice, dict):
                continue
            invoice_row = self._map_invoice_row(invoice)
            invoice_rows.append(invoice_row)
            invoice_details[invoice_row[0]] = self._map_invoice_details(invoice)

            invoice_id = self._normalize_invoice_id(invoice.get("invoice_id"))
            if invoice_id is not None:
                invoice_id_map[invoice_row[0]] = invoice_id
                invoice_raw_map[invoice_id] = dict(invoice)

        return invoice_rows, invoice_details, invoice_id_map, invoice_raw_map

    def get_categories(self) -> List[Dict[str, Any]]:
        token = self.ensure_token()
        url = f"{self.config.base_url.rstrip('/')}/api/v1/list_categories"
        headers = self._build_auth_headers(token)

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"Satta kategori isteği başarısız oldu: {exc}") from exc

        response_json = self._safe_json(response)
        if not response.ok:
            message = self._extract_error_message(response_json)
            if not message:
                message = response.text.strip()
            raise RuntimeError(
                f"Satta kategorileri alınamadı. HTTP {response.status_code}. {message}"
            )

        items = response_json.get("categories")
        if not isinstance(items, list):
            items = []

        categories = []
        for item in items:
            if not isinstance(item, dict):
                continue

            name = ""
            for key in ["name", "title", "label", "category_name"]:
                val = str(item.get(key, "")).strip()
                if val:
                    name = val
                    break

            erp_code = str(item.get("category_erp_code") or item.get("category_erp_id") or item.get("erp_code") or "").strip()
            category_id = item.get("id")
            category_type = str(item.get("category_type", "")).strip()

            categories.append({
                "id": category_id,
                "name": name,
                "category_erp_code": erp_code,
                "category_type": category_type
            })

        return categories

    def ensure_token(self, force_refresh: bool = False) -> str:
        if not force_refresh:
            current_token = self.get_saved_token()
            if current_token and not is_token_expired(current_token):
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
            cost_center_name = self._extract_cost_center_name(product, invoice)

            detail_rows.append(
                (
                    product_code,
                    product_name,
                    description,
                    self._format_quantity(product.get("shipped_amount")),
                    unit,
                    self._format_money(product.get("price")),
                    cost_center_name,
                )
            )

        return detail_rows

    def _extract_cost_center_name(self, product: Dict[str, Any], invoice: Optional[Dict[str, Any]] = None) -> str:
        if isinstance(product, dict):
            val = product.get("cost_center_name")
            if val is not None and str(val).strip():
                return str(val).strip()

            cost_center = product.get("cost_center")
            if isinstance(cost_center, dict):
                for key in ["name", "cost_center_name", "title", "label"]:
                    name_val = cost_center.get(key)
                    if name_val is not None and str(name_val).strip():
                        return str(name_val).strip()
            elif cost_center is not None and str(cost_center).strip():
                return str(cost_center).strip()

        if isinstance(invoice, dict):
            val_inv = invoice.get("cost_center_name")
            if val_inv is not None and str(val_inv).strip():
                return str(val_inv).strip()

            cost_center_inv = invoice.get("cost_center")
            if isinstance(cost_center_inv, dict):
                for key in ["name", "cost_center_name", "title", "label"]:
                    name_val = cost_center_inv.get(key)
                    if name_val is not None and str(name_val).strip():
                        return str(name_val).strip()
            elif cost_center_inv is not None and str(cost_center_inv).strip():
                return str(cost_center_inv).strip()

        return "-"

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
        return user_data_path(self.config.token_storage_file)

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

    def _normalize_invoice_id(self, value: Any) -> Optional[int]:
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