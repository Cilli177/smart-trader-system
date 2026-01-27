namespace web.Models; // Define o namespace como 'web.Models'

public class AssetNews
{
    public int Id { get; set; }
    public string Ticker { get; set; } = "";
    public string Title { get; set; } = "";
    public string Url { get; set; } = "";
    public decimal SentimentScore { get; set; }
    public string SentimentSummary { get; set; } = "";
    public DateTime CreatedAt { get; set; }
}