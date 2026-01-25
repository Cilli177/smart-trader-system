using Dapper;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);

// Pega a porta do ambiente (necessário para o Railway depois) ou usa 5000 local
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.UseUrls($"http://*:{port}");

var app = builder.Build();

// --- ENDPOINTS ---

app.MapGet("/", () => "🚀 Smart Trader API: Online e Operante!");

// 1. Endpoint para listar ativos monitorados
app.MapGet("/api/assets", async (IConfiguration config) =>
{
    var connString = config.GetConnectionString("DefaultConnection");
    using var conn = new NpgsqlConnection(connString);
    
    var sql = "SELECT id, ticker, name FROM assets WHERE is_active = true";
    var assets = await conn.QueryAsync(sql);
    
    return Results.Ok(assets);
});

// 2. Endpoint para ver o histórico de preços (OHLC)
app.MapGet("/api/quotes/{ticker}", async (string ticker, IConfiguration config) =>
{
    var connString = config.GetConnectionString("DefaultConnection");
    using var conn = new NpgsqlConnection(connString);
    
    // Query otimizada juntando as tabelas
    var sql = @"
        SELECT 
            m.trade_date as Date,
            m.close_price as Close,
            m.volume as Volume,
            m.open_price as Open,
            m.high_price as High,
            m.low_price as Low
        FROM market_quotes m
        JOIN assets a ON m.asset_id = a.id
        WHERE a.ticker = @Ticker
        ORDER BY m.trade_date DESC
        LIMIT 30"; // Pega os últimos 30 pregões

    var data = await conn.QueryAsync(sql, new { Ticker = ticker.ToUpper() });
    
    if (!data.Any()) return Results.NotFound(new { msg = "Ativo não encontrado ou sem dados." });
    
    return Results.Ok(data);
});

app.Run();