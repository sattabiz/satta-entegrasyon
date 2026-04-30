using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Reflection;
using LogoBridge.Console.Models;
using UnityObjects;

namespace LogoBridge.Console.Services;

public sealed class LogoObjectService
{
    private readonly InvoiceMapper _invoiceMapper;

    public LogoObjectService()
    {
        _invoiceMapper = new InvoiceMapper();
    }

    public List<BridgeResult> TransferPurchaseInvoices(List<InvoicePayload> payloads)
    {
        var results = new List<BridgeResult>();
        if (payloads == null || payloads.Count == 0) return results;

        object? unityApplication = null;
        try
        {
            unityApplication = CreateUnityApplication();
            var connectSucceeded = CallBooleanMethod(unityApplication, "Connect");
            if (!connectSucceeded)
            {
                results.Add(BridgeResult.Failure("Logo Objects Connect başarısız oldu.", "LOGO_CONNECT_FAILED"));
                return results;
            }

            var firstPayload = payloads[0];
            if (!TryUserLogin(unityApplication, firstPayload))
            {
                results.Add(BridgeResult.Failure("Logo kullanıcı girişi başarısız oldu.", "LOGO_USER_LOGIN_FAILED"));
                return results;
            }
            if (!TryCompanyLogin(unityApplication, firstPayload))
            {
                results.Add(BridgeResult.Failure("Logo firma girişi başarısız oldu.", "LOGO_COMPANY_LOGIN_FAILED"));
                return results;
            }

            foreach (var payload in payloads)
            {
                var result = TransferSinglePurchaseInvoice(unityApplication, payload);
                results.Add(result);
            }
        }
        catch (Exception ex)
        {
            var result = BridgeResult.Failure($"Toplu işlem sırasında hata: {ex.Message}", "BATCH_EXCEPTION");
            result.Details["exception_type"] = ex.GetType().Name;
            results.Add(result);
        }
        finally
        {
            SafeLogoutAndDisconnect(unityApplication);
        }

        return results;
    }

