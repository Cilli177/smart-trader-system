# Estágio 1: Build
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /app

# Instala Python e ferramentas WASM
RUN apt-get update && apt-get install -y python3 && \
    ln -sf /usr/bin/python3 /usr/bin/python
RUN dotnet workload install wasm-tools

# Copia e publica
COPY . .
RUN dotnet publish "web.csproj" -c Release -o /app/publish

# Estágio 2: Runtime (Nginx)
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Remove arquivos padrão do Nginx
RUN rm -rf ./*

# Copia os arquivos estáticos gerados (Conteúdo de wwwroot)
# Note que agora apontamos para /app/publish/wwwroot
COPY --from=build /app/publish/wwwroot .

# Copia a configuração que você já validou
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]