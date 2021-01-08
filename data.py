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


stickers = {
    'sbt': 'CAACAgIAAxkBAAICR16sCciIZsSAsLoLoyBnHozQmm0AAy4AA2YJ_hqTgccfKxajRhkE',
    'Dimon': 'CAACAgIAAxkBAAICTV6sCc4E0BKdqKjRtO4W0YnV4qErAAIxAANmCf4arQ4GNvpbBNQZBA',
    'Bodya': 'CAACAgIAAxkBAAICS16sCcxGCVSMymeWuqbrHI9bfP0sAAIwAANmCf4aOvoo_Xngc9UZBA',
    'Andrii': 'CAACAgIAAxkBAAICSV6sCcrS8Tw7UYumZtxva8fJdLydAAIvAANmCf4aFNWXT8cWhYIZBA',
    'Roman': 'CAACAgIAAxkBAAICT16sCdCPVPYxZtuqKb7dP_feHvbFAAIyAANmCf4ayrKgS5tzuGwZBA',
    'list': 'CAACAgIAAxkBAAICYV6sGGZNQBx-9lpLDdKHGVoh398UAAIzAANmCf4atp1lU1EOY7EZBA'
}


def cancel_rehearsal() -> tuple:
    rehearsals = get_rehearsals_list()
    requests.get(f'http://dodiki.herokuapp.com/cancel/{rehearsals[0]["rehearsal_id"]}',
                 auth=(os.environ['USER'], os.environ['PASSWORD']))
    return get_rehearsals()


def survey_question() -> str:
    rehearsal = get_rehearsals_list()[0]['rehearsal_date'].replace(' 00:00:00 GMT', '')
    return f'Are you able to visit the next rehearsal? - {rehearsal}'


def help_message() -> str:
    return """
    1 - type "Who pays next?" or "/next" to get the next rehearsal date and name of the guy who gonna pay;
2 - type "Rehearsals list" or "/list" to get a list of future rehearsals;
3 - type "Open site" or "/site" to get a link to the Dodik site;
4 - type "Card number" or "/card" to get a card number where need to transfer money;
5 - type "Cancel next rehearsal" or "/cancel" to cancel next rehearsal and shift all list forward;
6 - type "Survey" or "/survey" to start a survey about availability to go to the next rehearsal;
    """


def is_next_rehearsal_near() -> bool:
    rehearsal = get_rehearsals_list()[0]['rehearsal_date'].replace(' 00:00:00 GMT', '')
    next_date = datetime.strptime(rehearsal, '%a, %d %b %Y')
    delta_days = (next_date.date() - datetime.now().date()).days
    # Do not create a survey if next rehearsal is not upcoming
    return delta_days <= 3
