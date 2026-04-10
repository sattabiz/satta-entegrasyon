using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using System.Xml.Linq;
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

            return TryAppendPurchaseInvoiceXml(
                unityApplication,
                payload,
                headerFields,
                transactionLines);
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

    private BridgeResult TryAppendPurchaseInvoiceXml(
        object unityApplication,
        InvoicePayload payload,
        Dictionary<string, string> headerFields,
        List<Dictionary<string, string>> transactionLines)
    {
        var xmlDocument = BuildPurchaseInvoiceXml(payload);
        var paramXml = BuildAppendParametersXml();

        var xmlCandidates = new List<(string Format, string Value)>
        {
            ("raw", xmlDocument)
        };

        var dataTypeCandidates = new List<int>();
        var configuredXmlDataType = ReadOptionalPayloadInt(payload, "XmlDataType", "DataType");
        if (configuredXmlDataType > 0)
        {
            dataTypeCandidates.Add(configuredXmlDataType);
        }

        dataTypeCandidates.Add(1);
        dataTypeCandidates.Add(3);

        string bestError = string.Empty;
        string bestStatus = string.Empty;
        string selectedFormat = string.Empty;
        int selectedDataType = 0;
        int dataReference = 0;

        foreach (var dataType in dataTypeCandidates.Distinct())
        {
            foreach (var xmlCandidate in xmlCandidates)
            {
                var localReference = 0;
                var localXml = xmlCandidate.Value;
                var localParamXml = paramXml;
                var localError = string.Empty;
                byte localStatus = 32;

                var args = new object[]
                {
                    dataType,
                    localReference,
                    localXml,
                    localParamXml,
                    localError,
                    localStatus,
                    string.Empty,
                    0,
                    string.Empty
                };

                var invocation = TryInvokeMethodForObject(unityApplication, "AppendDataObject", args);
                if (!invocation.MethodFound)
                {
                    return BridgeResult.Failure(
                        message: "AppendDataObject metodu bulunamadı.",
                        errorCode: "LOGO_APPEND_DATA_OBJECT_NOT_FOUND");
                }

                localReference = SafeConvertToInt(args[1]);
                localError = Convert.ToString(args[4], CultureInfo.InvariantCulture) ?? string.Empty;
                localStatus = SafeConvertToByte(args[5]);

                if ((localStatus == 1 || localStatus == 0) && localReference > 0)
                {
                    var resultSuccess = BridgeResult.Success(
                        message: "Satınalma faturası Logo'ya XML AppendDataObject ile başarıyla kaydedildi.",
                        logicalRef: localReference,
                        invoiceNumber: payload.InvoiceNumber,
                        documentNumber: payload.DocumentNumber,
                        arpCode: payload.ArpCode);

                    AppendPayloadSummary(resultSuccess, payload);
                    AppendMappedHeaderSummary(resultSuccess, headerFields);
                    AppendMappedLineSummary(resultSuccess, transactionLines);
                    AppendLogoRuntimeDetails(resultSuccess, unityApplication);

                    resultSuccess.Details["append_data_type"] = dataType.ToString(CultureInfo.InvariantCulture);
                    resultSuccess.Details["append_xml_format"] = xmlCandidate.Format;
                    resultSuccess.Details["append_status"] = localStatus.ToString(CultureInfo.InvariantCulture);
                    resultSuccess.Details["append_xml_preview"] = xmlDocument.Length > 2000
                        ? xmlDocument[..2000]
                        : xmlDocument;

                    return resultSuccess;
                }

                if (!string.IsNullOrWhiteSpace(localError))
                {
                    bestError = localError;
                }

                bestStatus = localStatus.ToString(CultureInfo.InvariantCulture);
                selectedFormat = xmlCandidate.Format;
                selectedDataType = dataType;
                dataReference = localReference;
            }
        }

        var resultFailure = BridgeResult.Failure(
            message: "Satınalma faturası XML AppendDataObject ile kaydedilemedi.",
            errorCode: "LOGO_APPEND_DATA_OBJECT_FAILED");

        AppendPayloadSummary(resultFailure, payload);
        AppendMappedHeaderSummary(resultFailure, headerFields);
        AppendMappedLineSummary(resultFailure, transactionLines);
        AppendLogoRuntimeDetails(resultFailure, unityApplication);

        resultFailure.Details["append_error"] = bestError;
        resultFailure.Details["append_status"] = bestStatus;
        resultFailure.Details["append_xml_format"] = selectedFormat;
        resultFailure.Details["append_data_type"] = selectedDataType.ToString(CultureInfo.InvariantCulture);
        resultFailure.Details["append_data_reference"] = dataReference.ToString(CultureInfo.InvariantCulture);
        resultFailure.Details["append_xml_preview"] = xmlDocument.Length > 2000
            ? xmlDocument[..2000]
            : xmlDocument;

        return resultFailure;
    }

    private string BuildPurchaseInvoiceXml(InvoicePayload payload)
    {
        var documentDate = payload.DocumentDate?.ToString("dd.MM.yyyy", CultureInfo.InvariantCulture) ?? string.Empty;
        var timeValue = ResolveLogoTimeValue(payload.DocumentTime);
        var totalDiscounted = payload.Lines.Sum(x => x.Total);
        var totalVat = payload.Lines.Sum(x => x.Total * x.VatRate / 100m);
        var totalGross = totalDiscounted;
        var totalNet = totalDiscounted + totalVat;

        var invoiceElement = new XElement("INVOICE",
            new XAttribute("DBOP", "INS"),
            new XElement("TYPE", "1"),
            new XElement("NUMBER", string.IsNullOrWhiteSpace(payload.InvoiceNumber) ? "~" : payload.InvoiceNumber),
            new XElement("DATE", documentDate),
            new XElement("TIME", timeValue),
            new XElement("DOC_NUMBER", payload.DocumentNumber ?? string.Empty),
            new XElement("AUXIL_CODE", ReadOptionalPayloadString(payload, "AuxiliaryCode", string.Empty)),
            new XElement("ARP_CODE", payload.ArpCode ?? string.Empty),
            new XElement("GRPCODE", ReadOptionalPayloadString(payload, "GroupCode", "1")),
            new XElement("DOCODE", ReadOptionalPayloadString(payload, "DoCode", "~")),
            new XElement("CURRSEL_TOTAL", "1"),
            new XElement("SOURCE_WH", payload.WarehouseNr.ToString(CultureInfo.InvariantCulture)),
            new XElement("SOURCE_COST_GRP", payload.SourceIndex.ToString(CultureInfo.InvariantCulture)),
            new XElement("POST_FLAGS", "247"),
            new XElement("TOTAL_DISCOUNTED", totalDiscounted.ToString(CultureInfo.InvariantCulture)),
            new XElement("TOTAL_VAT", totalVat.ToString(CultureInfo.InvariantCulture)),
            new XElement("TOTAL_GROSS", totalGross.ToString(CultureInfo.InvariantCulture)),
            new XElement("TOTAL_NET", totalNet.ToString(CultureInfo.InvariantCulture)),
            new XElement("PAYMENT_LIST"),
            new XElement("TRANSACTIONS",
                payload.Lines.Select(line => BuildTransactionXml(line, payload)))
        );

        if (!string.Equals(payload.CurrencyCode, "TRY", StringComparison.OrdinalIgnoreCase) &&
            payload.ExchangeRate > 0)
        {
            invoiceElement.Add(new XElement("CURRSEL_TOTAL", ResolveCurrencyCode(payload.CurrencyCode)));
            invoiceElement.Add(new XElement("TC_XRATE", payload.ExchangeRate.ToString(CultureInfo.InvariantCulture)));
            invoiceElement.Add(new XElement("RC_XRATE", payload.ExchangeRate.ToString(CultureInfo.InvariantCulture)));
        }

        var root = new XElement("PURCHASE_INVOICES", invoiceElement);
        var document = new XDocument(new XDeclaration("1.0", "utf-16", "yes"), root);
        return document.ToString(SaveOptions.DisableFormatting);
    }

    private XElement BuildTransactionXml(InvoiceLinePayload line, InvoicePayload payload)
    {
        var lineElement = new XElement("TRANSACTION",
            new XElement("TYPE", "0"),
            new XElement("MASTER_CODE", line.MasterCode ?? string.Empty),
            new XElement("QUANTITY", line.Quantity.ToString(CultureInfo.InvariantCulture)),
            new XElement("PRICE", line.UnitPrice.ToString(CultureInfo.InvariantCulture)),
            new XElement("TOTAL", line.Total.ToString(CultureInfo.InvariantCulture)),
            new XElement("VAT_RATE", line.VatRate.ToString(CultureInfo.InvariantCulture)),
            new XElement("UNIT_CODE", string.IsNullOrWhiteSpace(line.UnitCode) ? "ADET" : line.UnitCode),
            new XElement("UNIT_CONV1", "1"),
            new XElement("UNIT_CONV2", "1"),
            new XElement("SOURCE_WH", line.WarehouseNr.ToString(CultureInfo.InvariantCulture)),
            new XElement("SOURCE_COST_GRP", line.SourceIndex.ToString(CultureInfo.InvariantCulture)),
            new XElement("DESCRIPTION", line.Description ?? string.Empty),
            new XElement("MONTH", payload.DocumentDate?.Month.ToString(CultureInfo.InvariantCulture) ?? "1"),
            new XElement("YEAR", payload.DocumentDate?.Year.ToString(CultureInfo.InvariantCulture) ?? DateTime.Now.Year.ToString(CultureInfo.InvariantCulture))
        );

        if (!string.Equals(line.CurrencyCode, "TRY", StringComparison.OrdinalIgnoreCase) &&
            line.ExchangeRate > 0)
        {
            lineElement.Add(new XElement("CURR_PRICE", ResolveCurrencyCode(line.CurrencyCode)));
            lineElement.Add(new XElement("TC_XRATE", line.ExchangeRate.ToString(CultureInfo.InvariantCulture)));
            lineElement.Add(new XElement("RC_XRATE", line.ExchangeRate.ToString(CultureInfo.InvariantCulture)));
            lineElement.Add(new XElement("EDT_CURR", ResolveCurrencyCode(line.CurrencyCode)));
        }

        return lineElement;
    }

    private string BuildAppendParametersXml()
    {
        return
            "<?xml version=\"1.0\" encoding=\"utf-16\"?>" +
            "<Parameters>" +
            "<ReplicMode>0</ReplicMode>" +
            "<CheckParams>1</CheckParams>" +
            "<CheckRight>1</CheckRight>" +
            "<ApplyCampaign>0</ApplyCampaign>" +
            "<ApplyCondition>0</ApplyCondition>" +
            "<FillAccCodes>1</FillAccCodes>" +
            "<FormSeriLotLines>0</FormSeriLotLines>" +
            "<GetStockLinePrice>0</GetStockLinePrice>" +
            "<ExportAllData>0</ExportAllData>" +
            "</Parameters>";
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
            new object[] { payload.LogoUser, payload.LogoPassword, payload.FirmNo, 0 },
        };

        foreach (var args in candidateArgumentSets)
        {
            var invocationResult = TryInvokeMethod(unityApplication, "UserLogin", args);
            if (invocationResult.MethodFound && invocationResult.Success)
            {
                return true;
            }
        }

        var combinedLoginArgumentSets = new List<object[]>
        {
            new object[] { payload.LogoUser, payload.LogoPassword, payload.FirmNo, 0 },
            new object[] { payload.LogoUser, payload.LogoPassword, payload.FirmNo, payload.PeriodNo },
        };

        foreach (var args in combinedLoginArgumentSets)
        {
            var invocationResult = TryInvokeMethod(unityApplication, "Login", args);
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

        return true;
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

    private int ReadOptionalPayloadInt(object payload, params string[] memberNames)
    {
        foreach (var memberName in memberNames)
        {
            try
            {
                var property = payload.GetType().GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance);
                if (property is not null)
                {
                    var value = property.GetValue(payload);
                    if (value is not null)
                    {
                        return Convert.ToInt32(value, CultureInfo.InvariantCulture);
                    }
                }
            }
            catch
            {
                // Bir sonraki alan denenir.
            }
        }

        return 0;
    }

    private string ReadOptionalPayloadString(object payload, string memberName, string defaultValue)
    {
        try
        {
            var property = payload.GetType().GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance);
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

    private bool CallBooleanMethod(object target, string methodName)
    {
        var invocationResult = TryInvokeMethod(target, methodName, Array.Empty<object>());
        return invocationResult.MethodFound && invocationResult.Success;
    }

    private (bool MethodFound, bool Success) TryInvokeMethod(object target, string methodName, params object[] args)
    {
        var invocation = TryInvokeMethodForObject(target, methodName, args);
        return (invocation.MethodFound, invocation.Success);
    }

    private (bool MethodFound, bool Success, object? ReturnValue) TryInvokeMethodForObject(object target, string methodName, params object[] args)
    {
        try
        {
            var result = target.GetType().InvokeMember(
                methodName,
                BindingFlags.InvokeMethod | BindingFlags.Public | BindingFlags.Instance,
                binder: null,
                target: target,
                args: args);

            return (true, CoerceInvocationResultToSuccess(result), result);
        }
        catch (MissingMethodException)
        {
            return (false, false, null);
        }
        catch (TargetInvocationException)
        {
            return (true, false, null);
        }
        catch
        {
            return (true, false, null);
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

        if (headerFields.TryGetValue("FICHENO", out var invoiceNumber))
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

        if (firstLine.TryGetValue("PRICE", out var unitPrice))
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


    private string ResolveLogoTimeValue(string? documentTime)
    {
        if (string.IsNullOrWhiteSpace(documentTime))
        {
            return "0";
        }

        if (TimeSpan.TryParse(documentTime, CultureInfo.InvariantCulture, out var parsedTime))
        {
            var packedTime = (parsedTime.Hours * 16777216) + (parsedTime.Minutes * 65536) + (parsedTime.Seconds * 256);
            return packedTime.ToString(CultureInfo.InvariantCulture);
        }

        return "0";
    }

    private string ResolveCurrencyCode(string? currencyCode)
    {
        var normalizedCode = (currencyCode ?? string.Empty).Trim().ToUpperInvariant();

        return normalizedCode switch
        {
            "TRY" or "TL" => "0",
            "USD" => "1",
            "EUR" => "20",
            "GBP" => "17",
            _ => "0"
        };
    }

    private int SafeConvertToInt(object? value)
    {
        try
        {
            return Convert.ToInt32(value, CultureInfo.InvariantCulture);
        }
        catch
        {
            return 0;
        }
    }

    private byte SafeConvertToByte(object? value)
    {
        try
        {
            return Convert.ToByte(value, CultureInfo.InvariantCulture);
        }
        catch
        {
            return 0;
        }
    }
}