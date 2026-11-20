import hmac
import logging
import os
from html import escape
from time import time

import telebot
from flask import Flask, request, abort
from telebot import apihelper

from data import (get_rehearsals, STICKERS, cancel_rehearsal, help_message, survey_question, is_next_rehearsal_near,
                  sticker_for, DODIKI_URL, now_kyiv, get_rehearsals_list, refresh_rehearsals, SESSION, TIMEOUT)

logging.basicConfig(level=logging.INFO)
# Fail fast: a serverless function has a hard time limit, a hanging Telegram call must not eat all of it.
apihelper.CONNECT_TIMEOUT = 5
apihelper.READ_TIMEOUT = 15

OPTIONS = {'Next': 'Who pays next?', 'Rehearsals': 'Rehearsals list', 'URL': 'Open site', 'Card': 'Card number',
           'Cancel': 'Cancel next rehearsal', 'Survey': 'Survey', 'Help': 'Help'}
TOKEN = os.getenv('TOKEN')
BOT = telebot.TeleBot(TOKEN, threaded=False, parse_mode='HTML')
app = Flask(__name__)
# Telegram redelivers an update if we answer slowly/with an error; do not run destructive commands on old ones
CANCEL_MAX_AGE_SECONDS = 60

KEYBOARD1 = telebot.types.ReplyKeyboardMarkup()
KEYBOARD1.row(OPTIONS['Next'], OPTIONS['Rehearsals'], OPTIONS['URL'], OPTIONS['Card'], OPTIONS['Cancel'])


def chat_id_from_env() -> int:
    return int(os.environ['CHAT_ID'])


def allowed_chat_ids() -> set:
    """The band chat plus optional extra chats (e.g. a test chat) from the comma-separated ALLOWED_CHAT_IDS."""
    extra = [int(i) for i in os.getenv('ALLOWED_CHAT_IDS', '').replace(' ', '').split(',') if i]
    return {chat_id_from_env(), *extra}


def is_allowed(message) -> bool:
    """Only the allowed chats and the members of the band chat (in a private chat) may use the bot."""
    allowed = message.chat.id in allowed_chat_ids()
    if not allowed and message.chat.type == 'private':
        try:
            allowed = BOT.get_chat_member(chat_id_from_env(), message.from_user.id).status in (
                'creator', 'administrator', 'member', 'restricted')
        except telebot.apihelper.ApiTelegramException:
            allowed = False
    if not allowed:
        logging.warning('ignored message from chat %s (%s), CHAT_ID is %s', message.chat.id, message.chat.type,
                        chat_id_from_env())
        BOT.send_message(message.chat.id, f'This bot is not enabled for this chat (id {message.chat.id})')
    return allowed


def command_of(text: str) -> str:
    """Map a button caption or a /command (also `/next@bot_name`) to an OPTIONS key; '' if unknown."""
    text = text.strip().lower()
    first = text.split()[0].split('@')[0] if text else ''
    for key, caption in OPTIONS.items():
        if text == caption.lower() or first == f'/{key.lower()}':
            return key
    # /list and /site are the historic names of the Rehearsals and URL options
    return {'/list': 'Rehearsals', '/site': 'URL'}.get(first, '')


@BOT.message_handler(commands=['start'])
def start_message(message):
    if is_allowed(message):
        BOT.send_sticker(message.chat.id, STICKERS['sbt'])
        BOT.send_message(message.chat.id, 'Please choose an option', reply_markup=KEYBOARD1)


@BOT.message_handler(content_types=['sticker'])
def get_sticker_id(message):
    if is_allowed(message):
        BOT.send_message(message.chat.id, f'Sticker Id - {message.sticker.file_id}')


@BOT.message_handler(content_types=['text'])
def send_text(message):
    if not is_allowed(message):
        return
    try:
        handle_command(message)
    except Exception:  # pylint: disable=broad-except
        logging.exception('command failed: %s', message.text)
        BOT.send_message(message.chat.id, 'Something went wrong, please try again in a minute')


def handle_command(message):
    chat_id = message.chat.id
    command = command_of(message.text)
    if command == 'Next':
        rehearsals = get_rehearsals()
        BOT.send_message(chat_id, rehearsals[0])
        BOT.send_sticker(chat_id, sticker_for(rehearsals[2]))
    elif command == 'Rehearsals':
        BOT.send_message(chat_id, get_rehearsals()[1])
        BOT.send_sticker(chat_id, STICKERS['list'])
    elif command == 'URL':
        BOT.send_message(chat_id, f'Site URL - {DODIKI_URL}')
    elif command == 'Card':
        BOT.send_message(chat_id, '<b>IBAN:</b>\n'
                                  '<code>UA023220010000026005320037612</code>\n\n'
                                  '<b>ЄДРПОУ:</b>\n'
                                  '<code>3224421492</code>\n\n'
                                  '<b>Отримувач:</b>\n'
                                  '<code>Рябчук Юрій Миколайович</code>\n\n'
                                  '<b>Призначення:</b>\n'
                                  f'<code>за репетицію {now_kyiv().date()}</code>')
    elif command == 'Cancel':
        if time() - message.date > CANCEL_MAX_AGE_SECONDS:
            BOT.send_message(chat_id, 'This cancel request is too old, send it again if you still need it')
            return
        BOT.send_message(chat_id, 'Canceling next rehearsal')
        rehearsals = cancel_rehearsal()
        BOT.send_message(chat_id, 'Done! Next rehearsal:')
        BOT.send_message(chat_id, rehearsals[0])
        BOT.send_sticker(chat_id, sticker_for(rehearsals[2]))
    elif command == 'Help':
        BOT.send_message(chat_id, escape(help_message()))
    elif command == 'Survey':
        run_survey(chat_id=chat_id)
    else:
        BOT.send_message(chat_id, 'Kurwa, I did not understand this command')
        BOT.send_sticker(chat_id, 'CAACAgIAAxkBAAIBkl6pr4kVOGisB5LUX54w8USsN6hWAAL5AANWnb0KlWVuqyorGzYZBA')