    private BridgeResult TransferSinglePurchaseInvoice(object unityApplication, InvoicePayload payload)
    {
        object? dataObject = null;
        try
        {
            if (payload is null) return BridgeResult.Failure("Invoice payload boş olamaz.", "PAYLOAD_NULL");

            payload.Validate();
            var validationErrors = ValidateBusinessRules(payload);
            if (validationErrors.Count > 0)
            {
                return BridgeResult.Failure("Payload iş kuralları doğrulamasından geçemedi.", "BUSINESS_VALIDATION_FAILED", validationErrors);
            }

            var headerFields = _invoiceMapper.MapHeaderFields(payload);
            var transactionLines = _invoiceMapper.MapTransactionLines(payload);

            var creationResult = TryCreatePurchaseInvoiceDataObject(unityApplication);
            dataObject = creationResult.DataObject;
            if (dataObject is null)
            {
                var result = BuildLogoFailureResult(unityApplication, dataObject, payload, headerFields, transactionLines,
                    "Satınalma faturası object oluşturulamadı.", "LOGO_DATA_OBJECT_CREATE_FAILED");
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            if (!TryInitializeDataObject(dataObject))
            {
                var result = BuildLogoFailureResult(unityApplication, dataObject, payload, headerFields, transactionLines,
                    "Satınalma faturası object başlatılamadı.", "LOGO_DATA_OBJECT_INIT_FAILED");
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            if (!TryMapHeaderFields(dataObject, payload, out var headerError))
            {
                var result = BuildLogoFailureResult(unityApplication, dataObject, payload, headerFields, transactionLines,
                    "Fatura üst bilgileri yazılamadı.", "LOGO_HEADER_MAPPING_FAILED");
                result.Details["header_mapping_error"] = headerError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            if (!TryMapTransactionLines(dataObject, payload, out var lineError))
            {
                var result = BuildLogoFailureResult(unityApplication, dataObject, payload, headerFields, transactionLines,
                    "Fatura satırları yazılamadı.", "LOGO_LINE_MAPPING_FAILED");
                result.Details["line_mapping_error"] = lineError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            TryFillAccCodes(dataObject);

            if (!TryPostDataObject(dataObject, unityApplication, out var postError))
            {
                var result = BuildLogoFailureResult(unityApplication, dataObject, payload, headerFields, transactionLines,
                    "Fatura Logo'ya kaydedilemedi.", "LOGO_POST_FAILED");
                result.Details["post_error_desc"] = postError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var resultSuccess = BridgeResult.Success(
                message: "Satınalma faturası Logo'ya başarıyla kaydedildi.",
                logicalRef: ReadPossibleIntPropertyOrMethod(dataObject, "InternalReference", "LogicalRef", "DATA_REFERENCE"),
                invoiceNumber: payload.InvoiceNumber,
                documentNumber: payload.DocumentNumber,
                arpCode: payload.ArpCode);

            AppendPayloadSummary(resultSuccess, payload);
            AppendMappedHeaderSummary(resultSuccess, headerFields);
            AppendMappedLineSummary(resultSuccess, transactionLines);
            AppendLogoRuntimeDetails(resultSuccess, unityApplication, dataObject);
            resultSuccess.Details["data_object_create_strategy"] = creationResult.Strategy;

            return resultSuccess;
        }
        catch (Exception exception)
        {
            var result = BridgeResult.Failure($"Logo Objects servis hatası: {exception.Message}", "LOGO_OBJECTS_SERVICE_EXCEPTION");
            result.Details["exception_type"] = exception.GetType().Name;
            return result;
        }
    }

    public BridgeResult TransferPurchaseInvoice(InvoicePayload payload)
    {
        object? unityApplication = null;
        object? dataObject = null;

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
                    dataObject,
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
                    dataObject,
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
                    dataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Logo firma girişi başarısız oldu.",
                    "LOGO_COMPANY_LOGIN_FAILED");
            }

            var creationResult = TryCreatePurchaseInvoiceDataObject(unityApplication);
            dataObject = creationResult.DataObject;
            if (dataObject is null)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    dataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Satınalma faturası object oluşturulamadı. Unity DataObjectType enum değeri çözümlenemedi veya object açılamadı.",
                    "LOGO_DATA_OBJECT_CREATE_FAILED");
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            if (!TryInitializeDataObject(dataObject))
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    dataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Satınalma faturası object başlatılamadı.",
                    "LOGO_DATA_OBJECT_INIT_FAILED");
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var headerMappingSucceeded = TryMapHeaderFields(dataObject, payload, out var headerError);
            if (!headerMappingSucceeded)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    dataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Fatura üst bilgileri Logo object üzerine yazılamadı.",
                    "LOGO_HEADER_MAPPING_FAILED");
                result.Details["header_mapping_error"] = headerError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var lineMappingSucceeded = TryMapTransactionLines(dataObject, payload, out var lineError);
            if (!lineMappingSucceeded)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    dataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Fatura satırları Logo object üzerine yazılamadı.",
                    "LOGO_LINE_MAPPING_FAILED");
                result.Details["line_mapping_error"] = lineError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            TryFillAccCodes(dataObject);

            var postSucceeded = TryPostDataObject(dataObject, unityApplication, out var postError);
            if (!postSucceeded)
            {
                var result = BuildLogoFailureResult(
                    unityApplication,
                    dataObject,
                    payload,
                    headerFields,
                    transactionLines,
                    "Satınalma faturası Logo'ya kaydedilemedi.",
                    "LOGO_POST_FAILED");
                result.Details["post_error_desc"] = postError;
                result.Details["data_object_create_strategy"] = creationResult.Strategy;
                return result;
            }

            var resultSuccess = BridgeResult.Success(
                message: "Satınalma faturası Logo'ya başarıyla kaydedildi.",
                logicalRef: ReadPossibleIntPropertyOrMethod(dataObject, "InternalReference", "LogicalRef", "DATA_REFERENCE"),
                invoiceNumber: payload.InvoiceNumber,
                documentNumber: payload.DocumentNumber,
                arpCode: payload.ArpCode);

            AppendPayloadSummary(resultSuccess, payload);
            AppendMappedHeaderSummary(resultSuccess, headerFields);
            AppendMappedLineSummary(resultSuccess, transactionLines);
            AppendLogoRuntimeDetails(resultSuccess, unityApplication, dataObject);
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

    private (object? DataObject, string Strategy) TryCreatePurchaseInvoiceDataObject(object unityApplication)
    {
    var candidates = new List<(object EnumValue, string Strategy)>
    {
        (DataObjectType.doPurchInvoice, "NewDataObject(doPurchInvoice)"),
        (DataObjectType.doSalesInvoice, "NewDataObject(doSalesInvoice)")
    };

    var triedStrategies = new List<string>();

    foreach (var candidate in candidates)
    {
        triedStrategies.Add(candidate.Strategy);

        var invocation = TryInvokeMethodForObject(unityApplication, "NewDataObject", candidate.EnumValue);
        if (invocation.MethodFound && invocation.ReturnValue is not null)
        {
            return (invocation.ReturnValue, candidate.Strategy);
        }

        triedStrategies.Add($"invoke_failed:{candidate.Strategy}");
    }

    return (null, string.Join(" | ", triedStrategies));
    }

