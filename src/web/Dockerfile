# ESTÁGIO 1: Build
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /app

# Instala as ferramentas de WebAssembly (resolve o erro ResolveWasmOutputs)
RUN dotnet workload install wasm-tools

# Copia os arquivos e restaura
COPY . .
RUN dotnet publish "web.csproj" -c Release -o out

# ESTÁGIO 2: Runtime (Servidor leve Nginx)
FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Copia os arquivos compilados e a configuração do Nginx
COPY --from=build /app/out/wwwroot .
COPY nginx.conf /etc/nginx/conf.d/default.conf

# A Railway usa a porta 80 por padrão em containers Docker
EXPOSE 80