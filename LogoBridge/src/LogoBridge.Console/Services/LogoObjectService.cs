using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
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
        object? invoiceDataObject = null;

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
                    invoiceDataObject,
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
                    invoiceDataObject,
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
                    invoiceDataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Logo firma girişi başarısız oldu.",
                    "LOGO_COMPANY_LOGIN_FAILED");
            }

            var creationResult = TryCreatePurchaseInvoiceDataObject(unityApplication);
            invoiceDataObject = creationResult.DataObject;
            if (invoiceDataObject is null)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    invoiceDataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Satınalma faturası data object oluşturulamadı.",
                    "LOGO_DATA_OBJECT_CREATE_FAILED");
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                result.Details["unity_available_members"] = string.Join(", ", GetPublicMemberNames(unityApplication));
                return result;
            }

            var headerMappingSucceeded = TryMapHeaderFields(invoiceDataObject, headerFields, out var headerError);
            if (!headerMappingSucceeded)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    invoiceDataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Fatura üst bilgi alanları Logo data object üzerine yazılamadı.",
                    "LOGO_HEADER_MAPPING_FAILED");
                result.Details["header_mapping_error"] = headerError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var lineMappingSucceeded = TryMapTransactionLines(invoiceDataObject, transactionLines, out var lineError);
            if (!lineMappingSucceeded)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    invoiceDataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Fatura satırları Logo data object üzerine yazılamadı.",
                    "LOGO_LINE_MAPPING_FAILED");
                result.Details["line_mapping_error"] = lineError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var postSucceeded = TryPostDataObject(invoiceDataObject);
            if (!postSucceeded)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    invoiceDataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Satınalma faturası Logo'ya kaydedilemedi.",
                    "LOGO_POST_FAILED");
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var resultSuccess = BridgeResult.Success(
                message: "Satınalma faturası Logo'ya başarıyla kaydedildi.",
                logicalRef: ReadPossibleIntPropertyOrMethod(invoiceDataObject, "LogicalRef", "InternalReference", "GetInternalReference"),
                invoiceNumber: payload.InvoiceNumber,
                documentNumber: payload.DocumentNumber,
                arpCode: payload.ArpCode);

            AppendPayloadSummary(resultSuccess, payload);
            AppendMappedHeaderSummary(resultSuccess, headerFields);
            AppendMappedLineSummary(resultSuccess, transactionLines);
            AppendLogoRuntimeDetails(resultSuccess, unityApplication, invoiceDataObject);
            resultSuccess.Details["data_object_create_strategy"] = creationResult.Strategy;

            return resultSuccess;
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

    private (object? DataObject, string Strategy) TryCreatePurchaseInvoiceDataObject(object unityApplication)
    {
        var candidateStrategies = new List<(string MethodName, object[] Args, string StrategyName)>
        {
            ("NewDataObject", new object[] { "doPurchInvoice" }, "NewDataObject(doPurchInvoice)"),
            ("NewDataObject", new object[] { "purchaseInvoice" }, "NewDataObject(purchaseInvoice)"),
            ("NewDataObject", new object[] { "PurchInvoice" }, "NewDataObject(PurchInvoice)"),
            ("NewDataObject", new object[] { 1 }, "NewDataObject(1)"),
            ("NewDataObject", new object[] { 8 }, "NewDataObject(8)"),
            ("GetDataObject", new object[] { "doPurchInvoice" }, "GetDataObject(doPurchInvoice)"),
            ("GetDataObject", new object[] { "purchaseInvoice" }, "GetDataObject(purchaseInvoice)"),
            ("CreateDataObject", new object[] { "doPurchInvoice" }, "CreateDataObject(doPurchInvoice)"),
            ("CreateDataObject", new object[] { "purchaseInvoice" }, "CreateDataObject(purchaseInvoice)"),
        };

        foreach (var candidate in candidateStrategies)
        {
            var invocation = TryInvokeMethodForObject(unityApplication, candidate.MethodName, candidate.Args);
            if (invocation.MethodFound && invocation.Success && invocation.ReturnValue is not null)
            {
                return (invocation.ReturnValue, candidate.StrategyName);
            }
        }

        return (null, string.Empty);
    }

    private bool TryMapHeaderFields(object invoiceDataObject, Dictionary<string, string> headerFields, out string errorMessage)
    {
        var skippedOptionalFields = new List<string>();

        foreach (var field in headerFields)
        {
            var candidateNames = GetHeaderFieldCandidates(field.Key);
            var setSucceeded = false;

            foreach (var candidateName in candidateNames)
            {
                if (TrySetFieldValue(invoiceDataObject, candidateName, field.Value))
                {
                    setSucceeded = true;
                    break;
                }
            }

            if (setSucceeded)
            {
                continue;
            }

            if (IsOptionalHeaderField(field.Key))
            {
                skippedOptionalFields.Add(field.Key);
                continue;
            }

            errorMessage = $"Header alanı yazılamadı: {field.Key}";
            return false;
        }

        errorMessage = skippedOptionalFields.Count > 0
            ? $"Opsiyonel alanlar atlandı: {string.Join(", ", skippedOptionalFields)}"
            : string.Empty;

        return true;
    }

    private IEnumerable<string> GetHeaderFieldCandidates(string fieldName)
    {
        return fieldName.ToUpperInvariant() switch
        {
            "TYPE" => new[] { "TYPE", "TRCODE" },
            "NUMBER" => new[] { "NUMBER", "FICHENO", "FICHE_NO" },
            "DOC_NUMBER" => new[] { "DOC_NUMBER", "DOCUMENT_NO", "DOCUMENT_NUMBER" },
            "DATE" => new[] { "DATE" },
            "TIME" => new[] { "TIME", "HOUR" },
            "ARP_CODE" => new[] { "ARP_CODE", "CLIENT_CODE", "ARP_REF", "CLIENTREF" },
            "DESCRIPTION" => new[] { "DESCRIPTION" },
            "AUXILIARY_CODE" => new[] { "AUXILIARY_CODE", "AUX_CODE" },
            "AUTH_CODE" => new[] { "AUTH_CODE", "AUTHORIZATION_CODE" },
            "TRADING_GROUP" => new[] { "TRADING_GROUP" },
            "DIVISION" => new[] { "DIVISION" },
            "DEPARTMENT" => new[] { "DEPARTMENT" },
            "SOURCE_WH" => new[] { "SOURCE_WH", "SOURCEINDEX", "SOURCE_INDEX", "WAREHOUSE_NR", "WAREHOUSENR" },
            "SOURCE_COST_GRP" => new[] { "SOURCE_COST_GRP", "SOURCECOSTGRP", "SOURCE_COSTGROUP", "SOURCE_INDEX" },
            "FACTORY_NR" => new[] { "FACTORY_NR", "FACTORYNR" },
            "CURR_INVOICE" => new[] { "CURR_INVOICE", "CURRENCY_CODE", "CURR_CODE" },
            "TC_XRATE" => new[] { "TC_XRATE", "EXCHANGE_RATE" },
            "RC_XRATE" => new[] { "RC_XRATE", "EXCHANGE_RATE" },
            "NOTES" => new[] { "NOTES" },
            _ => new[] { fieldName }
        };
    }

    private bool IsOptionalHeaderField(string fieldName)
    {
        var optionalFields = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "NUMBER",
            "TYPE",
            "DOC_NUMBER",
            "TIME",
            "AUXILIARY_CODE",
            "AUTH_CODE",
            "TRADING_GROUP",
            "FACTORY_NR",
            "CURRENCY_CODE",
            "EXCHANGE_RATE"
        };

        return optionalFields.Contains(fieldName);
    }

    private IEnumerable<string> GetLineFieldCandidates(string fieldName)
    {
        return fieldName.ToUpperInvariant() switch
        {
            "TYPE" => new[] { "TYPE", "LINETYPE", "LINE_TYPE" },
            "MASTER_CODE" => new[] { "MASTER_CODE", "ITEM_CODE", "STOCK_CODE" },
            "DESCRIPTION" => new[] { "DESCRIPTION" },
            "QUANTITY" => new[] { "QUANTITY" },
            "UNIT_CODE" => new[] { "UNIT_CODE", "UNIT" },
            "PRICE" => new[] { "PRICE", "UNIT_PRICE" },
            "VAT_RATE" => new[] { "VAT_RATE" },
            "TOTAL" => new[] { "TOTAL" },
            "CURR_TRANSACTION" => new[] { "CURR_TRANSACTION", "CURRENCY_CODE", "CURR_CODE" },
            "TC_XRATE" => new[] { "TC_XRATE", "EXCHANGE_RATE" },
            "RC_XRATE" => new[] { "RC_XRATE", "EXCHANGE_RATE" },
            "SOURCEINDEX" => new[] { "SOURCEINDEX", "SOURCE_INDEX", "WAREHOUSE_NR", "WAREHOUSENR" },
            "SOURCECOSTGRP" => new[] { "SOURCECOSTGRP", "SOURCE_COST_GRP", "SOURCE_COSTGROUP" },
            "DIVISION" => new[] { "DIVISION" },
            "DEPARTMENT" => new[] { "DEPARTMENT" },
            "AUXILIARY_CODE" => new[] { "AUXILIARY_CODE", "AUX_CODE" },
            "PROJECT_CODE" => new[] { "PROJECT_CODE" },
            "CENTER_CODE" => new[] { "CENTER_CODE", "COST_CENTER_CODE" },
            "VARIANT_CODE" => new[] { "VARIANT_CODE" },
            _ => new[] { fieldName }
        };
    }

    private bool IsOptionalLineField(string fieldName)
    {
        var optionalFields = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "DESCRIPTION",
            "CURR_TRANSACTION",
            "TC_XRATE",
            "RC_XRATE",
            "AUXILIARY_CODE",
            "PROJECT_CODE",
            "CENTER_CODE",
            "VARIANT_CODE"
        };

        return optionalFields.Contains(fieldName);
    }

    private bool TryMapTransactionLines(object invoiceDataObject, List<Dictionary<string, string>> transactionLines, out string errorMessage)
    {
        if (transactionLines.Count == 0)
        {
            errorMessage = string.Empty;
            return true;
        }

        var transactionsField = TryGetFieldObject(invoiceDataObject, "TRANSACTIONS");
        if (transactionsField is null)
        {
            errorMessage = "TRANSACTIONS alanı bulunamadı.";
            return false;
        }

        var linesContainer = TryGetLinesContainer(transactionsField);
        if (linesContainer is null)
        {
            errorMessage = "TRANSACTIONS satır koleksiyonu bulunamadı.";
            return false;
        }

        for (var i = 0; i < transactionLines.Count; i++)
        {
            var appendResult = TryAppendLine(linesContainer);
            if (!appendResult.Success || appendResult.LineObject is null)
            {
                errorMessage = $"{i + 1}. satır için yeni transaction line oluşturulamadı.";
                return false;
            }

            var skippedOptionalFields = new List<string>();

            foreach (var field in transactionLines[i])
            {
                var candidateNames = GetLineFieldCandidates(field.Key);
                var setSucceeded = false;

                foreach (var candidateName in candidateNames)
                {
                    if (TrySetFieldValue(appendResult.LineObject, candidateName, field.Value))
                    {
                        setSucceeded = true;
                        break;
                    }
                }

                if (setSucceeded)
                {
                    continue;
                }

                if (IsOptionalLineField(field.Key))
                {
                    skippedOptionalFields.Add(field.Key);
                    continue;
                }

                errorMessage = $"{i + 1}. satır alanı yazılamadı: {field.Key}";
                return false;
            }
        }

        errorMessage = string.Empty;
        return true;
    }

    private bool TryPostDataObject(object invoiceDataObject)
    {
        var invocationResult = TryInvokeMethod(invoiceDataObject, "Post", Array.Empty<object>());
        if (invocationResult.MethodFound)
        {
            return invocationResult.Success;
        }

        invocationResult = TryInvokeMethod(invoiceDataObject, "Save", Array.Empty<object>());
        return invocationResult.MethodFound && invocationResult.Success;
    }

    private object? TryGetFieldObject(object target, string fieldName)
    {
        var fieldsContainer = TryGetMemberValue(target, "DataFields", "Fields");
        if (fieldsContainer is null)
        {
            return null;
        }

        var byNameCandidates = new[]
        {
            new { Method = "FieldByName", Args = new object[] { fieldName } },
            new { Method = "Item", Args = new object[] { fieldName } },
            new { Method = "get_Item", Args = new object[] { fieldName } },
        };

        foreach (var candidate in byNameCandidates)
        {
            var invocation = TryInvokeMethodForObject(fieldsContainer, candidate.Method, candidate.Args);
            if (invocation.MethodFound && invocation.Success && invocation.ReturnValue is not null)
            {
                return invocation.ReturnValue;
            }
        }

        return null;
    }

    private bool TrySetFieldValue(object target, string fieldName, string value)
    {
        var fieldObject = TryGetFieldObject(target, fieldName);
        if (fieldObject is null)
        {
            return false;
        }

        if (TrySetMemberValue(fieldObject, "Value", value))
        {
            return true;
        }

        var assignInvocation = TryInvokeMethod(fieldObject, "Assign", value);
        return assignInvocation.MethodFound && assignInvocation.Success;
    }

    private object? TryGetLinesContainer(object transactionsField)
    {
        return TryGetMemberValue(transactionsField, "Lines", "LineCollection", "Items");
    }

    private (bool Success, object? LineObject) TryAppendLine(object linesContainer)
    {
        var appendCandidates = new[]
        {
            "AppendLine",
            "AddLine",
            "Append",
            "Add",
        };

        foreach (var methodName in appendCandidates)
        {
            var invocation = TryInvokeMethodForObject(linesContainer, methodName, Array.Empty<object>());
            if (invocation.MethodFound && invocation.Success)
            {
                if (invocation.ReturnValue is not null)
                {
                    return (true, invocation.ReturnValue);
                }

                var currentLine = TryGetMemberValue(linesContainer, "LastLine", "CurrentLine", "ActiveLine");
                if (currentLine is not null)
                {
                    return (true, currentLine);
                }
            }
        }

        return (false, null);
    }

    private BridgeResult BuildLogoFailureResult(
        object unityApplication,
        object? invoiceDataObject,
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
        AppendLogoRuntimeDetails(result, unityApplication, invoiceDataObject);

        var dataFieldNames = GetDataFieldNames(invoiceDataObject);
        if (dataFieldNames.Count > 0)
        {
            result.Details["data_object_fields"] = string.Join(", ", dataFieldNames);
        }

        return result;
    }

    private void AppendLogoRuntimeDetails(BridgeResult result, object unityApplication, object? invoiceDataObject)
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

        if (invoiceDataObject is not null)
        {
            result.Details["data_object_last_error"] = ReadPossibleStringPropertyOrMethod(
                invoiceDataObject,
                "GetLastErrorString",
                "LastErrorString",
                "ErrorDesc",
                "ErrorDescription");

            result.Details["data_object_members"] = string.Join(", ", GetPublicMemberNames(invoiceDataObject));
        }
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

    private int ReadPossibleIntPropertyOrMethod(object target, params string[] memberNames)
    {
        foreach (var memberName in memberNames)
        {
            try
            {
                var method = target.GetType().GetMethod(memberName, BindingFlags.Public | BindingFlags.Instance);
                if (method is not null && method.GetParameters().Length == 0)
                {
                    var methodResult = method.Invoke(target, null);
                    return Convert.ToInt32(methodResult, CultureInfo.InvariantCulture);
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
                    return Convert.ToInt32(propertyValue, CultureInfo.InvariantCulture);
                }
            }
            catch
            {
                // Bir sonraki alan denenir.
            }
        }

        return 0;
    }

    private object? TryGetMemberValue(object target, params string[] memberNames)
    {
        foreach (var memberName in memberNames)
        {
            try
            {
                var property = target.GetType().GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance);
                if (property is not null)
                {
                    var propertyValue = property.GetValue(target);
                    if (propertyValue is not null)
                    {
                        return propertyValue;
                    }
                }
            }
            catch
            {
                // Bir sonraki alan denenir.
            }

            try
            {
                var method = target.GetType().GetMethod(memberName, BindingFlags.Public | BindingFlags.Instance);
                if (method is not null && method.GetParameters().Length == 0)
                {
                    var methodValue = method.Invoke(target, null);
                    if (methodValue is not null)
                    {
                        return methodValue;
                    }
                }
            }
            catch
            {
                // Bir sonraki alan denenir.
            }
        }

        return null;
    }

    private bool TrySetMemberValue(object target, string memberName, object? value)
    {
        try
        {
            var property = target.GetType().GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance);
            if (property is not null && property.CanWrite)
            {
                var convertedValue = ConvertToPropertyType(value, property.PropertyType);
                property.SetValue(target, convertedValue);
                return true;
            }
        }
        catch
        {
            // Fallback denenir.
        }

        try
        {
            target.GetType().InvokeMember(
                memberName,
                BindingFlags.SetProperty | BindingFlags.Public | BindingFlags.Instance,
                binder: null,
                target: target,
                args: new[] { value });
            return true;
        }
        catch
        {
            return false;
        }
    }

    private object? ConvertToPropertyType(object? value, Type propertyType)
    {
        if (value is null)
        {
            return null;
        }

        var targetType = Nullable.GetUnderlyingType(propertyType) ?? propertyType;
        if (targetType == typeof(string))
        {
            return Convert.ToString(value, CultureInfo.InvariantCulture) ?? string.Empty;
        }

        if (targetType == typeof(int))
        {
            return Convert.ToInt32(value, CultureInfo.InvariantCulture);
        }

        if (targetType == typeof(short))
        {
            return Convert.ToInt16(value, CultureInfo.InvariantCulture);
        }

        if (targetType == typeof(double))
        {
            return Convert.ToDouble(value, CultureInfo.InvariantCulture);
        }

        if (targetType == typeof(decimal))
        {
            return Convert.ToDecimal(value, CultureInfo.InvariantCulture);
        }

        if (targetType == typeof(bool))
        {
            return CoerceInvocationResultToSuccess(value);
        }

        return Convert.ChangeType(value, targetType, CultureInfo.InvariantCulture);
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

    private IEnumerable<string> GetPublicMemberNames(object target)
    {
        return target.GetType()
            .GetMembers(BindingFlags.Public | BindingFlags.Instance)
            .Select(member => member.Name)
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(name => name, StringComparer.OrdinalIgnoreCase)
            .Take(200)
            .ToList();
    }

    private List<string> GetDataFieldNames(object? dataObject)
    {
        var names = new List<string>();

        if (dataObject is null)
        {
            return names;
        }

        var fieldsContainer = TryGetMemberValue(dataObject, "DataFields", "Fields");
        if (fieldsContainer is null)
        {
            return names;
        }

        try
        {
            if (fieldsContainer is IEnumerable enumerable)
            {
                foreach (var item in enumerable)
                {
                    if (item is null)
                    {
                        continue;
                    }

                    var name = ReadPossibleStringPropertyOrMethod(item, "Name");
                    if (!string.IsNullOrWhiteSpace(name))
                    {
                        names.Add(name);
                    }
                }
            }
        }
        catch
        {
            // Teşhis amaçlı, hata yutulabilir.
        }

        return names
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(x => x, StringComparer.OrdinalIgnoreCase)
            .ToList();
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
}