using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace LogoBridge.Console.Models;

public sealed class InvoicePayload
{
    [JsonPropertyName("firm_no")]
    public int FirmNo { get; set; }

    [JsonPropertyName("period_no")]
    public int PeriodNo { get; set; }

    [JsonPropertyName("logo_user")]
    public string LogoUser { get; set; } = string.Empty;

    [JsonPropertyName("logo_password")]
    public string LogoPassword { get; set; } = string.Empty;

    [JsonPropertyName("logo_company_code")]
    public string LogoCompanyCode { get; set; } = string.Empty;

    [JsonPropertyName("logo_working_year")]
    public string LogoWorkingYear { get; set; } = string.Empty;

    [JsonPropertyName("invoice_type")]
    public string InvoiceType { get; set; } = "purchase";

    [JsonPropertyName("document_number")]
    public string DocumentNumber { get; set; } = string.Empty;

    [JsonPropertyName("document_date")]
    public DateTime? DocumentDate { get; set; }

    [JsonPropertyName("document_time")]
    public string DocumentTime { get; set; } = string.Empty;

    [JsonPropertyName("arp_code")]
    public string ArpCode { get; set; } = string.Empty;

    [JsonPropertyName("invoice_number")]
    public string InvoiceNumber { get; set; } = string.Empty;

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("auxiliary_code")]
    public string AuxiliaryCode { get; set; } = string.Empty;

    [JsonPropertyName("authorization_code")]
    public string AuthorizationCode { get; set; } = string.Empty;

    [JsonPropertyName("trading_group")]
    public string TradingGroup { get; set; } = string.Empty;

    [JsonPropertyName("division")]
    public int Division { get; set; }

    [JsonPropertyName("department")]
    public int Department { get; set; }

    [JsonPropertyName("source_index")]
    public int SourceIndex { get; set; }

    [JsonPropertyName("factory_nr")]
    public int FactoryNr { get; set; }

    [JsonPropertyName("warehouse_nr")]
    public int WarehouseNr { get; set; }

    [JsonPropertyName("currency_code")]
    public string CurrencyCode { get; set; } = "TRY";

    [JsonPropertyName("exchange_rate")]
    public decimal ExchangeRate { get; set; }

    [JsonPropertyName("notes")]
    public List<string> Notes { get; set; } = new();

    [JsonPropertyName("lines")]
    public List<InvoiceLinePayload> Lines { get; set; } = new();

    public void Validate()
    {
        if (FirmNo <= 0)
        {
            throw new InvalidOperationException("firm_no 0'dan büyük olmalıdır.");
        }

        if (PeriodNo <= 0)
        {
            throw new InvalidOperationException("period_no 0'dan büyük olmalıdır.");
        }

        if (string.IsNullOrWhiteSpace(LogoUser))
        {
            throw new InvalidOperationException("logo_user zorunludur.");
        }

        if (string.IsNullOrWhiteSpace(LogoPassword))
        {
            throw new InvalidOperationException("logo_password zorunludur.");
        }

        if (string.IsNullOrWhiteSpace(ArpCode))
        {
            throw new InvalidOperationException("arp_code zorunludur.");
        }

        if (DocumentDate is null)
        {
            throw new InvalidOperationException("document_date zorunludur.");
        }

        if (Lines.Count == 0)
        {
            throw new InvalidOperationException("En az bir fatura satırı olmalıdır.");
        }

        for (var i = 0; i < Lines.Count; i++)
        {
            Lines[i].Validate(i + 1);
        }
    }
}