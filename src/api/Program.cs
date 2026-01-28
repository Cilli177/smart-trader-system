using Dapper;
using Npgsql;
using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

// --- 1. CONFIGURAÇÃO DE PORTA (RAILWAY) ---
var port = Environment.GetEnvironmentVariable("PORT") ?? "5000";
builder.WebHost.ConfigureKestrel(options => options.ListenAnyIP(int.Parse(port)));

// --- 2. SERVIÇOS ---
var connectionString = "Host=shuttle.proxy.rlwy.net;Port=12070;Database=railway;Username=postgres;Password=bryYtZCTlvOwzAodgPAdjLQJbFTxGSzk";
builder.Services.AddNpgsqlDataSource(connectionString);
builder.Services.AddControllers();
builder.Services.AddCors(options => options.AddPolicy("AllowAll", p => p.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

var app = builder.Build();

// --- 3. AUTO-MIGRATION PODEROSA (Cria tudo o que falta) ---
using (var scope = app.Services.CreateScope())
{
    try 
    {
        var dataSource = scope.ServiceProvider.GetRequiredService<NpgsqlDataSource>();
        using var conn = await dataSource.OpenConnectionAsync();
        
        // A. Cria Tabela de Favoritos
        await conn.ExecuteAsync(@"
            CREATE TABLE IF NOT EXISTS user_favorites (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(10) NOT NULL UNIQUE,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );");

        // B. Cria Tabelas do Sistema (Setores e Ativos) para suportar o Worker
        await conn.ExecuteAsync(@"
            CREATE TABLE IF NOT EXISTS sectors (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE
            );
            
            CREATE TABLE IF NOT EXISTS assets (
                id SERIAL PRIMARY KEY,
                ticker VARCHAR(20) NOT NULL UNIQUE,
                name VARCHAR(100),
                sector_id INTEGER REFERENCES sectors(id),
                is_active BOOLEAN DEFAULT TRUE,
                price DECIMAL(18, 2) DEFAULT 0,
                pe_ratio DECIMAL(10, 2) DEFAULT 0,
                dy_percentage DECIMAL(10, 2) DEFAULT 0,
                ai_analysis TEXT,
                news_summary TEXT,
                news_links JSONB,
                sentiment VARCHAR(20) DEFAULT 'Neutro',
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );");

        // C. Seed Inicial (Garante que existem dados para o JOIN não falhar)
        await conn.ExecuteAsync("INSERT INTO sectors (name) VALUES ('Geral') ON CONFLICT DO NOTHING;");
        await conn.ExecuteAsync(@"
            INSERT INTO assets (ticker, name, sector_id) VALUES 
            ('PETR4.SA', 'Petrobras', 1),
            ('VALE3.SA', 'Vale', 1),
            ('BBAS3.SA', 'Banco do Brasil', 1),
            ('ITUB4.SA', 'Itau', 1),
            ('WEGE3.SA', 'Weg', 1)
            ON CONFLICT (ticker) DO NOTHING;
        ");
        
        Console.WriteLine("✅ [MIGRATION] Banco de dados atualizado e populado com sucesso!");
    }
    catch (Exception ex) 
    {
        Console.WriteLine($"❌ [ERRO MIGRATION]: {ex.Message}");
    }
}

// --- 4. ENDPOINTS ---
app.UseCors("AllowAll");
app.MapControllers();

app.MapGet("/", () => "🚀 Smart Trader API Online & Database Ready");

// Endpoint Principal: Listagem Inteligente (Com LEFT JOIN para evitar crash)
app.MapGet("/api/favorites", async (NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    
    // O LEFT JOIN garante trazer o ticker mesmo se a tabela assets estiver vazia de dados
    var sql = @"
        SELECT 
            f.ticker, 
            COALESCE(a.price, 0) as Price, 
            a.pe_ratio as PeRatio, 
            a.dy_percentage as DyPercentage, 
            COALESCE(a.ai_analysis, 'Aguardando processamento do Worker...') as AiAnalysis, 
            a.news_summary as NewsSummary, 
            a.sentiment
        FROM user_favorites f
        LEFT JOIN assets a ON f.ticker = a.ticker
        ORDER BY f.ticker";
    
    var favs = await conn.QueryAsync(sql);
    return Results.Ok(favs);
});

// Adicionar Favorito
app.MapPost("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    var cleanTicker = ticker.Trim().ToUpper();
    
    // 1. Salva nos favoritos
    await conn.ExecuteAsync("INSERT INTO user_favorites (ticker) VALUES (@T) ON CONFLICT (ticker) DO NOTHING", new { T = cleanTicker });
    
    // 2. Garante que o ativo exista na tabela de assets para o Worker processar depois
    // (Se não existir, cria um registro "dummy" para o Worker preencher)
    await conn.ExecuteAsync(@"
        INSERT INTO assets (ticker, name, sector_id) 
        VALUES (@T, 'Novo Ativo', 1) 
        ON CONFLICT (ticker) DO NOTHING", new { T = cleanTicker });

    return Results.Ok(new { msg = "Monitoramento iniciado" });
});

// Remover Favorito
app.MapDelete("/api/favorites/{ticker}", async (string ticker, NpgsqlDataSource dataSource) =>
{
    using var conn = await dataSource.OpenConnectionAsync();
    await conn.ExecuteAsync("DELETE FROM user_favorites WHERE ticker = @T", new { T = ticker.Trim().ToUpper() });
    return Results.Ok();
});

app.Run();