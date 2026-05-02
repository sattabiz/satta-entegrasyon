

using System;
using System.Text.Json.Serialization;

namespace LogoBridge.Console.Models;

public sealed class InvoiceLinePayload
{
    [JsonPropertyName("master_code")]
    public string MasterCode { get; set; } = string.Empty;

    [JsonPropertyName("line_type")]
    public int LineType { get; set; }

    [JsonPropertyName("description")]
    public string Description { get; set; } = string.Empty;

    [JsonPropertyName("quantity")]
    public decimal Quantity { get; set; }

    [JsonPropertyName("unit_code")]
    public string UnitCode { get; set; } = string.Empty;

    [JsonPropertyName("unit_price")]
    public decimal UnitPrice { get; set; }

    [JsonPropertyName("vat_rate")]
    public decimal VatRate { get; set; }

    [JsonPropertyName("total")]
    public decimal Total { get; set; }

    [JsonPropertyName("currency_code")]
    public string CurrencyCode { get; set; } = "TRY";

    [JsonPropertyName("exchange_rate")]
    public decimal ExchangeRate { get; set; }

    [JsonPropertyName("currency_id")]
    public int CurrencyId { get; set; }

    [JsonPropertyName("currency_rate")]
    public decimal CurrencyRate { get; set; }

    [JsonPropertyName("foreign_currency_price")]
    public decimal ForeignCurrencyPrice { get; set; }

    [JsonPropertyName("warehouse_nr")]
    public int WarehouseNr { get; set; }

    [JsonPropertyName("source_index")]
    public int SourceIndex { get; set; }

    [JsonPropertyName("division")]
    public int Division { get; set; }

    [JsonPropertyName("department")]
    public int Department { get; set; }

    [JsonPropertyName("auxiliary_code")]
    public string AuxiliaryCode { get; set; } = string.Empty;

    [JsonPropertyName("project_code")]
    public string ProjectCode { get; set; } = string.Empty;

    [JsonPropertyName("cost_center_code")]
    public string CostCenterCode { get; set; } = string.Empty;

    [JsonPropertyName("variant_code")]
    public string VariantCode { get; set; } = string.Empty;

    public void Validate(int lineNumber)
    {
        if (string.IsNullOrWhiteSpace(MasterCode))
        {
            throw new InvalidOperationException($"{lineNumber}. satır için master_code zorunludur.");
        }

        if (Quantity <= 0)
        {
            throw new InvalidOperationException($"{lineNumber}. satır için quantity 0'dan büyük olmalıdır.");
        }

        if (UnitPrice < 0)
        {
            throw new InvalidOperationException($"{lineNumber}. satır için unit_price negatif olamaz.");
        }

        if (VatRate < 0)
        {
            throw new InvalidOperationException($"{lineNumber}. satır için vat_rate negatif olamaz.");
        }

        if (LineType < 0)
        {
            throw new InvalidOperationException($"{lineNumber}. satır için line_type negatif olamaz.");
        }
    }
}