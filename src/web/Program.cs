using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using web;

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

// --- CONEXÃO COM A SUA API REAL NA RAILWAY ---
// Usando o link que você confirmou que está online
builder.Services.AddScoped(sp => new HttpClient 
{ 
    BaseAddress = new Uri("https://positive-reprieve-production-04d0.up.railway.app/") 
});

await builder.Build().RunAsync();