# Architektonické principy

**Dokument:** 08  
**Verze:** 0.2  
**Stav:** platné pracovní principy  
**Datum vytvoření:** 14. 7. 2026

## 1. Jedna informace existuje pouze jednou

Stejný fakt, dokument, zdroj nebo vztah se nemá ukládat duplicitně.

Příklady:

- jeden sňatek je jedna událost propojená s oběma osobami,
- jedna vazba se ukládá jednou a zobrazuje se obousměrně,
- jeden dokument může dokládat více záznamů,
- jedno hrobové místo může patřit více osobám.

## 2. Uživatel zadává fakta, aplikace odvozuje informace

Uživatel zadává základní údaje.

Aplikace automaticky odvozuje:

- věk,
- stav žijící/zemřelý,
- věk při úmrtí,
- římské číslice,
- opačné vazby,
- chronologické řazení.

## 3. Automatizovat vše, co není nutné zadávat ručně

Ruční zadávání odvozených hodnot vede k chybám a nekonzistenci.

## 4. Strukturovaná data mají přednost před volným textem

Pokud lze údaj uložit strukturovaně, nemá zůstat pouze v poznámce.

Příklad:

- bydliště se uloží jako záznam bydliště,
- vztah se uloží jako vazba,
- očkování se uloží jako zdravotní záznam nebo událost.

## 5. Objekty mají být znovu použitelné

Fotografie, dokumenty, zdroje, místa a hrobová místa mohou být propojeny s více objekty.

## 6. Neúplnost se nesmí maskovat falešnou přesností

Neznámé datum se nenahrazuje hodnotou typu 1. 1. daného roku.

Systém musí umět rozlišit:

- přesné datum,
- pouze rok,
- měsíc a rok,
- přibližné datum,
- datum před nebo po určitém okamžiku,
- rozmezí,
- neznámý údaj.

## 7. Historie se zachovává

Důležité změny musí být dohledatelné.

Mazání se nahrazuje archivací nebo měkkým odstraněním.

## 8. Bezpečnost a soukromí jsou součást návrhu

Citlivé údaje nejsou dodatečný doplněk.

Zdravotní informace a údaje žijících osob mají přísnější výchozí ochranu.

## 9. Jednoduché pro uživatele, bohaté na data

Rozhraní má působit jednoduše, i když pod ním stojí flexibilní datový model.

## 10. Rozšiřitelnost bez zbytečné složitosti

Systém má umožnit budoucí rozšíření, ale nesmí se předem zatěžovat funkcemi bez reálného využití.

Příklad: štítky byly z návrhu odstraněny jako zbytečné.

## 11. Návrh má přednost před implementací

Nová významná funkce se nejprve navrhne, prodiskutuje, schválí a zapíše do dokumentace.

## 12. Dokumentace je součást produktu

Dokumentace není vedlejší výstup.

Musí být dostatečně přesná, aby podle ní mohl aplikaci implementovat jiný vývojář nebo jiný AI systém.

## 13. Jednodušší řešení má přednost

Pokud dvě řešení splňují stejné požadavky, preferuje se jednodušší, srozumitelnější a lépe udržovatelné řešení.

## 14. Každé významné rozhodnutí musí mít důvod

U důležitých architektonických rozhodnutí má být zaznamenáno:

- co bylo rozhodnuto,
- proč,
- jaké byly důsledky,
- případně jaké alternativy byly odmítnuty.

## 15. Projekt musí být pochopitelný i za pět let

Po delší přestávce musí být možné pochopit stav projektu pouze z aktuální dokumentace a historie změn.


## 16. Lehký klient a serverově renderované rozhraní

- server vrací hotové HTML,
- HTMX načítá pouze měněné fragmenty,
- nepoužívá se SPA,
- velký javascriptový framework se nepřidává bez prokazatelné potřeby,
- média se načítají v optimalizovaných velikostech,
- neaktivní záložky se nenačítají předem.

## 17. Jeden hlavní jazyk projektu

Python je hlavním jazykem webové aplikace i podpůrných nástrojů, zejména pro importy, exporty, opravy dat, automatizaci a budoucí zpracování dokumentů.
