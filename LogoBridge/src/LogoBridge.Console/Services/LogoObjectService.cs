using System;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
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
        object? unityApplication = null;

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

            unityApplication = CreateUnityApplication();
            var connectSucceeded = CallBooleanMethod(unityApplication, "Connect");
            if (!connectSucceeded)
            {
                return BuildLogoFailureResult(
                    unityApplication,
                    payload,
                    headerFields,
                    transactionLines,
                    "Logo Objects Connect başarısız oldu.",
                    "LOGO_CONNECT_FAILED");
            }

            var userLoginSucceeded = TryUserLogin(unityApplication, payload);
            if (!userLoginSucceeded)
            {
                return BuildLogoFailureResult(
                    unityApplication,
                    payload,
                    headerFields,
                    transactionLines,
                    "Logo kullanıcı girişi başarısız oldu.",
                    "LOGO_USER_LOGIN_FAILED");
            }

            var companyLoginSucceeded = TryCompanyLogin(unityApplication, payload);
            if (!companyLoginSucceeded)
            {
                return BuildLogoFailureResult(
                    unityApplication,
                    payload,
                    headerFields,
                    transactionLines,
                    "Logo firma girişi başarısız oldu.",
                    "LOGO_COMPANY_LOGIN_FAILED");
            }

            var result = BridgeResult.Success(
                message: "Logo Objects bağlantısı, kullanıcı girişi ve firma girişi başarılı. Fatura Post akışı henüz eklenmedi.",
                invoiceNumber: payload.InvoiceNumber,
                documentNumber: payload.DocumentNumber,
                arpCode: payload.ArpCode);

            AppendPayloadSummary(result, payload);
            AppendMappedHeaderSummary(result, headerFields);
            AppendMappedLineSummary(result, transactionLines);
            AppendLogoRuntimeDetails(result, unityApplication);
            result.Warnings.Add("Purchase invoice object oluşturma ve Post akışı henüz eklenmedi.");

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
        finally
        {
            SafeLogoutAndDisconnect(unityApplication);
        }
    }

    private object CreateUnityApplication()
    {
        var candidateProgIds = new[]
        {
            "UnityObjects.UnityApplication",
            "UnityObjects.Application",
        };

        foreach (var progId in candidateProgIds)
        {
            var comType = Type.GetTypeFromProgID(progId, throwOnError: false);
            if (comType is null)
            {
                continue;
            }

            try
            {
                var instance = Activator.CreateInstance(comType);
                if (instance is not null)
                {
                    return instance;
                }
            }
            catch
            {
                // Bir sonraki ProgID adayı denenecek.
            }
        }

        throw new InvalidOperationException(
            "UnityObjects COM nesnesi oluşturulamadı. LOBJECTS register edilmiş mi kontrol et.");
    }

    private bool TryUserLogin(object unityApplication, InvoicePayload payload)
    {
        var candidateArgumentSets = new List<object[]>
        {
            new object[] { payload.LogoUser, payload.LogoPassword },
            new object[] { payload.LogoUser, payload.LogoPassword, payload.FirmNo },
            new object[] { payload.LogoUser, payload.LogoPassword, payload.FirmNo, payload.PeriodNo },
        };

        foreach (var args in candidateArgumentSets)
        {
            var invocationResult = TryInvokeMethod(unityApplication, "UserLogin", args);
            if (invocationResult.MethodFound && invocationResult.Success)
            {
                return true;
            }
        }

        return false;
    }

    private bool TryCompanyLogin(object unityApplication, InvoicePayload payload)
    {
        var candidateArgumentSets = new List<object[]>
        {
            new object[] { payload.FirmNo },
            new object[] { payload.FirmNo, payload.PeriodNo },
            new object[] { payload.FirmNo, payload.PeriodNo, payload.LogoWorkingYear },
            new object[] { payload.LogoCompanyCode },
            new object[] { payload.LogoCompanyCode, payload.PeriodNo },
        };

        foreach (var args in candidateArgumentSets)
        {
            var invocationResult = TryInvokeMethod(unityApplication, "CompanyLogin", args);
            if (invocationResult.MethodFound && invocationResult.Success)
            {
                return true;
            }
        }

        return false;
    }

    private BridgeResult BuildLogoFailureResult(
        object unityApplication,
        InvoicePayload payload,
        Dictionary<string, string> headerFields,
        List<Dictionary<string, string>> transactionLines,
        string message,
        string errorCode)
    {
        var result = BridgeResult.Failure(message: message, errorCode: errorCode);
        AppendPayloadSummary(result, payload);
        AppendMappedHeaderSummary(result, headerFields);
        AppendMappedLineSummary(result, transactionLines);
        AppendLogoRuntimeDetails(result, unityApplication);
        return result;
    }

    private void AppendLogoRuntimeDetails(BridgeResult result, object unityApplication)
    {
        result.Details["logo_last_error"] = ReadPossibleStringPropertyOrMethod(
            unityApplication,
            "GetLastErrorString",
            "LastErrorString",
            "ErrorDesc",
            "ErrorDescription");

        result.Details["logo_last_error_code"] = ReadPossibleStringPropertyOrMethod(
            unityApplication,
            "GetLastError",
            "LastError",
            "ErrorCode");

        result.Details["logo_db_error"] = ReadPossibleStringPropertyOrMethod(
            unityApplication,
            "GetLastDBObjectError",
            "LastDBObjectError");
    }

    private string ReadPossibleStringPropertyOrMethod(object target, params string[] memberNames)
    {
        foreach (var memberName in memberNames)
        {
            try
            {
                var method = target.GetType().GetMethod(memberName, BindingFlags.Public | BindingFlags.Instance);
                if (method is not null && method.GetParameters().Length == 0)
                {
                    var methodResult = method.Invoke(target, null);
                    if (methodResult is not null)
                    {
                        return Convert.ToString(methodResult, CultureInfo.InvariantCulture) ?? string.Empty;
                    }
                }
            }
            catch
            {
                // Bir sonraki alan denenir.
            }

            try
            {
                var property = target.GetType().GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance);
                if (property is not null)
                {
                    var propertyValue = property.GetValue(target);
                    if (propertyValue is not null)
                    {
                        return Convert.ToString(propertyValue, CultureInfo.InvariantCulture) ?? string.Empty;
                    }
                }
            }
            catch
            {
                // Bir sonraki alan denenir.
            }
        }

        return string.Empty;
    }

    private bool CallBooleanMethod(object target, string methodName)
    {
        var invocationResult = TryInvokeMethod(target, methodName, Array.Empty<object>());
        return invocationResult.MethodFound && invocationResult.Success;
    }

    private (bool MethodFound, bool Success) TryInvokeMethod(object target, string methodName, params object[] args)
    {
        try
        {
            var result = target.GetType().InvokeMember(
                methodName,
                BindingFlags.InvokeMethod | BindingFlags.Public | BindingFlags.Instance,
                binder: null,
                target: target,
                args: args);

            return (true, CoerceInvocationResultToSuccess(result));
        }
        catch (MissingMethodException)
        {
            return (false, false);
        }
        catch (TargetInvocationException)
        {
            return (true, false);
        }
        catch
        {
            return (true, false);
        }
    }

    private bool CoerceInvocationResultToSuccess(object? result)
    {
        if (result is null)
        {
            return true;
        }

        if (result is bool boolResult)
        {
            return boolResult;
        }

        if (result is int intResult)
        {
            return intResult != 0;
        }

        if (result is short shortResult)
        {
            return shortResult != 0;
        }

        if (result is string stringResult)
        {
            return !string.IsNullOrWhiteSpace(stringResult)
                   && !string.Equals(stringResult, "0", StringComparison.OrdinalIgnoreCase)
                   && !string.Equals(stringResult, "false", StringComparison.OrdinalIgnoreCase);
        }

        try
        {
            return Convert.ToInt32(result, CultureInfo.InvariantCulture) != 0;
        }
        catch
        {
            return true;
        }
    }

    private void SafeLogoutAndDisconnect(object? unityApplication)
    {
        if (unityApplication is null)
        {
            return;
        }

        TryInvokeMethod(unityApplication, "CompanyLogout", Array.Empty<object>());
        TryInvokeMethod(unityApplication, "UserLogout", Array.Empty<object>());
        TryInvokeMethod(unityApplication, "Disconnect", Array.Empty<object>());
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