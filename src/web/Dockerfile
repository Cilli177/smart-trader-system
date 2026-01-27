# Estágio 1: Build usando o SDK do .NET 9
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /app

# Instala ferramentas necessárias para Blazor WASM
RUN dotnet workload install wasm-tools

# Copia e compila
COPY . .
RUN dotnet publish "web.csproj" -c Release -o out

# Estágio 2: Servidor Nginx leve para rodar o site
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Copia os arquivos gerados e a configuração do servidor
COPY --from=build /app/out/wwwroot .
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80