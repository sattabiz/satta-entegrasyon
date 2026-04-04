

using System;
using System.Collections.Generic;
using LogoBridge.Console.Models;

namespace LogoBridge.Console.Services;

public sealed class InvoiceMapper
{
    public Dictionary<string, string> MapHeaderFields(InvoicePayload payload)
    {
        if (payload is null)
        {
            throw new InvalidOperationException("Invoice payload boş olamaz.");
        }

        payload.Validate();

        return new Dictionary<string, string>
        {
            ["NUMBER"] = payload.InvoiceNumber,
            ["DOC_NUMBER"] = payload.DocumentNumber,
            ["ARP_CODE"] = payload.ArpCode,
            ["DATE"] = payload.DocumentDate?.ToString("dd.MM.yyyy") ?? string.Empty,
            ["TIME"] = payload.DocumentTime,
            ["DESCRIPTION"] = payload.Description,
            ["AUXILIARY_CODE"] = payload.AuxiliaryCode,
            ["AUTH_CODE"] = payload.AuthorizationCode,
            ["TRADING_GROUP"] = payload.TradingGroup,
            ["DIVISION"] = payload.Division.ToString(),
            ["DEPARTMENT"] = payload.Department.ToString(),
            ["SOURCE_INDEX"] = payload.SourceIndex.ToString(),
            ["FACTORY_NR"] = payload.FactoryNr.ToString(),
            ["WAREHOUSE_NR"] = payload.WarehouseNr.ToString(),
            ["CURRENCY_CODE"] = payload.CurrencyCode,
            ["EXCHANGE_RATE"] = payload.ExchangeRate.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["INVOICE_TYPE"] = payload.InvoiceType,
            ["NOTES"] = string.Join(" | ", payload.Notes),
        };
    }

    public List<Dictionary<string, string>> MapTransactionLines(InvoicePayload payload)
    {
        if (payload is null)
        {
            throw new InvalidOperationException("Invoice payload boş olamaz.");
        }

        payload.Validate();

        var lines = new List<Dictionary<string, string>>();

        foreach (var line in payload.Lines)
        {
            lines.Add(MapSingleLine(line));
        }

        return lines;
    }

    public Dictionary<string, string> MapSingleLine(InvoiceLinePayload line)
    {
        if (line is null)
        {
            throw new InvalidOperationException("Invoice satırı boş olamaz.");
        }

        line.Validate(1);

        return new Dictionary<string, string>
        {
            ["MASTER_CODE"] = line.MasterCode,
            ["LINE_TYPE"] = line.LineType.ToString(),
            ["DESCRIPTION"] = line.Description,
            ["QUANTITY"] = line.Quantity.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["UNIT_CODE"] = line.UnitCode,
            ["UNIT_PRICE"] = line.UnitPrice.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["VAT_RATE"] = line.VatRate.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["TOTAL"] = line.Total.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["CURRENCY_CODE"] = line.CurrencyCode,
            ["EXCHANGE_RATE"] = line.ExchangeRate.ToString(System.Globalization.CultureInfo.InvariantCulture),
            ["WAREHOUSE_NR"] = line.WarehouseNr.ToString(),
            ["SOURCE_INDEX"] = line.SourceIndex.ToString(),
            ["DIVISION"] = line.Division.ToString(),
            ["DEPARTMENT"] = line.Department.ToString(),
            ["AUXILIARY_CODE"] = line.AuxiliaryCode,
            ["PROJECT_CODE"] = line.ProjectCode,
            ["COST_CENTER_CODE"] = line.CostCenterCode,
            ["VARIANT_CODE"] = line.VariantCode,
        };
    }
}