FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /app

# Instala Python e ferramentas de WASM
RUN apt-get update && apt-get install -y python3 && ln -sf /usr/bin/python3 /usr/bin/python
RUN dotnet workload install wasm-tools

COPY . .
RUN dotnet publish "web.csproj" -c Release -o /app/publish

FROM nginx:alpine
WORKDIR /usr/share/nginx/html
RUN rm -rf ./*

# Copia os arquivos gerados no publish para a pasta do Nginx
COPY --from=build /app/publish/wwwroot .
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]