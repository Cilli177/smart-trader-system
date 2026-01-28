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

app.MapGet("/", () => "API Online 🚀");

// --- ENDPOINT PRINCIPAL (Tipado e Seguro) ---
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    try
    {
        using var conn = await dataSource.OpenConnectionAsync();
        
        // SQL Otimizado
        var sql = @"
            SELECT 
                f.ticker as Ticker, 
                COALESCE(a.price, 0)::decimal as Price, 
                COALESCE(a.pe_ratio, 0)::decimal as PeRatio, 
                COALESCE(a.dy_percentage, 0)::decimal as DyPercentage, 
                COALESCE(a.ai_analysis, 'Aguardando Worker...') as AiAnalysis, 
                COALESCE(a.news_summary, 'Sem notícias.') as NewsSummary
            FROM user_favorites f
            LEFT JOIN assets a ON f.ticker = a.ticker
            ORDER BY f.ticker";
        
        var result = await conn.QueryAsync<AssetResponse>(sql);
        return Results.Ok(result);
    }
    catch (Exception ex)
    {
        // Log para ver o erro real no painel da Railway se precisar
        Console.WriteLine($"[ERRO API]: {ex.Message}");
        return Results.Problem($"ERRO NO SERVIDOR: {ex.Message}");
    }
});

// --- RESET NUCLEAR (A Solução do Problema) ---
app.MapGet("/api/reset", async (NpgsqlDataSource dataSource) =>
{
    try {
        using var conn = await dataSource.OpenConnectionAsync();
        
        // 1. DESTRÓI TUDO O QUE É VELHO (CUIDADO: Apaga dados existentes)
        await conn.ExecuteAsync("DROP TABLE IF EXISTS market_quotes CASCADE;");
        await conn.ExecuteAsync("DROP TABLE IF EXISTS assets CASCADE;");
        await conn.ExecuteAsync("DROP TABLE IF EXISTS sectors CASCADE;");
        await conn.ExecuteAsync("DROP TABLE IF EXISTS user_favorites CASCADE;");

        // 2. RECRIAR DO ZERO (Estrutura Nova com colunas de IA)
        await conn.ExecuteAsync(@"
            CREATE TABLE user_favorites (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) UNIQUE NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ");

        await conn.ExecuteAsync(@"
            CREATE TABLE sectors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL
            );
        ");

        await conn.ExecuteAsync(@"
            CREATE TABLE assets (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) UNIQUE NOT NULL,
                name VARCHAR(100),
                sector_id INTEGER,
                price DECIMAL(18,2) DEFAULT 0,
                pe_ratio DECIMAL(10,2) DEFAULT 0,
                dy_percentage DECIMAL(10,2) DEFAULT 0,
                ai_analysis TEXT,
                news_summary TEXT,
                news_links JSONB,
                sentiment VARCHAR(20) DEFAULT 'Neutro',
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ");

        // 3. SEED (Dados Iniciais)
        await conn.ExecuteAsync("INSERT INTO sectors (name) VALUES ('Geral');");
        await conn.ExecuteAsync("INSERT INTO assets (ticker, name, ai_analysis) VALUES ('PETR4.SA', 'Petrobras', 'Análise de Teste: Ativo sólido.'), ('VALE3.SA', 'Vale', 'Aguardando processamento.');");
        await conn.ExecuteAsync("INSERT INTO user_favorites (ticker) VALUES ('PETR4.SA'), ('VALE3.SA');");

        return Results.Ok("SUCESSO: Banco Resetado e Tabelas Novas Criadas!");
    } catch (Exception ex) { return Results.Problem($"Erro no Reset: {ex.Message}"); }
});

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

// DTO
public class AssetResponse
{
    public string Ticker { get; set; } = string.Empty;
    public decimal Price { get; set; }
    public decimal PeRatio { get; set; }
    public decimal DyPercentage { get; set; }
    public string AiAnalysis { get; set; } = string.Empty;
    public string NewsSummary { get; set; } = string.Empty;
}