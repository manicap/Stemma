# Agent v Cezaru šetří kroky

- **Datum:** 2026-11-25
- **Úloha:** po první úloze (issue #2), která spotřebovala zhruba polovinu měsíčního limitu Codexu
- **PR:** viz PR této větve

## Co se změnilo
Zadání agenta ve workflow `slice` má tři nová pravidla: nespouštět celou sadu testů (spustí ji workflow), nečíst velké soubory celé a soubory či commity k převzetí brát přes git místo ručního přepisování.

## Proč
První úloha potřebovala 40 volání modelu a při každém se znovu posílá celý kontext (1,8 mil. tokenů, z toho 1,72 mil. opakovaně). Méně kroků znamená výrazně menší spotřebu.

## Jak to vyzkoušet
1. Spustit další úlohu ve workflow `slice`.
2. Porovnat počet volání modelu a tokeny podle postupu v Multipoolu (`docs/mereni.md`).
