import json
from typing import Any, Dict, List, TypedDict

import requests

from Common.path_helper import user_data_path


class CostCenterOption(TypedDict):
    name: str
    erp_id: str


class SattaCostCenterConnector:
    SETTINGS_FILE = user_data_path("app_settings.json")
    SESSION_FILE = user_data_path("satta_session.json")

    def __init__(self):
        self.settings = self._load_settings()
        self.base_url = self._safe_text(self.settings.get("base_url"), "https://test.satta.biz")
        self.username = self._safe_text(self.settings.get("username"))
        self.token = self._resolve_token()

    def get_cost_centers(self) -> List[CostCenterOption]:
        response_json = self._read_cost_center_response()
        return self._extract_cost_centers(response_json)

    def _read_cost_center_response(self) -> Dict[str, Any]:
        if not self.token:
            raise RuntimeError("Satta token bulunamadı. Önce ayarlardan giriş yapıp token al.")

        url = self._build_cost_center_url()
        headers = self._build_headers(self.token)

        try:
            response = requests.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            raise RuntimeError(f"Satta masraf merkezi isteği başarısız oldu: {exc}") from exc

        response_json = self._safe_json(response)

        if not response.ok:
            message = self._extract_error_message(response_json)
            if not message:
                message = response.text.strip()
            raise RuntimeError(
                f"Satta masraf merkezleri alınamadı. HTTP {response.status_code}. {message}"
            )

        return response_json

    def _extract_cost_centers(self, response_json: Dict[str, Any]) -> List[CostCenterOption]:
        items = self._find_collection(response_json)
        values: List[CostCenterOption] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            name = self._first_text(item, ["name", "cost_center_name", "title", "label"])
            if not name:
                continue

            erp_id = self._safe_text(item.get("erp_id"))
            values.append({"name": name, "erp_id": erp_id})

        return self._unique_cost_centers(values)

    def _unique_cost_centers(self, values: List[CostCenterOption]) -> List[CostCenterOption]:
        seen = set()
        ordered: List[CostCenterOption] = []

        for value in values:
            name = self._safe_text(value.get("name"))
            erp_id = self._safe_text(value.get("erp_id"))
            key = (name.casefold(), erp_id.casefold())
            if key in seen:
                continue
            seen.add(key)
            ordered.append({"name": name, "erp_id": erp_id})

        return ordered

    def _find_collection(self, response_json: Dict[str, Any]) -> List[Any]:
        candidate_keys = [
            "cost_centers",
            "cost_center_list",
            "data",
            "items",
            "results",
            "response",
        ]

        for key in candidate_keys:
            value = response_json.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                for nested_key in ["cost_centers", "items", "results", "data"]:
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        return nested_value

        return []

    def _build_cost_center_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/api/v1/list_cost_centers"

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

    def _first_text(self, data: Dict[str, Any], keys: List[str]) -> str:
        for key in keys:
            value = self._safe_text(data.get(key))
            if value:
                return value
        return ""

    def _unique_preserve_order(self, values: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for value in values:
            normalized = value.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(value)
        return ordered

    @staticmethod
    def _safe_text(value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default