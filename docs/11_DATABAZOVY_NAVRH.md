# Databázový návrh

**Dokument:** 11  
**Verze:** 0.4
**Stav:** schválený technický návrh v implementaci
**Datum revize:** 16. 7. 2026

## 1. Účel

Dokument definuje implementovatelný databázový návrh aplikace **Stemma** pro Django a SQLite. Navazuje zejména na dokumenty `02_FUNKCNI_SPECIFIKACE.md`, `03_DATOVY_MODEL.md`, `04_UZIVATELSKE_ROLE_A_PRAVA.md`, `08_ARCHITEKTONICKE_PRINCIPY.md`, `09_CODING_STANDARD.md` a `10_UI_UX_NAVRH.md`.

Návrh prošel logickou i architektonickou revizí. Milníky M0 a M1 jsou implementovány; další etapou je vytvoření konkrétních doménových modelů, migrací, služeb a testů integrity v M2.

### 1.1 Stav implementace

- M0: projekt `config`, aplikace `accounts`, vlastní `accounts.User` a první migrace jsou dokončeny.
- M1: aplikace `common`, pět aktuálně potřebných pevných výčtů, sedm abstraktních modelů a validace neúplných dat jsou dokončeny.
- `common` nevytváří vlastní tabulku; při dokončení M1 nevznikla nová migrace.
- Aktuální implementační krok je M2: Osoba, Místo, Událost a Vazba.

## 2. Závazné principy

- Narození a úmrtí jsou události.
- Stav žijící nebo zemřelý, věk, věk při úmrtí a římská číslice se odvozují.
- Opačný směr vazby mezi osobami se neukládá.
- Sňatek je jedna sdílená událost s více účastníky.
- Stejný fakt, soubor ani zdroj se nemá ukládat duplicitně.
- Neúplné datum se nesmí nahrazovat falešným přesným datem.
- Zdravotní skutečnosti se ukládají jako zdravotní záznamy, nikoli současně jako obecné události.
- Důležité záznamy se archivují nebo odstraňují měkce.
- Zdravotní údaje mají výchozí přístupovou úroveň `omezené`.
- Databázový návrh musí fungovat v SQLite a nesmí bezdůvodně blokovat PostgreSQL.

## 3. Rozdělení Django aplikací

```text
stemma/
├── accounts/      uživatelé, skupiny a oprávnění
├── common/        výčty, abstraktní modely, normalizace a validace
├── people/        osoby, jména, kategorie a vazby
├── places/        místa, bydliště a hrobová místa
├── events/        události a účastníci
├── materials/     přílohy, zdroje a jejich propojení
├── health/        zdravotní záznamy
└── audit/         auditní historie
```

Obchodní aplikace zůstávají součástí jednoho Django projektu. Hlavní objekty nemají přímé cizí klíče zpět do `materials`; přílohy a zdroje se připojují explicitními spojovacími modely.

## 4. Společné technické vzory

### 4.1 Pevné výčty

Pevnými Django `TextChoices` budou zejména:

- pohlaví: muž, žena, neznámé,
- přístupová úroveň: veřejné, pouze přihlášení, omezené, pouze správce,
- stav ověření: ověřeno, pravděpodobné, nejisté, sporné, nepotvrzené,
- přesnost a kvalifikátor data,
- auditní operace,
- stav fyzického souboru.

Tyto hodnoty nebudou uživatelsky spravovanými číselníky, protože jsou součástí validační nebo bezpečnostní logiky. V M1 byly implementovány výčty pro pohlaví, přístupovou úroveň, stav ověření, přesnost data a kvalifikátor data. Auditní operace a stav fyzického souboru budou doplněny s příslušnými doménami.

### 4.2 Abstraktní modely

Společná pole se budou sdílet pomocí abstraktních Django modelů:

- `TimestampedModel` — vytvořeno a změněno,
- `AuthoredModel` — autor záznamu,
- `AccessControlledModel` — přístupová úroveň,
- `VerifiableModel` — stav ověření,
- `LifecycleModel` — archivace a měkké odstranění,
- `PartialDateModel` — neúplný a nejistý časový údaj,
- `LookupModel` — společný základ číselníků.

