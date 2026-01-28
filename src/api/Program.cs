using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE PORTA ---
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

// --- 2. BANCO DE DADOS ---
var dbUrl = Environment.GetEnvironmentVariable("DATABASE_URL");
var connectionString = string.IsNullOrEmpty(dbUrl) 
    ? "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk"
    : dbUrl;

builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();
builder.Services.AddCors(options => { options.AddPolicy("AllowAll", policy => policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()); });

var app = builder.Build();
app.UseCors("AllowAll");
app.MapControllers();

app.MapGet("/", () => "API Online 🚀");

// --- ENDPOINT BLINDADO (Com tratamento de erro explícito) ---
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    try
    {
        using var conn = await dataSource.OpenConnectionAsync();
        
        // O segredo está nos COALESCE: Transformam NULL em 0 ou texto padrão
        var sql = @"
            SELECT 
                f.ticker, 
                COALESCE(a.price, 0) as Price, 
                COALESCE(a.pe_ratio, 0) as PeRatio, 
                COALESCE(a.dy_percentage, 0) as DyPercentage, 
                COALESCE(a.ai_analysis, 'Aguardando atualização do Worker...') as AiAnalysis, 
                COALESCE(a.news_summary, 'Sem notícias no momento') as NewsSummary
            FROM user_favorites f
            LEFT JOIN assets a ON f.ticker = a.ticker
            ORDER BY f.ticker";
        
        var result = await conn.QueryAsync(sql);
        return Results.Ok(result);
    }
    catch (Exception ex)
    {
        // Se der erro, ele vai aparecer na tela em vez de apenas '500'
        Console.WriteLine($"[ERRO GRAVE]: {ex.Message}");
        return Results.Problem($"Erro no servidor: {ex.Message}");
    }
});

// Endpoint de Reset (Mantido caso precise usar de novo)
app.MapGet("/api/reset", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    // (Código de criação de tabelas mantido igual ao anterior...)
    await conn.ExecuteAsync("CREATE TABLE IF NOT EXISTS user_favorites (id SERIAL PRIMARY KEY, ticker VARCHAR(10) UNIQUE, added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);");
    await conn.ExecuteAsync("CREATE TABLE IF NOT EXISTS sectors (id SERIAL PRIMARY KEY, name VARCHAR(100) UNIQUE);");
    await conn.ExecuteAsync("CREATE TABLE IF NOT EXISTS assets (id SERIAL PRIMARY KEY, ticker VARCHAR(20) UNIQUE, name VARCHAR(100), sector_id INTEGER, price DECIMAL(18,2), pe_ratio DECIMAL(10,2), dy_percentage DECIMAL(10,2), ai_analysis TEXT, news_summary TEXT, news_links JSONB, sentiment VARCHAR(20), last_update TIMESTAMP);");
    await conn.ExecuteAsync("INSERT INTO sectors (name) VALUES ('Geral') ON CONFLICT DO NOTHING;");
    await conn.ExecuteAsync("INSERT INTO assets (ticker, name) VALUES ('PETR4.SA', 'Petrobras'), ('VALE3.SA', 'Vale') ON CONFLICT (ticker) DO NOTHING;");
    return Results.Ok("SUCESSO: Banco Resetado.");
});

// Adicionar Favorito
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var t = ticker.Trim().ToUpper();
    await conn.ExecuteAsync("INSERT INTO user_favorites (ticker) VALUES (@T) ON CONFLICT (ticker) DO NOTHING", new { T = t });
    await conn.ExecuteAsync("INSERT INTO assets (ticker, name) VALUES (@T, 'Novo') ON CONFLICT (ticker) DO NOTHING", new { T = t });
    return Results.Ok();
});

// Remover Favorito
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    await conn.ExecuteAsync("DELETE FROM user_favorites WHERE ticker = @T", new { T = ticker.Trim().ToUpper() });
    return Results.Ok();
});

app.Run();