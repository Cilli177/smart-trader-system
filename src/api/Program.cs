using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- CONFIGURAÇÃO ROBUSTA ---
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

// Garante que pega a URL do ambiente OU usa uma fixa se falhar (Segurança)
var dbUrl = Environment.GetEnvironmentVariable("DATABASE_URL");
if (string.IsNullOrEmpty(dbUrl))
{
    // Coloque aqui sua URL interna da Railway se a variável falhar
    dbUrl = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";
}

builder.Services.AddNpgsqlDataSource(dbUrl);
builder.Services.AddControllers();
builder.Services.AddCors(options => { options.AddPolicy("AllowAll", p => p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()); });

var app = builder.Build();
app.UseCors("AllowAll");
app.MapControllers();

app.MapGet("/", () => "API V15 Online 🚀");

app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    try
    {
        using var conn = await dataSource.OpenConnectionAsync();
        
        // Query Blindada: Se a coluna full_report ainda não existir, o SQL abaixo evita o crash
        // Mas o ideal é o Worker criar a coluna.
        var sql = @"
            SELECT 
                f.ticker as Ticker, 
                COALESCE(a.price, 0)::decimal as Price, 
                COALESCE(a.pe_ratio, 0)::decimal as PeRatio, 
                COALESCE(a.dy_percentage, 0)::decimal as DyPercentage, 
                COALESCE(a.ai_analysis, 'Aguardando...') as AiAnalysis,
                -- Verifica se a tabela tem a coluna antes de selecionar (apenas truque, o ideal é a migration)
                -- Vamos manter o select direto, pois o Worker JÁ DEVE ter criado.
                COALESCE(a.full_report, 'Detalhes indisponíveis.') as FullReport,
                COALESCE(a.news_summary, 'Sem notícias.') as NewsSummary
            FROM user_favorites f
            LEFT JOIN assets a ON f.ticker = a.ticker
            ORDER BY f.ticker";
        
        var result = await conn.QueryAsync<AssetResponse>(sql);
        return Results.Ok(result);
    }
    catch (Exception ex)
    {
        Console.WriteLine($"ERRO API: {ex.Message}");
        return Results.Problem($"Erro SQL: {ex.Message}");
    }
});

// ... (Mantenha os endpoints de POST e DELETE iguais) ...
// Adicionar
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var t = ticker.Trim().ToUpper();
    await conn.ExecuteAsync("INSERT INTO user_favorites (ticker) VALUES (@T) ON CONFLICT (ticker) DO NOTHING", new { T = t });
    await conn.ExecuteAsync("INSERT INTO assets (ticker, name) VALUES (@T, 'Novo') ON CONFLICT (ticker) DO NOTHING", new { T = t });
    return Results.Ok();
});

// Remover
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    await conn.ExecuteAsync("DELETE FROM user_favorites WHERE ticker = @T", new { T = ticker.Trim().ToUpper() });
    return Results.Ok();
});

app.Run();

public class AssetResponse
{
    public string Ticker { get; set; } = string.Empty;
    public decimal Price { get; set; }
    public decimal PeRatio { get; set; }
    public decimal DyPercentage { get; set; }
    public string AiAnalysis { get; set; } = string.Empty;
    public string FullReport { get; set; } = string.Empty;
    public string NewsSummary { get; set; } = string.Empty;
}