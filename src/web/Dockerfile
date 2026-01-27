# Estágio 1: Build usando o SDK do .NET 9
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /app

# 1. Instala Python 3 e cria link simbólico (Essencial para o compilador WASM)
RUN apt-get update && apt-get install -y python3 && \
    ln -sf /usr/bin/python3 /usr/bin/python

# 2. Instala as ferramentas de WebAssembly (wasm-tools)
RUN dotnet workload install wasm-tools

# 3. Copia os arquivos do projeto e restaura as dependências
COPY . .
RUN dotnet restore "web.csproj"

# 4. Publica o projeto gerando os arquivos estáticos na pasta /app/out
RUN dotnet publish "web.csproj" -c Release -o out

# Estágio 2: Servidor Nginx leve para rodar o site no Railway
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# 5. Limpa a pasta padrão do Nginx para evitar conflitos
RUN rm -rf ./*

# 6. Copia EXATAMENTE o conteúdo da pasta wwwroot gerada no publish para a raiz do servidor
COPY --from=build /app/out/wwwroot .

# 7. Copia a configuração do Nginx que você já confirmou estar correta
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 8. Expõe a porta 80 (padrão do Nginx e o que configuramos na Railway)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]