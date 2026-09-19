import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import pyodbc

logger = logging.getLogger(__name__)


@dataclass
class ConnectInvoiceRecord:
    logical_ref: int
    invoice_number: str  # 16 haneli GİB Fatura No (DOCNR)
    ettn_guid: str       # 36 haneli ETTN (REFERENCEID)
    supplier_vkn: str    # Tedarikçi Vergi No (CLRETAILVKN)
    supplier_name: str   # Tedarikçi Ünvanı (SENDERTITLE)
    invoice_date: Optional[datetime]
    total_amount: float
    tax_exclusive_total: float
    tax_total: float
    profile_id: int      # 1: Temel, 2: Ticari
    status: int
    approved: int
    doc_ref: int         # 0: Bekliyor, >0: ERP Ref


class LogoConnectReader:
    def __init__(self, logo_settings: Dict[str, Any]):
        self.logo_settings = logo_settings or {}
        self.server = str(self.logo_settings.get("server", "")).strip()
        self.main_database = str(self.logo_settings.get("database", "")).strip()
        connect_db = str(self.logo_settings.get("connect_database", "")).strip()
        self.connect_database = connect_db if connect_db else self.main_database
        self.username = str(self.logo_settings.get("db_username", "")).strip()
        self.password = str(self.logo_settings.get("db_password", "")).strip()
        try:
            connect_firm = self.logo_settings.get("connect_firm_no")
            if connect_firm is not None and int(connect_firm) > 0:
                self.firm_no = int(connect_firm)
            else:
                self.firm_no = int(self.logo_settings.get("firm_no", 1) or 1)
        except (TypeError, ValueError):
            self.firm_no = 1

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
        return f"LG_{self.firm_no:03d}_APPROVAL"

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

    def mark_as_transferred(self, connect_logicalref: int, erp_logicalref: int) -> bool:
        """
        Fatura Tiger ERP'ye başarıyla kaydedildiğinde Connect APPROVAL tablosundaki DOCREF alanını
        ERP'deki LOGICALREF ile günceller ve onay durumunu işaretler.
        """
        if connect_logicalref <= 0 or erp_logicalref <= 0:
            return False

        table_name = self.get_approval_table_name()
        query = f"""
        UPDATE {table_name}
        SET DOCREF = ?,
            STATUS = 12,
            APPROVED = 1
        WHERE LOGICALREF = ?
        """

        conn_str = self.build_connection_string()
        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(query, (erp_logicalref, connect_logicalref))
                conn.commit()
                return True
        except Exception as exc:
            logger.warning(
                "Connect APPROVAL tablosu güncellenemedi (ConnectRef: %s, ERPRef: %s): %s",
                connect_logicalref,
                erp_logicalref,
                exc,
            )
            return False
