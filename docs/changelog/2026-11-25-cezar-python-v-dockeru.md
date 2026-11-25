# Cezar najde Python 3.14 uvnitř svého kontejneru

- **Datum:** 2026-11-25
- **Úloha:** první běh issue #2 v Cezaru (krok setup selhával)
- **PR:** viz PR této větve

## Co se změnilo
Přípravný krok workflow `slice` teď nejdřív hledá Python 3.14, který je zabudovaný v image Cezaru (`/opt/stemma-python`). Systémový Python použije, jen pokud umí vytvořit virtuální prostředí.

## Proč
Cezar na FUNBOXu běží v Dockeru. V kontejneru je systémový `python3` ve verzi 3.11 bez modulu `ensurepip`, takže `.venv` nešlo vytvořit a úloha spadla hned na začátku.

## Jak to vyzkoušet
1. Na FUNBOXu stáhnout `agent/rc-0.2` do `/opt/stacks/cezar-workspaces/Stemma`.
2. V Cezaru znovu spustit úlohu z issue #2 (workflow `slice`).
3. V kroku „Příprava prostředí“ má být `[setup] python: /opt/stemma-python/bin/python3.14` a na konci `[setup] hotovo`.