def mentions(chat_id: int) -> str:
    """Tag the chat admins; an empty string in chats where admins cannot be listed (e.g. a private chat)."""
    try:
        admins = BOT.get_chat_administrators(chat_id)
    except telebot.apihelper.ApiTelegramException:
        return ''
    return ' '.join(f'<a href="tg://user?id={admin.user.id}">{escape(admin.user.first_name)}</a>'
                    for admin in admins if not admin.user.is_bot)


def run_survey(chat_id: int = None):
    """Create the availability poll. Without chat_id it is a cron run: target CHAT_ID and stay silent if too early."""
    cron = chat_id is None
    if cron:
        chat_id = chat_id_from_env()
        refresh_rehearsals()

    if not is_next_rehearsal_near():
        if not cron:
            BOT.send_message(chat_id, 'There are no upcoming rehearsals for the next 3 days')
        return

    question = survey_question()
    users = mentions(chat_id)
    if users:
        BOT.send_message(chat_id, users)
    if os.getenv('WAR'):
        BOT.send_poll(chat_id, question, ('Звісно 🔥', 'Все, пезда, нема більше грошей 🐖'), is_anonymous=False)
        BOT.send_sticker(chat_id, STICKERS['sbt'])
    else:
        BOT.send_poll(chat_id, question, ('Yes', 'No'), is_anonymous=False)


def run_rehearsal_reminder() -> bool:
    """Cron: on the rehearsal day tell the chat who pays, if the next rehearsal is today."""
    refresh_rehearsals()
    if not is_next_rehearsal_near(0):
        return False
    payer = get_rehearsals_list()[0]['member_name']
    chat_id = chat_id_from_env()
    BOT.send_message(chat_id, f'Rehearsal today! <b>{escape(payer)}</b> pays')
    BOT.send_sticker(chat_id, sticker_for(payer))
    return True


def require_secret(header: str, expected: str, scheme: str = ''):
    """Abort with 403 unless the request header matches the expected secret (constant-time compare)."""
    given = request.headers.get(header, '')
    if not expected or not hmac.compare_digest(given.encode(), f'{scheme}{expected}'.encode()):
        abort(403)


@app.route('/')
def index():
    return 'dodibot is alive', 200


@app.route('/webhook', methods=['POST'])
def webhook():
    """Telegram pushes updates here (registered by /set_webhook, protected by a secret token)."""
    require_secret('X-Telegram-Bot-Api-Secret-Token', os.getenv('WEBHOOK_SECRET'))
    try:
        BOT.process_new_updates([telebot.types.Update.de_json(request.get_data().decode('utf-8'))])
    except Exception:  # pylint: disable=broad-except
        # Never answer with an error: Telegram would redeliver the very same update again and again
        logging.exception('update processing failed')
    return '!', 200


@app.route('/set_webhook')
def set_webhook():
    """One-off: register the webhook. Call with `Authorization: Bearer $CRON_SECRET`."""
    require_secret('Authorization', os.getenv('CRON_SECRET'), 'Bearer ')
    url = f"{os.environ['SERVER'].rstrip('/')}/webhook"
    BOT.set_webhook(url=url, secret_token=os.environ['WEBHOOK_SECRET'], drop_pending_updates=True)
    return f'webhook set to {url}', 200


@app.route('/cron/wake')
def cron_wake():
    """Warm up dodiki (its function/DB cold start) shortly before people ask the bot something."""
    require_secret('Authorization', os.getenv('CRON_SECRET'), 'Bearer ')
    status = SESSION.get(f'{DODIKI_URL}/get_rehearsals', timeout=TIMEOUT).status_code
    return f'dodiki responded {status}', 200 if status == 200 else 502


@app.route('/cron/survey')
def cron_survey():
    require_secret('Authorization', os.getenv('CRON_SECRET'), 'Bearer ')
    run_survey()
    return 'survey done', 200


@app.route('/cron/reminder')
def cron_reminder():
    require_secret('Authorization', os.getenv('CRON_SECRET'), 'Bearer ')
    return ('reminder sent' if run_rehearsal_reminder() else 'no rehearsal today'), 200


if __name__ == '__main__':
    # Local mode: long polling instead of the webhook (it must be removed or Telegram refuses to poll)
    BOT.remove_webhook()
    print('Polling... (cron endpoints are served by `flask --app index run`)')
    BOT.infinity_polling()
