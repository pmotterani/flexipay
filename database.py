# database.py

import psycopg2
from psycopg2.extras import DictCursor, register_decimal
from decimal import Decimal, getcontext
from datetime import datetime, timedelta
import logging
import config

logger = logging.getLogger(__name__)

# Define precisão global para operações monetárias
getcontext().prec = 10

# Habilita o uso automático de Decimal no psycopg2
register_decimal()

def get_db_connection():
    try:
        conn = psycopg2.connect(config.DATABASE_URL)
        return conn
    except psycopg2.OperationalError as e:
        logger.critical(f"FATAL: Falha ao conectar ao banco de dados PostgreSQL: {e}", exc_info=True)
        raise

def init_db():
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    balance NUMERIC(10, 2) DEFAULT 0.00,
                    created_at TIMESTAMPTZ NOT NULL
                );
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    user_telegram_id BIGINT NOT NULL,
                    type TEXT NOT NULL,
                    amount NUMERIC(10, 2) NOT NULL,
                    status TEXT NOT NULL,
                    pix_key TEXT,
                    mercado_pago_id TEXT,
                    admin_notes TEXT,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    FOREIGN KEY (user_telegram_id) REFERENCES users (telegram_id)
                );
            ''')
        conn.commit()
    logger.info("✅ Tabelas criadas/verificadas com sucesso.")

def get_balance(telegram_id):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT balance FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                return Decimal(result['balance']) if result else Decimal("0.00")
            except Exception as e:
                logger.error(f"❌ Erro ao buscar saldo: {e}", exc_info=True)
                return Decimal("0.00")

def update_balance(telegram_id, amount_change, conn_ext=None):
    conn = conn_ext or get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT balance FROM users WHERE telegram_id = %s FOR UPDATE", (telegram_id,))
            result = cursor.fetchone()
            current_balance = Decimal(result['balance']) if result else Decimal("0.00")
            new_balance = current_balance + Decimal(amount_change)

            if new_balance < 0:
                logger.warning(f"⚠️ Saldo negativo para {telegram_id}. Operação cancelada.")
                return False

            cursor.execute("UPDATE users SET balance = %s WHERE telegram_id = %s", (new_balance, telegram_id))
            if not conn_ext:
                conn.commit()

            logger.info(f"💰 Saldo atualizado para {telegram_id}: R${new_balance:.2f}")
            return True
    except Exception as e:
        if not conn_ext:
            conn.rollback()
        logger.error(f"❌ Erro ao atualizar saldo: {e}", exc_info=True)
        return False
    finally:
        if not conn_ext:
            conn.close()

def create_user_if_not_exists(telegram_id, username, first_name):
    now = datetime.now()
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            try:
                cursor.execute("""
                    INSERT INTO users (telegram_id, username, first_name, balance, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (telegram_id) DO NOTHING
                """, (telegram_id, username, first_name, Decimal("0.00"), now))
                conn.commit()
            except Exception as e:
                conn.rollback()
                logger.error(f"❌ Erro ao criar usuário {telegram_id}: {e}", exc_info=True)

def admin_set_balance(user_telegram_id, new_balance):
    with get_db_connection() as conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE users SET balance = %s WHERE telegram_id = %s", (Decimal(new_balance), user_telegram_id))
                if cursor.rowcount > 0:
                    record_transaction(
                        user_telegram_id=user_telegram_id,
                        type='AJUSTE_MANUAL',
                        amount=Decimal(new_balance),
                        status='CONCLUIDO',
                        admin_notes=f"Saldo definido manualmente.",
                        conn_ext=conn
                    )
                    conn.commit()
                    return True
                return False
        except Exception as e:
            conn.rollback()
            logger.error(f"❌ Erro ao setar saldo: {e}", exc_info=True)
            return False

def record_transaction(**kwargs):
    conn = kwargs.pop('conn_ext', None) or get_db_connection()
    now = datetime.now()
    kwargs.setdefault('pix_key', None)
    kwargs.setdefault('mercado_pago_id', None)
    kwargs.setdefault('admin_notes', None)
    kwargs['created_at'] = now
    kwargs['updated_at'] = now

    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            keys = ', '.join(kwargs.keys())
            values = list(kwargs.values())
            placeholders = ', '.join(['%s'] * len(values))
            cursor.execute(f"INSERT INTO transactions ({keys}) VALUES ({placeholders}) RETURNING id", values)
            transaction_id = cursor.fetchone()['id']
            if 'conn_ext' not in kwargs:
                conn.commit()
            return transaction_id
    except Exception as e:
        if 'conn_ext' not in kwargs:
            conn.rollback()
        logger.error(f"❌ Erro ao registrar transação: {e}", exc_info=True)
        return None
    finally:
        if 'conn_ext' not in kwargs:
            conn.close()

def update_transaction_status(transaction_id, new_status, **kwargs):
    """Atualiza o status e outros campos de uma transação."""
    conn = kwargs.pop('conn_ext', None) or get_db_connection()
    fields_to_update = ["status = %s", "updated_at = %s"]
    values = [new_status, datetime.now()]
    if 'mp_id' in kwargs:
        fields_to_update.append("mercado_pago_id = %s")
        values.append(kwargs['mp_id'])
    if 'admin_notes' in kwargs:
        fields_to_update.append("admin_notes = %s")
        values.append(kwargs['admin_notes'])
    values.append(transaction_id)
    try:
        with conn.cursor() as cursor:
            sql = f"UPDATE transactions SET {', '.join(fields_to_update)} WHERE id = %s"
            cursor.execute(sql, tuple(values))
            if 'conn_ext' not in kwargs: conn.commit()
        logger.info(f"🔄 Status da transação {transaction_id} atualizado para '{new_status}'.")
        return True
    except psycopg2.Error as e:
        logger.error(f"❌ Erro ao atualizar status da transação {transaction_id}: {e}", exc_info=True)
        if 'conn_ext' not in kwargs and conn: conn.rollback()
        return False
    finally:
        if 'conn_ext' not in kwargs and conn: conn.close()

def get_transaction_details(transaction_id):
    """Busca todos os detalhes de uma transação pelo seu ID."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM transactions WHERE id = %s", (transaction_id,))
                return cursor.fetchone()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar detalhes da transação {transaction_id}: {e}", exc_info=True)
                return None

def get_pending_withdrawals():
    """Retorna todas as transações de saque com status 'EM ANÁLISE'."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM transactions WHERE type = 'WITHDRAWAL' AND status = %s", (config.STATUS_EM_ANALISE,))
                return cursor.fetchall()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar saques pendentes: {e}", exc_info=True)
                return []

def calculate_profits():
    """Calcula o lucro total somando todas as transações do tipo 'FEE'."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT SUM(amount) FROM transactions WHERE type = 'FEE' AND status = %s", (config.STATUS_CONCLUIDO,))
                result = cursor.fetchone()
                return result[0] if result and result[0] is not None else 0.00
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao calcular lucro: {e}", exc_info=True)
                return 0.00

def get_fee_for_withdrawal(withdrawal_transaction_id):
    """Busca o valor da taxa associada a uma transação de saque."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                note = f"Taxa referente ao saque ID {withdrawal_transaction_id}"
                cursor.execute("SELECT amount FROM transactions WHERE type = 'FEE' AND admin_notes = %s", (note,))
                result = cursor.fetchone()
                return result['amount'] if result else 0.00
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar taxa para o saque {withdrawal_transaction_id}: {e}", exc_info=True)
                return 0.00

def get_user_info(telegram_id):
    """Busca informações básicas de um usuário."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT * FROM users WHERE telegram_id = %s", (telegram_id,))
                return cursor.fetchone()
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar info do usuário {telegram_id}: {e}", exc_info=True)
                return None

def get_last_transaction_date(telegram_id):
    """Busca a data da última transação atualizada de um usuário."""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            try:
                cursor.execute("SELECT updated_at FROM transactions WHERE user_telegram_id = %s ORDER BY updated_at DESC LIMIT 1", (telegram_id,))
                result = cursor.fetchone()
                if result:
                    return result['updated_at'].strftime('%d/%m/%Y %H:%M')
                return "Nenhuma transação"
            except psycopg2.Error as e:
                logger.error(f"❌ Erro ao buscar última data de transação para {telegram_id}: {e}", exc_info=True)
                return "Erro ao consultar"