    private bool TryInitializeDataObject(object dataObject)
    {
        var newInvocation = TryInvokeMethod(dataObject, "New", Array.Empty<object>());
        if (newInvocation.MethodFound)
        {
            return newInvocation.Success;
        }

        return true;
    }

    private bool TryMapHeaderFields(dynamic dataObject, InvoicePayload payload, out string errorMessage)
    {
        try
        {
            var typeCode = ReadOptionalPayloadInt(payload, "LogoInvoiceType", "InvoiceTypeCode");
            if (typeCode <= 0) typeCode = 1;

            dataObject.DataFields.FieldByName("TYPE").Value = typeCode;
            dataObject.DataFields.FieldByName("NUMBER").Value = string.IsNullOrWhiteSpace(payload.InvoiceNumber) ? "~" : payload.InvoiceNumber;
            
            if (!string.IsNullOrWhiteSpace(payload.DocumentNumber))
                dataObject.DataFields.FieldByName("DOC_NUMBER").Value = payload.DocumentNumber;
                
            dataObject.DataFields.FieldByName("AUXIL_CODE").Value = ReadOptionalPayloadString(payload, "AuxiliaryCode", "AUTO");
            
            var docDateStr = payload.DocumentDate?.ToString("dd.MM.yyyy", CultureInfo.InvariantCulture) ?? string.Empty;
            dataObject.DataFields.FieldByName("DATE").Value = docDateStr;
            dataObject.DataFields.FieldByName("DOC_DATE").Value = docDateStr;
            
            dataObject.DataFields.FieldByName("TIME").Value = ResolveLogoPackedTime(payload.DocumentTime);
            dataObject.DataFields.FieldByName("ARP_CODE").Value = payload.ArpCode ?? string.Empty;
            
            var paymentCode = ReadOptionalPayloadString(payload, "PaymentCode", string.Empty);
            if (!string.IsNullOrWhiteSpace(paymentCode))
                dataObject.DataFields.FieldByName("PAYMENT_CODE").Value = paymentCode;

            dataObject.DataFields.FieldByName("NOTES1").Value = payload.Description ?? string.Empty;
            dataObject.DataFields.FieldByName("SOURCE_WH").Value = payload.WarehouseNr;
            dataObject.DataFields.FieldByName("DIVISION").Value = payload.Division;
            dataObject.DataFields.FieldByName("DEPARTMENT").Value = payload.Department;

            errorMessage = string.Empty;
            return true;
        }
        catch (Exception ex)
        {
            errorMessage = $"Header mapping failed: {ex.Message}";
            return false;
        }
    }

    private bool TryMapTransactionLines(dynamic dataObject, InvoicePayload payload, out string errorMessage)
    {
        try
        {
            dynamic transactionsField = dataObject.DataFields.FieldByName("TRANSACTIONS");
            dynamic linesObject = transactionsField.Lines;

            for (var index = 0; index < payload.Lines.Count; index++)
            {
                linesObject.AppendLine();
                dynamic currentLine = linesObject[index];
                var line = payload.Lines[index];

                currentLine.FieldByName("TYPE").Value = (short)(line.LineType >= 0 ? line.LineType : 0);
                currentLine.FieldByName("MASTER_CODE").Value = line.MasterCode ?? string.Empty;
                currentLine.FieldByName("QUANTITY").Value = (double)(line.Quantity > 0 ? line.Quantity : 1.0m);
                currentLine.FieldByName("PRICE").Value = (double)line.UnitPrice;
                currentLine.FieldByName("VAT_RATE").Value = (double)(line.VatRate >= 0 ? line.VatRate : 0m);
                currentLine.FieldByName("UNIT_CODE").Value = string.IsNullOrWhiteSpace(line.UnitCode) ? "ADET" : line.UnitCode;
                currentLine.FieldByName("UNIT_CONV1").Value = (double)1.0;
                currentLine.FieldByName("UNIT_CONV2").Value = (double)1.0;
                
                if (line.WarehouseNr > 0)
                    currentLine.FieldByName("SOURCEINDEX").Value = line.WarehouseNr;
                else
                    currentLine.FieldByName("SOURCEINDEX").Value = payload.WarehouseNr;
            }

            errorMessage = string.Empty;
            return true;
        }
        catch (Exception ex)
        {
            errorMessage = $"Line mapping failed: {ex.Message}";
            return false;
        }
    }