Abstraktní model nevytváří vlastní tabulku. Jeho pole se vloží do konkrétních modelů. Všechny uvedené abstraktní modely byly implementovány a otestovány v M1.

### 4.3 Archivace a měkké odstranění

Archivace a měkké odstranění mají rozdílný význam.

- Archivovaný záznam zůstává platným historickým záznamem, ale běžně se nezobrazuje.
- Měkce odstraněný záznam je považován za odstraněný a nepoužívá se pro odvozené hodnoty.

Hlavní entity budou používat pole:

- `archived_at`, `archived_by`,
- `deleted_at`, `deleted_by`,
- důvod zásahu.

Číselníky budou používat `is_active` a `is_system` místo archivace.

## 5. Jednotný model neúplného data

Stejná struktura data se použije u událostí, vazeb, bydlišť, zdravotních záznamů, dalších jmen, názvů míst, příloh, zdrojů a propojení osob s hroby.

Podporované významy:

- přesné datum,
- měsíc a rok,
- pouze rok,
- rozmezí,
- přibližně,
- před,
- po,
- zcela neznámé datum.

Logická pole:

- přesnost data,
- kvalifikátor,
- rok, měsíc a den začátku,
- rok, měsíc a den konce,
- původní text data,
- poznámka k datu,
- technické `sort_date` a `sort_date_end`.

Technická řadicí data se automaticky odvozují a nesmějí se zobrazovat jako historický fakt. Uživatel je neupravuje.

Validace hlídá správný rozsah roku a měsíce, existenci dne v konkrétním měsíci, návaznost částí data, povolené kvalifikátory, zákaz konce mimo rozmezí a zákaz konce před začátkem. Implementace v `common/partial_dates.py` používá čisté pomocné funkce a stabilní chybové kódy. Modelová metoda `clean()` validuje a nastavuje technické meze; `save()` nevolá `full_clean()` a pouze zajišťuje jejich přepočet před uložením.

## 6. Osoba a jména

### 6.1 Osoba

Osoba obsahuje pouze stabilní identitu:

- hlavní jméno,
- hlavní příjmení,
- pohlaví,
- kategorii osoby,
- tituly,
- stručnou poznámku,
- životopisný text,
- přístupovou úroveň,
- technická a auditní pole.

Musí být vyplněno alespoň jméno nebo příjmení. Jméno ani jeho kombinace nejsou unikátní.

Osoba neobsahuje přímá pole narození, úmrtí, věku, stavu žijící/zemřelý ani římské číslice.

### 6.2 Kategorie osoby

Spravovatelný číselník s výchozími hodnotami:

- Přímá rodina,
- Ostatní rodina,
- Blízcí rodině,
- Duchovní,
- Další související osoby.

Kategorie je nepovinná a nenahrazuje konkrétní vztahy.

### 6.3 Další jméno osoby

Samostatný model uchovává například:

- rodné příjmení,
- další křestní jméno,
- dřívější příjmení,
- alternativní zápis,
- přezdívku,
- jméno uvedené ve zdroji.

Každý záznam má typ, hodnotu, normalizovanou vyhledávací hodnotu, stav ověření, případnou časovou platnost a zdroje.

## 7. Místo

Místo je opakovaně použitelný geografický nebo fyzický objekt.

Obsahuje zejména:

- hlavní název,
- normalizovaný název,
- typ místa,
- volitelné nadřazené místo,
- zemi,
- popis,
- souřadnice a jejich přesnost,
- přístupovou úroveň.

Hierarchie míst nesmí obsahovat cyklus. Detailní adresní údaje se primárně ukládají u bydliště nebo události. Samostatné místo pro dům nebo budovu vznikne pouze tehdy, pokud se opakovaně používá nebo má vlastní historii a materiály.

Historické, jazykové a alternativní názvy mohou být vedeny v samostatném modelu `PlaceName`.

