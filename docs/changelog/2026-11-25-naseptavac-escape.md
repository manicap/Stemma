# Našeptávač po Escape

- **Datum:** 2026-11-25
- **Úloha:** [GitHub issue #2](https://github.com/manicap/Stemma/issues/2)
- **PR:** Bude doplněno při založení pull requestu.

## Co se změnilo

Po zavření našeptávače osob klávesou Escape zůstane seznam návrhů skrytý i po průběžném načtení výsledků nebo výměně části stránky po uložení detailu. Další psaní do vyhledávacího pole návrhy opět zobrazí.

## Proč

Výměna obsahu přes HTMX dosud vytvořila nový viditelný seznam a tím zrušila uživatelovo zavření našeptávače.

## Jak to vyzkoušet

1. V části Osoby napište do vyhledávání jméno, stiskněte Escape a ověřte, že návrhy zmizí.
2. Nechte doběhnout vyhledání nebo uložte detail; návrhy zůstanou skryté. Začněte znovu psát a ověřte jejich návrat.
3. Pro prohlížečovou regresní kontrolu spusťte izolovaný lokální server s testovacími osobami `Synthetic` a `SwarmPublic`, potom `STEMMA_TEST_URL=http://127.0.0.1:18761 .venv/bin/python people/browser_test_search_delay.py`. Vyžaduje lokálně nainstalovaný Playwright a Chromium; nejsou součástí závislostí projektu.
