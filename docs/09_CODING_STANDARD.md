# Coding standard

**Dokument:** 09  
**Verze:** 0.3  
**Stav:** platná pravidla pro začátek implementace  
**Datum revize:** 15. 7. 2026

## 1. Účel

Pravidla implementace projektu Stemma pro vývojáře, Codex a další AI nástroje.

## 2. Potvrzený technologický základ

- Python
- Django
- Django templates
- HTMX
- SQLite
- minimum vlastního JavaScriptu
- Git a GitHub

Přesné podporované verze Pythonu a Djanga budou potvrzeny před založením projektu.

## 3. Struktura Django aplikací

```text
accounts/      uživatelé a oprávnění
common/        výčty, abstraktní modely, validace a pomocné funkce
people/        osoby, jména, kategorie a vazby
places/        místa, bydliště a hrobová místa
events/        události a účastníci
materials/     přílohy, zdroje a propojení
health/        zdravotní záznamy
audit/         historie změn
```

Obchodní logika se nesmí přesouvat do šablon.

## 4. Základní pravidla kódu

- Řídit se PEP 8.
- Preferovat čitelný, explicitní a typově anotovaný kód.
- Nepřidávat závislost bez jasného přínosu.
- Nepoužívat SPA ani velký frontendový framework bez schváleného ACP.
- Vlastní JavaScript omezit na nezbytné minimum.
- Citlivé údaje nevkládat do logů, chybových zpráv ani analytiky.
- Novou funkci doprovodit testy.
- Codex nesmí bez schválení měnit architekturu ani systémové významy číselníků.

## 5. Modely a databáze

- Každý model musí mít stručně popsanou odpovědnost.
- Společná pole používat prostřednictvím abstraktních modelů.
- Pevné bezpečnostní a validační hodnoty používat jako `TextChoices`.
- Uživatelsky rozšiřitelné typy používat jako číselníkové modely.
- Obchodní integritu prosazovat co nejblíže databázi, pokud je pravidlo lokální a přenositelné.
- Složitá pravidla přes více objektů řešit v doménových službách.
- Nepoužívat generické vztahy pro přílohy a zdroje; používat explicitní spojovací modely.
- Odvozené hodnoty neukládat, pokud nemají schválený technický nebo výkonový důvod.
- Technická řadicí hodnota neúplného data je povolená, protože podporuje indexy a řazení.
- SQLite specifické řešení nesmí bezdůvodně blokovat PostgreSQL.

## 6. Validace

### Databázová omezení

Používat pro:

- povinné hodnoty,
- cizí klíče,
- unikátní kódy,
- jednoduché kontroly hodnot,
- přesné aktivní duplicity,
- zákaz vazby osoby sama na sebe.

### Modelová validace

Používat pro pravidla jednoho objektu, například:

- jméno nebo příjmení osoby,
- strukturu neúplného data,
- souřadnice,
- lokalizační údaj bydliště,
- vhodnost hlavní fotografie.

Metoda `save()` se nesmí považovat za jedinou validační vrstvu. Běžné `save()` automaticky nevolá `full_clean()`.

### Doménové služby

Používat pro operace přes více modelů, například:

- vytvoření události a jejích účastníků,
- sňatek,
- narození a úmrtí,
- rodičovské cykly,
- hlavní fotografii,
- archivaci a obnovu,
- připojení příloh a zdrojů,
- audit.

Významná operace musí proběhnout v `transaction.atomic()`.

## 7. Služby a selektory

Zápisová obchodní logika patří do `services.py` nebo balíčku `services/`.

Čtecí dotazy patří do `selectors.py`, zejména pokud obsahují:

- kontrolu viditelnosti,
- filtrování měkce odstraněných záznamů,
- `select_related()`,
- `prefetch_related()`,
- anotace a agregace.

Views mají koordinovat HTTP požadavek, formulář, službu a odpověď; nemají obsahovat rozsáhlou obchodní logiku.

## 8. Archivace a měkké odstranění

- Hlavní entity rozlišují archivaci a měkké odstranění.
- Měkce odstraněné záznamy se nepoužívají v aktivních výpočtech.
- Číselníky se běžně nemažou; deaktivují se.
- Fyzické odstranění je pouze správní a výjimečná operace.
- Odstranění spojovacího záznamu nesmí odstranit samotnou přílohu, zdroj ani cílový objekt.

## 9. Přílohy a soubory

- Fyzické soubory ukládat přes Django Storage API.
- Databáze ukládá interní klíč úložiště, nikoli veřejnou absolutní cestu jako zdroj pravdy.
- MIME typ se nesmí určovat pouze podle přípony.
- Po nahrání vypočítat SHA-256.
- Přímý odkaz na soubor nesmí obejít oprávnění.
- Nahrazení fyzického souboru je auditovaná operace.

## 10. Oprávnění a bezpečnost

- Používat Django Groups a Permissions.
- Kontrola oprávnění musí být na serveru, nikoli pouze skrytím tlačítka v UI.
- Zdravotní údaje a jejich přílohy vyžadují zvláštní oprávnění.
- Výsledný přístup se řídí nejpřísnějším omezením souvisejících objektů.
- Hesla, tokeny a autentizační tajemství se nikdy neauditují ani nelogují.

## 11. Audit

- Hlavní audit se zapisuje explicitně v doménové službě.
- Signály nemají být jediným mechanismem auditu.
- Jedna uživatelská operace má vytvořit jeden hlavní auditní záznam a více změn polí.
- Audit citlivého objektu nesmí být dostupnější než objekt samotný.
- Obsah souborů se do auditu nekopíruje.

## 12. Migrace

- Migrace musí být malé a srozumitelné.
- Strukturální a datové migrace oddělovat, pokud to zlepšuje čitelnost a vratnost.
- Základní systémové číselníky naplnit datovými migracemi.
- Migrace po začlenění do sdílené větve nepřepisovat; opravu řešit novou migrací.
- Před každou migrací zkontrolovat dopad na SQLite i případný PostgreSQL.

## 13. Testy databázové integrity

Minimálně testovat:

- osobu bez jména a příjmení,
- neúplná data a jejich řazení,
- jednu aktivní událost narození a úmrtí,
- počty povinných rolí události,
- symetrické a směrové vazby,
- rodičovské cykly,
- jednu hlavní fotografii,
- měkké odstranění a obnovu,
- ochranu zdravotních údajů,
- audit významných operací,
- fyzické soubory a kontrolní součty.

## 14. HTMX a šablony

- Server vrací úplné HTML nebo HTML fragmenty.
- HTMX endpoint musí vracet konzistentní fragment a správný HTTP stav.
- Validace formuláře se zobrazuje u pole i v místě práce uživatele.
- Šablona nesmí rozhodovat o obchodní integritě.
- Akce bez oprávnění se nemají pouze skrýt; server je musí také odmítnout.

## 15. Git a code review

- Jeden commit má představovat jednu srozumitelnou změnu.
- Commit message má být stručná a věcná.
- Změna modelu musí obsahovat migraci a testy.
- Review musí kontrolovat integritu, oprávnění, dopad na migrace, N+1 dotazy a audit.
- Významná změna architektury vyžaduje před implementací schválené ACP.
