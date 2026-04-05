using System;
using System.Text.Json;
using LogoBridge.Console.Models;
using LogoBridge.Console.Services;

namespace LogoBridge.Console;

internal static class Program
{
    private static int Main(string[] args)
    {
        var result = new BridgeResult();
        var jsonFileService = new JsonFileService();
        var logoObjectService = new LogoObjectService();

        try
        {
            if (args.Length == 0)
            {
                result = BridgeResult.Failure(
                    message: "Payload dosya yolu verilmedi.",
                    errorCode: "ARGUMENT_MISSING");

                WriteResult(result);
                return 1;
            }

            var payloadPath = args[0];
            if (string.IsNullOrWhiteSpace(payloadPath))
            {
                result = BridgeResult.Failure(
                    message: "Payload dosya yolu boş olamaz.",
                    errorCode: "ARGUMENT_EMPTY");

                WriteResult(result);
                return 1;
            }

            var payload = jsonFileService.ReadFromFile<InvoicePayload>(payloadPath);
            payload.Validate();

            result = logoObjectService.TransferPurchaseInvoice(payload);
            result.Details["payload_path"] = payloadPath;

            WriteResult(result);
            return result.IsSuccess ? 0 : 1;
        }
        catch (JsonException jsonException)
        {
            result = BridgeResult.Failure(
                message: $"Payload JSON parse edilemedi: {jsonException.Message}",
                errorCode: "PAYLOAD_JSON_INVALID");
            result.Details["exception_type"] = nameof(JsonException);

            WriteResult(result);
            return 1;
        }
        catch (Exception exception)
        {
            result = BridgeResult.Failure(
                message: exception.Message,
                errorCode: "UNHANDLED_EXCEPTION");
            result.Details["exception_type"] = exception.GetType().Name;

            WriteResult(result);
            return 1;
        }
    }

    private static void WriteResult(BridgeResult result)
    {
        var serializerOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
        };

        var jsonOutput = JsonSerializer.Serialize(result, serializerOptions);
        global::System.Console.WriteLine(jsonOutput);
    }
}