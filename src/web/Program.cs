using Microsoft.AspNetCore.Components.Web;
using Microsoft.AspNetCore.Components.WebAssembly.Hosting;
using web; // Garante que o App.razor seja encontrado no namespace 'web'

var builder = WebAssemblyHostBuilder.CreateDefault(args);
builder.RootComponents.Add<App>("#app");
builder.RootComponents.Add<HeadOutlet>("head::after");

// --- LIGAÇÃO COM A API ---
// Endereço público da sua porta 5000 que confirmamos estar funcional
builder.Services.AddScoped(sp => new HttpClient 
{ 
    BaseAddress = new Uri("https://improved-rotary-phone-694ww6rv6wcxv79-5000.app.github.dev/") 
});

await builder.Build().RunAsync();