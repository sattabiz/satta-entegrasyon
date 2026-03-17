
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass
class SupplierReaderConfig:
    server: str = "127.0.0.1"
    database: str = "TIGERDB"
    username: str = "sa"
    password: str = ""
    firm_no: int = 1


class SupplierReader:
    def __init__(self, config: SupplierReaderConfig | None = None):
        self.config = config or SupplierReaderConfig()

    def get_suppliers(self) -> List[Tuple[str, str, str, str, str, str]]:
        """
        Şimdilik mock veri döner.
        Sonraki aşamada bu metodun içine Logo SQL okuması eklenecek.
        Dönen alan sırası UI tablosu ile uyumlu olmalı:
        (kod, unvan, ilgili_kisi, email, vergi_no, durum)
        """
        raw_rows = self._read_mock_rows()
        return [self._normalize_row(row) for row in raw_rows]

    def _read_mock_rows(self) -> Sequence[Tuple[str, str, str, str, str, str]]:
        return [
            ("SUP001", "Örnek Tedarikçi A.Ş.", "Ahmet Yılmaz", "ahmet@example.com", "1234567890", "Hazır"),
            ("SUP002", "Deneme Tedarikçi Ltd.", "Ayşe Demir", "ayse@example.com", "0987654321", "Bekliyor"),
            ("SUP003", "Atlas Tedarik", "Mehmet Kaya", "mehmet@example.com", "4567891230", "Hata"),
            ("SUP004", "Beta Endüstri", "Zeynep Arslan", "zeynep@example.com", "5544332211", "Hazır"),
        ]

    def _normalize_row(self, row: Tuple[str, str, str, str, str, str]) -> Tuple[str, str, str, str, str, str]:
        code, name, contact_name, email, tax_number, status = row
        return (
            str(code).strip(),
            str(name).strip(),
            str(contact_name).strip(),
            str(email).strip(),
            str(tax_number).strip(),
            str(status).strip(),
        )