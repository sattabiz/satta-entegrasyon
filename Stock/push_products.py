

import json
from typing import Any, Dict, Iterable, List

import requests

from Common.path_helper import project_path


class SattaProductPushConnector:
    SETTINGS_FILE = project_path("Settings", "app_settings.json")
    SESSION_FILE = project_path("Settings", "satta_session.json")

    def __init__(self):
        self.settings = self._load_settings()
        self.base_url = self._safe_text(self.settings.get("base_url"), "https://test.satta.biz")
        self.username = self._safe_text(self.settings.get("username"))
        self.token = self._resolve_token()

    def push_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._build_payload([product_data])
        return self._post_products(payload)

    def push_products(self, products: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        product_list = [product for product in products if isinstance(product, dict)]
        if not product_list:
            raise ValueError("Gönderilecek ürün listesi boş olamaz.")

        payload = self._build_payload(product_list)
        return self._post_products(payload)

    def _build_payload(self, products: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}

        for index, product in enumerate(products):
            payload[str(index)] = {
                "company_product": {
                    "product_name": self._safe_text(product.get("product_name"), "-"),
                    "description": self._safe_text(product.get("description")),
                    "category_text": self._safe_text(product.get("category_text")),
                    "erp_id": self._safe_text(product.get("erp_id")),
                    "unit": self._safe_text(product.get("unit"), "AD"),
                    "tax_rate": self._to_number(product.get("tax_rate"), default=0),
                    "price": self._to_number(product.get("price"), default=0),
                    "currency": self._safe_text(product.get("currency"), "TRY"),
                    "max_quantity": self._to_number(product.get("max_quantity"), default=0),
                    "min_quantity": self._to_number(product.get("min_quantity"), default=0),
                    "quantity_tolerance": self._to_number(product.get("quantity_tolerance"), default=0),
                    "notes": self._safe_text(product.get("notes")),
                    "cost_center_erp_ids": self._normalize_cost_center_ids(product.get("cost_center_erp_ids")),
                    "un_no": self._safe_text(product.get("un_no")),
                    "erp_code": self._safe_text(product.get("erp_code")),
                }
            }

        return payload

    def _post_products(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("Satta token bulunamadı. Önce ayarlardan giriş yapıp token al.")

        url = self._build_push_url()
        headers = self._build_headers(self.token)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"Satta ürün gönderme isteği başarısız oldu: {exc}") from exc

        response_json = self._safe_json(response)

        if not response.ok:
            message = self._extract_error_message(response_json)
            if not message:
                message = response.text.strip()
            raise RuntimeError(
                f"Satta ürünleri oluşturamadı. HTTP {response.status_code}. {message}"
            )

        return response_json

    def _build_push_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/company_products"

    def _build_headers(self, token: str) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": token,
            "Content-Type": "application/json",
        }

    def _load_settings(self) -> Dict[str, Any]:
        if not self.SETTINGS_FILE.exists():
            return {}

        try:
            data = json.loads(self.SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

        satta_settings = data.get("satta", {})
        return satta_settings if isinstance(satta_settings, dict) else {}

    def _resolve_token(self) -> str:
        token_from_settings = self._safe_text(self.settings.get("token"))
        if token_from_settings:
            return token_from_settings

        if not self.SESSION_FILE.exists():
            return ""

        try:
            session_data = json.loads(self.SESSION_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return ""

        if not isinstance(session_data, dict):
            return ""

        username_key = self.username.lower()
        user_session = session_data.get(username_key, {}) if username_key else {}
        if isinstance(user_session, dict):
            token_from_session = self._safe_text(user_session.get("token"))
            if token_from_session:
                return token_from_session

        for value in session_data.values():
            if isinstance(value, dict):
                token_from_session = self._safe_text(value.get("token"))
                if token_from_session:
                    return token_from_session

        return ""

    def _normalize_cost_center_ids(self, value: Any) -> List[str]:
        if value is None:
            return []

        if isinstance(value, list):
            normalized_values: List[str] = []
            for item in value:
                text = self._safe_text(item)
                if text:
                    normalized_values.append(text)
            return normalized_values

        text = self._safe_text(value)
        return [text] if text else []

    def _to_number(self, value: Any, default: int | float = 0) -> int | float:
        if value is None or value == "":
            return default

        try:
            number = float(value)
        except (TypeError, ValueError):
            return default

        if number.is_integer():
            return int(number)
        return number

    def _safe_json(self, response: requests.Response) -> Dict[str, Any]:
        try:
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {"data": payload}
        except ValueError:
            return {}

    def _extract_error_message(self, response_json: Dict[str, Any]) -> str:
        message_keys = ["response_message", "message", "error", "error_message", "detail"]
        for key in message_keys:
            value = response_json.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    @staticmethod
    def _safe_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default