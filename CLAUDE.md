# CLAUDE.md – Stemma

Rodinný informační systém: Django 5.2 LTS, Python 3.14, SQLite, serverové
šablony + HTMX, bez SPA. Komunikuj česky, stručně a věcně. Uživatelské texty
v aplikaci jsou česky, uložené systémové hodnoty anglicky.

## Větve

- Aktivní vývoj: **`agent/rc-0.2-dev`**. Commituj a pushuj sem.
- `agent/rc-0.2` (pozastavená práce na Cezarovi/swarmu), `agent/rc-0.1`,
  `feature/mvp`, `backup/pre-agent-2026-08-17`: neměnit.
- Do `main` ani `feature/mvp` nic nemergovat bez výslovného souhlasu.
- Žádný force-push, přepis historie, `git add .` ani mazání větví.
- Necommituj `config/settings_local.py`, `db.sqlite3` ani lokální launchery
  `start_stemma_test.*` a `stemma_local_test_launcher*`.

## Způsob práce

- Malé vertikální řezy dotažené do konce: kód, testy, dokumentace, commit,
  push. Jeden řez = jeden commit.
- Když je cíl implementace, výsledkem je změněný a otestovaný kód, ne plán.
- Nepřidávej neschválené analýzy, audity ani přestavby procesu.
- Čti jen dokumenty relevantní pro daný řez (tabulka níže). Celá `docs/` má
  ~690 kB, neprocházej ji celou.
- Nový funkční řez vyžaduje schválení uživatelem. Změnu ACP, architektury,
  významu systémových hodnot nebo přístupové policy nejdřív navrhni ke
  schválení.

## Architektura (závazné)

- Každý fakt se ukládá jen jednou. Narození a úmrtí jsou události.
- Odvozené údaje (věk, stav, římské číslování) se neukládají. Neúplné datum
  se nenahrazuje falešně přesným.
- Zápisy jen přes doménové služby (`services.py`) v `transaction.atomic()`;
  actor-aware hranice zápisu v `use_cases.py`. Čtení přes actor-aware
  selectory. Views jen koordinují HTTP, formuláře a služby.
- Oprávnění se vynucují na serveru. Skrytý nebo nedostupný objekt selže
  jednotně (404) bez úniku údajů.
- Přílohy a zdroje mají explicitní spojovací modely, žádné generic relations.
- Pevné hodnoty `TextChoices`, rozšiřitelné slovníky lookup modely.
- Nová oprávnění pro skupinu přes datovou migraci v `accounts/migrations/`
  a synchronizace `bootstrap_demo_accounts`.
- Vzor posledních řezů: `events/use_cases.py` (narození a úmrtí) a
  `people/use_cases.py` (vztahy rodič, dítě, partner).
- Při změně `people/static/people/stemma.js` nebo `stemma.css` vždy zvyš `?v=`
  u obou souborů v `common/templates/common/base.html`.

## Příkazy

```
python manage.py test --parallel 4               # plná sada (~1 700 testů)
python manage.py test people.test_relationship_write_web   # cílený test
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py seed_demo_data
python manage.py bootstrap_demo_accounts         # demo Čtenář/Editor/Správce
python manage.py runserver
```

Během práce spouštěj cílené testy, plnou sadu jednou nad hotovým diffem.
`check` a kontrolu migrací spusť při změně modelů, migrací, URL nebo nastavení.

## Dokumentace podle oblasti

| Oblast | Dokument |
| --- | --- |
| Aktuální stav, index | `docs/00_README.md` (sekce „Aktuální fáze projektu“) |
| Funkce a jejich stav | `docs/02_FUNKCNI_SPECIFIKACE.md` (jen dotčená kapitola) |
| Modely | `docs/03_DATOVY_MODEL.md`, `docs/11_DATABAZOVY_NAVRH.md` |
| Role a oprávnění | `docs/04_UZIVATELSKE_ROLE_A_PRAVA.md` |
| Pravidla dokumentace | `docs/05_PRAVIDLA_DOKUMENTACE.md` |
| Rozhodnutí | `docs/06_ROZHODNUTI_A_OTEVRENE_OTAZKY.md` |
| Roadmapa | `docs/07_ROADMAPA.md` |
| UI/UX | `docs/10_UI_UX_NAVRH.md` |
| ACP | `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md` |

Po dokončení řezu aktualizuj dotčené dokumenty (verze a datum revize v
hlavičce), `docs/CHANGELOG.md` a případně stav v `docs/00_README.md` a
`docs/07_ROADMAPA.md`.

`AGENTS.md` obsahuje podrobná procesní pravidla pro autonomní agenty
(eskalace, invalidační brána, review role). Čti ho jen při nejasnosti.
