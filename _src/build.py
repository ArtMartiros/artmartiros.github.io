#!/usr/bin/env python3
"""Builds the studio site from _src/.

    python3 _src/build.py          rebuild the pages
    python3 _src/build.py --check  only check that the pages match _src/

Each game is a card _src/games/<folder>.json and an icon <folder>/icon.png. It gets
<folder>/index.html (the game's page) and <folder>/privacy.html (its privacy policy),
and the home page index.html lists every game. The folder name is the game's address,
artmartiros.github.io/<folder>/, and never changes once it is in a store or a build.
"""
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from string import Template

SRC = Path(__file__).resolve().parent
SITE = SRC.parent
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
CARD_FIELDS = ["name", "store_name", "kind", "platforms", "description", "about", "policy_date",
               "play_data", "settings_example", "attribution", "ad_formats", "ad_networks", "audience"]
EFFECTIVE = re.compile(r"<p>Effective [^<]*</p>")


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def template(name):
    return Template((SRC / "templates" / name).read_text(encoding="utf-8"))


def and_list(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def game_values(slug, card, studio, networks, trackers):
    missing = [f for f in CARD_FIELDS if f not in card]
    unknown = [n for n in card.get("ad_networks", []) if n not in networks]
    unknown_trackers = [t for t in card.get("attribution", []) if t not in trackers]
    if missing:
        sys.exit(f"_src/games/{slug}.json: missing fields {missing}")
    if unknown:
        sys.exit(f"_src/games/{slug}.json: ad networks not in _src/ad_networks.json {unknown}")
    if unknown_trackers:
        sys.exit(f"_src/games/{slug}.json: attribution services not in _src/attribution.json {unknown_trackers}")
    if not (SITE / slug / "icon.png").exists():
        sys.exit(f"{slug}/icon.png is missing")
    values = {f: html.escape(card[f]) for f in CARD_FIELDS if isinstance(card[f], str)}
    day = date.fromisoformat(card["policy_date"])
    ads = card["ad_networks"]
    # The services that find out which ad campaign brought a player: one row each in the table of recipients.
    used = card["attribution"]
    values.update(
        slug=slug,
        tagline=values["kind"][0].upper() + values["kind"][1:] + " for " + values["platforms"],
        policy_date=f"{MONTHS[day.month - 1]} {day.day}, {day.year}",
        publisher=html.escape(studio["publisher"]),
        email=html.escape(studio["email"]),
        ad_networks_text=html.escape(and_list(ads)),
        ad_networks_list=html.escape(", ".join(ads)),
        ad_networks_links=", ".join(
            f'<a href="{html.escape(networks[n]["policy"])}">{html.escape(networks[n]["link"])}</a>'
            for n in ads),
        attribution_rows="\n".join(
            f'  <tr><td>{html.escape(t)} ({html.escape(trackers[t]["company"])})</td>'
            f'<td>Finding out which ad campaign brought a player, fraud prevention</td>'
            f'<td><a href="{html.escape(trackers[t]["policy"])}">{html.escape(trackers[t]["link"])}</a></td></tr>'
            for t in used),
        attribution_text=html.escape(", ".join(used)),
    )
    return values


def build():
    studio = load(SRC / "studio.json")
    networks = load(SRC / "ad_networks.json")
    trackers = load(SRC / "attribution.json")
    games = [game_values(card.stem, load(card), studio, networks, trackers)
             for card in sorted((SRC / "games").glob("*.json"))]
    pages = {}
    for game in games:
        pages[f"{game['slug']}/index.html"] = template("game.html").substitute(game)
        pages[f"{game['slug']}/privacy.html"] = template("privacy.html").substitute(game)
    pages["index.html"] = template("home.html").substitute(
        publisher=html.escape(studio["publisher"]),
        email=html.escape(studio["email"]),
        games="\n".join(template("home_game.html").substitute(game) for game in games),
    )
    return pages


def text_only(page):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", page))


def date_kept(old, new):
    """The policy now reads differently, but its effective date stayed the same."""
    old_date, new_date = EFFECTIVE.search(old), EFFECTIVE.search(new)
    return (old_date and new_date and old_date.group() == new_date.group()
            and text_only(old) != text_only(new))


def main():
    check = sys.argv[1:] == ["--check"]
    changed = []
    for name, page in build().items():
        path = SITE / name
        old = path.read_text(encoding="utf-8") if path.exists() else None
        if old == page:
            continue
        changed.append(name)
        if check:
            continue
        if old and name.endswith("privacy.html") and date_kept(old, page):
            print(f"warning: {name}: the policy text changed but its date did not; "
                  f"if the change matters to players, update policy_date in the card")
        path.parent.mkdir(exist_ok=True)
        path.write_text(page, encoding="utf-8")
        print("built", name)
    if check and changed:
        sys.exit("out of date, run python3 _src/build.py: " + ", ".join(changed))
    if not changed:
        print("all pages match _src/")


if __name__ == "__main__":
    main()