    private object? TryGetLineByIndex(object linesObject, int index)
    {
        var candidates = new[]
        {
            new { Method = "Item", Args = new object[] { index } },
            new { Method = "get_Item", Args = new object[] { index } },
        };

        foreach (var candidate in candidates)
        {
            var invocation = TryInvokeMethodForObject(linesObject, candidate.Method, candidate.Args);
            if (invocation.MethodFound && invocation.ReturnValue is not null)
            {
                return invocation.ReturnValue;
            }
        }

        try
        {
            return linesObject.GetType().InvokeMember(
                string.Empty,
                BindingFlags.GetProperty | BindingFlags.Public | BindingFlags.Instance,
                binder: null,
                target: linesObject,
                args: new object[] { index });
        }
        catch
        {
            return null;
        }
    }

    private bool TryPostDataObject(dynamic dataObject, dynamic unityApplication, out string errorMessage)
    {
        try
        {
            dynamic dynData = dataObject;
            bool isSuccess = dynData.Post();
            if (isSuccess)
            {
                errorMessage = string.Empty;
                return true;
            }

            var errorCode = dynData.ErrorCode;
            var errorDesc = dynData.ErrorDesc;
            
            var detailedError = $"[Code: {errorCode}] {errorDesc}";
            
            try 
            {
                var dbError1 = unityApplication.GetLastErrorString();
                if (!string.IsNullOrWhiteSpace((string)dbError1)) detailedError += $" | AppErr: {dbError1}";
            } catch { }

            try 
            {
                var dbError2 = unityApplication.GetLastDBObjectError();
                if (!string.IsNullOrWhiteSpace((string)dbError2)) detailedError += $" | DBErr: {dbError2}";
            } catch { }
            
            try 
            {
                var validationErrors = dynData.ValidateErrors;
                if (validationErrors != null && validationErrors.Count > 0)
                {
                    detailedError += " | Validation: " + validationErrors[0].Error;
                }
            } catch { }

            errorMessage = detailedError;
            return false;
        }
        catch (Exception ex)
        {
            errorMessage = $"Post exception: {ex.Message}";
            return false;
        }
    }

    private void TryFillAccCodes(object dataObject)
    {
        TryInvokeMethod(dataObject, "FillAccCodes", Array.Empty<object>());
    }

    private bool TrySetDataFieldValue(object target, string fieldName, object? value)
    {
        var fieldObject = TryGetDataFieldObject(target, fieldName);
        if (fieldObject is null)
        {
            return false;
        }

        return TrySetMemberValue(fieldObject, "Value", value);
    }

    private bool TrySetFirstAvailableDataFieldValue(object target, IEnumerable<string> fieldNames, object? value)
    {
        foreach (var fieldName in fieldNames)
        {
            if (TrySetDataFieldValue(target, fieldName, value))
            {
                return true;
            }
        }

        return false;
    }

    private bool TrySetLineFieldValue(object lineObject, string fieldName, object? value)
    {
        var fieldObject = TryGetFieldByName(lineObject, fieldName);
        if (fieldObject is null)
        {
            return false;
        }

        return TrySetMemberValue(fieldObject, "Value", value);
    }

    private bool TrySetFirstAvailableLineFieldValue(object lineObject, IEnumerable<string> fieldNames, object? value)
    {
        foreach (var fieldName in fieldNames)
        {
            if (TrySetLineFieldValue(lineObject, fieldName, value))
            {
                return true;
            }
        }

        return false;
    }

    private object? TryGetDataFieldObject(object target, string fieldName)
    {
        var dataFields = TryGetMemberValue(target, "DataFields");
        if (dataFields is null)
        {
            return null;
        }

        return TryGetFieldByName(dataFields, fieldName);
    }

    private object? TryGetFieldByName(object container, string fieldName)
    {
        var candidates = new[]
        {
            new { Method = "FieldByName", Args = new object[] { fieldName } },
            new { Method = "Item", Args = new object[] { fieldName } },
            new { Method = "get_Item", Args = new object[] { fieldName } },
        };

