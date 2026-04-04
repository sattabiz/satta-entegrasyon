

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from Common.path_helper import project_path, user_data_path


class LogoBridgeRunner:
    def __init__(self, bridge_executable_path: Optional[str] = None):
        self.bridge_executable_path = bridge_executable_path or self._resolve_bridge_executable_path()

    def run_invoice_transfer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Bridge payload sözlük tipinde olmalıdır.")

        payload_file_path = self._write_payload_file(payload)

        try:
            completed_process = subprocess.run(
                [self.bridge_executable_path, str(payload_file_path)],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Logo bridge çalıştırılamadı. Dosya bulunamadı: {self.bridge_executable_path}"
            ) from exc
        except OSError as exc:
            raise RuntimeError(f"Logo bridge başlatılamadı: {exc}") from exc
        finally:
            self._cleanup_payload_file(payload_file_path)

        stdout_text = (completed_process.stdout or "").strip()
        stderr_text = (completed_process.stderr or "").strip()

        result = self._parse_bridge_output(stdout_text)

        if not result:
            result = {
                "is_success": False,
                "message": "Logo bridge geçerli bir JSON sonuç döndürmedi.",
                "error_code": "BRIDGE_OUTPUT_INVALID",
                "details": {
                    "stdout": stdout_text,
                    "stderr": stderr_text,
                    "return_code": str(completed_process.returncode),
                },
            }
            return result

        details = result.setdefault("details", {})
        if not isinstance(details, dict):
            details = {}
            result["details"] = details

        details.setdefault("return_code", str(completed_process.returncode))
        if stderr_text:
            details.setdefault("stderr", stderr_text)

        if completed_process.returncode != 0 and result.get("is_success") is True:
            result["is_success"] = False
            result["message"] = result.get("message") or "Logo bridge hata kodu ile sonlandı."
            result.setdefault("error_code", "BRIDGE_PROCESS_FAILED")

        return result

    def _resolve_bridge_executable_path(self) -> str:
        candidate_paths = [
            project_path("LogoBridge", "publish", "LogoBridge.Console.exe"),
            project_path("LogoBridge", "src", "LogoBridge.Console", "bin", "x86", "Debug", "net8.0-windows", "LogoBridge.Console.exe"),
            project_path("LogoBridge", "src", "LogoBridge.Console", "bin", "x86", "Release", "net8.0-windows", "LogoBridge.Console.exe"),
            user_data_path("LogoBridge", "LogoBridge.Console.exe"),
        ]

        for candidate_path in candidate_paths:
            if candidate_path.exists():
                return str(candidate_path)

        return str(candidate_paths[0])

    def _write_payload_file(self, payload: Dict[str, Any]) -> Path:
        temp_directory = Path(tempfile.mkdtemp(prefix="satta_logo_bridge_"))
        payload_file_path = temp_directory / "invoice_payload.json"
        payload_file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload_file_path

    def _cleanup_payload_file(self, payload_file_path: Path) -> None:
        try:
            if payload_file_path.exists():
                payload_file_path.unlink()
            parent_directory = payload_file_path.parent
            if parent_directory.exists():
                parent_directory.rmdir()
        except OSError:
            pass

    def _parse_bridge_output(self, stdout_text: str) -> Dict[str, Any]:
        if not stdout_text:
            return {}

        try:
            parsed_output = json.loads(stdout_text)
        except json.JSONDecodeError:
            return {}

        if not isinstance(parsed_output, dict):
            return {}

        return parsed_output