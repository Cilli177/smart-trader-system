namespace SmartTraderApi.Models;

public class MarketNews
{
    public int Id { get; set; }
    public string Ticker { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string Url { get; set; } = string.Empty;
    public decimal SentimentScore { get; set; }
    public string SentimentSummary { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; }
}