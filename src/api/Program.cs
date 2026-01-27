using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE PORTA PARA PRODUÇÃO (RAILWAY) ---
// A Railway injeta a porta dinamicamente. Se falhar, usamos a 5000 como fallback.
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";

builder.WebHost.ConfigureKestrel(options =>
{
    // CRÍTICO: ListenAnyIP permite que a Railway encaminhe tráfego para dentro do container.
    options.ListenAnyIP(int.Parse(port));
});

// --- 2. CONFIGURAÇÃO DE SERVIÇOS ---
var connectionString = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";

builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();

// CORS: Permite que o seu futuro serviço Blazor (Web) acesse esta API.
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy => 
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader());
});

var app = builder.Build();

// --- 3. AUTO-MIGRATION (Garante que o banco de dados está pronto) ---
using (var scope = app.Services.CreateScope())
{
    try 
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
    catch (Exception ex) 
    {
        // Log de erro no console para debug via Railway Deploy Logs
        Console.WriteLine($"[ERRO MIGRATION]: {ex.Message}");
    }
}

// --- 4. PIPELINE E ENDPOINTS ---
app.UseCors("AllowAll");
app.MapControllers();

// Endpoint de Saúde: Use este link para testar se a API estabilizou.
app.MapGet("/", () => $"🚀 Smart Trader API Online na porta: {port}");

// Listar ativos favoritos
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var favs = await conn.QueryAsync("SELECT ticker FROM user_favorites ORDER BY ticker");
    return Results.Ok(favs);
});

// Adicionar favorito
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = "INSERT INTO user_favorites (ticker) VALUES (@Ticker) ON CONFLICT (ticker) DO NOTHING";
    await conn.ExecuteAsync(sql, new { Ticker = ticker.Trim().ToUpper() });
    return Results.Ok(new { msg = "Sucesso" });
});

// Remover favorito
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = "DELETE FROM user_favorites WHERE ticker = @Ticker";
    var affected = await conn.ExecuteAsync(sql, new { Ticker = ticker.Trim().ToUpper() });
    return affected > 0 ? Results.Ok(new { msg = "Removido" }) : Results.NotFound();
});

app.Run();