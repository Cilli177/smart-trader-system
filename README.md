# 📈 Smart Trader System (AI-Powered)

Um sistema distribuído de análise financeira que monitora ativos da B3 (Bolsa Brasileira) e utiliza Inteligência Artificial para analisar o sentimento de notícias em tempo real.

![Status](https://img.shields.io/badge/Status-Online-brightgreen)
![Tech](https://img.shields.io/badge/Stack-.NET_9_%7C_Python_%7C_PostgreSQL-blue)
![AI](https://img.shields.io/badge/AI-Gemini_Flash-orange)

## 🧠 Arquitetura do Projeto

O sistema opera em uma arquitetura de microsserviços simplificada:

1.  **Data Ingestion Worker (Python):**
    * Monitora RSS feeds de notícias financeiras (Google News).
    * Utiliza a API **Google Gemini 1.5 Flash** para ler as notícias.
    * Classifica o sentimento (Score de -1.0 a +1.0) e gera resumos automáticos.
    * Persiste os dados enriquecidos no banco.

2.  **Core API (.NET 9):**
    * API RESTful de alta performance.
    * Endpoints para cotações (OHLC) e Análises de IA.
    * Conexão otimizada com PostgreSQL usando Npgsql.

3.  **Database (PostgreSQL):**
    * Armazena ativos, histórico de preços e as análises de sentimento geradas pela IA.

---

## 🚀 Como testar (Live Demo)

A API está rodando em produção no Railway:

* **Ver Cotações (JSON):** `https://positive-reprieve-production-04d0.up.railway.app/api/quotes/PETR4.SA`
* **Ver Análise de IA (Notícias):** `https://positive-reprieve-production-04d0.up.railway.app/api/news/PETR4`
* **Listar Ativos:** `https://positive-reprieve-production-04d0.up.railway.app/api/assets`

---

## 🛠️ Stack Tecnológica

* **Backend:** C# .NET 9 (Web API)
* **Worker/ETL:** Python 3.12 + SQLAlchemy
* **AI/LLM:** Google Gemini (Generative AI)
* **Database:** PostgreSQL (Cloud)
* **Infraestrutura:** Docker + Railway

## ⚙️ Como rodar localmente

### Pré-requisitos
* .NET 9 SDK
* Python 3.12
* Docker (Opcional)

### Passos
1.  Clone o repositório.
2.  Configure o arquivo `.env` com sua `DATABASE_URL` e `GEMINI_API_KEY`.
3.  Rode o Worker: `python src/worker/news_analyst.py`
4.  Rode a API: `dotnet run --project src/api`

---
*Desenvolvido como projeto de portfólio focado em Sistemas Distribuídos e Integração de IA.*