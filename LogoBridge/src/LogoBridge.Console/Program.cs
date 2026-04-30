using System;
using System.Text.Json;
using LogoBridge.Console.Models;
using LogoBridge.Console.Services;

namespace LogoBridge.Console;

internal static class Program
{
    private static int Main(string[] args)
    {
        var results = new System.Collections.Generic.List<BridgeResult>();
        BridgeResult fatalResult;
        var jsonFileService = new JsonFileService();
        var logoObjectService = new LogoObjectService();

        try
        {
            if (args.Length == 0)
            {
                fatalResult = BridgeResult.Failure(
                    message: "Payload dosya yolu verilmedi.",
                    errorCode: "ARGUMENT_MISSING");
                results.Add(fatalResult);
                WriteResult(results);
                return 1;
            }

            var payloadPath = args[0];
            if (string.IsNullOrWhiteSpace(payloadPath))
            {
                fatalResult = BridgeResult.Failure(
                    message: "Payload dosya yolu boş olamaz.",
                    errorCode: "ARGUMENT_EMPTY");
                results.Add(fatalResult);
                WriteResult(results);
                return 1;
            }

            var payloads = jsonFileService.ReadFromFile<System.Collections.Generic.List<InvoicePayload>>(payloadPath);
            foreach(var payload in payloads)
            {
                payload.Validate();
            }

            results = logoObjectService.TransferPurchaseInvoices(payloads);
            foreach(var r in results)
            {
                r.Details["payload_path"] = payloadPath;
            }

            WriteResult(results);
            return results.TrueForAll(r => r.IsSuccess) ? 0 : 1;
        }
        catch (JsonException jsonException)
        {
            fatalResult = BridgeResult.Failure(
                message: $"Payload JSON parse edilemedi: {jsonException.Message}",
                errorCode: "PAYLOAD_JSON_INVALID");
            fatalResult.Details["exception_type"] = nameof(JsonException);
            results.Add(fatalResult);
            WriteResult(results);
            return 1;
        }
        catch (Exception exception)
        {
            fatalResult = BridgeResult.Failure(
                message: exception.Message,
                errorCode: "UNHANDLED_EXCEPTION");
            fatalResult.Details["exception_type"] = exception.GetType().Name;
            results.Add(fatalResult);
            WriteResult(results);
            return 1;
        }
    }

    private static void WriteResult(object result)
    {
        var serializerOptions = new JsonSerializerOptions
        {
            WriteIndented = true,
        };

        var jsonOutput = JsonSerializer.Serialize(result, serializerOptions);
        global::System.Console.WriteLine(jsonOutput);
    }
}