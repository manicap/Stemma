# Roadmapa projektu

**Dokument:** 07  
**Verze:** 0.10
**Stav:** realizace MVP + experimentální RC 0.1
**Datum revize:** 17. 8. 2026

## Fáze 1 – Konsolidace návrhu ✅

- uzavřen funkční a základní datový model,
- uzavřeny hlavní entity a architektonické principy.

## Fáze 2 – Návrh UI/UX ✅

- uzavřen schválený pracovní základ hlavního rozhraní,
- definovány světlý a tmavý motiv,
- definována responzivita, editace a ochrana neuložených změn.

## Fáze 3 – Databázový a technický návrh ✅

### Dokončené výstupy

- katalog entit a jejich odpovědností,
- přesný katalog polí,
- kardinality a povinné vazby,
- společný model neúplného data,
- pravidla integrity a unikátnosti,
- pravidla archivace a měkkého odstranění,
- přílohy a zdroje s explicitními vazbami,
- ochrana zdravotních údajů,
- návrh auditního modelu,
- návrh indexů,
- ER diagram,
- struktura Django aplikací,
- rozdělení validace mezi databázi, modely a služby,
- návrh pořadí migrací,
- architektonická revize.

### Implementační milníky

#### M0 – založení Django projektu ✅

- potvrzen Python 3.14 a Django 5.2 LTS,
- založeno reprodukovatelné prostředí `venv` + `pip`,
- založen Django projekt s balíčkem `config`,
- vytvořena aplikace `accounts`,
- vytvořen vlastní model `accounts.User` a migrace `accounts.0001_initial`,
- doplněna registrace v Django Adminu a základní testy,
- nastavena SQLite, čeština, časové pásmo `Europe/Prague` a lokální tajná konfigurace mimo Git,
- změny commitnuty a pushnuty do `feature/mvp`.

#### M1 – společný základ ✅

- založena a registrována aplikace `common`,
- vytvořeny pevné výčty pro pohlaví, přístup, ověření a neúplná data,
- vytvořeno sedm abstraktních modelů společných polí a číselníků,
- doplněna validace neúplných a nejistých dat,
- doplněn výpočet technických mezí `sort_date` a `sort_date_end`,
- doplněny testy; M1 nevytváří vlastní databázovou tabulku ani migraci,
- změny implementovány a ověřeny ve větvi `feature/mvp`.

#### M2 – jádro Osoba, Místo, Událost a Vazba ◀ aktuální v původní implementační posloupnosti

1. založit doménové aplikace potřebné pro jádro,
2. implementovat základní číselníky a model Osoba,
3. implementovat Místo,
4. implementovat Událost a účastníky události,
5. implementovat Vazbu mezi osobami,
6. vytvářet malé strukturální a datové migrace,
7. doplňovat testy databázové integrity a doménových pravidel.

#### Následující implementační kroky původní posloupnosti

1. dokončit M2 – jádro Osoba, Místo, Událost a Vazba,
2. doplnit bydliště a hrobová místa,
3. doplnit přílohy, zdroje a jejich propojení,
4. doplnit zdravotní záznamy,
5. doplnit audit a projektová oprávnění,
6. rozšiřovat testy databázové integrity,
7. připravit vývojová ukázková data.

## Experimentální cílový průřez – RC 0.1 ◀ aktivní na `agent/rc-0.1`

RC 0.1 je pracovní označení prvního skutečně použitelného kandidáta aplikace. Neznamená dokončení celé roadmapy ani schválení produkčního nasazení. Jeho účelem je co nejdříve ověřit jeden úplný uživatelský průchod od databáze přes oprávnění až po skutečné UI.

Na experimentální větvi `agent/rc-0.1` smí hlavní agent podle ACP-006 volit nejmenší bezpečné vertikální řezy přes více níže uvedených fází, pokud zachová schválené závislosti, datový model, oprávnění a UI/UX principy. Stav původních milníků se tím nemění, dokud nejsou jejich vlastní podmínky skutečně splněny.

### RC 0.1 – povinná acceptance kritéria

RC 0.1 lze označit za dokončené pouze tehdy, když jsou splněny **všechny** následující oblasti a stav je ověřen automatickými testy i skutečným uživatelským průchodem v prohlížeči.

#### A. Reprodukovatelné spuštění

- čistý checkout lze zprovoznit podle aktuální dokumentace bez znalosti historie chatu,
- instalace závislostí, migrace a běžné spuštění vývojového serveru mají jednoznačný postup,
- projekt nevyžaduje commitnutá tajemství ani lokální databázi,
- existuje jednoduchý dokumentovaný způsob vytvoření nebo načtení bezpečných ukázkových dat pro ověření UI.

#### B. Skutečný seznam osob

