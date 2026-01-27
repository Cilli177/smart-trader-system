# Estágio 1: Build usando o SDK do .NET 9
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /app

# Instala Python 3 e cria um link simbólico (Essencial para o Emscripten compilar WASM)
RUN apt-get update && apt-get install -y python3 && \
    ln -sf /usr/bin/python3 /usr/bin/python

# Instala as ferramentas de WebAssembly
RUN dotnet workload install wasm-tools

# Copia os arquivos e compila o projeto
COPY . .
RUN dotnet publish "web.csproj" -c Release -o out

# Estágio 2: Servidor Nginx leve para rodar o site
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Copia os arquivos compilados do estágio anterior
COPY --from=build /app/out/wwwroot .
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80