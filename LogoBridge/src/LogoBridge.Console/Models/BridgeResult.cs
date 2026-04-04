

using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace LogoBridge.Console.Models;

public sealed class BridgeResult
{
    [JsonPropertyName("is_success")]
    public bool IsSuccess { get; set; }

    [JsonPropertyName("message")]
    public string Message { get; set; } = string.Empty;

    [JsonPropertyName("error_code")]
    public string ErrorCode { get; set; } = string.Empty;

    [JsonPropertyName("logical_ref")]
    public int LogicalRef { get; set; }

    [JsonPropertyName("invoice_number")]
    public string InvoiceNumber { get; set; } = string.Empty;

    [JsonPropertyName("document_number")]
    public string DocumentNumber { get; set; } = string.Empty;

    [JsonPropertyName("arp_code")]
    public string ArpCode { get; set; } = string.Empty;

    [JsonPropertyName("warnings")]
    public List<string> Warnings { get; set; } = new();

    [JsonPropertyName("details")]
    public Dictionary<string, string> Details { get; set; } = new();

    public static BridgeResult Success(
        string message,
        int logicalRef = 0,
        string invoiceNumber = "",
        string documentNumber = "",
        string arpCode = "")
    {
        return new BridgeResult
        {
            IsSuccess = true,
            Message = message,
            LogicalRef = logicalRef,
            InvoiceNumber = invoiceNumber,
            DocumentNumber = documentNumber,
            ArpCode = arpCode,
        };
    }

    public static BridgeResult Failure(
        string message,
        string errorCode = "",
        Dictionary<string, string>? details = null)
    {
        return new BridgeResult
        {
            IsSuccess = false,
            Message = message,
            ErrorCode = errorCode,
            Details = details ?? new Dictionary<string, string>(),
        };
    }
}