import pyodbc
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class SupplierReaderConfig:
    server: str = "127.0.0.1"
    database: str = "TIGERDB"
    username: str = "sa"
    password: str = ""
    firm_no: int = 1

class SupplierReader:
    def __init__(self, config: Optional[SupplierReaderConfig] = None):
        self.config = config or SupplierReaderConfig()

    def get_suppliers(self) -> List[Tuple[str, str, str, str, str, str]]:
        """
        Logo veritabanından pyodbc aracılığıyla tedarikçi kartlarını (CLCARD) getirir.
        Dönen alan dizilimi: (kod, unvan, ilgili_kisi, telefon, e-posta, vergi_no)
        """
        raw_rows = self._read_from_sql()
        return [self._normalize_row(row) for row in raw_rows]

    def _read_from_sql(self) -> List[Tuple[str, str, str, str, str, str]]:
        # ODBC sürücüsünü sistemde var olan genel bir SQL Server sürücüsü olarak varsayıyoruz
        # Kullanıcının sistemine göre ODBC Driver 17 veya genel SQL Server sürücüsü denenebilir
        driver_name = "{ODBC Driver 17 for SQL Server}"
        # Fallback for classic sql server driver if 17 is missing in some environments
        # We can just attempt "SQL Server" if 17 fails but for now try generic or specific string
        # using the generic "SQL Server" might be more universally available out of the box on Windows
        conn_str = (
            f"DRIVER={{SQL Server}};"
            f"SERVER={self.config.server};"
            f"DATABASE={self.config.database};"
            f"UID={self.config.username};"
            f"PWD={self.config.password};"
        )
        
        table_name = f"LG_{self.config.firm_no:03d}_CLCARD"
        
        query = f"""
        SELECT 
            CODE,
            DEFINITION_,
            '' AS contact_name,
            CASE WHEN TELNRS1 IS NOT NULL AND LTRIM(RTRIM(TELNRS1)) <> '' THEN TELNRS1 ELSE TELNRS2 END AS phone,
            EMAILADDR,
            TAXNR
        FROM {table_name}
        ORDER BY LOGICALREF DESC
        """
        
        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                
                result = []
                for r in rows:
                    code = str(r[0]) if r[0] is not None else ""
                    name = str(r[1]) if r[1] is not None else ""
                    contact = str(r[2]) if r[2] is not None else ""
                    phone = str(r[3]) if r[3] is not None else ""
                    email = str(r[4]) if r[4] is not None else ""
                    taxnr = str(r[5]) if r[5] is not None else ""
                    
                    result.append((code, name, contact, phone, email, taxnr))
                return result
        except Exception as e:
            raise Exception(f"Logo veritabanı bağlantı veya sorgu hatası:\n{str(e)}")

    def _normalize_row(self, row: Tuple[str, str, str, str, str, str]) -> Tuple[str, str, str, str, str, str]:
        return (
            str(row[0]).strip(),
            str(row[1]).strip(),
            str(row[2]).strip(),
            str(row[3]).strip(),
            str(row[4]).strip(),
            str(row[5]).strip()
        )