"""Daglig udgivelse af by-strømmens RSS 2.0-feeds (O61). Ingen afhængigheder.

Kører hver morgen i GitHub Actions (.github/workflows/dagligt.yml) og kan køres lokalt.
Læser ko.json og skriver feeds/<tavle>.xml med de pins, hvis dato er nået (dansk tid).
Pinterest henter feedet og laver pins af nye items (Auto-publish, ét feed pr. tavle).
Kun pins med status "klar" kommer med, og kun pins som billedkontrollen og tekstkontrollen har
GODKENDT (kraev_billedkontrol / kraev_tekstkontrol i indstillinger.json). Pins med en dato i fremtiden kommer aldrig i feedet,
så Pinterest ikke kan udgive en hel måned på én dag.

Brug:  python udgiv.py [--dato 2026-11-08] [--base-url https://…]
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import html
import json
import os
import re
import unicodedata
from pathlib import Path

HER = Path(__file__).resolve().parent
KO = HER / 'ko.json'
INDSTILLINGER = HER / 'indstillinger.json'
FEEDS = HER / 'feeds'
MAKS_ITEMS = 30


def slug(s: str) -> str:
    s = s.lower().replace('æ', 'ae').replace('ø', 'oe').replace('å', 'aa')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')


def dansk_dato() -> dt.date:
    # CET/CEST uden tzdata: november-marts er UTC+1, ellers UTC+2 (godt nok til en dato kl. 6 om morgenen)
    nu = dt.datetime.now(dt.timezone.utc)
    return (nu + dt.timedelta(hours=1 if nu.month in (11, 12, 1, 2, 3) else 2)).date()


def rss(tavle: str, items: list[dict], base: str) -> str:
    e = html.escape
    nu = email.utils.format_datetime(dt.datetime.now(dt.timezone.utc))
    ud = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">', '<channel>',
          f'<title>HjemEgn: {e(tavle)}</title>', '<link>https://www.hjemegn.dk/</link>',
          f'<description>Byplakater fra HjemEgn til tavlen {e(tavle)}</description>',
          '<language>da-dk</language>', f'<lastBuildDate>{nu}</lastBuildDate>']
    for p in items:
        billede = f'{base}/pins/{p["fil"]}'
        tid = dt.datetime.fromisoformat(p['dato']).replace(hour=6, tzinfo=dt.timezone.utc)
        ud += ['<item>', f'<title>{e(p["titel"])}</title>', f'<link>{e(p["link"])}</link>',
               f'<description>{e(p["beskrivelse"])}</description>',
               f'<guid isPermaLink="false">hjemegn-pin-{e(p["id"])}</guid>',
               f'<pubDate>{email.utils.format_datetime(tid)}</pubDate>',
               f'<enclosure url="{e(billede)}" length="{p.get("bytes", 0)}" type="image/jpeg"/>',
               f'<media:content url="{e(billede)}" medium="image" type="image/jpeg" width="1000" height="1500"/>',
               '</item>']
    ud += ['</channel>', '</rss>', '']
    return '\n'.join(ud)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dato', help='udgiv som om det var denne dato (test)')
    ap.add_argument('--base-url')
    a = ap.parse_args()
    ind = json.loads(INDSTILLINGER.read_text(encoding='utf-8'))
    base = (a.base_url or os.environ.get('HJEMEGN_PINS_URL') or ind['base_url']).rstrip('/')
    i_dag = dt.date.fromisoformat(a.dato) if a.dato else dansk_dato()
    ko = json.loads(KO.read_text(encoding='utf-8'))
    tavler = sorted({p['tavle'] for p in ko})
    FEEDS.mkdir(exist_ok=True)
    udgivet = 0
    for tavle in tavler:
        items = [p for p in ko if p['tavle'] == tavle and p['status'] == 'klar'
                 and dt.date.fromisoformat(p['dato']) <= i_dag
                 and (not ind.get('kraev_billedkontrol') or p.get('billedkontrol') == 'GODKENDT')
                 and (not ind.get('kraev_tekstkontrol') or p.get('tekstkontrol') == 'GODKENDT')]
        items.sort(key=lambda p: p['id'], reverse=True)
        items = items[:MAKS_ITEMS]
        udgivet += len(items)
        (FEEDS / f'{slug(tavle)}.xml').write_text(rss(tavle, items, base), encoding='utf-8')
    print(f'{i_dag}: {len(tavler)} feeds, {udgivet} items i alt')


if __name__ == '__main__':
    main()
