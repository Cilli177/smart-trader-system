namespace SmartTraderWeb.Models;

public class MarketNews {
    public string Ticker { get; set; } = "";
    public string Title { get; set; } = "";
    public string Url { get; set; } = "";
    public decimal SentimentScore { get; set; }
    public string SentimentSummary { get; set; } = "";
}