- hlavní obrazovka čte skutečné osoby z databáze, nikoli mocky nebo pevně zapsaná demonstrační data v šabloně,
- seznam vrací pouze osoby viditelné pro aktuálního actora podle existujících pravidel přístupové úrovně a lifecycle,
- výběr osoby otevře její skutečný detail,
- prázdný seznam a neexistující výsledek mají použitelné uživatelské sdělení.

#### C. Skutečný detail osoby

- detail pracuje se skutečným modelem `Person` a schválenými odvozenými údaji,
- minimálně zobrazuje dostupné základní identifikační údaje osoby a respektuje schválený návrh záhlaví a rozvržení,
- neexistující a neviditelná osoba jsou bezpečně zpracovány bez úniku chráněných údajů,
- přímé zadání URL nesmí obejít autorizaci, kterou uplatňuje seznam nebo UI.

#### D. Přihlášení a role v uživatelském průchodu

- funguje přihlášení a odhlášení,
- lze prakticky ověřit alespoň anonymního návštěvníka, přihlášeného čtenáře a editora,
- UI zobrazuje akce podle oprávnění, ale skutečné vynucení práv probíhá vždy na serveru,
- neaktivní uživatel, `is_staff`, superuser a zvýšená obsahová oprávnění zachovávají již zdokumentovanou centrální policy.

#### E. Jednoduchá editace osoby

- oprávněný editor může z detailu otevřít formulář pro základní údaje entity `Person`,
- formulář vychází z existujícího modelu a schválených pravidel; nevytváří pole narození, úmrtí ani jiné údaje, které patří do samostatných událostí nebo entit,
- změna probíhá přes servisní/doménovou hranici odpovídající architektuře projektu, nikoli přímým nekontrolovaným zápisem ve view,
- validace je serverová a chybové stavy se zobrazí uživateli,
- po úspěšném uložení se změna skutečně zapíše do databáze a projeví v aktuálním UI bez nutnosti ručního obnovení celé stránky tam, kde je podle schváleného návrhu vhodné HTMX.

#### F. Bezpečnostní a autorizační brána

Musí existovat cílené automatické testy a nezávislý security review alespoň pro relevantní kombinace:

- anonymní návštěvník,
- aktivní běžný autentizovaný uživatel,
- editor,
- neaktivní uživatel,
- `is_staff` bez obsahových oprávnění,
- aktivní superuser,
- objekt s `public`, `authenticated`, `restricted` a `admin_only` přístupem,
- archivovaná a měkce odstraněná osoba tam, kde se jejich lifecycle vztahuje k danému průchodu,
- pokus o přímé otevření nebo změnu chráněného objektu přes URL nebo ručně sestavený HTTP požadavek.

RC nesmí oslabit existující selector, service ani permission kontrakty jen proto, aby UI prošlo testy.

#### G. Použitelné skutečné UI

- hlavní obrazovka odpovídá základnímu dvousloupcovému konceptu na desktopu,
- mobilní zobrazení je funkčně použitelné bez nutnosti zoomu a bez funkcí dostupných pouze hoverem,
- základní vizuální systém vychází ze schváleného UI/UX návrhu,
- světlý i tmavý motiv jsou alespoň funkčně použitelné; RC nevyžaduje finální kosmetické vyladění,
- běžné loading, empty, validation a permission stavy nejsou nahrazeny debug výstupem nebo Django Adminem,
- výsledný průchod musí být ověřen v reálném browseru, nikoli pouze testovacím klientem.

#### H. Kontrolní brána projektu

Před označením RC 0.1 za hotové musí projít minimálně:

