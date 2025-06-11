# adm.py (Versão com comando /setsaldo e visualização de saldos)
"""
👑 Módulo Administrativo
------------------------
Contém todos os handlers e funções para o painel de administração do bot.
Permite visualizar e gerenciar saques, verificar lucros e outras tarefas.
"""
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import config
import database
import pay

logger = logging.getLogger(__name__)
bot = None  # Instância global do bot, inicializada por register_admin_handlers

def get_admin_menu_markup():
    """Cria e retorna o markup do menu principal de administração."""
    markup = InlineKeyboardMarkup(row_width=1)
    btn_pending = InlineKeyboardButton("💰 Ver Saques Pendentes", callback_data="admin_view_pending")
    btn_profit = InlineKeyboardButton("📈 Ver Lucro com Taxas", callback_data="admin_view_profit")
    btn_manage_users = InlineKeyboardButton("👤 Administrar Saldo de Usuário", callback_data="admin_user_menu")
    btn_view_balances = InlineKeyboardButton("👥 Ver Saldos de Usuários", callback_data="admin_view_balances")
    markup.add(btn_pending, btn_profit, btn_manage_users, btn_view_balances)
    return markup

def register_admin_handlers(bot_instance):
    """
    Registra todos os handlers de comandos e callbacks relacionados ao admin.
    """
    global bot
    bot = bot_instance

    def is_admin(user_id):
        """Verifica se um ID de usuário pertence a um administrador."""
        return user_id in config.ADMIN_TELEGRAM_IDS

    @bot.message_handler(commands=['admin', 'adm'])
    def handle_admin_command(message):
        """Exibe o painel de administração se o usuário for um admin."""
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Acesso negado. Este comando é restrito.")
            return

        logger.info(f"👑 Admin {message.from_user.id} acessou o painel.")
        bot.send_message(message.chat.id, "⚙️ *Painel do Administrador*", reply_markup=get_admin_menu_markup(), parse_mode="Markdown")

    # <<< START: NEW FUNCTIONALITY TO FIX THE ISSUE >>>
    @bot.callback_query_handler(func=lambda call: call.data == "admin_view_profit")
    def handle_view_profit(call):
        """Calcula e exibe o lucro total com taxas."""
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Ação não permitida!", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Calculando lucro...")
        
        try:
            total_profit = database.calculate_profits()
            profit_message = (
                f"📈 *Lucro Total com Taxas*\n\n"
                f"O lucro total acumulado com taxas de depósito e saque é de:\n\n"
                f"💰 *R$ {total_profit:.2f}*"
            )
            
            markup = InlineKeyboardMarkup()
            btn_back = InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="admin_back_to_menu")
            markup.add(btn_back)

            bot.edit_message_text(profit_message, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
        
        except Exception as e:
            logger.error(f"Erro ao calcular/exibir lucro: {e}", exc_info=True)
            bot.answer_callback_query(call.id, "❌ Erro ao buscar lucro.", show_alert=True)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_back_to_menu")
    def handle_back_to_admin_menu(call):
        """Retorna ao painel de administração principal."""
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Ação não permitida!", show_alert=True)
            return
        
        bot.answer_callback_query(call.id)
        bot.edit_message_text("⚙️ *Painel do Administrador*", call.message.chat.id, call.message.message_id, reply_markup=get_admin_menu_markup(), parse_mode="Markdown")
    # <<< END: NEW FUNCTIONALITY TO FIX THE ISSUE >>>
    
    # ... (o restante do arquivo, como handle_set_saldo_command, handle_view_balances, etc., permanece o mesmo) ...
    @bot.message_handler(commands=['setsaldo'])
    def handle_set_saldo_command(message):
        """Inicia o fluxo de alteração de saldo via comando."""
        if not is_admin(message.from_user.id):
            bot.reply_to(message, "❌ Acesso negado. Este comando é restrito.")
            return

        # Pede o ID do usuário para o qual o saldo será alterado
        msg = bot.reply_to(message, "👤 Por favor, envie o `ID do Telegram` do usuário para alterar o saldo.")
        bot.register_next_step_handler(msg, process_user_id_for_balance)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_view_balances")
    def handle_view_balances(call):
        """Busca e exibe todos os usuários com saldo > 0."""
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Ação não permitida!", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Buscando usuários com saldo...")
        users_with_balance = database.get_users_with_balance()

        if not users_with_balance:
            bot.edit_message_text("✅ Nenhum usuário com saldo encontrado.", call.message.chat.id, call.message.message_id)
            return

        message_text = "👥 *Usuários com Saldo:*\n"
        for user in users_with_balance:
            username = f"(@{user['username']})" if user['username'] else ""
            message_text += (
                f"\n👤 *{user['first_name']}* {username}\n"
                f"   - ID: `{user['telegram_id']}`\n"
                f"   - Saldo: *R$ {user['balance']:.2f}*\n"
            )
        
        try:
            bot.edit_message_text(message_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException as e:
            if "message is too long" in str(e):
                bot.edit_message_text("⚠️ A lista de usuários é muito longa para ser exibida em uma única mensagem.", call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "admin_user_menu")
    def handle_admin_user_menu(call):
        """Inicia o fluxo para administrar um usuário pelo menu."""
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Ação não permitida!", show_alert=True)
            return

        msg = bot.edit_message_text(
            "👤 *Administrar Saldo de Usuário*\n\n"
            "Por favor, envie o `ID do Telegram` do usuário que você deseja gerenciar.",
            call.message.chat.id, call.message.message_id, parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_user_id_for_balance)

    def process_user_id_for_balance(message):
        """Recebe o ID do usuário e pede o novo saldo."""
        admin_id = message.from_user.id
        if not is_admin(admin_id): return

        try:
            target_user_id = int(message.text)
        except (ValueError, TypeError):
            bot.reply_to(message, "❌ ID inválido. Por favor, envie apenas o número. Tente novamente a partir do comando ou painel.")
            return
        
        user_info = database.get_user_info(target_user_id)
        if not user_info:
            bot.reply_to(message, f"❌ Usuário com ID `{target_user_id}` não encontrado. Verifique o ID.")
            return

        msg = bot.reply_to(
            message,
            f"✅ Usuário `{target_user_id}` (`{user_info.get('first_name', 'N/A')}`) encontrado.\n"
            f"💰 Saldo atual: *R$ {user_info.get('balance', 0.00):.2f}*\n\n"
            "Envie o *novo saldo* a ser definido (ex: `150.75`).",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_new_balance, target_user_id)

    def process_new_balance(message, target_user_id):
        """Recebe e atualiza o novo saldo do usuário."""
        admin_id = message.from_user.id
        if not is_admin(admin_id): return
        
        try:
            new_balance = float(message.text.replace(',', '.'))
            if new_balance < 0:
                bot.reply_to(message, "❌ O saldo não pode ser negativo. Operação cancelada.")
                return
        except (ValueError, TypeError):
            bot.reply_to(message, "❌ Valor inválido. Envie um número (ex: `25.50`). Operação cancelada.")
            return

        logger.info(f"👑 Admin {admin_id} está definindo o saldo do usuário {target_user_id} para R${new_balance:.2f}.")
        
        if database.admin_set_balance(target_user_id, new_balance):
            bot.reply_to(message, f"✅ Sucesso! O saldo de `{target_user_id}` foi definido para *R$ {new_balance:.2f}*.", parse_mode="Markdown")
            logger.info(f"✅ Saldo de {target_user_id} definido para R${new_balance:.2f} por {admin_id}.")
            
            try:
                bot.send_message(target_user_id, f"ℹ️ *Aviso Administrativo:*\nSeu saldo foi ajustado para *R$ {new_balance:.2f}*.", parse_mode="Markdown")
            except Exception as e:
                logger.warning(f"Não foi possível notificar {target_user_id} sobre a alteração de saldo: {e}")
        else:
            bot.reply_to(message, f"❌ Erro! Não foi possível atualizar o saldo para `{target_user_id}`. Verifique os logs.")
            logger.error(f"Falha ao definir saldo para {target_user_id} por {admin_id}.")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("admin_withdraw_"))
    def handle_admin_withdrawal_action(call):
        """Processa a aprovação ou rejeição de uma solicitação de saque."""
        admin_id = call.from_user.id
        if not is_admin(admin_id):
            bot.answer_callback_query(call.id, "❌ Ação não permitida!", show_alert=True)
            return

        try:
            _, _, action, transaction_id_str = call.data.split("_")
            transaction_id = int(transaction_id_str)
        except ValueError:
            logger.error(f"Erro ao parsear callback_data: {call.data}")
            bot.answer_callback_query(call.id, "❌ Erro no formato do comando.", show_alert=True)
            return

        transaction = database.get_transaction_details(transaction_id)
        if not transaction or transaction['status'] != config.STATUS_EM_ANALISE:
            bot.answer_callback_query(call.id, "⚠️ Transação não encontrada ou já processada.", show_alert=True)
            bot.edit_message_text("Esta solicitação já foi tratada por outro administrador ou não é mais válida.", call.message.chat.id, call.message.message_id, reply_markup=None)
            return
        
        user_telegram_id = transaction['user_telegram_id']
        original_amount = transaction['amount']

        if action == "approve":
            logger.info(f"👑 Admin {admin_id} iniciou APROVAÇÃO do saque {transaction_id} no valor de R${original_amount:.2f}.")
            bot.answer_callback_query(call.id, "⏳ Processando pagamento...")
            bot.edit_message_text(f"⏳ Processando pagamento para saque ID `{transaction_id}` (R${original_amount:.2f})...", call.message.chat.id, call.message.message_id, reply_markup=None)
            database.update_transaction_status(transaction_id, config.STATUS_EM_ANDAMENTO)
            
            payout_result = pay.process_payout(
                transaction_id_local=transaction_id,
                amount=original_amount,
                pix_key_receiver=transaction['pix_key'],
                description=f"Saque {config.NOME_BOT} ID {transaction_id}"
            )

            if payout_result.get('success'):
                payout_id = payout_result.get('payout_id')
                database.update_transaction_status(transaction_id, config.STATUS_CONCLUIDO, mp_id=payout_id)
                bot.send_message(user_telegram_id, f"✅ Seu saque de R${original_amount:.2f} foi *APROVADO* e o pagamento foi enviado!\nID da transação: `{transaction_id}`")
                bot.edit_message_text(f"✅ Saque ID `{transaction_id}` (R${original_amount:.2f}) *APROVADO E PAGO*.\nID do Gateway: `{payout_id}`", call.message.chat.id, call.message.message_id)
                logger.info(f"✅ Saque {transaction_id} APROVADO e pago pelo admin {admin_id}.")
            else:
                error_msg = payout_result.get('message', 'Erro desconhecido')
                database.update_transaction_status(transaction_id, config.STATUS_FALHA_PAGAMENTO, admin_notes=f"Admin {admin_id} tentou aprovar. Gateway: {error_msg}")
                fee_amount = database.get_fee_for_withdrawal(transaction_id)
                total_to_refund = original_amount + fee_amount
                
                if database.update_balance(user_telegram_id, total_to_refund):
                    bot.send_message(user_telegram_id, f"⚠️ *Atenção:* Ocorreu uma falha no envio do seu saque de R${original_amount:.2f} (ID: `{transaction_id}`). O valor total de *R${total_to_refund:.2f}* foi estornado ao seu saldo. Por favor, tente novamente mais tarde ou contate o suporte.")
                    bot.edit_message_text(f"❌ *FALHA NO PAGAMENTO* para saque ID `{transaction_id}`.\nMotivo: {error_msg}\n\n*O valor total (saque + taxa) foi estornado ao saldo do usuário.*", call.message.chat.id, call.message.message_id)
                    logger.error(f"❌ Falha no pagamento do saque {transaction_id} (Admin: {admin_id}). Valor estornado ao usuário.")
                else:
                    logger.critical(f"🆘 CRÍTICO: FALHA NO PAGAMENTO do saque {transaction_id} E FALHA AO ESTORNAR o saldo para o usuário {user_telegram_id}. INTERVENÇÃO MANUAL URGENTE!")
                    bot.edit_message_text(f"🆘 *CRÍTICO:* Falha no pagamento para saque ID `{transaction_id}` E *FALHA AO ESTORNAR O SALDO*. Contate o suporte técnico imediatamente!", call.message.chat.id, call.message.message_id)

        elif action == "reject":
            logger.info(f"👑 Admin {admin_id} iniciou REJEIÇÃO do saque {transaction_id}.")
            bot.answer_callback_query(call.id, "🚫 Rejeitando e estornando valor...")
            fee_amount = database.get_fee_for_withdrawal(transaction_id)
            total_to_refund = original_amount + fee_amount
            
            if database.update_balance(user_telegram_id, total_to_refund):
                admin_notes = f"Rejeitado pelo administrador {admin_id}."
                database.update_transaction_status(transaction_id, config.STATUS_RECUSADO, admin_notes=admin_notes)
                bot.edit_message_text(f"🚫 Saque ID `{transaction_id}` *RECUSADO*. O valor de R$ {total_to_refund:.2f} foi estornado com sucesso ao usuário.", call.message.chat.id, call.message.message_id, reply_markup=None)
                bot.send_message(user_telegram_id, f"❌ Sua solicitação de saque de R${original_amount:.2f} (ID: `{transaction_id}`) foi *RECUSADA*. O valor total debitado de R${total_to_refund:.2f} foi devolvido integralmente ao seu saldo.")
                logger.info(f"🚫 Saque {transaction_id} REJEITADO pelo admin {admin_id}. Valor estornado.")
            else:
                logger.critical(f"🆘 CRÍTICO: FALHA AO ESTORNAR saldo para o saque rejeitado {transaction_id} (Admin: {admin_id}). INTERVENÇÃO MANUAL URGENTE!")
                bot.edit_message_text(f"🆘 *CRÍTICO:* Saque ID `{transaction_id}` rejeitado, MAS FALHOU AO ESTORNAR O SALDO. Contate o suporte técnico imediatamente!", call.message.chat.id, call.message.message_id)

