

import json
from typing import Any, Dict, Iterable, List

import requests

from Common.path_helper import user_data_path


class SattaSupplierPushConnector:
    SETTINGS_FILE = user_data_path("app_settings.json")
    SESSION_FILE = user_data_path("satta_session.json")

    def __init__(self):
        self.settings = self._load_settings()
        self.base_url = self._safe_text(self.settings.get("base_url"))
        self.username = self._safe_text(self.settings.get("username"))
        self.token = self._resolve_token()

    def push_supplier(self, supplier_data: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._build_payload([supplier_data])
        return self._post_suppliers(payload)

    def push_suppliers(self, suppliers: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        supplier_list = [supplier for supplier in suppliers if isinstance(supplier, dict)]
        if not supplier_list:
            raise ValueError("Gönderilecek tedarikçi listesi boş olamaz.")

        payload = self._build_payload(supplier_list)
        return self._post_suppliers(payload)

    def _build_payload(self, suppliers: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}

        for index, supplier in enumerate(suppliers):
            payload[str(index)] = {
                "invited_company": {
                    "name": self._safe_text(supplier.get("name"), "-"),
                    "invited_person": self._safe_text(supplier.get("invited_person")),
                    "phone": self._safe_text(supplier.get("phone")),
                    "invited_email": self._safe_text(supplier.get("invited_email")),
                    "tax_id": self._safe_text(supplier.get("tax_id")),
                    "erp_id": self._safe_text(supplier.get("erp_id")),
                }
            }

        return payload

    def _post_suppliers(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("Satta token bulunamadı. Önce ayarlardan giriş yapıp token al.")
        if not self.base_url:
            raise RuntimeError("Satta base URL bulunamadı. Ayarlar ekranından Satta bağlantı adresini kaydet.")

        url = self._build_push_url()
        headers = self._build_headers(self.token)

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"Satta tedarikçi gönderme isteği başarısız oldu: {exc}") from exc

        response_json = self._safe_json(response)

        if not response.ok:
            message = self._extract_error_message(response_json)
            if not message:
                message = response.text.strip()
            raise RuntimeError(
                f"Satta tedarikçileri oluşturamadı. HTTP {response.status_code}. {message}"
            )

        return response_json

    def _build_push_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/invited_companies"

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