import requests


def get_rehearsals():
    rehearsals = requests.get('http://dodiki.herokuapp.com/get_rehearsals').json()['rehearsals']
    next_pay = f"*{rehearsals[0]['member']}* - at {rehearsals[0]['date'].replace(' 00:00:00 GMT', '')}"
    rehearsals_list = '\n'.join([f'*{_["member"]}* at {_["date"].replace(" 00:00:00 GMT", "")}' for _ in rehearsals])
    return next_pay, rehearsals_list, rehearsals[0]['member']


stickers = {
    'sbt': 'CAACAgIAAxkBAAICR16sCciIZsSAsLoLoyBnHozQmm0AAy4AA2YJ_hqTgccfKxajRhkE',
    'Dimon': 'CAACAgIAAxkBAAICTV6sCc4E0BKdqKjRtO4W0YnV4qErAAIxAANmCf4arQ4GNvpbBNQZBA',
    'Bodya': 'CAACAgIAAxkBAAICS16sCcxGCVSMymeWuqbrHI9bfP0sAAIwAANmCf4aOvoo_Xngc9UZBA',
    'Andrii': 'CAACAgIAAxkBAAICSV6sCcrS8Tw7UYumZtxva8fJdLydAAIvAANmCf4aFNWXT8cWhYIZBA',
    'Roman': 'CAACAgIAAxkBAAICT16sCdCPVPYxZtuqKb7dP_feHvbFAAIyAANmCf4ayrKgS5tzuGwZBA',
    'list': 'CAACAgIAAxkBAAIBh16prxNbEgme1n_uECeShXDlUhekAAIFAQACVp29Crfk_bYORV93GQQ'
}
