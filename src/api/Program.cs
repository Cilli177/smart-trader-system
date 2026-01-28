using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- CONFIGURAÇÕES ---
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

var dbUrl = Environment.GetEnvironmentVariable("DATABASE_URL");
var connectionString = string.IsNullOrEmpty(dbUrl) 
    ? "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk"
    : dbUrl;

builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();
builder.Services.AddCors(options => { options.AddPolicy("AllowAll", p => p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()); });

var app = builder.Build();
app.UseCors("AllowAll");
app.MapControllers();

app.MapGet("/", () => "API Online e Tipada 🚀");

// --- ENDPOINT PRINCIPAL (Agora Tipado) ---
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    try
    {
        using var conn = await dataSource.OpenConnectionAsync();
        
        // SQL Otimizado: COALESCE garante que nunca venha NULL
        // Note o cast explícito ::decimal para garantir que o Postgres entregue o tipo certo para o C#
        var sql = @"
            SELECT 
                f.ticker as Ticker, 
                COALESCE(a.price, 0)::decimal as Price, 
                COALESCE(a.pe_ratio, 0)::decimal as PeRatio, 
                COALESCE(a.dy_percentage, 0)::decimal as DyPercentage, 
                COALESCE(a.ai_analysis, 'Aguardando análise...') as AiAnalysis, 
                COALESCE(a.news_summary, 'Sem notícias.') as NewsSummary
            FROM user_favorites f
            LEFT JOIN assets a ON f.ticker = a.ticker
            ORDER BY f.ticker";
        
        // O PULO DO GATO: Usar <AssetResponse> evita erro de serialização dinâmica
        var result = await conn.QueryAsync<AssetResponse>(sql);
        
        return Results.Ok(result);
    }
    catch (Exception ex)
    {
        // Retorna o erro real para aparecer na caixa vermelha do front
        return Results.Problem($"ERRO API: {ex.Message} | Stack: {ex.StackTrace}");
    }
});

// Reset de Emergência (Mantido)
app.MapGet("/api/reset", async (NpgsqlDataSource dataSource) =>
{
    try {
        using var conn = await dataSource.OpenConnectionAsync();
        await conn.ExecuteAsync("CREATE TABLE IF NOT EXISTS user_favorites (id SERIAL PRIMARY KEY, ticker VARCHAR(10) UNIQUE, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);");
        await conn.ExecuteAsync("CREATE TABLE IF NOT EXISTS sectors (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE);");
        await conn.ExecuteAsync("CREATE TABLE IF NOT EXISTS assets (id SERIAL PRIMARY KEY, ticker VARCHAR(20) UNIQUE, name VARCHAR(100), sector_id INTEGER, price DECIMAL(18,2), pe_ratio DECIMAL(10,2), dy_percentage DECIMAL(10,2), ai_analysis TEXT, news_summary TEXT, news_links JSONB, sentiment VARCHAR(20), last_update TIMESTAMP);");
        await conn.ExecuteAsync("INSERT INTO sectors (name) VALUES ('Geral') ON CONFLICT DO NOTHING;");
        await conn.ExecuteAsync("INSERT INTO assets (ticker, name, price) VALUES ('PETR4.SA', 'Petrobras', 0), ('VALE3.SA', 'Vale', 0) ON CONFLICT (ticker) DO NOTHING;");
        return Results.Ok("Reset Realizado com Sucesso.");
    } catch (Exception ex) { return Results.Problem(ex.Message); }
});

// Adicionar (Tipado)
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

// --- DTO PARA MAPEAMENTO SEGURO ---
public class AssetResponse
{
    public string Ticker { get; set; } = string.Empty;
    public decimal Price { get; set; }
    public decimal PeRatio { get; set; }
    public decimal DyPercentage { get; set; }
    public string AiAnalysis { get; set; } = string.Empty;
    public string NewsSummary { get; set; } = string.Empty;
}