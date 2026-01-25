# Dockerfile da API (C#)

# 1. Imagem de Construção (Build)
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Copia os arquivos de projeto e restaura
COPY ["api.csproj", "./"]
RUN dotnet restore "api.csproj"

# Copia todo o código e compila
COPY . .
RUN dotnet publish "api.csproj" -c Release -o /app/publish

# 2. Imagem de Execução (Runtime - Mais leve)
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

# Variável para o Railway detectar a porta
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "api.dll"]