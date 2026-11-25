# Stemma

Stemma je rodinný informační systém pro dlouhodobou a bezpečnou evidenci osob,
vztahů, událostí, míst, zdravotních údajů a souvisejících materiálů.

## Stav projektu

- **Milestone:** RC 0.2
- **Aktuální řez:** person-centric zápis základních rodinných vazeb
- **Dostupné person-centric funkce:** vytvoření a základní editace osoby,
  vyhledávání, zápis základních Vztahů, narození a úmrtí, read-only Bydliště a
  Hrobová místa a A4/PDF export osoby
- **Aktuální etapa:** M3 – Materials a bezpečné soubory
- **Poslední dokončený návrhový řez:** M3.0 – Návrh Materials/File Storage
  architektury
- **Materials security základ:** Vault-aware privátní filesystem, bezpečný
  server-side upload, owner/grant privacy policy a kontextově autorizované
  otevření nebo stažení přílohy
- **Materials UI:** karta osoby bezpečně zobrazuje, otevírá, stahuje a oprávněně
  nahrává novou přílohu; obecné management UI Materials zůstává plánované

## Technologický základ

Python 3.14, Django 5.2 LTS, SQLite, server-rendered Django templates, HTMX a
minimum vlastního JavaScriptu.

## Dokumentace

Detailní projektová dokumentace a její index jsou v
[`docs/00_README.md`](docs/00_README.md). Pokračovat lze přímo na
[`roadmapu`](docs/07_ROADMAPA.md),
[`instalaci a lokální spuštění`](docs/00_README.md#reprodukovatelné-lokální-spuštění)
nebo na [`pravidla práce v repozitáři`](AGENTS.md).
