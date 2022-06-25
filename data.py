import os
from datetime import datetime

import requests


def get_rehearsals_list() -> list:
    return requests.get('http://dodiki.herokuapp.com/get_rehearsals').json()['rehearsals']


def get_rehearsals() -> tuple:
    rehearsals = get_rehearsals_list()
    next_pay = f"*{rehearsals[0]['member_name']}* - at {rehearsals[0]['rehearsal_date'].replace(' 00:00:00 GMT', '')}"
    rehearsals_list = '\n'.join(
        [f'*{_["member_name"]}* at {_["rehearsal_date"].replace(" 00:00:00 GMT", "")}' for _ in rehearsals])
    return next_pay, rehearsals_list, rehearsals[0]['member_name']


STICKERS = {
    'sbt': 'CAACAgIAAxkBAAICR16sCciIZsSAsLoLoyBnHozQmm0AAy4AA2YJ_hqTgccfKxajRhkE',
    'Dimon': 'CAACAgIAAxkBAAICTV6sCc4E0BKdqKjRtO4W0YnV4qErAAIxAANmCf4arQ4GNvpbBNQZBA',
    'Bodya': 'CAACAgIAAxkBAAICS16sCcxGCVSMymeWuqbrHI9bfP0sAAIwAANmCf4aOvoo_Xngc9UZBA',
    'Andrii': 'CAACAgIAAxkBAAICSV6sCcrS8Tw7UYumZtxva8fJdLydAAIvAANmCf4aFNWXT8cWhYIZBA',
    'Roman': 'CAACAgIAAxkBAAICT16sCdCPVPYxZtuqKb7dP_feHvbFAAIyAANmCf4ayrKgS5tzuGwZBA',
    'list': 'CAACAgIAAxkBAAICYV6sGGZNQBx-9lpLDdKHGVoh398UAAIzAANmCf4atp1lU1EOY7EZBA'
}
DEFAULT_STICKER = 'CAACAgIAAxkBAAIE1mKva8QHgK8vTDmyZ2FJ3e7BwoVRAAIOGwACnCK4SRpJxB_Xi-QrJAQ'


def cancel_rehearsal() -> tuple:
    rehearsals = get_rehearsals_list()
    requests.get(f'http://dodiki.herokuapp.com/cancel/{rehearsals[0]["rehearsal_id"]}',
                 auth=(os.environ['USER'], os.environ['PASSWORD']))
    return get_rehearsals()


def survey_question() -> str:
    if os.getenv('WAR'):
        msg = '🇺🇦 а ти задонатив на зсу цього тижня? 🇺🇦'
    else:
        rehearsals = get_rehearsals_list()
        rehearsal_date = rehearsals[0]['rehearsal_date'].replace(' 00:00:00 GMT', '')
        rehearsal_date += ' at 11 am' if 'Sun' in rehearsal_date else ' at 8 pm'
        msg = f'are you able to visit the next rehearsal? - ' \
              f'{rehearsal_date} ({rehearsals[0]["member_name"]} gonna pay)'
    return msg


def help_message() -> str:
    return """
    1 - type "who pays next?" or "/next" to get the next rehearsal date and name of the guy who gonna pay;
2 - type "rehearsals list" or "/list" to get a list of future rehearsals;
3 - type "open site" or "/site" to get a link to the dodik site;
4 - type "card number" or "/card" to get a card number where need to transfer money;
5 - type "cancel next rehearsal" or "/cancel" to cancel next rehearsal and shift all list forward;
6 - type "survey" or "/survey" to start a survey about availability to go to the next rehearsal;
    """


def is_next_rehearsal_near() -> bool:
    rehearsal = get_rehearsals_list()[0]['rehearsal_date'].replace(' 00:00:00 GMT', '')
    next_date = datetime.strptime(rehearsal, '%a, %d %b %Y')
    delta_days = (next_date.date() - datetime.now().date()).days
    # do not create a survey if next rehearsal is not upcoming
    return delta_days <= 3
