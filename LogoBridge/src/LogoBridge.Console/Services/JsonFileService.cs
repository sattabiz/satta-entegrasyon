

using System;
using System.IO;
using System.Text.Json;

namespace LogoBridge.Console.Services;

public sealed class JsonFileService
{
    private readonly JsonSerializerOptions _readOptions = new()
    {
        PropertyNameCaseInsensitive = true,
    };

    private readonly JsonSerializerOptions _writeOptions = new()
    {
        WriteIndented = true,
    };

    public T ReadFromFile<T>(string filePath)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            throw new InvalidOperationException("JSON dosya yolu boş olamaz.");
        }

        if (!File.Exists(filePath))
        {
            throw new FileNotFoundException($"JSON dosyası bulunamadı: {filePath}", filePath);
        }

        var jsonText = File.ReadAllText(filePath);
        if (string.IsNullOrWhiteSpace(jsonText))
        {
            throw new InvalidOperationException($"JSON dosyası boş: {filePath}");
        }

        var result = JsonSerializer.Deserialize<T>(jsonText, _readOptions);
        if (result is null)
        {
            throw new InvalidOperationException($"JSON deserialize edilemedi: {filePath}");
        }

        return result;
    }

    public void WriteToFile<T>(string filePath, T value)
    {
        if (string.IsNullOrWhiteSpace(filePath))
        {
            throw new InvalidOperationException("JSON çıktı dosya yolu boş olamaz.");
        }

        var directoryPath = Path.GetDirectoryName(filePath);
        if (!string.IsNullOrWhiteSpace(directoryPath) && !Directory.Exists(directoryPath))
        {
            Directory.CreateDirectory(directoryPath);
        }

        var jsonText = JsonSerializer.Serialize(value, _writeOptions);
        File.WriteAllText(filePath, jsonText);
    }
}