        foreach (var candidate in candidates)
        {
            var invocation = TryInvokeMethodForObject(container, candidate.Method, candidate.Args);
            if (invocation.MethodFound && invocation.ReturnValue is not null)
            {
                return invocation.ReturnValue;
            }
        }

        return null;
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
        object? dataObject,
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
        AppendLogoRuntimeDetails(result, unityApplication, dataObject);
        return result;
    }

    private void AppendLogoRuntimeDetails(BridgeResult result, object unityApplication, object? dataObject)
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

        if (dataObject is not null)
        {
            result.Details["data_object_error_code"] = ReadPossibleStringPropertyOrMethod(
                dataObject,
                "ErrorCode",
                "GetLastError");

            result.Details["data_object_error_desc"] = ReadPossibleStringPropertyOrMethod(
                dataObject,
                "ErrorDesc",
                "ErrorDescription");

            result.Details["data_object_db_error_desc"] = ReadPossibleStringPropertyOrMethod(
                dataObject,
                "DBErrorDesc",
                "GetLastDBObjectError");
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

    private object? TryResolveUnityEnumValue(string enumMemberName)
    {
    try
    {
        var primaryAssembly = typeof(UnityApplication).Assembly;

        var primaryEnumType = primaryAssembly.GetTypes()
            .FirstOrDefault(type =>
                type.IsEnum &&
                (string.Equals(type.Name, "DataObjectType", StringComparison.OrdinalIgnoreCase) ||
                 string.Equals(type.FullName, "UnityObjects.DataObjectType", StringComparison.OrdinalIgnoreCase)));

        if (primaryEnumType is not null)
        {
            try
            {
                return Enum.Parse(primaryEnumType, enumMemberName, ignoreCase: true);
            }
            catch
            {
            }
        }
    }
    catch
    {
    }

    try
    {
        var assemblies = AppDomain.CurrentDomain.GetAssemblies();

        foreach (var assembly in assemblies)
        {
            Type? enumType = null;

            try
            {
                enumType = assembly.GetTypes()
                    .FirstOrDefault(type =>
                        type.IsEnum &&
                        (string.Equals(type.Name, "DataObjectType", StringComparison.OrdinalIgnoreCase) ||
                         string.Equals(type.FullName, "UnityObjects.DataObjectType", StringComparison.OrdinalIgnoreCase)));
            }
            catch
            {
                continue;
            }

            if (enumType is null)
            {
                continue;
            }

            try
            {
                return Enum.Parse(enumType, enumMemberName, ignoreCase: true);
            }
            catch
            {
            }
        }
    }
    catch
    {
    }

    return null;
    }

    private int ReadPossibleIntPropertyOrMethod(object target, params string[] memberNames)
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
                        return Convert.ToInt32(propertyValue, CultureInfo.InvariantCulture);
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
                    var methodResult = method.Invoke(target, null);
                    if (methodResult is not null)
                    {
                        return Convert.ToInt32(methodResult, CultureInfo.InvariantCulture);
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

    private int ResolveLogoPackedTime(string? documentTime)
    {
        if (string.IsNullOrWhiteSpace(documentTime))
        {
            return PackTime(12, 12, 12);
        }

        if (TimeSpan.TryParse(documentTime, CultureInfo.InvariantCulture, out var parsedTime))
        {
            return PackTime(parsedTime.Hours, parsedTime.Minutes, parsedTime.Seconds);
        }

        return PackTime(12, 12, 12);
    }

    private int PackTime(int hour, int minute, int second)
    {
        return (hour * 16777216) + (minute * 65536) + (second * 256);
    }

    private bool IsEmptyValue(object? value)
    {
        return value is null || string.IsNullOrWhiteSpace(Convert.ToString(value, CultureInfo.InvariantCulture));
    }

    private object? TryGetMemberValue(object target, string memberName)
    {
        try
        {
            var property = target.GetType().GetProperty(memberName, BindingFlags.Public | BindingFlags.Instance);
            if (property is not null)
            {
                return property.GetValue(target);
            }
        }
        catch
        {
            // Bir sonraki yol denenir.
        }

        try
        {
            var method = target.GetType().GetMethod(memberName, BindingFlags.Public | BindingFlags.Instance);
            if (method is not null && method.GetParameters().Length == 0)
            {
                return method.Invoke(target, null);
            }
        }
        catch
        {
            // Bir sonraki yol denenir.
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
        }

        return errors;
    }
}