def notify_admin_of_withdrawal_request(transaction_id, user_telegram_id, user_first_name, amount, pix_key, target_admin_id=None):
    """
    Envia uma mensagem de notificação para os administradores sobre um novo saque.
    Se target_admin_id for especificado, envia apenas para ele.
    """
    admin_list = [target_admin_id] if target_admin_id else config.ADMIN_TELEGRAM_IDS
    if not admin_list:
        logger.warning(f"⚠️ Nenhum administrador para notificar sobre o saque {transaction_id}.")
        return

    markup = InlineKeyboardMarkup(row_width=2)
    btn_approve = InlineKeyboardButton("✅ Aprovar Pagamento", callback_data=f"admin_withdraw_approve_{transaction_id}")
    btn_reject = InlineKeyboardButton("❌ Recusar e Estornar", callback_data=f"admin_withdraw_reject_{transaction_id}")
    markup.add(btn_approve, btn_reject)

    message_text = (
        f"⚠️ *Nova Solicitação de Saque Pendente:*\n\n"
        f"👤 *Usuário:* {user_first_name} (`{user_telegram_id}`)\n"
        f"🆔 *ID da Transação:* `{transaction_id}`\n\n"
        f"💸 *Valor a Pagar (Líquido):* `R$ {amount:.2f}`\n"
        f"🔑 *Chave PIX:* `{pix_key}`"
    )

    for admin_id in admin_list:
        try:
            bot.send_message(admin_id, message_text, reply_markup=markup)
            logger.info(f"📬 Notificação de saque {transaction_id} enviada ao admin ID: {admin_id}.")
        except Exception as e:
            logger.error(f"❌ Erro ao enviar notificação de saque {transaction_id} para admin ID {admin_id}: {e}")
