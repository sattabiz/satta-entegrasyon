using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
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

        var dict = new Dictionary<string, string>
        {
            ["ARP_CODE"] = payload.ArpCode,
            ["FICHENO"] = payload.InvoiceNumber,
            ["DATE"] = payload.DocumentDate?.ToString("dd.MM.yyyy") ?? string.Empty,
            ["GRPCODE"] = ReadOptionalPayloadString(payload, "GroupCode", "1"),
            ["DOCODE"] = ReadOptionalPayloadString(payload, "DoCode", "~"),
            ["DOC_NUMBER"] = payload.DocumentNumber,
            ["TIME"] = payload.DocumentTime,
            ["SOURCE_WH"] = payload.WarehouseNr.ToString(CultureInfo.InvariantCulture),
            ["SOURCE_COST_GRP"] = payload.SourceIndex.ToString(CultureInfo.InvariantCulture),
            ["DIVISION"] = payload.Division.ToString(CultureInfo.InvariantCulture),
            ["DEPARTMENT"] = payload.Department.ToString(CultureInfo.InvariantCulture),
            ["DESCRIPTION"] = payload.Description,
        };

        if (payload.TransactionCurrencyId > 0)
        {
            dict["CURRSEL_TOTALS"] = "1";
            dict["TRCURR"] = payload.TransactionCurrencyId.ToString(CultureInfo.InvariantCulture);
            dict["TC_XRATE"] = payload.TransactionCurrencyRate.ToString(CultureInfo.InvariantCulture);
        }

        return dict;
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

        var dict = new Dictionary<string, string>
        {
            ["MASTER_CODE"] = line.MasterCode,
            ["QUANTITY"] = line.Quantity.ToString(CultureInfo.InvariantCulture),
            ["PRICE"] = line.UnitPrice.ToString(CultureInfo.InvariantCulture),
            ["SOURCEINDEX"] = line.WarehouseNr.ToString(CultureInfo.InvariantCulture),
            ["SOURCECOSTGRP"] = line.SourceIndex.ToString(CultureInfo.InvariantCulture),
            ["UNIT_CODE"] = line.UnitCode,
            ["VAT_RATE"] = line.VatRate.ToString(CultureInfo.InvariantCulture),
            ["TOTAL"] = line.Total.ToString(CultureInfo.InvariantCulture),
            ["DESCRIPTION"] = line.Description,
        };

        if (line.CurrencyId > 0)
        {
            dict["PRCURR"] = line.CurrencyId.ToString(CultureInfo.InvariantCulture);
            dict["PR_RATE"] = line.CurrencyRate.ToString(CultureInfo.InvariantCulture);
            dict["FC_PRICE"] = line.ForeignCurrencyPrice.ToString(CultureInfo.InvariantCulture);
        }

        return dict;
    }

    private string ReadOptionalPayloadString(InvoicePayload payload, string propertyName, string defaultValue)
    {
        try
        {
            var property = payload.GetType().GetProperty(propertyName, BindingFlags.Public | BindingFlags.Instance);
            if (property is null)
            {
                return defaultValue;
            }

            var value = property.GetValue(payload);
            if (value is null)
            {
                return defaultValue;
            }

            var text = Convert.ToString(value, CultureInfo.InvariantCulture)?.Trim();
            return string.IsNullOrWhiteSpace(text) ? defaultValue : text;
        }
        catch
        {
            return defaultValue;
        }
    }
}