```text
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Dále musí být ověřeno:

- cílené testy nového uživatelského průchodu,
- nezávislý QA review,
- nezávislý security/access-control review,
- UI/UX review v prohlížeči pro desktop a mobilní šířku,
- konzistence implementace s aktuální dokumentací,
- čistý diff bez tajemství, lokální databáze, cache a nesouvisejících změn.

### RC 0.1 – co do cíle záměrně nepatří

Pokud následující funkce nejsou nutné jako závislost výše uvedeného průchodu, jejich dokončení **není podmínkou RC 0.1**:

- kompletní UI všech událostí,
- kompletní editace vztahů,
- kompletní UI bydlišť a hrobových míst,
- materiály, fotografie a zdroje v plném rozsahu,
- zdravotní UI,
- PDF export osoby,
- samostatný rodokmen,
- kompletní časová osa,
- pokročilé vyhledávání a všechny filtry,
- finální auditní UI,
- kompletní archivace a obnova přes UI,
- finální vizuální polish a všechny budoucí možnosti personalizace.

Existující backendové funkce z těchto oblastí se nesmějí odstranit, obejít nebo účelově oslabit. Agent má používat a zachovávat již implementované části a regresní testy.

### Aktuální ověřený stav RC 0.1

Oblast A má implementovaný reprodukovatelný lokální postup:

- dokumentace vede čistý checkout od Python 3.14 přes izolovaný `venv`,
  instalaci jediného deklarovaného balíčku, lokální tajný klíč a migrace až
  ke spuštění serveru,
- lokální konfigurace, databáze a launcher artefakty zůstávají mimo Git,
- lokálně omezený `seed_demo_data` vytvoří syntetické osoby pro tři
  přístupové úrovně, při zachování markerů je idempotentní, podporuje
  `--dry-run`, nic nemaže ani nepřepisuje a neobsahuje demo hesla nebo jiná
  tajemství; při `DEBUG=False` selže bez zápisu.
- izolovaný Windows clean-snapshot smoke test prošel vytvořením nového
  Python 3.14 `venv`, instalací z `requirements.txt`, všemi migracemi,
  dry-runem, prvním i opakovaným seedem, `manage.py check` a HTTP 200 ze
  skutečně spuštěného vývojového serveru; POSIX varianta byla zkontrolována
  staticky proti stejným projektovým vstupům.

Oblast A je tím pro RC 0.1 splněna. Její regresní brána zůstává součástí
závěrečného ověření celého kandidáta.

Oblast D má implementovaný autentizační a rolový základ:

- funguje standardní session login, bezpečný lokální návrat a CSRF chráněný
  POST logout; neaktivní účet se nepřihlásí,
- topbar rozlišuje anonymní a přihlášený stav a po změně session se seznam
  přepočítá podle aktuální centrální access policy,
- Čtenář zůstává bez editace, Editor a Správce dostávají konkrétní
  `people.change_person`; `is_staff`, superuser a zvýšená obsahová permission
  zachovávají samostatný dokumentovaný význam,
- cílené testy pokrývají anonymního uživatele, neplatný i neaktivní login,
  bezpečný `next`, logout/CSRF a praktický obsahový rozdíl rolí.

Oblast D zůstává jako celek otevřená do propojení editační akce v E a
skutečného browser průchodu login–edit–logout.

První vertikální řez B+C+G je rozpracován a zatím neuzavírá celé oblasti:

- hlavní URL čte skutečné, pro actora viditelné osoby z databáze,
- výchozí seznam i detail bezpečně vylučují archivované a měkce odstraněné
  osoby a jednotně skrývají existenci neviditelného přímého cíle,
- detail se načítá jako plná stránka i HTMX fragment a používá lokálně
  verzovaný HTMX asset,
- existuje dvousloupcový desktopový základ, mobilní vysouvací seznam,
  světlý a tmavý motiv a použitelné empty, loading a 404 stavy,
- desktopový i mobilní list/detail průchod včetně opakované HTMX výměny,
  výběru osoby, motivu a mobilního zavření panelu prošel reálným browserem,
- Person a navazující jména a vztahy v Django Adminu respektují stejnou
  čtecí policy a jsou do zavedení doménové editační služby pouze pro čtení,
- cílené automatické testy pokrývají access matice, čerstvý stav actora,
  lifecycle, přímou URL, HTMX a admin bypass.

Oblasti B, C a G zůstávají nesplněné jako celek, dokud detail nedoplní
schválené odvozené údaje a nejsou splněny i související login a editační
části D a E včetně úplného browser ověření výsledného RC průchodu.

## Fáze 4 – Interaktivní prototyp

- layout nad skutečnými Django views a šablonami,
- ukázkový seznam osob,
- přepínání detailu pomocí HTMX,
- základní záložky,
- ukázkové formuláře,
- test použitelnosti.

## Fáze 5 – MVP

- přihlášení,
- osoby,
- narození a úmrtí,
- základní vazby,
- fotografie,
- vyhledávání,
- historie změn,
- základní oprávnění.

## Fáze 6 – První použitelná verze

- všechny běžné události,
- bydliště,
- dokumenty a přílohy,
- zdravotní záznamy,
- hrobová místa,
- zdroje,
- rodokmen,
- časová osa,
- záloha a export.

## Fáze 7 – Testování v rodině

- ověření s méně technickými uživateli,
- kontrola formulářů,
- kontrola čitelnosti,
- kontrola oprávnění,
- kontrola zálohování,
- úpravy podle používání.

## Fáze 8 – Budoucí rozšíření

- import/export GEDCOM,
- mapa míst,
- pokročilý rodokmen,
- návrhy duplicit,
- veřejné sdílení vybraných částí,
- pokročilé vyhledávání,
- univerzální model tvrzení,
- automatizované zpracování dokumentů.
