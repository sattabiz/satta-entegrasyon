import pyodbc
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class ProductReaderConfig:
    server: str = "127.0.0.1"
    database: str = "TIGERDB"
    db_username: str = ""
    db_password: str = ""
    username: str = ""
    password: str = ""
    firm_no: int = 1
    period_no: int = 1

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


class ProductReader:
    """
    Logo ürün verilerini okumak için başlangıç katmanı.

    Şimdilik SupplierReader tarafındaki mantığa benzer şekilde:
    - mock veri desteği var
    - SQL bağlantısı ayarlardan gelen Logo bilgileriyle kuruluyor
    - UI tarafına uygun sabit kolon sıralı tuple listesi dönüyor

    Dönen tuple sırası (UI tablosuna uyumlu):
        0 -> ürün kodu
        1 -> ürün adı
        2 -> kategori
        3 -> birim
        4 -> kaynak miktar
        5 -> hedef miktar
        6 -> KDV oranı
        7 -> kaynak fiyat
        8 -> kaynak döviz
        9 -> hedef fiyat
        10 -> hedef döviz
        11 -> açıklama
        12 -> durum

    Notlar:
    - Ürünler sayfasındaki gerçek kolonlar netleşince `_normalize_row` ve SQL sorgusu revize edilecek.
    - Kategori, maliyet merkezi, fiyat listesi gibi detaylar daha sonra genişletilebilir.
    """

    def __init__(self, config: Optional[ProductReaderConfig] = None):
        self.config = config or ProductReaderConfig()

    def read_products(self) -> Tuple[List[str], List[Tuple]]:
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

    def _build_items_table_name(self) -> str:
        firm_str = f"{self.config.firm_no:03d}"
        return f"LG_{firm_str}_ITEMS"

    def _read_from_sql(self) -> Tuple[List[str], List[Tuple]]:
        conn_str = self._build_connection_string()
        items_table = self._build_items_table_name()
        firm_str = f"{self.config.firm_no:03d}"
        unitsetl_table = f"LG_{firm_str}_UNITSETL"

        query = f"""
        SELECT
            ISNULL(I.CODE, '') AS 'Ürün Kodu',
            ISNULL(I.NAME, '') AS 'Ürün Adı',
            ISNULL(U.CODE, '') AS 'Birim',
            CAST(ISNULL(I.VAT, 0) AS NVARCHAR(10)) AS 'KDV Oranı',
            CASE I.ACTIVE
                WHEN 0 THEN 'Kullanımda'
                WHEN 1 THEN 'Kullanım Dışı'
            END AS 'Kullanım Durumu'
        FROM {items_table} I WITH (NOLOCK)
        OUTER APPLY (
            SELECT TOP 1 CODE 
            FROM {unitsetl_table} WITH (NOLOCK) 
            WHERE UNITSETREF = I.UNITSETREF 
            ORDER BY LINENR
        ) U
        WHERE ISNULL(I.ACTIVE, 0) = 0
        ORDER BY I.LOGICALREF DESC
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
                auth_mode_text = "SQL Authentication" if self.config.db_username else "Windows Authentication"
                raise Exception(
                    "Logo ürün sorgusu giriş hatası:\n"
                    "SQL Server oturumu açılamadı.\n\n"
                    "Bu genelde şu nedenlerle olur:\n"
                    "- DB kullanıcı adı veya DB şifre yanlış\n"
                    "- SQL Server'da SQL Authentication kapalı\n"
                    "- Yanlış sunucuya veya yanlış veritabanına bağlanılıyor\n"
                    "- Kullanıcı hesabının ilgili veritabanına yetkisi yok\n\n"
                    f"Bağlantı bilgileri:\n"
                    f"Server: {self.config.server}\n"
                    f"Database: {self.config.database}\n"
                    f"Authentication: {auth_mode_text}\n"
                    f"DB Username: {self.config.db_username or '(Windows kullanıcısı)'}"
                )

            if "Invalid object name" in error_text:
                raise Exception(
                    "Logo ürün sorgu hatası:\n"
                    f"'{items_table}' tablosu bulunamadı.\n\n"
                    "Bu genelde şu nedenlerle olur:\n"
                    "- Ayarlardaki Firma No yanlış\n"
                    "- Yanlış Logo veritabanına bağlanılıyor\n"
                    "- İlgili firmaya ait ürün tablosu bu veritabanında yok\n\n"
                    f"Bağlantı bilgileri:\n"
                    f"Server: {self.config.server}\n"
                    f"Database: {self.config.database}\n"
                    f"Firma No: {self.config.firm_no}\n"
                    f"Sorgulanan tablo: {items_table}"
                )

            raise Exception(f"Logo ürün bağlantı veya sorgu hatası:\n{error_text}")

        except Exception as exc:
            raise Exception(f"Logo ürün bağlantı veya sorgu hatası:\n{str(exc)}")
