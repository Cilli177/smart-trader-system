using Dapper;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE SERVIÇOS (Injeção de Dependência) ---

// Pega a string de conexão
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");

// [NOVO] Registra o NpgsqlDataSource. 
// Isso é vital para o NewsController que criamos receber a conexão automaticamente.
builder.Services.AddNpgsqlDataSource(connectionString!);

// [NOVO] Habilita o uso de Controllers (arquivos separados na pasta Controllers)
builder.Services.AddControllers();

// Configuração de Porta (Mantendo sua lógica original)
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.UseUrls($"http://*:{port}");

var app = builder.Build();

// --- 2. ENDPOINTS ---

app.MapGet("/", () => "🚀 Smart Trader API: Online, Operante e com IA!");

// [NOVO] Mapeia os Controllers (Faz o NewsController funcionar)
app.MapControllers();


// --- SEUS ENDPOINTS ANTIGOS (Minimal APIs) ---
// Mantivemos eles intactos para garantir que o front/testes antigos não quebrem.

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
        LIMIT 30";

    var data = await conn.QueryAsync(sql, new { Ticker = ticker.ToUpper() });
    
    if (!data.Any()) return Results.NotFound(new { msg = "Ativo não encontrado ou sem dados." });
    
    return Results.Ok(data);
});

app.Run();