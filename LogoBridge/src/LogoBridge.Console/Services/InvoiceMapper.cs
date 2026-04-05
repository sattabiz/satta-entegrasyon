

using System;
using System.Collections.Generic;
using System.Globalization;
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
            ["TYPE"] = ResolveInvoiceType(payload.InvoiceType),
            ["NUMBER"] = payload.InvoiceNumber,
            ["DOC_NUMBER"] = payload.DocumentNumber,
            ["ARP_CODE"] = payload.ArpCode,
            ["DATE"] = payload.DocumentDate?.ToString("dd.MM.yyyy") ?? string.Empty,
            ["TIME"] = payload.DocumentTime,
            ["DESCRIPTION"] = payload.Description,
            ["AUXILIARY_CODE"] = payload.AuxiliaryCode,
            ["AUTH_CODE"] = payload.AuthorizationCode,
            ["TRADING_GROUP"] = payload.TradingGroup,
            ["DIVISION"] = payload.Division.ToString(CultureInfo.InvariantCulture),
            ["DEPARTMENT"] = payload.Department.ToString(CultureInfo.InvariantCulture),
            ["SOURCE_WH"] = payload.WarehouseNr.ToString(CultureInfo.InvariantCulture),
            ["SOURCE_COST_GRP"] = payload.SourceIndex.ToString(CultureInfo.InvariantCulture),
            ["FACTORY_NR"] = payload.FactoryNr.ToString(CultureInfo.InvariantCulture),
            ["CURR_INVOICE"] = ResolveCurrencyCode(payload.CurrencyCode),
            ["TC_XRATE"] = payload.ExchangeRate.ToString(CultureInfo.InvariantCulture),
            ["RC_XRATE"] = payload.ExchangeRate.ToString(CultureInfo.InvariantCulture),
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
            ["TYPE"] = ResolveLineType(line.LineType),
            ["MASTER_CODE"] = line.MasterCode,
            ["DESCRIPTION"] = line.Description,
            ["QUANTITY"] = line.Quantity.ToString(CultureInfo.InvariantCulture),
            ["UNIT_CODE"] = line.UnitCode,
            ["PRICE"] = line.UnitPrice.ToString(CultureInfo.InvariantCulture),
            ["VAT_RATE"] = line.VatRate.ToString(CultureInfo.InvariantCulture),
            ["TOTAL"] = line.Total.ToString(CultureInfo.InvariantCulture),
            ["CURR_TRANSACTION"] = ResolveCurrencyCode(line.CurrencyCode),
            ["TC_XRATE"] = line.ExchangeRate.ToString(CultureInfo.InvariantCulture),
            ["RC_XRATE"] = line.ExchangeRate.ToString(CultureInfo.InvariantCulture),
            ["SOURCEINDEX"] = line.WarehouseNr.ToString(CultureInfo.InvariantCulture),
            ["SOURCECOSTGRP"] = line.SourceIndex.ToString(CultureInfo.InvariantCulture),
            ["DIVISION"] = line.Division.ToString(CultureInfo.InvariantCulture),
            ["DEPARTMENT"] = line.Department.ToString(CultureInfo.InvariantCulture),
            ["AUXILIARY_CODE"] = line.AuxiliaryCode,
            ["PROJECT_CODE"] = line.ProjectCode,
            ["CENTER_CODE"] = line.CostCenterCode,
            ["VARIANT_CODE"] = line.VariantCode,
        };
    }

    private string ResolveInvoiceType(string invoiceType)
    {
        if (string.Equals(invoiceType, "purchase", StringComparison.OrdinalIgnoreCase))
        {
            return "1";
        }

        return "1";
    }

    private string ResolveLineType(int lineType)
    {
        if (lineType < 0)
        {
            return "0";
        }

        return lineType.ToString(CultureInfo.InvariantCulture);
    }

    private string ResolveCurrencyCode(string currencyCode)
    {
        var normalizedCode = (currencyCode ?? string.Empty).Trim().ToUpperInvariant();

        return normalizedCode switch
        {
            "TRY" or "TL" => "0",
            "USD" => "1",
            "EUR" => "20",
            "GBP" => "17",
            _ => normalizedCode,
        };
    }
}