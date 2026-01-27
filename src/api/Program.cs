using Dapper;
using Npgsql;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE SERVIÇOS ---
var connectionString = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";

builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();

// CORS: Permitindo especificamente o método DELETE
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy => 
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader());
});

var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.UseUrls($"http://*:{port}");

var app = builder.Build();

// --- 2. AUTO-MIGRATION ---
using (var scope = app.Services.CreateScope())
{
    var dataSource = scope.ServiceProvider.GetRequiredService<NpgsqlDataSource>();
    using var conn = await dataSource.OpenConnectionAsync();
    await conn.ExecuteAsync(@"
        CREATE TABLE IF NOT EXISTS user_favorites (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10) NOT NULL UNIQUE,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );");
}

// --- 3. PIPELINE E ENDPOINTS ---
app.UseCors("AllowAll");
app.MapControllers();

app.MapGet("/", () => "🚀 Smart Trader API: Pronta para Favoritar e Remover!");

// Listar favoritos
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    return Results.Ok(await conn.QueryAsync("SELECT ticker FROM user_favorites ORDER BY ticker"));
});

// Salvar favorito
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = "INSERT INTO user_favorites (ticker) VALUES (@Ticker) ON CONFLICT (ticker) DO NOTHING";
    await conn.ExecuteAsync(sql, new { Ticker = ticker.Trim().ToUpper() });
    return Results.Ok(new { status = "sucesso" });
});

// REMOVER favorito (Endpoint Corrigido)
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = "DELETE FROM user_favorites WHERE ticker = @Ticker";
    // O Trim() remove espaços invisíveis que podem causar falha na remoção
    var rowsAffected = await conn.ExecuteAsync(sql, new { Ticker = ticker.Trim().ToUpper() });
    
    return rowsAffected > 0 
        ? Results.Ok(new { status = "removido" }) 
        : Results.NotFound(new { status = "não encontrado" });
});

app.Run();