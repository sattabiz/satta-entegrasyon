import pyodbc
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ServiceReaderConfig:
    server: str = "127.0.0.1"
    database: str = "TIGERDB"
    db_username: str = ""
    db_password: str = ""
    username: str = ""
    password: str = ""
    firm_no: int = 1
    period_no: int = 1
    use_mock_data: bool = False

    def __post_init__(self):
        self.server = str(self.server).strip()
        self.database = str(self.database).strip()
        self.db_username = str(self.db_username).strip()
        self.db_password = str(self.db_password)
        self.username = str(self.username).strip()
        self.password = str(self.password)

        if not self.db_username and self.username:
            self.db_username = self.username
        if not self.db_password and self.password:
            self.db_password = self.password

        self.firm_no = self._coerce_int(self.firm_no, "firm_no")
        self.period_no = self._coerce_int(self.period_no, "period_no")

    @staticmethod
    def _coerce_int(value, field_name: str) -> int:
        if isinstance(value, int):
            return value

        text_value = str(value).strip()
        if not text_value:
            raise ValueError(f"{field_name} boş olamaz.")

        try:
            return int(text_value)
        except ValueError as exc:
            raise ValueError(f"{field_name} sayısal olmalıdır: {value}") from exc


class ServiceReader:
    """
    Logo hizmet verilerini (Alınan Hizmetler) okumak için veri erişim sınıfı.
    """

    def __init__(self, config: Optional[ServiceReaderConfig] = None):
        self.config = config or ServiceReaderConfig()

    def read_services(self) -> Tuple[List[str], List[Tuple]]:
        return self._read_from_sql()

    def _build_connection_string(self) -> str:
        if self.config.db_username:
            return (
                f"DRIVER={{SQL Server}};"
                f"SERVER={self.config.server};"
                f"DATABASE={self.config.database};"
                f"UID={self.config.db_username};"
                f"PWD={self.config.db_password};"
            )

        return (
            f"DRIVER={{SQL Server}};"
            f"SERVER={self.config.server};"
            f"DATABASE={self.config.database};"
            "Trusted_Connection=yes;"
        )

    def _read_from_sql(self) -> Tuple[List[str], List[Tuple]]:
        conn_str = self._build_connection_string()
        firm_str = f"{self.config.firm_no:03d}"
        srvcard_table = f"LG_{firm_str}_SRVCARD"
        srvunita_table = f"LG_{firm_str}_SRVUNITA"
        unitsetl_table = f"LG_{firm_str}_UNITSETL"

        query = f"""
        SELECT 
            S.CODE AS 'Hizmet Kodu',
            S.DEFINITION_ AS 'Hizmet Açıklaması',
            CASE S.CARDTYPE 
                WHEN 1 THEN 'Alınan Hizmet' 
                WHEN 2 THEN 'Verilen Hizmet' 
            END AS 'Hizmet Tipi',
            U.CODE AS 'Birim',
            S.VAT AS 'KDV Oranı',
            CASE S.ACTIVE
                WHEN 0 THEN 'Kullanımda'
                WHEN 1 THEN 'Kullanım Dışı'
            END AS 'Kullanım Durumu'
        FROM {srvcard_table} S WITH (NOLOCK)
        LEFT JOIN {srvunita_table} SU WITH (NOLOCK) ON S.LOGICALREF = SU.SRVREF AND SU.LINENR = 1
        LEFT JOIN {unitsetl_table} U WITH (NOLOCK) ON SU.UNITLINEREF = U.LOGICALREF
        WHERE S.CARDTYPE = 1 AND ISNULL(S.ACTIVE, 0) = 0
        ORDER BY S.LOGICALREF DESC
        """

        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                headers = [column[0] for column in cursor.description]
                rows = cursor.fetchall()

                result = []
                for row in rows:
                    normalized_row = tuple(str(val).strip() if val is not None else "" for val in row)
                    result.append(normalized_row)

                return headers, result

        except pyodbc.Error as exc:
            error_text = str(exc)
            if "Login failed for user" in error_text:
                raise Exception("Logo SQL Server oturumu açılamadı. Lütfen ayarları kontrol edin.")
            if "Invalid object name" in error_text:
                raise Exception(f"Tablo bulunamadı. Firma No ayarını kontrol edin.\nTablo: {srvcard_table}")
            raise Exception(f"Logo hizmet sorgu hatası:\n{error_text}")
        except Exception as exc:
            raise Exception(f"Logo hizmet sorgu hatası:\n{str(exc)}")


