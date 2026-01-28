using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE PORTA ---
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

// --- 2. BANCO DE DADOS (IMPORTANTE) ---
// Tenta pegar a variável da Railway primeiro. Se não tiver, usa a sua string fixa de backup.
var dbUrl = Environment.GetEnvironmentVariable("DATABASE_URL");
var connectionString = string.IsNullOrEmpty(dbUrl) 
    ? "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk"
    : dbUrl;

builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();

// CORS Liberado
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy => 
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());
});

var app = builder.Build();

app.UseCors("AllowAll");
app.MapControllers();

// --- 3. ENDPOINTS ---

app.MapGet("/", () => "API Smart Trader Online 🚀");

// *** NOVO: Endpoint de Emergência para Criar Tabelas ***
// Se der erro 500, acesse: /api/reset no navegador
app.MapGet("/api/reset", async (NpgsqlDataSource dataSource) =>
{
    try 
    {
        using var conn = await dataSource.OpenConnectionAsync();
        
        await conn.ExecuteAsync(@"
            CREATE TABLE IF NOT EXISTS user_favorites (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL UNIQUE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS sectors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE
            );
            
            CREATE TABLE IF NOT EXISTS assets (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(100),
                sector_id INTEGER,
                price DECIMAL(18, 2) DEFAULT 0,
                pe_ratio DECIMAL(10, 2) DEFAULT 0,
                dy_percentage DECIMAL(10, 2) DEFAULT 0,
                ai_analysis TEXT,
                news_summary TEXT,
                news_links JSONB,
                sentiment VARCHAR(20) DEFAULT 'Neutro',
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ");

        // Insere dados de teste
        await conn.ExecuteAsync("INSERT INTO sectors (name) VALUES ('Geral') ON CONFLICT DO NOTHING;");
        await conn.ExecuteAsync("INSERT INTO assets (ticker, name) VALUES ('PETR4.SA', 'Petrobras'), ('VALE3.SA', 'Vale') ON CONFLICT (ticker) DO NOTHING;");
        
        return Results.Ok("SUCESSO: Tabelas Recriadas e Dados Inseridos! Volte para o Dashboard.");
    }
    catch (Exception ex)
    {
        return Results.Problem($"ERRO CRÍTICO NO BANCO: {ex.Message}");
    }
});

// Endpoint Principal (Dashboard)
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = @"
        SELECT 
            f.ticker, 
            COALESCE(a.price, 0) as Price, 
            a.pe_ratio as PeRatio, 
            a.dy_percentage as DyPercentage, 
            COALESCE(a.ai_analysis, 'Aguardando Worker...') as AiAnalysis, 
            a.news_summary as NewsSummary
        FROM user_favorites f
        LEFT JOIN assets a ON f.ticker = a.ticker
        ORDER BY f.ticker";
    
    return Results.Ok(await conn.QueryAsync(sql));
});

// Adicionar Favorito
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var cleanTicker = ticker.Trim().ToUpper();
    await conn.ExecuteAsync("INSERT INTO user_favorites (ticker) VALUES (@T) ON CONFLICT (ticker) DO NOTHING", new { T = cleanTicker });
    await conn.ExecuteAsync("INSERT INTO assets (ticker, name) VALUES (@T, 'Novo') ON CONFLICT (ticker) DO NOTHING", new { T = cleanTicker });
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