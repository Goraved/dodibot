import os
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from html import escape
from time import monotonic
from zoneinfo import ZoneInfo

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry



def load_env_file(path: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')):
    """Local runs: read KEY=VALUE lines from .env (variables already set in the environment win). No-op on Vercel."""
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"\''))


load_env_file()
TZ = ZoneInfo('Europe/Kyiv')
DODIKI_URL = os.getenv('DODIKI_URL', 'https://dodiki.vercel.app').rstrip('/')
SUNDAY = 6

# One pooled session; retries cover dodiki cold starts (502/503/504) and dropped connections.
SESSION = requests.Session()
for _scheme in ('https://', 'http://'):
    SESSION.mount(_scheme, HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=(502, 503, 504))))
TIMEOUT = 20
CACHE_TTL = 120  # seconds; the schedule only changes via the site or /cancel

STICKERS = {
    'sbt': 'CAACAgIAAxkBAAICR16sCciIZsSAsLoLoyBnHozQmm0AAy4AA2YJ_hqTgccfKxajRhkE',
    'Dimon': 'CAACAgIAAxkBAAICTV6sCc4E0BKdqKjRtO4W0YnV4qErAAIxAANmCf4arQ4GNvpbBNQZBA',
    'Bodya': 'CAACAgIAAxkBAAICS16sCcxGCVSMymeWuqbrHI9bfP0sAAIwAANmCf4aOvoo_Xngc9UZBA',
    'Andrii': 'CAACAgIAAxkBAAICSV6sCcrS8Tw7UYumZtxva8fJdLydAAIvAANmCf4aFNWXT8cWhYIZBA',
    'Roman': 'CAACAgIAAxkBAAICT16sCdCPVPYxZtuqKb7dP_feHvbFAAIyAANmCf4ayrKgS5tzuGwZBA',
    'list': 'CAACAgIAAxkBAAICYV6sGGZNQBx-9lpLDdKHGVoh398UAAIzAANmCf4atp1lU1EOY7EZBA'
}
DEFAULT_STICKER = 'CAACAgIAAxkBAAIE1mKva8QHgK8vTDmyZ2FJ3e7BwoVRAAIOGwACnCK4SRpJxB_Xi-QrJAQ'


def now_kyiv() -> datetime:
    return datetime.now(TZ)


def sticker_for(name: str) -> str:
    return STICKERS.get(name, DEFAULT_STICKER)


_cache = {'at': float('-inf'), 'rehearsals': []}


def refresh_rehearsals():
    """Drop the cached schedule so the next read hits dodiki (after a change or at the start of a cron job)."""
    _cache['at'] = float('-inf')


def get_rehearsals_list() -> list:
    """Future rehearsals from dodiki, cached for CACHE_TTL seconds: dodiki needs ~1.2s per call, Telegram ~50ms.

    Its main page generates a new schedule when none is left, so poke it once if the list is empty."""
    today = now_kyiv().date()
    if _cache['rehearsals'] and monotonic() - _cache['at'] < CACHE_TTL:
        cached = [r for r in _cache['rehearsals'] if rehearsal_date(r) >= today]
        if cached:
            return cached
    for attempt in range(2):
        response = SESSION.get(f'{DODIKI_URL}/get_rehearsals', timeout=TIMEOUT)
        response.raise_for_status()
        rehearsals = response.json()['rehearsals']
        if rehearsals:
            _cache.update(at=monotonic(), rehearsals=rehearsals)
            return rehearsals
        if attempt == 0:
            SESSION.get(f'{DODIKI_URL}/', timeout=TIMEOUT)
    raise RuntimeError('dodiki returned no upcoming rehearsals')


def rehearsal_date(rehearsal: dict) -> date:
    """dodiki sends dates like 'Sun, 29 Nov 2026 00:00:00 GMT'."""
    return parsedate_to_datetime(rehearsal['rehearsal_date']).date()


def format_date(rehearsal: dict) -> str:
    return rehearsal_date(rehearsal).strftime('%a, %d %b %Y')


def get_rehearsals() -> tuple:
    """(next rehearsal text, all rehearsals text, next payer name); texts are HTML."""
    rehearsals = get_rehearsals_list()
    first = rehearsals[0]
    next_pay = f'<b>{escape(first["member_name"])}</b> - at {format_date(first)}'
    rehearsals_list = '\n'.join(f'<b>{escape(_["member_name"])}</b> at {format_date(_)}' for _ in rehearsals)
    return next_pay, rehearsals_list, first['member_name']


def cancel_rehearsal() -> tuple:
    refresh_rehearsals()
    rehearsals = get_rehearsals_list()
    response = SESSION.get(f'{DODIKI_URL}/cancel/{rehearsals[0]["rehearsal_id"]}', timeout=TIMEOUT,
                           auth=(os.environ['DODIKI_USER'], os.environ['DODIKI_PASSWORD']))
    response.raise_for_status()
    refresh_rehearsals()
    return get_rehearsals()


def survey_question() -> str:
    if os.getenv('WAR'):
        return '🇺🇦 а ти задонатив на зсу цього тижня? 🇺🇦'
    first = get_rehearsals_list()[0]
    when = f'{format_date(first)} at {"11 am" if rehearsal_date(first).weekday() == SUNDAY else "8 pm"}'
    return f'are you able to visit the next rehearsal? - {when} ({first["member_name"]} gonna pay)'


def help_message() -> str:
    return """
    1 - type "who pays next?" or "/next" to get the next rehearsal date and name of the guy who gonna pay;
2 - type "rehearsals list" or "/list" to get a list of future rehearsals;
3 - type "open site" or "/site" to get a link to the dodik site;
4 - type "card number" or "/card" to get a card number where need to transfer money;
5 - type "cancel next rehearsal" or "/cancel" to cancel next rehearsal and shift all list forward;
6 - type "survey" or "/survey" to start a survey about availability to go to the next rehearsal;
    """


def is_next_rehearsal_near(max_days: int = 3) -> bool:
    """False if the next rehearsal is further than `max_days` away (no survey/reminder needed yet)."""
    delta_days = (rehearsal_date(get_rehearsals_list()[0]) - now_kyiv().date()).days
    return delta_days <= max_days
