using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE PORTA PARA PRODUÇÃO (RAILWAY) ---
// A Railway injeta a porta na variável de ambiente 'PORT'
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";

builder.WebHost.ConfigureKestrel(options =>
{
    // Escuta em qualquer IP (0.0.0.0) para permitir conexões externas
    options.ListenAnyIP(int.Parse(port));
});

// --- 2. SERVIÇOS ---
var connectionString = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";

builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();

// CORS: Essencial para que o seu Blazor (Web) consiga falar com esta API
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy => 
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader());
});

var app = builder.Build();

// --- 3. AUTO-MIGRATION (Executa uma vez ao subir) ---
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
        Console.WriteLine($"Erro na migração: {ex.Message}");
    }
}

// --- 4. PIPELINE E ENDPOINTS ---
app.UseCors("AllowAll");
app.MapControllers();

// Rota raiz para teste rápido de saúde da API
app.MapGet("/", () => "🚀 Smart Trader API: Online e respondendo na porta " + port);

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

// Remover favorito
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = "DELETE FROM user_favorites WHERE ticker = @Ticker";
    var rows = await conn.ExecuteAsync(sql, new { Ticker = ticker.Trim().ToUpper() });
    return rows > 0 ? Results.Ok(new { status = "removido" }) : Results.NotFound();
});

app.Run(); // Este comando DEVE ser alcançado para a API ficar online