# config.py (Versão para Hospedagem no Railway)
"""
⚙️ Arquivo de Configuração Central
------------------------------------
Este arquivo contém todas as variáveis, chaves de API, textos e parâmetros
que controlam o comportamento do bot. As chaves secretas são lidas do ambiente.
"""
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env (para desenvolvimento local)
load_dotenv()

# =============================================
# 🔑 CHAVES DE API E CONFIGURAÇÕES CRÍTICAS
# =============================================
# Lidos diretamente do ambiente de produção (configurado no painel do Railway)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN")

# Define se o bot está em modo de produção. Afeta logs e avisos.
PRODUCTION = os.getenv("PRODUCTION", "False").lower() == "true"


# --- LÓGICA DE CAMINHO PARA DADOS PERSISTENTES (RAILWAY) ---
# No Railway, o volume persistente é montado em /data por padrão
RAILWAY_DATA_DIR = "/data"

# Verifica se estamos rodando no Railway (pela presença do diretório)
if os.path.isdir(RAILWAY_DATA_DIR):
    # Se sim, o caminho do banco de dados e do log será dentro do volume
    DB_NAME = os.path.join(RAILWAY_DATA_DIR, "flexypay.db")
    LOG_FILE_PATH = os.path.join(RAILWAY_DATA_DIR, "flexypay.log")
else:
    # Se não (rodando localmente), usa o caminho padrão na pasta do projeto
    DB_NAME = "flexypay.db"
    LOG_FILE_PATH = "flexypay.log"
# --- FIM DA LÓGICA DE CAMINHO ---


# =============================================
# 👑 ADMINISTRADORES DO BOT
# =============================================
# Lista de IDs de usuários do Telegram que terão acesso aos comandos administrativos.
ADMIN_TELEGRAM_IDS = []
admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "") # Ex: "123456,789012"
if admin_ids_str:
    try:
        # Converte a string de IDs separados por vírgula em uma lista de inteiros
        ADMIN_TELEGRAM_IDS = [int(admin_id.strip()) for admin_id in admin_ids_str.split(',')]
    except ValueError:
        print("⚠️ ERRO: ADMIN_TELEGRAM_IDS no ambiente contém um valor inválido. Use números inteiros separados por vírgula.")


# =============================================
# 📊 CONFIGURAÇÕES FINANCEIRAS
# =============================================
TAXA_DEPOSITO_PERCENTUAL = 0.11
TAXA_SAQUE_PERCENTUAL = 0.025
TAXA_SAQUE_FIXA = 3.50
LIMITE_MINIMO_DEPOSITO = 7.50
LIMITE_MAXIMO_DEPOSITO = 1000.00


# =============================================
# 🏷️ STATUS DE TRANSAÇÕES (Uso interno)
# =============================================
STATUS_EM_ANALISE = "EM ANÁLISE"
STATUS_EM_ANDAMENTO = "EM ANDAMENTO"
STATUS_CONCLUIDO = "CONCLUÍDO"
STATUS_RECUSADO = "RECUSADO"
STATUS_FALHA_PAGAMENTO = "FALHA NO PAGAMENTO"
STATUS_DEPOSITO_PENDENTE = "AGUARDANDO PAGAMENTO"
STATUS_DEPOSITO_PAGO = "PAGO"
STATUS_AJUSTE_MANUAL = "AJUSTE MANUAL"


# =============================================
# 🤖 INFORMAÇÕES DO BOT E SUPORTE
# =============================================
NOME_BOT = "FlexiPay"
CANAL_OFICIAL = os.getenv("CANAL_OFICIAL", "@FlexiPayChannel")
BOT_SUPORTE = os.getenv("BOT_SUPORTE", "https://t.me/FlexiPaySuporteBot")
EMAIL_SUPORTE = "flexipaysuporte@gmail.com"
HORARIO_SUPORTE = "08:00 às 20:00 (GMT-3)"


# =============================================
# 📜 MENSAGENS PADRÃO (COPY)
# =============================================
COPY_INTRO = (
    f"🌐 *Bem-vindo(a) ao {NOME_BOT}: o BOT do PIX SEM RASTRO!*"
)

MSG_BOAS_VINDAS = (
    "🚀 Faça depósitos, saques e transferências anonimamente, direto pelo Telegram.\n"
    "*Nada de CPF, nada de banco, nada de rastro.*\n\n"
    "💼 Esquece burocracia, esquece regra — aqui você tem *liberdade total* pra movimentar sua grana como quiser."
)

MSG_DIFERENCIAIS = (
    "\nNossos Diferenciais:\n"
    "✅ *Operações 100% Automatizadas*\n"
    "🛡️ *Sistema Blindado, Privado e Discreto*\n"
    "💸 *Saques Rápidos e Anônimos*\n"
    "👨‍💻 *Suporte Especializado*\n"
)

MSG_COMANDOS_BASE = (
    "\n\n📋 *Comandos Disponíveis:*\n"
    "`/pix <valor>` - Gerar QR Code para depósito.\n"
    "`/sacar <chave> <total>` - Sacar (débito total).\n"
    "`/carteira` - Consultar seu saldo.\n"
    "`/taxa` - Ver as taxas de operação.\n"
    "`/suporte` - Falar com o suporte.\n"
    "`/canal` - Entrar no nosso canal."
)


# =============================================
# ❗ VALIDAÇÕES FINAIS (Garante que o bot possa iniciar)
# =============================================
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("FATAL: Token do Telegram não configurado. Defina a variável de ambiente TELEGRAM_BOT_TOKEN.")

if not MERCADOPAGO_ACCESS_TOKEN and PRODUCTION:
    print("AVISO: Token do Mercado Pago não configurado. Funcionalidades de pagamento podem não funcionar.")

if not ADMIN_TELEGRAM_IDS and PRODUCTION:
    print("AVISO: Nenhum ADMIN_TELEGRAM_ID configurado. Funcionalidades administrativas não funcionarão.")