## 8. Události

### 8.1 Typ události

Číselník určuje význam události, podporu období, možnost místa, možnost zobrazení v přehledu a výchozí viditelnost.

Základní typy zahrnují:

- narození,
- křest,
- sňatek,
- rozvod,
- stěhování,
- studium,
- maturitu,
- vojenskou službu,
- zaměstnání,
- úmrtí,
- pohřeb,
- jinou událost.

Úraz, operace, očkování a další zdravotní skutečnosti se ukládají jako zdravotní záznamy.

### 8.2 Role účastníka a povolené role

Účast osoby na události je samostatný spojovací model.

Role mohou být například:

- narozená osoba,
- zemřelá osoba,
- křtěná osoba,
- partner v manželství,
- rodič,
- svědek,
- kmotr,
- účastník.

Model `AllowedEventRole` určuje pro každou kombinaci typu události a role minimální a maximální počet, pořadí a aktivitu.

Systémová pravidla jsou současně chráněna aplikační validací:

- narození má právě jednu narozenou osobu,
- úmrtí má právě jednu zemřelou osobu,
- sňatek má dva hlavní partnery.

### 8.3 Událost

Událost obsahuje:

- typ,
- volitelný vlastní název,
- popis,
- neúplný časový údaj,
- volitelné místo a lokalizační detail,
- stav ověření,
- přístupovou úroveň,
- příznak zobrazení v přehledu,
- účastníky,
- přílohy a zdroje.

Příčina a okolnosti úmrtí se ukládají v samostatném modelu `DeathDetail` ve vztahu jedna ku jedné k události úmrtí.

Jedna osoba smí mít nejvýše jednu aktivní účast jako narozená osoba a jednu jako zemřelá osoba.

## 9. Vazby mezi osobami

Vazba se ukládá jednou mezi osobami A a B. Typ vazby určuje:

- význam A → B,
- význam B → A,
- genderované zobrazované názvy,
- symetrii,
- časový režim,
- kategorii,
- zda lze vztah odvodit.

U symetrické vazby se dvojice ukládá v normalizovaném pořadí. U směrové vazby je pořadí významové.

Tvrdé chyby zahrnují:

- vazbu osoby sama se sebou,
- přesnou aktivní duplicitu,
- obrácenou duplicitu symetrické vazby,
- cyklus přímého rodičovství,
- konec období před začátkem.

Biologické sourozenectví se primárně odvozuje ze společných biologických rodičů. Explicitní sourozenecká vazba se používá u neznámých rodičů nebo u adoptivního, nevlastního či sociálního sourozenectví.

## 10. Bydliště a hrobová místa

### 10.1 Bydliště

Bydliště spojuje právě jednu osobu s volitelným strukturovaným místem a časovým údajem.

Obsahuje:

- typ pobytu,
- místo,
- adresní text,
- ulici a čísla domu,
- lokalizační doplněk,
- poznámku,
- stav ověření,
- přístupovou úroveň,
- přílohy a zdroje.

Musí existovat strukturované místo nebo alespoň neprázdný lokalizační text. Překrývající se pobyty jsou povoleny.

### 10.2 Hrobové místo

Hrobové místo je samostatný fyzický nebo pamětní objekt. Obsahuje například:

- typ,
- stav existující/zaniklé/přemístěné/neověřené,
- místo nebo textovou lokalitu,
- oddíl, řadu a číslo,
- přepis nápisu,
- souřadnice,
- přílohy a zdroje.

Stav `zaniklé` není archivace.

Propojení osoby s hrobovým místem je samostatný model a určuje například:

- pohřbena,
- uložena urna,
- rozptýlena,
- připomenuta nápisem,
- symbolický hrob,
- ostatky přemístěny.

Jedna osoba může mít více propojení a jedno hrobové místo může být spojeno s více osobami.

## 11. Přílohy

Příloha reprezentuje jeden fyzicky uložený digitální soubor a jeho metadata.

Obsahuje zejména:

