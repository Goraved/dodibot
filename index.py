import os
from datetime import datetime
from threading import Thread
from time import sleep

import schedule
import telebot
from flask import Flask, request

from data import (
    get_rehearsals,
    STICKERS,
    cancel_rehearsal,
    help_message,
    survey_question,
    is_next_rehearsal_near,
    DEFAULT_STICKER,
)

OPTIONS = {
    "Next": "Who pays next?",
    "Rehearsals": "Rehearsals list",
    "URL": "Open site",
    "Card": "Card number",
    "Cancel": "Cancel next rehearsal",
    "Survey": "Survey",
    "Help": "Help",
}
TOKEN = os.getenv("TOKEN")
BOT = telebot.TeleBot(TOKEN)
app = Flask(__name__)
TOTAL_ANSWERS = []

KEYBOARD1 = telebot.types.ReplyKeyboardMarkup()
KEYBOARD1.row(
    OPTIONS["Next"],
    OPTIONS["Rehearsals"],
    OPTIONS["URL"],
    OPTIONS["Card"],
    OPTIONS["Cancel"],
)


@BOT.message_handler(commands=["start"])
def start_message(message):
    BOT.send_sticker(message.chat.id, STICKERS["sbt"])
    BOT.send_message(message.chat.id, "Please choose an option", reply_markup=KEYBOARD1)


@BOT.message_handler(content_types=["sticker"])
def get_sticker_id(sticker):
    BOT.send_message(sticker.chat.id, f"Sticker Id - {sticker.sticker.file_id}")


@BOT.message_handler(content_types=["answer"])
def get_answer(sticker):
    BOT.send_message(sticker.chat.id, f"Sticker Id - {sticker.sticker.file_id}")


@BOT.message_handler(content_types=["text"])
def send_text(message):
    if (
        message.text.lower() == OPTIONS["Next"].lower()
        or "/next" in message.text.lower()
    ):
        rehearsals = get_rehearsals()
        BOT.send_message(message.chat.id, rehearsals[0], parse_mode="Markdown")
        BOT.send_sticker(message.chat.id, STICKERS.get(rehearsals[2], DEFAULT_STICKER))
    elif (
        message.text.lower() == OPTIONS["Rehearsals"].lower()
        or "/list" in message.text.lower()
    ):
        BOT.send_message(message.chat.id, get_rehearsals()[1], parse_mode="Markdown")
        BOT.send_sticker(message.chat.id, STICKERS["list"])
    elif (
        message.text.lower() == OPTIONS["URL"].lower()
        or "/site" in message.text.lower()
    ):
        BOT.send_message(message.chat.id, "Site URL - https://dodiki.herokuapp.com")
    elif (
        message.text.lower() == OPTIONS["Card"].lower()
        or "/card" in message.text.lower()
    ):
        today = datetime.now().date()
        BOT.send_message(
            message.chat.id,
            "*IBAN:*\n"
            "`UA023220010000026005320037612`\n\n"
            "*ЄДРПОУ:*\n"
            "`3224421492`\n\n"
            "*Отримувач:*\n"
            "`Рябчук Юрій Миколайович`\n\n"
            "*Призначення:*\n"
            f"`за репетицію {today}`",
            parse_mode="Markdown",
        )
    elif (
        message.text.lower() == OPTIONS["Cancel"].lower()
        or "/cancel" in message.text.lower()
    ):
        BOT.send_message(message.chat.id, "Canceling next rehearsal")
        rehearsals = cancel_rehearsal()
        BOT.send_message(message.chat.id, "Done! Next rehearsal:")
        BOT.send_message(message.chat.id, rehearsals[0], parse_mode="Markdown")
        BOT.send_sticker(message.chat.id, STICKERS[rehearsals[2]])
    elif (
        message.text.lower() == OPTIONS["Help"].lower()
        or "/help" in message.text.lower()
    ):
        BOT.send_message(message.chat.id, help_message())
    elif (
        message.text.lower() == OPTIONS["Survey"].lower()
        or "/survey" in message.text.lower()
    ):
        run_survey(chat_id=message.chat.id)
    else:
        BOT.send_message(message.chat.id, "Kurwa, I did not understand this command")
        BOT.send_sticker(
            message.chat.id,
            "CAACAgIAAxkBAAIBkl6pr4kVOGisB5LUX54w8USsN6hWAAL5AANWnb0KlWVuqyorGzYZBA",
        )


def run_survey(chat_id: int = None):
    cron = False
    if not chat_id:
        chat_id = int(os.getenv("CHAT_ID"))
        cron = True

    rehearsal_near = is_next_rehearsal_near()
    if not rehearsal_near and not cron:
        BOT.send_message(
            chat_id,
            "There are no upcoming rehearsals for the next 3 days",
            parse_mode="Markdown",
        )

    admins = BOT.get_chat_administrators(chat_id)
    users = " ".join(
        [f"[{admin.user.first_name}](tg://user?id={admin.user.id})" for admin in admins]
    )
    question = survey_question()

    if question in TOTAL_ANSWERS:
        BOT.send_message(
            chat_id,
            "Survey for the next rehearsal has been already created",
            parse_mode="Markdown",
        )
    elif question not in TOTAL_ANSWERS and rehearsal_near:
        BOT.send_message(chat_id, users, parse_mode="Markdown")
        if os.getenv("WAR"):
            BOT.send_poll(
                chat_id,
                question,
                ("Звісно 🔥", "Все, пезда, нема більше грошей 🐖"),
                is_anonymous=False,
            )
            BOT.send_sticker(chat_id, STICKERS["sbt"])
        else:
            BOT.send_poll(chat_id, question, ("Yes", "No"), is_anonymous=False)
        TOTAL_ANSWERS.append(question)


def schedule_checker():
    while True:
        schedule.run_pending()
        sleep(1)


def run_schedule():
    trigger_time = os.getenv("TRIGGER_TIME")
    # schedule.every().tuesday.at(trigger_time).do(run_survey)
    schedule.every().friday.at(trigger_time).do(run_survey)
    # Spin up a thread to run the schedule check so it doesn't block your bot.
    # This will take the function schedule_checker which will check every second
    # to see if the scheduled job needs to be ran.
    Thread(target=schedule_checker).start()


# Uncomment to use local
if os.getenv("LOCAL"):
    BOT.remove_webhook()
    run_schedule()
    BOT.polling(none_stop=True)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

else:

    @app.route("/")
    def webhook():
        BOT.remove_webhook()
        sleep(1)
        run_schedule()
        BOT.set_webhook(url=f"{os.getenv('SERVER')}/{TOKEN}")
        return "!", 200

    # Heroku
    @app.route("/" + TOKEN, methods=["POST"])
    def getMessage():
        BOT.process_new_updates(
            [telebot.types.Update.de_json(request.stream.read().decode("utf-8"))]
        )
        return "?", 200

    app.run(host=os.getenv("SERVER"))
