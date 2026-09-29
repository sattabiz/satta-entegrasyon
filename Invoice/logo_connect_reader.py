import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
import pyodbc

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

    def auto_sync_transferred_invoices(self, period_no: int = 1) -> int:
        """
        Tiger ERP'de kaydı oluşan (INVOICE tablosunda bulunan) fakat Connect APPROVAL
        tablosunda DOCREF=0 veya boş kalmış e-faturaları otomatik tespit ederek
        Connect APPROVAL tablosunda DOCREF ve STATUS=3 (Kaydedildi) olarak günceller.
        Böylece takılı kalmış faturalar kullanıcı müdahalesi olmadan otomatik senkronize olur.
        """
        approval_table = self.get_approval_table_name()
        erp_invoice_table = f"LG_{self.firm_no:03d}_{period_no:02d}_INVOICE"
        if self.connect_database and self.main_database and self.connect_database.lower() != self.main_database.lower():
            erp_table_full = f"[{self.main_database}].dbo.[{erp_invoice_table}]"
        else:
            erp_table_full = f"[{erp_invoice_table}]"

        conn_str = self.build_connection_string()
        query = f"""
        UPDATE A
        SET A.DOCREF = I.LOGICALREF,
            A.STATUS = 3,
            A.APPROVED = 0
        FROM [{approval_table}] A
        INNER JOIN {erp_table_full} I
           ON (
               (NULLIF(LTRIM(RTRIM(A.DOCNR)), '') IS NOT NULL AND (A.DOCNR = I.FICHENO OR A.DOCNR = I.DOCTRACKINGNR))
               OR (NULLIF(LTRIM(RTRIM(A.FILENAME)), '') IS NOT NULL AND A.FILENAME = I.GUID)
               OR (NULLIF(LTRIM(RTRIM(A.REFERENCEID)), '') IS NOT NULL AND A.REFERENCEID = I.GUID)
           )
        WHERE (A.DOCREF = 0 OR A.DOCREF IS NULL)
          AND ISNULL(A.CANCELLED, 0) = 0
          AND ISNULL(I.CANCELLED, 0) = 0
          AND I.LOGICALREF > 0
        """
        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                updated_count = cursor.rowcount
                conn.commit()
                if updated_count > 0:
                    logger.info("Connect APPROVAL otomatik senkronize edildi: %s adet fatura bağlandı.", updated_count)
                return max(0, updated_count)
        except Exception as exc:
            logger.debug("Otomatik Connect senkronizasyonu çalıştırılamadı: %s", exc)
            return 0

    def mark_as_transferred(
        self,
        connect_logicalref: int,
        erp_logicalref: int,
        invoice_no: str = "",
    ) -> bool:
        """
        Fatura Tiger ERP'ye başarıyla kaydedildiğinde Connect APPROVAL tablosundaki:
        - DOCREF alanını ERP'deki LOGICALREF ile günceller
        - STATUS alanını 3 (Kaydedildi / ERP'ye Aktarıldı) olarak günceller
        - APPROVED alanını 0 olarak bırakır (Logo Connect standardı)
        """
        if erp_logicalref <= 0 or (connect_logicalref <= 0 and not invoice_no):
            return False

        table_name = self.get_approval_table_name()
        conn_str = self.build_connection_string()

        try:
            with pyodbc.connect(conn_str, timeout=10) as conn:
                cursor = conn.cursor()
                if connect_logicalref > 0:
                    query = f"""
                    UPDATE {table_name}
                    SET DOCREF = ?,
                        STATUS = 3,
                        APPROVED = 0
                    WHERE LOGICALREF = ?
                    """
                    cursor.execute(query, (erp_logicalref, connect_logicalref))
                elif invoice_no:
                    query = f"""
                    UPDATE {table_name}
                    SET DOCREF = ?,
                        STATUS = 3,
                        APPROVED = 0
                    WHERE DOCNR = ? AND (DOCREF = 0 OR DOCREF IS NULL)
                    """
                    cursor.execute(query, (erp_logicalref, str(invoice_no).strip()))
                conn.commit()
                logger.info(
                    "Connect APPROVAL tablosu güncellendi (Tablo: %s, ConnectRef: %s, FaturaNo: %s, ERPRef: %s, STATUS=3)",
                    table_name,
                    connect_logicalref,
                    invoice_no,
                    erp_logicalref,
                )
                return True
        except Exception as exc:
            logger.warning(
                "Connect APPROVAL tablosu güncellenemedi (Tablo: %s, ConnectRef: %s, FaturaNo: %s, ERPRef: %s): %s",
                table_name,
                connect_logicalref,
                invoice_no,
                erp_logicalref,
                exc,
            )
            return False
