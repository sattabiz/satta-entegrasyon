import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
try:
    import pyodbc
except ImportError:
    pyodbc = None

logger = logging.getLogger(__name__)


@dataclass
class ConnectInvoiceRecord:
    logical_ref: int
    invoice_number: str = ""  # 16 haneli GİB Fatura No (DOCNR)
    ettn_guid: str = ""       # 36 haneli ETTN (REFERENCEID / FILENAME)
    supplier_vkn: str = ""    # Tedarikçi Vergi No (CLRETAILVKN / SENDER)
    supplier_name: str = ""   # Tedarikçi Ünvanı (SENDERTITLE)
    invoice_date: Optional[datetime] = None
    total_amount: float = 0.0
    tax_exclusive_total: float = 0.0
    tax_total: float = 0.0
    profile_id: int = 1      # 1: Temel, 2: Ticari
    status: int = 0
    approved: int = 0
    doc_ref: int = 0         # 0: Bekliyor, >0: ERP Ref


def format_connect_table_name(firm_val: Any) -> str:
    """
    Logo Connect veritabanındaki onay tablosu adını döndürür.
    Örn: 1 -> LG_001_APPROVAL
         "223_01" -> LG_223_01_APPROVAL
         "LG_223_01_APPROVAL" -> LG_223_01_APPROVAL
    """
    s = str(firm_val or "").strip()
    if s.upper().startswith("LG_"):
        s = s[3:]
    if s.upper().endswith("_APPROVAL"):
        s = s[:-9]
    s = "".join(c for c in s if c.isalnum() or c == "_")
    if s.isdigit():
        s = f"{int(s):03d}"
    if not s:
        s = "001"
    return f"LG_{s}_APPROVAL"


class LogoConnectReader:
    def __init__(self, logo_settings: Dict[str, Any]):
        self.logo_settings = logo_settings or {}
        self.server = str(self.logo_settings.get("server", "")).strip()
        self.main_database = str(self.logo_settings.get("database", "")).strip()
        connect_db = str(self.logo_settings.get("connect_database", "")).strip()
        self.connect_database = connect_db if connect_db else self.main_database
        self.username = str(self.logo_settings.get("db_username", "")).strip()
        self.password = str(self.logo_settings.get("db_password", "")).strip()
        
        connect_firm = self.logo_settings.get("connect_firm_no")
        if connect_firm is not None and str(connect_firm).strip():
            self.firm_no = str(connect_firm).strip()
        else:
            self.firm_no = str(self.logo_settings.get("firm_no", 1) or 1).strip()

    def build_connection_string(self) -> str:
        if not self.server or not self.connect_database:
            raise ValueError("SQL Server veya Connect Database bilgisi eksik.")

        if self.username:
            return (
                f"DRIVER={{SQL Server}};"
                f"SERVER={self.server};"
                f"DATABASE={self.connect_database};"
                f"UID={self.username};"
                f"PWD={self.password};"
            )
        return (
            f"DRIVER={{SQL Server}};"
            f"SERVER={self.server};"
            f"DATABASE={self.connect_database};"
            f"Trusted_Connection=yes;"
        )

    def get_approval_table_name(self) -> str:
        return format_connect_table_name(self.firm_no)

    def fetch_untransferred_invoices(self) -> List[ConnectInvoiceRecord]:
        """
        Logo Connect gelen kutusunda henüz Tiger ERP'ye aktarılmamış (DOCREF=0 ve CANCELLED=0)
        e-faturaları WITH (NOLOCK) ile kilitlenmesiz ve ışık hızında çeker.
        """
        table_name = self.get_approval_table_name()
        query = f"""
        SELECT 
            LOGICALREF,
            ISNULL(DOCNR, '') AS DOCNR,
            COALESCE(
                NULLIF(LTRIM(RTRIM(REFERENCEID)), ''), 
                NULLIF(LTRIM(RTRIM(REPLACE(FILENAME, '.xml', ''))), ''), 
                ''
            ) AS REFERENCEID,
            COALESCE(
                NULLIF(LTRIM(RTRIM(CLRETAILVKN)), ''), 
                NULLIF(LTRIM(RTRIM(SENDER)), ''), 
                ''
            ) AS CLRETAILVKN,
            ISNULL(SENDERTITLE, '') AS SENDERTITLE,
            DOCDATE,
            ISNULL(DOCTOTAL, 0) AS DOCTOTAL,
            ISNULL(DOCTAXEXCLUSIVETOTAL, 0) AS DOCTAXEXCLUSIVETOTAL,
            ISNULL(DOCTAXTOTAL, 0) AS DOCTAXTOTAL,
            ISNULL(PROFILEID, 1) AS PROFILEID,
            ISNULL(STATUS, 0) AS STATUS,
            ISNULL(APPROVED, 0) AS APPROVED,
            ISNULL(DOCREF, 0) AS DOCREF
        FROM {table_name} WITH (NOLOCK)
        WHERE (DOCREF = 0 OR DOCREF IS NULL)
          AND ISNULL(CANCELLED, 0) = 0
        ORDER BY LOGICALREF DESC
        """

        conn_str = self.build_connection_string()
        records: List[ConnectInvoiceRecord] = []

        if pyodbc is None:
            raise RuntimeError("Python 'pyodbc' modülü yüklü değil. Veritabanı bağlantısı kurulamaz.")

        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                for row in rows:
                    records.append(
                        ConnectInvoiceRecord(
                            logical_ref=int(row[0]),
                            invoice_number=str(row[1]).strip(),
                            ettn_guid=str(row[2]).strip(),
                            supplier_vkn=str(row[3]).strip(),
                            supplier_name=str(row[4]).strip(),
                            invoice_date=row[5] if isinstance(row[5], datetime) else None,
                            total_amount=float(row[6] or 0.0),
                            tax_exclusive_total=float(row[7] or 0.0),
                            tax_total=float(row[8] or 0.0),
                            profile_id=int(row[9] or 1),
                            status=int(row[10] or 0),
                            approved=int(row[11] or 0),
                            doc_ref=int(row[12] or 0),
                        )
                    )
        except Exception as exc:
            logger.error("Logo Connect APPROVAL tablosu okunamadı: %s", exc)
            raise RuntimeError(f"Logo Connect gelen kutusu sorgulanamadı: {exc}") from exc

        return records

