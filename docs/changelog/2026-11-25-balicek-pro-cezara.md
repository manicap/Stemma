# Příprava Stemmy pro práci přes Cezara

- **Datum:** 2026-11-25
- **Úloha:** návrh Multipoolu, krok 1 (https://github.com/manicap/multipool)

## Co se změnilo
Pro uživatele aplikace se nic nemění. Mění se způsob, jakým na Stemmě pracuje AI agent:
- `AGENTS.md` je zkrácený z 25 kB na zhruba 5 kB. Agent už nemá před každou změnou číst osm velkých dokumentů.
- Pravidla projektu jsou zhuštěná do skillu `.ai/skills/stemma-context/SKILL.md` (do 20 kB), který Cezar předá agentovi.
- Nový workflow `.ai/cezar/workflows/slice.yaml`: jeden agent, pak testy, Django kontroly, limit velikosti změny a kontrola changelogu. Žádné role Lead, QA ani Security.
- Výchozí agent v Cezaru je Codex (`.ai/cezar/config.json`), úlohy vycházejí z větve `agent/rc-0.2`.
- Nová složka `docs/changelog/` s jedním lidským záznamem na každý krok.

## Proč
Předchozí pokus se swarmem spotřeboval kolem 780 tisíc tokenů a vyrobil 163 řádků. Hlavní příčiny: čtení celé dokumentace a víc LLM rolí, které si předávaly práci.

## Jak to vyzkoušet
1. V Cezaru otevři projekt Stemma, záložka Workflows: má být vidět `slice`.
2. Spusť malou úlohu s workflow `slice` a zkontroluj, že na konci přibyl záznam v `docs/changelog/`.

## Na co si dát pozor
Původní dlouhý `AGENTS.md` je v historii gitu. Pravidla ACP-006 a ACP-009 v `docs/12_ARCHITEKTONICKA_ROZHODNUTI.md` zůstávají beze změny; skill z nich vychází.
