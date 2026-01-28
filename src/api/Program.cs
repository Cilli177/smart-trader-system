using Dapper;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

var connectionString = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";
builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddCors(options => options.AddPolicy("AllowAll", p => p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

var app = builder.Build();
app.UseCors("AllowAll");

// Endpoint Principal: Agora retorna TUDO (Preço, IA, Notícias)
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    // Fazemos um JOIN para pegar os dados da inteligência da tabela assets
    var sql = @"
        SELECT f.ticker, a.price, a.pe_ratio, a.dy_percentage, a.ai_analysis, a.news_summary, a.sentiment
        FROM user_favorites f
        JOIN assets a ON f.ticker = a.ticker
        ORDER BY f.ticker";
    
    var favs = await conn.QueryAsync(sql);
    return Results.Ok(favs);
});

// Adicionar e Remover favoritos (mantidos como você enviou)
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) => { /* ... seu código ... */ return Results.Ok(); });
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) => { /* ... seu código ... */ return Results.Ok(); });

app.MapGet("/", () => $"🚀 Smart Trader AI API Online - Pronta para SaaS");
app.Run();