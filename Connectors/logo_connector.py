from dataclasses import dataclass
from typing import List, Sequence, Tuple


SupplierUiRow = Tuple[str, str, str, str, str, str, str]


@dataclass
class LogoConnectionConfig:
    server: str = "127.0.0.1"
    database: str = "TIGERDB"
    username: str = "sa"
    password: str = ""
    firm_no: int = 1
    use_mock_data: bool = True


class LogoConnector:
    def __init__(self, config: LogoConnectionConfig | None = None):
        self.config = config or LogoConnectionConfig()

    def get_suppliers_for_ui(self) -> List[SupplierUiRow]:
        raw_rows = self._read_supplier_rows()
        return [self._map_supplier_row_for_ui(row) for row in raw_rows]

    def _read_supplier_rows(self) -> Sequence[dict]:
        if self.config.use_mock_data:
            return self._read_mock_supplier_rows()

        return self._read_suppliers_from_sql()

    def _read_mock_supplier_rows(self) -> Sequence[dict]:
        return [
            {
                "supplier_code": "SUP001",
                "supplier_name": "Örnek Tedarikçi A.Ş.",
                "contact_name": "Ahmet Yılmaz",
                "phone_number": "553234567",
                "email": "ahmet@example.com",
                "tax_number": "1234567890",
            },
            {
                "supplier_code": "SUP002",
                "supplier_name": "Deneme Tedarikçi Ltd.",
                "contact_name": "Ayşe Demir",
                "phone_number": "5553987654",
                "email": "",
                "tax_number": "0987654321",
            },
            {
                "supplier_code": "SUP003",
                "supplier_name": "Atlas Tedarik",
                "contact_name": "Mehmet Kaya",
                "phone_number": "5553123456",
                "email": "mehmet@example.com",
                "tax_number": "",
            },
            {
                "supplier_code": "SUP004",
                "supplier_name": "Beta Endüstri",
                "contact_name": "Zeynep Arslan",
                "phone_number": "5535654321",
                "email": "zeynep@example.com",
                "tax_number": "5544332211",
            },
            {
                "supplier_code": "SUP005",
                "supplier_name": "Deneme Tedarik",
                "contact_name": "Mehmet Kaya",
                "phone_number": "5553987654",
                "email": "mehmet@example.com",
                "tax_number": "",
            },
        ]

    def _read_suppliers_from_sql(self) -> Sequence[dict]:
        raise NotImplementedError(
            "Gerçek Logo SQL okuması henüz bağlanmadı. "
            "Ayarlar ekranından bağlantı bilgileri alındıktan sonra bu metod pyodbc ile doldurulmalı."
        )

    def build_supplier_query(self) -> str:
        table_name = self._build_supplier_table_name()
        return f"""
SELECT
    C.CODE AS supplier_code,
    C.DEFINITION_ AS supplier_name,
    '' AS contact_name,
    C.TELNRS1 AS phone_number,
    '' AS email,
    C.TAXNR AS tax_number
FROM {table_name} C
ORDER BY C.LOGICALREF DESC
""".strip()

    def _build_supplier_table_name(self) -> str:
        return f"LG_{self.config.firm_no:03d}_CLCARD"

    def _map_supplier_row_for_ui(self, row: dict) -> SupplierUiRow:
        supplier_code = self._safe_text(row.get("supplier_code"))
        supplier_name = self._safe_text(row.get("supplier_name"))
        contact_name = self._safe_text(row.get("contact_name"))
        phone_number = self._safe_text(row.get("phone_number"))
        email = self._safe_text(row.get("email"))
        tax_number = self._safe_text(row.get("tax_number"))
        status = self._build_supplier_status(
            supplier_name=supplier_name,
            email=email,
            phone_number=phone_number,
            tax_number=tax_number,
        )

        return (
            supplier_code,
            supplier_name,
            contact_name,
            phone_number,
            email,
            tax_number,
            status,
        )

    def _build_supplier_status(self, supplier_name: str, email: str, phone_number: str, tax_number: str) -> str:
        if not supplier_name:
            return "Hata"

        if not tax_number or not email or not phone_number:
            return "Bekliyor"

        return "Hazır"

    @staticmethod
    def _safe_text(value) -> str:
        if value is None:
            return ""
        return str(value).strip()