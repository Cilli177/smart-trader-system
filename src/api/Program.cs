using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE PORTA ---
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

// --- 2. SERVIÇOS E CORS ---
var connectionString = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";
builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();

// Configuração permissiva para evitar bloqueio no Frontend
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy => 
        policy.AllowAnyOrigin()
              .AllowAnyMethod()
              .AllowAnyHeader());
});

var app = builder.Build();

// --- 3. AUTO-MIGRATION (CORREÇÃO DO BANCO) ---
using (var scope = app.Services.CreateScope())
{
    try 
    {
        var dataSource = scope.ServiceProvider.GetRequiredService<NpgsqlDataSource>();
        using var conn = await dataSource.OpenConnectionAsync();
        
        // Cria tabelas essenciais se não existirem
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

        // Insere dados iniciais para evitar tela em branco
        await conn.ExecuteAsync("INSERT INTO sectors (name) VALUES ('Geral') ON CONFLICT DO NOTHING;");
        await conn.ExecuteAsync("INSERT INTO assets (ticker, name, sector_id) VALUES ('PETR4.SA', 'Petrobras', 1), ('VALE3.SA', 'Vale', 1) ON CONFLICT (ticker) DO NOTHING;");
        
        Console.WriteLine("✅ Banco de dados corrigido com sucesso!");
    }
    catch (Exception ex) 
    {
        Console.WriteLine($"❌ Erro na Migration: {ex.Message}");
    }
}

// --- 4. ENDPOINTS ---
app.UseCors("AllowAll"); // Importante: Deve vir antes de MapControllers
app.MapControllers();

app.MapGet("/", () => "API Online e Banco Atualizado 🚀");

// Endpoint Blindado (Usa LEFT JOIN para não travar se faltar análise)
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var sql = @"
        SELECT 
            f.ticker, 
            COALESCE(a.price, 0) as Price, 
            a.pe_ratio as PeRatio, 
            a.dy_percentage as DyPercentage, 
            COALESCE(a.ai_analysis, 'Processando...') as AiAnalysis, 
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
    // Adiciona aos favoritos
    await conn.ExecuteAsync("INSERT INTO user_favorites (ticker) VALUES (@T) ON CONFLICT (ticker) DO NOTHING", new { T = cleanTicker });
    // Adiciona na tabela de ativos para o Worker processar depois
    await conn.ExecuteAsync("INSERT INTO assets (ticker, name) VALUES (@T, 'Novo') ON CONFLICT (ticker) DO NOTHING", new { T = cleanTicker });
    return Results.Ok();
});

app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    await conn.ExecuteAsync("DELETE FROM user_favorites WHERE ticker = @T", new { T = ticker.Trim().ToUpper() });
    return Results.Ok();
});

app.Run();