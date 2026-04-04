using System;
using System.Collections.Generic;
using System.Globalization;
using LogoBridge.Console.Models;

namespace LogoBridge.Console.Services;

public sealed class LogoObjectService
{
    private readonly InvoiceMapper _invoiceMapper;

    public LogoObjectService()
    {
        _invoiceMapper = new InvoiceMapper();
    }

    public BridgeResult TransferPurchaseInvoice(InvoicePayload payload)
    {
        try
        {
            if (payload is null)
            {
                return BridgeResult.Failure(
                    message: "Invoice payload boş olamaz.",
                    errorCode: "PAYLOAD_NULL");
            }

            payload.Validate();

            var validationErrors = ValidateBusinessRules(payload);
            if (validationErrors.Count > 0)
            {
                return BridgeResult.Failure(
                    message: "Payload iş kuralları doğrulamasından geçemedi.",
                    errorCode: "BUSINESS_VALIDATION_FAILED",
                    details: validationErrors);
            }

            var headerFields = _invoiceMapper.MapHeaderFields(payload);
            var transactionLines = _invoiceMapper.MapTransactionLines(payload);

            var result = BridgeResult.Failure(
                message: "Logo Objects entegrasyon katmanı henüz gerçek bağlantı ile tamamlanmadı.",
                errorCode: "LOGO_OBJECTS_NOT_IMPLEMENTED");

            AppendPayloadSummary(result, payload);
            AppendMappedHeaderSummary(result, headerFields);
            AppendMappedLineSummary(result, transactionLines);
            result.Warnings.Add("UnityObjects / Logo Objects referansı ve gerçek Post akışı henüz eklenmedi.");

            return result;
        }
        catch (Exception exception)
        {
            var result = BridgeResult.Failure(
                message: $"Logo Objects servis hatası: {exception.Message}",
                errorCode: "LOGO_OBJECTS_SERVICE_EXCEPTION");
            result.Details["exception_type"] = exception.GetType().Name;
            return result;
        }
    }

    private void AppendPayloadSummary(BridgeResult result, InvoicePayload payload)
    {
        result.Details["firm_no"] = payload.FirmNo.ToString(CultureInfo.InvariantCulture);
        result.Details["period_no"] = payload.PeriodNo.ToString(CultureInfo.InvariantCulture);
        result.Details["arp_code"] = payload.ArpCode;
        result.Details["invoice_type"] = payload.InvoiceType;
        result.Details["line_count"] = payload.Lines.Count.ToString(CultureInfo.InvariantCulture);
        result.Details["invoice_number"] = payload.InvoiceNumber;
        result.Details["document_number"] = payload.DocumentNumber;
        result.Details["currency_code"] = payload.CurrencyCode;
        result.Details["warehouse_nr"] = payload.WarehouseNr.ToString(CultureInfo.InvariantCulture);
        result.Details["source_index"] = payload.SourceIndex.ToString(CultureInfo.InvariantCulture);
    }

    private void AppendMappedHeaderSummary(BridgeResult result, Dictionary<string, string> headerFields)
    {
        result.Details["mapped_header_count"] = headerFields.Count.ToString(CultureInfo.InvariantCulture);

        if (headerFields.TryGetValue("ARP_CODE", out var arpCode))
        {
            result.Details["mapped_header_arp_code"] = arpCode;
        }

        if (headerFields.TryGetValue("NUMBER", out var invoiceNumber))
        {
            result.Details["mapped_header_number"] = invoiceNumber;
        }

        if (headerFields.TryGetValue("DATE", out var invoiceDate))
        {
            result.Details["mapped_header_date"] = invoiceDate;
        }
    }

    private void AppendMappedLineSummary(BridgeResult result, List<Dictionary<string, string>> transactionLines)
    {
        result.Details["mapped_line_count"] = transactionLines.Count.ToString(CultureInfo.InvariantCulture);

        if (transactionLines.Count == 0)
        {
            return;
        }

        var firstLine = transactionLines[0];

        if (firstLine.TryGetValue("MASTER_CODE", out var masterCode))
        {
            result.Details["first_line_master_code"] = masterCode;
        }

        if (firstLine.TryGetValue("QUANTITY", out var quantity))
        {
            result.Details["first_line_quantity"] = quantity;
        }

        if (firstLine.TryGetValue("UNIT_PRICE", out var unitPrice))
        {
            result.Details["first_line_unit_price"] = unitPrice;
        }
    }

    private Dictionary<string, string> ValidateBusinessRules(InvoicePayload payload)
    {
        var errors = new Dictionary<string, string>();

        if (!string.Equals(payload.InvoiceType, "purchase", StringComparison.OrdinalIgnoreCase))
        {
            errors["invoice_type"] = "Bu servis şu an sadece purchase tipindeki faturaları destekler.";
        }

        if (payload.Division < 0)
        {
            errors["division"] = "division negatif olamaz.";
        }

        if (payload.Department < 0)
        {
            errors["department"] = "department negatif olamaz.";
        }

        if (payload.SourceIndex < 0)
        {
            errors["source_index"] = "source_index negatif olamaz.";
        }

        if (payload.WarehouseNr < 0)
        {
            errors["warehouse_nr"] = "warehouse_nr negatif olamaz.";
        }

        for (var i = 0; i < payload.Lines.Count; i++)
        {
            var line = payload.Lines[i];
            var lineNo = i + 1;

            if (string.IsNullOrWhiteSpace(line.MasterCode))
            {
                errors[$"lines[{lineNo}].master_code"] = "master_code zorunludur.";
            }

            if (line.Quantity <= 0)
            {
                errors[$"lines[{lineNo}].quantity"] = "quantity 0'dan büyük olmalıdır.";
            }

            if (line.WarehouseNr < 0)
            {
                errors[$"lines[{lineNo}].warehouse_nr"] = "warehouse_nr negatif olamaz.";
            }

            if (line.SourceIndex < 0)
            {
                errors[$"lines[{lineNo}].source_index"] = "source_index negatif olamaz.";
            }
        }

        return errors;
    }
}