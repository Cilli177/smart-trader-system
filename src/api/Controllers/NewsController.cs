using Microsoft.AspNetCore.Mvc;
using Npgsql;
using SmartTraderApi.Models;

namespace SmartTraderApi.Controllers;

[ApiController]
[Route("api/[controller]")]
public class NewsController : ControllerBase
{
    private readonly NpgsqlDataSource _dataSource;

    public NewsController(NpgsqlDataSource dataSource)
    {
        _dataSource = dataSource;
    }

    [HttpGet("{ticker}")]
    public async Task<IActionResult> GetNews(string ticker)
    {
        var newsList = new List<MarketNews>();
        
        // SQL que cruza a tabela de notícias com a de ativos (JOIN)
        // Pega as 10 mais recentes
        var sql = @"
            SELECT 
                n.id, 
                a.ticker, 
                n.title, 
                n.url, 
                n.sentiment_score, 
                n.sentiment_summary, 
                n.created_at
            FROM market_news n
            JOIN assets a ON n.asset_id = a.id
            WHERE a.ticker ILIKE @ticker
            ORDER BY n.created_at DESC
            LIMIT 10";

        await using var conn = await _dataSource.OpenConnectionAsync();
        await using var cmd = new NpgsqlCommand(sql, conn);
        
        // Adiciona o parâmetro (evita SQL Injection)
        cmd.Parameters.AddWithValue("ticker", $"%{ticker}%");

        await using var reader = await cmd.ExecuteReaderAsync();
        while (await reader.ReadAsync())
        {
            newsList.Add(new MarketNews
            {
                Id = reader.GetInt32(0),
                Ticker = reader.GetString(1),
                Title = reader.GetString(2),
                Url = reader.GetString(3),
                SentimentScore = reader.GetDecimal(4),
                SentimentSummary = reader.GetString(5),
                CreatedAt = reader.GetDateTime(6)
            });
        }

        if (newsList.Count == 0)
            return NotFound(new { message = "Nenhuma notícia analisada encontrada para este ativo." });

        return Ok(newsList);
    }
}