- kategorii,
- uživatelský název a popis,
- původní název souboru,
- interní klíč úložiště,
- MIME typ a velikost,
- kontrolní součet SHA-256,
- stav souboru,
- autora nebo původce,
- původ materiálu,
- vlastníka originálu,
- jazyk,
- datum vzniku,
- technická metadata,
- přístupovou úroveň.

Soubor se ukládá pouze jednou. Připojuje se explicitními spojovacími modely k osobě, události, vazbě, bydlišti, zdravotnímu záznamu, hrobovému místu, místu a zdroji.

Spojení obsahuje:

- roli přílohy,
- popis souvislosti,
- pořadí,
- příznak hlavní přílohy.

Hlavní fotografie osoby je pouze role spojení `PersonAttachment`; na osobě není druhý přímý odkaz. Jedna osoba smí mít nejvýše jednu aktivní hlavní fotografii.

## 12. Zdroje

Zdroj popisuje původ informace, nikoli samotný digitální soubor.

Obsahuje například:

- typ zdroje,
- název a úplnou citaci,
- instituci, fond, signaturu, svazek a inventární číslo,
- autora nebo původce,
- publikační údaje,
- URL a datum přístupu,
- externí identifikátor,
- důvěryhodnost,
- přístupovou úroveň.

Zdroj se explicitně váže ke konkrétním strukturovaným záznamům, zejména k:

- dalšímu jménu osoby,
- události,
- vazbě,
- bydlišti,
- zdravotnímu záznamu,
- hrobovému místu,
- příloze.

Propojení obsahuje roli zdroje, citovanou část, krátký úryvek, výklad a sílu podpory. Zdroj může tvrzení potvrzovat, naznačovat, doplňovat nebo mu odporovat.

Univerzální systém zdrojování libovolného databázového pole není součástí první verze.

## 13. Zdravotní záznamy

Zdravotní záznam patří právě jedné osobě a má samostatný typ.

Podporované typy zahrnují:

- diagnózu,
- vyšetření,
- operaci,
- úraz,
- očkování,
- alergii,
- lék,
- hospitalizaci,
- dlouhodobý stav,
- tělesnou zvláštnost,
- jiné zdravotní informace.

Záznam obsahuje název nebo popis, časový údaj, lékaře či zařízení, volitelné místo, stav ověření, přílohy, zdroje a přístupovou úroveň.

Výchozí viditelnost je `omezené`. Zdravotní záznam se neukládá současně jako obecná událost, ale může se zobrazit v obecné časové ose.

## 14. Uživatelé a oprávnění

Použije se vlastní Django uživatelský model založený na standardních mechanismech Djanga.

Základní skupiny:

- Čtenář,
- Editor,
- Správce.

Nepřihlášený návštěvník není databázová role.

Django Groups a Permissions budou doplněny zvláštními oprávněními například pro:

- zdravotní údaje,
- omezené záznamy,
- správu přístupových úrovní,
- archivaci a obnovu,
- exporty,
- systémové číselníky,
- citlivý audit.

Volitelné propojení účtu s evidovanou osobou vznikne v samostatném profilu až po vytvoření modelu Osoba.

Výsledný přístup se posuzuje podle nejpřísnějšího omezení objektu, propojení, přílohy nebo zdroje a zvláštních oprávnění uživatele.

## 15. Audit

Audit má dvě úrovně:

- `AuditOperation` — jedna uživatelská nebo systémová operace,
- `AuditFieldChange` — jednotlivé změněné pole.

Auditní operace uchovává:

- původce,
- čas,
- druh operace,
- typ a ID objektu,
- orientační název objektu,
- komentář,
- přístupovou úroveň,
- identifikátor požadavku,
- technický kontext.

Audit používá generickou identifikaci objektu, protože jde o historický záznam, nikoli aktivní obchodní vazbu.

Citlivé údaje zůstávají chráněné i v auditu. Hesla, tokeny a obsah souborů se do auditu neukládají.

Běžné prohlížení stránek se v první verzi neaudituje. Auditují se změny, exporty, stažení citlivých příloh a správní operace.

