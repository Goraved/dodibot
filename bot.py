import os
from threading import Thread
from time import sleep

import schedule
import telebot
from flask import Flask, request

from data import get_rehearsals, stickers, cancel_rehearsal, help_message, survey_question

options = {'Next': 'Who pays next?', 'Rehearsals': 'Rehearsals list', 'URL': 'Open site', 'Card': 'Card number',
           'Cancel': 'Cancel next rehearsal', 'Survey': 'Survey', 'Help': 'Help'}
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)
server = Flask(__name__)
total_answers = 0

keyboard1 = telebot.types.ReplyKeyboardMarkup()
keyboard1.row(options['Next'], options['Rehearsals'], options['URL'], options['Card'], options['Cancel'])


@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_sticker(message.chat.id, stickers['sbt'])
    bot.send_message(message.chat.id, 'Please choose an option', reply_markup=keyboard1)


@bot.message_handler(content_types=['sticker'])
def get_sticker_id(sticker):
    bot.send_message(sticker.chat.id, f'Sticker Id - {sticker.sticker.file_id}')


@bot.message_handler(content_types=['text'])
def send_text(message):
    if message.text.lower() == options['Next'].lower() or '/next' in message.text.lower():
        rehearsals = get_rehearsals()
        bot.send_message(message.chat.id, rehearsals[0], parse_mode="Markdown")
        bot.send_sticker(message.chat.id, stickers[rehearsals[2]])
    elif message.text.lower() == options['Rehearsals'].lower() or '/list' in message.text.lower():
        bot.send_message(message.chat.id, get_rehearsals()[1], parse_mode="Markdown")
        bot.send_sticker(message.chat.id, stickers['list'])
    elif message.text.lower() == options['URL'].lower() or '/site' in message.text.lower():
        bot.send_message(message.chat.id, 'Site URL - https://dodiki.herokuapp.com')
    elif message.text.lower() == options['Card'].lower() or '/card' in message.text.lower():
        bot.send_message(message.chat.id, 'Card number - 5375414106892499')
    elif message.text.lower() == options['Cancel'].lower() or '/cancel' in message.text.lower():
        bot.send_message(message.chat.id, 'Canceling next rehearsal')
        rehearsals = cancel_rehearsal()
        bot.send_message(message.chat.id, 'Done! Next rehearsal:')
        bot.send_message(message.chat.id, rehearsals[0], parse_mode="Markdown")
        bot.send_sticker(message.chat.id, stickers[rehearsals[2]])
    elif message.text.lower() == options['Help'].lower() or '/help' in message.text.lower():
        bot.send_message(message.chat.id, help_message())
    elif message.text.lower() == options['Survey'].lower() or '/survey' in message.text.lower():
        run_survey()
    else:
        bot.send_message(message.chat.id, 'Kurwa, I did not understand this command')
        bot.send_sticker(message.chat.id, 'CAACAgIAAxkBAAIBkl6pr4kVOGisB5LUX54w8USsN6hWAAL5AANWnb0KlWVuqyorGzYZBA')


def run_survey():
    global total_answers
    chat_id = int(os.getenv('CHAT_ID'))
    admins = bot.get_chat_administrators(chat_id)
    users = ' '.join([f'[{admin.user.first_name}](tg://user?id={admin.user.id})' for admin in admins])
    question = survey_question()

    if not total_answers:
        bot.send_message(chat_id, users, parse_mode="Markdown")
        bot.send_poll(chat_id, question, ('Yes', 'No'), is_anonymous=False, explanation_parse_mode="Markdown")
        total_answers += 1
    elif total_answers == 4:
        bot.stop_poll(chat_id, question)


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(1)


def run_schedule():
    trigger_time = os.getenv('TRIGGER_TIME')
    schedule.every().saturday.at(trigger_time).do(run_survey)
    schedule.every().thursday.at(trigger_time).do(run_survey)
    # Spin up a thread to run the schedule check so it doesn't block your bot.
    # This will take the function schedule_checker which will check every second
    # to see if the scheduled job needs to be ran.
    Thread(target=schedule_checker).start()


# Uncomment to use local
# bot.remove_webhook()
# run_schedule()
# bot.polling(none_stop=True)


# Heroku
@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return '!', 200


# Comment to use local
@server.route("/")
def webhook():
    bot.remove_webhook()
    run_schedule()
    bot.set_webhook(url="https://dodibot.herokuapp.com/" + TOKEN)
    return "!", 200


if __name__ == '__main__':
    server.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
