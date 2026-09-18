import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from Invoice.logo_connect_reader import ConnectInvoiceRecord


@dataclass
class InvoiceMatchResult:
    is_matched: bool
    match_type: str  # 'EXACT_NO', 'VKN_AMOUNT', 'TITLE_AMOUNT', 'MANUAL', 'NONE'
    connect_record: Optional[ConnectInvoiceRecord] = None
    reason: str = ""
    display_text: str = ""


class InvoiceMatcher:
    def __init__(self, connect_records: List[ConnectInvoiceRecord]):
        self.connect_records = connect_records or []
        self._index_records()

    def _index_records(self) -> None:
        """
        O(1) hızında arama yapabilmek için Connect kayıtlarını bellekte 3 ayrı hash haritasına indeksler.
        """
        self.by_clean_no: Dict[str, ConnectInvoiceRecord] = {}
        self.by_vkn_amount: Dict[Tuple[str, float], List[ConnectInvoiceRecord]] = {}
        self.by_clean_title_amount: Dict[Tuple[str, float], List[ConnectInvoiceRecord]] = {}

        for rec in self.connect_records:
            clean_no = self.normalize_invoice_number(rec.invoice_number)
            if clean_no:
                self.by_clean_no[clean_no] = rec

            clean_vkn = self.normalize_vkn(rec.supplier_vkn)
            amount_key = round(rec.total_amount, 2)
            if clean_vkn and amount_key > 0:
                self.by_vkn_amount.setdefault((clean_vkn, amount_key), []).append(rec)

            clean_title = self.normalize_company_title(rec.supplier_name)
            if clean_title and amount_key > 0:
                self.by_clean_title_amount.setdefault((clean_title, amount_key), []).append(rec)

    def match_satta_invoice(self, satta_invoice: Dict[str, Any]) -> InvoiceMatchResult:
        if not isinstance(satta_invoice, dict):
            return InvoiceMatchResult(
                is_matched=False,
                match_type="NONE",
                reason="Geçersiz fatura verisi",
                display_text="❌ Veri Hatası",
            )

        raw_invoice_no = str(satta_invoice.get("invoice_no") or "").strip()
        seller_name = str(satta_invoice.get("seller_name") or "").strip()
        seller_vkn = self.normalize_vkn(str(satta_invoice.get("seller_tax_number") or ""))

        # Toplam tutarı hesapla
        total_amount = self._calculate_satta_total_amount(satta_invoice)
        amount_key = round(total_amount, 2)

        # 1. Kademe: Fatura Numarası ile Eşleştirme
        clean_inv_no = self.normalize_invoice_number(raw_invoice_no)
        if clean_inv_no and clean_inv_no in self.by_clean_no:
            matched_rec = self.by_clean_no[clean_inv_no]
            guid_short = matched_rec.ettn_guid[:8] if matched_rec.ettn_guid else ""
            return InvoiceMatchResult(
                is_matched=True,
                match_type="EXACT_NO",
                connect_record=matched_rec,
                reason=f"Fatura numarası ile tam eşleşti ({matched_rec.invoice_number})",
                display_text=f"✓ E-Fatura ({guid_short}...)",
            )

        # 1.1 Kademe: Numara son haneleri ile eşleştirme (Kullanıcı sadece son 6-8 haneyi girdiyse)
        if clean_inv_no and len(clean_inv_no) >= 5:
            for rec in self.connect_records:
                rec_clean_no = self.normalize_invoice_number(rec.invoice_number)
                if rec_clean_no.endswith(clean_inv_no) or clean_inv_no.endswith(rec_clean_no):
                    guid_short = rec.ettn_guid[:8] if rec.ettn_guid else ""
                    return InvoiceMatchResult(
                        is_matched=True,
                        match_type="EXACT_NO",
                        connect_record=rec,
                        reason=f"Fatura numarası son haneleri ile eşleşti ({rec.invoice_number})",
                        display_text=f"✓ E-Fatura ({guid_short}...)",
                    )

        # 2. Kademe: Tedarikçi VKN + Tutar Eşleştirmesi
        if seller_vkn and amount_key > 0:
            candidates = self.by_vkn_amount.get((seller_vkn, amount_key), [])
            if len(candidates) == 1:
                matched_rec = candidates[0]
                guid_short = matched_rec.ettn_guid[:8] if matched_rec.ettn_guid else ""
                return InvoiceMatchResult(
                    is_matched=True,
                    match_type="VKN_AMOUNT",
                    connect_record=matched_rec,
                    reason=f"Tedarikçi VKN ({seller_vkn}) ve Tutar ({amount_key:,.2f}) ile eşleşti",
                    display_text=f"✓ E-Fatura ({guid_short}...)",
                )

        # 3. Kademe: Tedarikçi Unvanı + Tutar Eşleştirmesi (VKN eksik/hatalı olsa dahi)
        clean_seller_title = self.normalize_company_title(seller_name)
        if clean_seller_title and amount_key > 0:
            # Doğrudan unvan eşleşmesi
            candidates = self.by_clean_title_amount.get((clean_seller_title, amount_key), [])
            if len(candidates) == 1:
                matched_rec = candidates[0]
                guid_short = matched_rec.ettn_guid[:8] if matched_rec.ettn_guid else ""
                return InvoiceMatchResult(
                    is_matched=True,
                    match_type="TITLE_AMOUNT",
                    connect_record=matched_rec,
                    reason=f"Tedarikçi Unvanı ({matched_rec.supplier_name}) ve Tutar ile eşleşti",
                    display_text=f"✓ E-Fatura ({guid_short}...)",
                )

            # Alt metin / kapsama kontrolü (Örn: Satta'da "ABC Lojistik", Connect'te "ABC Lojistik Hizmetleri A.Ş.")
            for (connect_title, c_amount), rec_list in self.by_clean_title_amount.items():
                if c_amount == amount_key and len(rec_list) == 1:
                    if (
                        clean_seller_title in connect_title
                        or connect_title in clean_seller_title
                        or self._tokens_overlap(clean_seller_title, connect_title)
                    ):
                        matched_rec = rec_list[0]
                        guid_short = matched_rec.ettn_guid[:8] if matched_rec.ettn_guid else ""
                        return InvoiceMatchResult(
                            is_matched=True,
                            match_type="TITLE_AMOUNT",
                            connect_record=matched_rec,
                            reason=f"Tedarikçi Unvan benzerliği ({matched_rec.supplier_name}) ve Tutar ile eşleşti",
                            display_text=f"✓ E-Fatura ({guid_short}...)",
                        )

        # Eşleşme bulunamadı
        return InvoiceMatchResult(
            is_matched=False,
            match_type="NONE",
            reason="Connect gelen kutusunda eşleşen e-fatura bulunamadı.",
            display_text="⏳ Connect'te Yok",
        )

    def get_supplier_candidates(self, satta_invoice: Dict[str, Any]) -> List[ConnectInvoiceRecord]:
        """
        Kullanıcı manuel seçim yapmak isterse, o faturanın tedarikçisine ait
        Connect'te bekleyen fatura adaylarını döndürür.
        """
        seller_vkn = self.normalize_vkn(str(satta_invoice.get("seller_tax_number") or ""))
        clean_seller_title = self.normalize_company_title(str(satta_invoice.get("seller_name") or ""))

        candidates = []
        for rec in self.connect_records:
            if seller_vkn and self.normalize_vkn(rec.supplier_vkn) == seller_vkn:
                candidates.append(rec)
                continue
            if clean_seller_title and (
                clean_seller_title in self.normalize_company_title(rec.supplier_name)
                or self.normalize_company_title(rec.supplier_name) in clean_seller_title
            ):
                candidates.append(rec)

        return candidates

    @staticmethod
    def normalize_invoice_number(inv_no: Any) -> str:
        if not inv_no:
            return ""
        text = str(inv_no).strip().upper()
        # Boşlukları, tireleri ve noktalama işaretlerini kaldır
        return re.sub(r"[^A-Z0-9]", "", text)

    @staticmethod
    def normalize_vkn(vkn: Any) -> str:
        if not vkn:
            return ""
        # Yalnızca rakamları tut
        digits = re.sub(r"\D", "", str(vkn).strip())
        return digits if len(digits) in (10, 11) else digits

    @staticmethod
    def normalize_company_title(title: Any) -> str:
        if not title:
            return ""
        text = str(title).strip().upper()
        # Türkçe karakterleri normalize et
        charmap = {
            "İ": "I", "ı": "I",
            "Ş": "S", "ş": "S",
            "Ğ": "G", "ğ": "G",
            "Ü": "U", "ü": "U",
            "Ö": "O", "ö": "O",
            "Ç": "C", "ç": "C",
        }
        for tr_char, en_char in charmap.items():
            text = text.replace(tr_char, en_char)

        # Şirket türü eklerini temizle
        suffixes = [
            r"\bANONIM SIRKETI\b", r"\bANONIM STI\b", r"\bA\.?S\.?\b",
            r"\bLIMITED SIRKETI\b", r"\bLIMITED STI\b", r"\bLTD\.? STI\.?\b", r"\bLTD\.?\b",
            r"\bSANAYI VE TICARET\b", r"\bSAN\.? VE TIC\.?\b", r"\bTIC\.? VE SAN\.?\b",
            r"\bSANAYI\b", r"\bTICARET\b", r"\bSAN\.?\b", r"\bTIC\.?\b",
            r"\bHOLDING\b", r"\bGRUP\b",
        ]
        for pattern in suffixes:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE)

        # Özel karakterleri boşluğa çevir ve fazla boşlukları sadeleştir
        text = re.sub(r"[^A-Z0-9\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _tokens_overlap(title1: str, title2: str) -> bool:
        tokens1 = {t for t in title1.split() if len(t) > 2}
        tokens2 = {t for t in title2.split() if len(t) > 2}
        if not tokens1 or not tokens2:
            return False
        common = tokens1.intersection(tokens2)
        # En az 2 anahtar kelime ortaksa veya tekil uzun bir marka adı uyuşuyorsa
        return len(common) >= 2 or any(len(word) >= 5 for word in common)

    @staticmethod
    def _calculate_satta_total_amount(invoice: Dict[str, Any]) -> float:
        # Önce doğrudan belirtilen toplam tutarları kontrol et
        for key in ("total_tl_price", "total_price", "grand_total"):
            val = invoice.get(key)
            if val is not None:
                try:
                    fval = float(val)
                    if fval > 0:
                        return fval
                except (TypeError, ValueError):
                    pass

        # Faturanın KDV hariç tutarı + KDV toplamı
        price_without_vat = 0.0
        vat_total = 0.0
        try:
            price_without_vat = float(invoice.get("price_without_vat") or 0.0)
            vat_total = float(invoice.get("invoice_vat_total") or 0.0)
        except (TypeError, ValueError):
            pass

        if price_without_vat > 0 or vat_total > 0:
            return price_without_vat + vat_total

        # Satır kalemlerinden topla
        products = invoice.get("products") or []
        line_sum = 0.0
        for p in products:
            if isinstance(p, dict):
                try:
                    line_sum += float(p.get("line_total_without_tax") or p.get("price") or 0.0)
                except (TypeError, ValueError):
                    pass
        return line_sum
