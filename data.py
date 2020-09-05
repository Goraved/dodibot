import os

import requests


def get_rehearsals_list() -> list:
    return requests.get('http://dodiki.herokuapp.com/get_rehearsals').json()['rehearsals']


def get_rehearsals():
    rehearsals = get_rehearsals_list()
    next_pay = f"*{rehearsals[0]['member']}* - at {rehearsals[0]['date'].replace(' 00:00:00 GMT', '')}"
    rehearsals_list = '\n'.join([f'*{_["member"]}* at {_["date"].replace(" 00:00:00 GMT", "")}' for _ in rehearsals])
    return next_pay, rehearsals_list, rehearsals[0]['member']


stickers = {
    'sbt': 'CAACAgIAAxkBAAICR16sCciIZsSAsLoLoyBnHozQmm0AAy4AA2YJ_hqTgccfKxajRhkE',
    'Dimon': 'CAACAgIAAxkBAAICTV6sCc4E0BKdqKjRtO4W0YnV4qErAAIxAANmCf4arQ4GNvpbBNQZBA',
    'Bodya': 'CAACAgIAAxkBAAICS16sCcxGCVSMymeWuqbrHI9bfP0sAAIwAANmCf4aOvoo_Xngc9UZBA',
    'Andrii': 'CAACAgIAAxkBAAICSV6sCcrS8Tw7UYumZtxva8fJdLydAAIvAANmCf4aFNWXT8cWhYIZBA',
    'Roman': 'CAACAgIAAxkBAAICT16sCdCPVPYxZtuqKb7dP_feHvbFAAIyAANmCf4ayrKgS5tzuGwZBA',
    'list': 'CAACAgIAAxkBAAICYV6sGGZNQBx-9lpLDdKHGVoh398UAAIzAANmCf4atp1lU1EOY7EZBA'
}


def cancel_rehearsal():
    rehearsals = get_rehearsals_list()
    requests.get(f'http://dodiki.herokuapp.com/cancel/{rehearsals[0]["id"]}',
                 auth=(os.environ['USER'], os.environ['PASSWORD']))
    return get_rehearsals()