## 16. Rozdělení validace

### Databáze

Databáze hlídá zejména:

- povinné hodnoty,
- cizí klíče,
- unikátní kódy,
- jednoduché `CheckConstraint`,
- přesné aktivní duplicity,
- zákaz vazby osoby sama na sebe,
- jednu aktivní hlavní fotografii,
- jedinečnou účast osoby ve stejné roli na stejné události.

### Model a formulář

Modelová validace hlídá zejména:

- alespoň jméno nebo příjmení,
- strukturu neúplného data,
- souřadnice,
- hierarchii místa,
- povinný lokalizační údaj bydliště,
- název nebo popis zdravotního záznamu,
- vhodnost hlavní fotografie.

### Doménová služba

Servisní vrstva řeší pravidla přes více objektů:

- vytvoření a změnu události s účastníky,
- narození, úmrtí a sňatek,
- rodičovské cykly,
- symetrické vazby,
- hlavní fotografii,
- přílohy a zdroje,
- archivaci a obnovu,
- oprávnění,
- audit celé operace.

Významné zápisy probíhají v `transaction.atomic()`.

## 17. Selektory a výkon

Složitější čtecí dotazy budou soustředěny v modulech `selectors.py`, například:

- seznam osob,
- detail osoby,
- časová osa,
- skupiny vztahů,
- materiály osoby.

Selektory zajišťují filtrování odstraněných záznamů, kontrolu viditelnosti a optimalizované `select_related()` a `prefetch_related()`.

Prioritní indexy podporují:

- normalizované jméno a příjmení,
- kategorii a stav osoby,
- účast osoby v narození a úmrtí,
- časové osy podle osoby a `sort_date`,
- obě strany vazby,
- hlavní fotografii,
- kontrolní součet souboru,
- archivní identifikaci zdroje,
- historii konkrétního objektu.

Počty záznamů, věk, stav osoby, římská číslice a další agregace se zatím počítají za běhu.

## 18. Pořadí migrací

Doporučené pořadí:

```text
accounts.0001_initial
people.0001_lookup_models
people.0002_person_and_names
places.0001_place_models
events.0001_event_lookups
events.0002_events_and_participation
people.0003_relationships
places.0002_residence_lookups
places.0003_residences
places.0004_grave_models
materials.0001_attachment_lookups
materials.0002_attachments
materials.0003_attachment_links
materials.0004_source_lookups
materials.0005_sources
materials.0006_source_links
health.0001_health_models
health.0002_material_links
audit.0001_initial
accounts.0002_user_profile_person_link
```

Datové migrace základních číselníků budou malé a rozdělené podle aplikací.

## 19. Hlavní technická rizika

1. Podmíněná unikátní omezení je nutné ověřit proti zvolené verzi Djanga a SQLite.
2. Model obsahuje mnoho číselníků; běžný editor je nebude spravovat a systémové hodnoty vzniknou datovou migrací.
3. Explicitní propojení příloh a zdrojů znamená více tabulek, ale zachovává referenční integritu.
4. Validace přes více objektů nesmí být rozptýlena ve views ani pouze v metodách `save()`.
5. Přímý přístup k fyzickým souborům nesmí obejít kontrolu oprávnění.
6. Audit nesmí vytvořit vedlejší únik citlivých údajů.

Žádné z těchto rizik nevyžaduje změnu schválených ACP.

## 20. Kritéria připravenosti k implementaci

Návrh je připraven k implementaci, protože:

- entity mají jasnou odpovědnost,
- kardinality a povinnosti jsou určeny,
- odvozené hodnoty se zbytečně neukládají,
- přílohy a zdroje jsou znovu použitelné,
- neúplná data jsou strukturovaná bez falešné přesnosti,
- integrita je rozdělena mezi databázi, modely a služby,
- hlavní indexy jsou známé,
- oprávnění, archivace a audit jsou součástí návrhu,
- existuje ER diagram,
- návrh prošel architektonickou revizí,
- otevřené otázky neblokují první migraci.
