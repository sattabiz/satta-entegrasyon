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
    period_no: int = 1

    def __post_init__(self):
        self.server = str(self.server).strip()
        self.database = str(self.database).strip()
        self.username = str(self.username).strip()
        self.password = str(self.password)
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

class SupplierReader:
    def __init__(self, config: Optional[SupplierReaderConfig] = None):
        self.config = config or SupplierReaderConfig()

    def get_suppliers(self) -> List[Tuple[str, str, str, str, str, str, str]]:
        """
        Logo veritabanından pyodbc aracılığıyla tedarikçi kartlarını (CLCARD) getirir.
        Dönen alan dizilimi: (kod, unvan, ilgili_kisi, telefon, e-posta, vergi_no, son_fatura_turu)
        """
        raw_rows = self._read_from_sql()
        return [self._normalize_row(row) for row in raw_rows]

    def _build_table_name(self) -> str:
        firm_str = f"{self.config.firm_no:03d}"
        return f"LG_{firm_str}_CLCARD"

    def _build_connection_string(self) -> str:
        if self.config.username:
            return (
                f"DRIVER={{SQL Server}};"
                f"SERVER={self.config.server};"
                f"DATABASE={self.config.database};"
                f"UID={self.config.username};"
                f"PWD={self.config.password};"
            )

        return (
            f"DRIVER={{SQL Server}};"
            f"SERVER={self.config.server};"
            f"DATABASE={self.config.database};"
            "Trusted_Connection=yes;"
        )

    def _read_from_sql(self) -> List[Tuple[str, str, str, str, str, str, str]]:
        # ODBC sürücüsünü sistemde var olan genel bir SQL Server sürücüsü olarak varsayıyoruz.
        # Kullanıcı adı girildiyse SQL Authentication, boş bırakıldıysa Windows Authentication kullanılır.
        conn_str = self._build_connection_string()
        
        # CLCARD tablosu dönemden bağımsız olduğu için sadece firma numarasını kullanır.
        # Döneme bağlı tablolar (ör: STLINE, INVOICE) için: f"LG_{firm_str}_{period_str}_INVOICE"
        table_name = self._build_table_name()
        clfline_table_name = f"LG_{self.config.firm_no:03d}_{self.config.period_no:02d}_CLFLINE"
        query = f"""
        SELECT 
            C.CODE,
            C.DEFINITION_,
            '' AS contact_name,
            CASE WHEN C.TELNRS1 IS NOT NULL AND LTRIM(RTRIM(C.TELNRS1)) <> '' THEN C.TELNRS1 ELSE C.TELNRS2 END AS phone,
            C.EMAILADDR,
            C.TAXNR,
            CASE LF.TRCODE
                WHEN 31 THEN 'Satınalma Faturası'
                WHEN 34 THEN 'Alınan Hizmet Faturası'
                ELSE ''
            END AS last_invoice_type
        FROM {table_name} C
        OUTER APPLY (
            SELECT TOP 1 F.TRCODE
            FROM {clfline_table_name} F WITH (NOLOCK)
            WHERE F.CLIENTREF = C.LOGICALREF
              AND F.TRCODE IN (31, 34)
            ORDER BY F.DATE_ DESC, F.LOGICALREF DESC
        ) LF
        WHERE C.CARDTYPE IN (2, 3)
        ORDER BY C.LOGICALREF DESC
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
                    last_invoice_type = str(r[6]) if r[6] is not None else ""
                    
                    result.append((code, name, contact, phone, email, taxnr, last_invoice_type))
                return result
        except pyodbc.Error as e:
            error_text = str(e)
            if "Login failed for user" in error_text:
                auth_mode_text = "SQL Authentication" if self.config.username else "Windows Authentication"
                raise Exception(
                    "Logo veritabanı giriş hatası:\n"
                    "SQL Server oturumu açılamadı.\n\n"
                    "Bu genelde şu nedenlerle olur:\n"
                    "- Kullanıcı adı veya şifre yanlış\n"
                    "- SQL Server'da SQL Authentication kapalı\n"
                    "- Yanlış sunucuya veya yanlış veritabanına bağlanılıyor\n"
                    "- Kullanıcı hesabının ilgili veritabanına yetkisi yok\n\n"
                    f"Bağlantı bilgileri:\n"
                    f"Server: {self.config.server}\n"
                    f"Database: {self.config.database}\n"
                    f"Authentication: {auth_mode_text}\n"
                    f"Username: {self.config.username or '(Windows kullanıcısı)'}"
                )
            if "Invalid object name" in error_text:
                raise Exception(
                    "Logo veritabanı sorgu hatası:\n"
                    f"'{table_name}' veya '{clfline_table_name}' tablosu bulunamadı.\n\n"
                    "Bu genelde şu nedenlerle olur:\n"
                    "- Ayarlardaki Firma No yanlış\n"
                    "- Ayarlardaki Dönem No yanlış\n"
                    "- Yanlış Logo veritabanına bağlanılıyor\n"
                    "- İlgili firmaya / döneme ait tablo bu veritabanında yok\n\n"
                    f"Bağlantı bilgileri:\n"
                    f"Server: {self.config.server}\n"
                    f"Database: {self.config.database}\n"
                    f"Firma No: {self.config.firm_no}\n"
                    f"Dönem No: {self.config.period_no}\n"
                    f"Sorgulanan cari tablo: {table_name}\n"
                    f"Sorgulanan hareket tablo: {clfline_table_name}"
                )
            raise Exception(f"Logo veritabanı bağlantı veya sorgu hatası:\n{error_text}")
        except Exception as e:
            raise Exception(f"Logo veritabanı bağlantı veya sorgu hatası:\n{str(e)}")

    def _normalize_row(self, row: Tuple[str, str, str, str, str, str, str]) -> Tuple[str, str, str, str, str, str, str]:
        return (
            str(row[0]).strip(),
            str(row[1]).strip(),
            str(row[2]).strip(),
            str(row[3]).strip(),
            str(row[4]).strip(),
            str(row[5]).strip(),
            str(row[6]).strip()
        )