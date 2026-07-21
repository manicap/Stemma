# Návrh datového modelu

**Dokument:** 03  
**Verze:** 0.10
**Stav:** koncept  
**Datum revize:** 21. 7. 2026

## 1. Základní pilíře

Datový model stojí na třech hlavních entitách:

- Osoba – kdo,
- Událost – co a kdy se stalo,
- Vazba – kdo je s kým propojen.

Další hlavní entity:

- Místo,
- Bydliště,
- Hrobové místo,
- Příloha,
- Zdroj,
- Zdravotní záznam,
- Uživatel,
- Změna.

## 2. Osoba

Navržená pole:

- ID,
- jméno,
- příjmení,
- rodné příjmení,
- další jména,
- přezdívka,
- pohlaví,
- kategorie osoby,
- titul před jménem,
- titul za jménem,
- stručná poznámka,
- ID hlavní fotografie,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Neukládá se přímo:

- datum narození,
- místo narození,
- datum úmrtí,
- místo úmrtí,
- příznak žije/zemřel,
- věk,
- římská číslice.

Tyto údaje se odvozují z událostí a pravidel aplikace.

### 2.1 Kategorie osoby

Každá osoba může být zařazena do jedné hlavní kategorie podle svého vztahu k rodině a významu v rodinném příběhu.

Základní kategorie:

1. **Přímá rodina** – přímí předci a potomci.
2. **Ostatní rodina** – sourozenci předků, jejich potomci, příbuzní sňatkem a další vzdálenější příbuzenstvo.
3. **Blízcí rodině** – rodinní přátelé, kmotři a další dlouhodobě blízké osoby, pokud již nepatří do některé rodinné kategorie.
4. **Duchovní** – farář nebo jiný duchovní významně spojený s rodinou.
5. **Další související osoby** – svědci, sousedé, zaměstnavatelé, hospodářští správci a jiné osoby důležité pro rodinný příběh.

Pravidla:

- kategorie je obecné zařazení osoby a nenahrazuje konkrétní vazby mezi osobami,
- kmotrovství, příbuzenství, partnerství a další konkrétní vztahy se nadále evidují jako vazby,
- pokud osoba splňuje více možností, přednost má rodinná kategorie,
- seznam kategorií má být spravován jako číselník, aby jej bylo možné později rozšířit bez změny struktury entity Osoba,
- kategorie může být dočasně nevyplněná, pokud zatím nelze osobu spolehlivě zařadit.

## 3. Událost

### 3.1 Typ události

Typ události je uživatelsky rozšiřitelný číselník. Vedle kódu, názvu,
popisu, pořadí, aktivity a systémového příznaku určuje:

- zda typ podporuje časové rozmezí,
- zda událost může mít místo,
- zda se nová událost tohoto typu ve výchozím stavu zobrazuje v přehledu,
- výchozí přístupovou úroveň nové události.

Systémové typy jsou narození, křest, sňatek, rozvod, stěhování, studium,
maturita, vojenská služba, zaměstnání, úmrtí, pohřeb a jiná událost.
Zdravotní skutečnosti se evidují jako zdravotní záznamy.

### 3.2 Záznam události

`Event` používá společná pole časových razítek, přístupu, ověření, autora,
životního cyklu a úplnou strukturu `PartialDateModel`. Vlastní pole jsou:

- povinný typ události,
- volitelné strukturované místo,
- `location_detail` pro dobový adresní nebo lokalizační detail,
- volitelný vlastní zobrazovaný název `title`,
- popis,
- uložený příznak `show_in_overview`.

Neznámé datum je platný stav. Rozmezí lze použít pouze u typu, který je
podporuje. Typ bez povoleného místa zakazuje strukturované místo i
neprázdný lokalizační detail.

Výchozí přístup a zobrazení v přehledu jsou snapshotové návrhy typu pro
novou událost. Budoucí doménová služba je při založení zkopíruje, pokud
uživatel nezadá vlastní hodnotu. Pozdější změna typu nebo jeho defaultů
existující událost nepřepisuje.

Pravidla:

- každá osoba může mít nejvýše jednu aktivní událost Narození,
- každá osoba může mít nejvýše jednu aktivní událost Úmrtí,
- sňatek je jedna společná událost propojená s více osobami,
- neznámé datum se nenahrazuje vymyšleným přesným datem.

Příčina a okolnosti úmrtí patří do samostatného specializovaného detailu
`DeathDetail` ve vztahu jedna ku jedné k události úmrtí.

## 4. Účast osoby na události

`EventParticipant` je samostatná spojovací entita a není součástí
základního modelu `Event`. Obsahuje povinné vazby na:

- existující osobu,
- událost,
- roli osoby v události,
- volitelnou poznámku ke konkrétní účasti.

Stejná osoba může mít v jedné události více různých rolí a stejnou roli
může mít více osob. Trojice událost, osoba a role je jedinečná; rozdílná
poznámka nepovoluje duplicitní účast.

Databázový constraint hlídá pouze přesnou duplicitu. Povolenost a aktivita
role, minimální a maximální počty a úplnost celé události budou ověřovány
budoucí transakční doménovou službou. Změna konfigurace nemá zpětně
zneplatňovat uložené historické účasti.

Role osoby je spravovatelný číselník. Systémové role jsou hlavní osoba,
narozená osoba, křtěná osoba, zemřelá osoba, manželský partner, rodič,
dítě, kmotr nebo kmotra, svědek, účastník a jiná role.

Manželský partner používá jedinou genderově neutrální technickou roli
`spouse`. Genderované označení je pouze odvozená zobrazovací logika.

Konfigurační model `AllowedEventRole` spojuje typ události s povolenou rolí
a určuje její minimální a maximální počet, pořadí a aktivitu. Nulové
minimum znamená nepovinnou roli, kladné minimum povinný počet a prázdné
maximum počet bez horního omezení. Každá dvojice typu a role má nejvýše
jedno konfigurační pravidlo.

## 5. Vazba mezi osobami

Pole:

- ID,
- osoba A,
- osoba B,
- typ vazby,
- datum od,
- datum do,
- textová podoba období,
- stav ověření,
- poznámka,
- přístupová úroveň,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Každý typ vazby definuje:

- označení směru A → B,
- označení směru B → A,
- varianty podle pohlaví,
- kategorii,
- zda je vazba symetrická,
- zda může být časově omezená.

`RelationshipType` je uživatelsky rozšiřitelný číselník odvozený pouze
z `LookupModel`. Vedle společných polí číselníku obsahuje:

- `forward_label_male`, `forward_label_female` a
  `forward_label_unknown` — povinné názvy osoby B z pohledu osoby A,
- `reverse_label_male`, `reverse_label_female` a
  `reverse_label_unknown` — povinné názvy osoby A z pohledu osoby B,
- `category` — pevnou kategorii vztahu,
- `is_symmetric` — zda pořadí osob nemění význam vztahu,
- `supports_date_range` — zda budoucí konkrétní vazba smí používat
  `DatePrecision.RANGE`,
- `is_derivable` — zda lze vztah odvodit z jiných strukturovaných údajů.

Pevné kategorie jsou rodič a dítě (`parent_child`), partnerství
(`partner`), sourozenectví (`sibling`), kmotrovství (`godparent`), péče
a poručenství (`care`), sociální vazba (`social`) a jiná vazba (`other`).

Osoba A je výchozí osoba uloženého vztahu a osoba B cílová osoba.
Genderová varianta názvu A → B se vybírá podle osoby B a varianta názvu
B → A podle osoby A. Varianta `unknown` se použije při neznámém nebo
chybějícím genderu. U symetrického typu musí být všechny tři dvojice
názvů obou směrů shodné.

Systémový katalog obsahuje kódy `biological_parent`, `adoptive_parent`,
`step_parent`, `foster_parent`, `guardian`, `spouse`, `partner`, `sibling`,
`adoptive_sibling`, `step_sibling`, `social_sibling`, `godparent`,
`family_friend` a `other`. Pouze biologické sourozenectví `sibling` je
v této etapě označeno jako odvoditelné. Samotný algoritmus odvození ani
konkrétní model `Relationship` nejsou součástí M2.5a.

### 5.1 Konkrétní vazba

`Relationship` je samostatná historická doménová entita. Dědí
`TimestampedModel`, `AccessControlledModel`, `VerifiableModel`,
`AuthoredModel`, `LifecycleModel`, `PartialDateModel` a `models.Model`.

Vlastní pole jsou:

- `relationship_type` — povinný `ForeignKey` na `RelationshipType`,
  `on_delete=PROTECT`, `related_name="relationships"`,
- `person_a` — povinný `ForeignKey` na `Person`, `on_delete=PROTECT`,
  `related_name="relationships_as_a"`,
- `person_b` — povinný `ForeignKey` na `Person`, `on_delete=PROTECT`,
  `related_name="relationships_as_b"`,
- `note` — `TextField(blank=True)` pro běžnou doménovou poznámku.

`person_a` je výchozí osoba a `person_b` cílová osoba. Opačný zobrazovaný
směr se odvozuje z typu a nevytváří druhý databázový řádek. U symetrického
typu je kanonické pořadí `person_a_id < person_b_id`; model pořadí pouze
validuje a doménová služba je před zápisem normalizuje.

Jeden řádek představuje jedno souvislé období. `UNKNOWN` znamená neznámý
čas, `EXACT`, `MONTH` a `YEAR` známý vznik vztahu a `RANGE` období platnosti
se začátkem a koncem. Technické `sort_date_end` u jednoduché přesnosti není
koncem vztahu. Rozmezí je povoleno pouze typem s
`supports_date_range=True`.

Stejná orientovaná trojice může mít více odlišných známých období, ale jen
jeden měkce neodstraněný záznam s neznámým časem. Archivované záznamy se do
unikátnosti nadále započítávají; měkce odstraněné nikoli. Rozdílná poznámka,
přístupová úroveň, stav ověření ani původní text data nemění identitu
období.

Model zakazuje vztah osoby k sobě. Pro známý čas a neznámý čas používá dva
samostatné podmíněné unikátní constrainty. Obrácená nesymetrická vazba je
jiné tvrzení. Odvoditelný typ lze explicitně uložit; M2.5b nic automaticky
neodvozuje a neřeší rodičovské cykly ani překryvy období.

Metadata jsou `verbose_name = "Vazba"`, `verbose_name_plural = "Vazby"`
a řazení podle typu, technických časových mezí, obou osob a primárního
klíče. Textová reprezentace používá formát
`"{person_a} – {relationship_type} – {person_b}"` s bezpečnými fallbacky.

### 5.2 Doménová služba vazeb

Veřejné zápisové rozhraní je v `people/services.py`. Používá frozen
dataclass se slots `RelationshipInput` a keyword-only funkce
`create_relationship(*, data, created_by=None)` a
`update_relationship(*, relationship, data)`. Vstup obsahuje typ, obě
osoby, poznámku, přístup, stav ověření a historické části
`PartialDateModel`; technické `sort_date` a `sort_date_end` se nepředávají.

Create nastavuje také volitelné `created_by`. Update může měnit typ, osoby,
poznámku, přístup, ověření a časový údaj, ale nemění autora, čas vytvoření
ani lifecycle pole. `updated_at` a technické meze zachovávají standardní
modelové chování.

Služba pracuje v `transaction.atomic()` s aktuálním databázovým stavem.
Update načítá vztah přes `select_for_update()`. Symetrické dvojice před
`full_clean()` normalizuje podle PK; nesymetrickou orientaci zachovává.
Archivované i měkce odstraněné osoby jsou povoleny, pokud jejich řádky
existují. Neaktivní typ nelze použít při create ani na něj přejít při
update; existující vztah může svůj neaktivní typ zachovat. Archivovaný
vztah lze upravit, měkce odstraněný nikoli.

Přesné duplicity běžně zachytí `full_clean()`. Souběžný `IntegrityError`
se po rollbacku převede na `duplicate_relationship` pouze tehdy, pokud
databázový dotaz potvrdí konflikt stejné schválené časové identity. Jiná
integritní chyba se nemaskuje. M2.5c nevytváří migraci a neřeší rodičovské
cykly, věk, překryvy období ani automaticky odvozené nebo opačné vztahy.

### 5.3 Rodičovský graf

Genealogický rodičovský graf tvoří pouze typy `biological_parent`,
`adoptive_parent`, `step_parent` a `foster_parent`. `person_a` je
rodičovská osoba, `person_b` dítě a orientovaná hrana proto vede
`person_a → person_b`. Všechny čtyři typy se vyhodnocují společně a cyklus
může být smíšený. `guardian` ani jiné systémové či uživatelské typy do
grafu automaticky nevstupují.

Do grafu se započítávají všechny měkce neodstraněné vztahy uvedených typů.
Archivace, neaktivita typu ani přesnost, stáří nebo ukončení časového údaje
rodičovský fakt nevyřazují. Měkce odstraněný vztah se nezapočítává.

Nová hrana `A → B` je odmítnuta, právě když v existujícím grafu vede cesta
`B → … → A`. Create validuje nový vztah; update vyloučí vlastní současný
řádek a ověří navrhovaný výsledný stav. Změna na nerodičovský typ může
starší cyklus odstranit. Nesouvisející starší nekonzistence jinde v grafu
změnu neblokuje. Stabilní chyba má klíč `person_b` a kód
`relationship_parent_cycle`.

Kontrola probíhá transakčně v doménové službě a načítá graf jedním
querysetem. Obecný grafový cyklus nelze vyjádřit běžným databázovým
constraintem. SQLite neposkytuje skutečné řádkové zámky a ani databáze se
zámky bez silnější izolace nemusí pokrýt všechny souběžné phantom scénáře.
M2.5d nemění model ani migrace a neřeší věk nebo překryvy období.

## 6. Bydliště

Pole:

- ID,
- osoba,
- datum nebo období,
- obec,
- ulice,
- číslo domu,
- úplná adresa,
- ID místa,
- poznámka,
- stav ověření,
- přístupová úroveň.

Bydliště může mít zdroje a přílohy.

## 7. Hrobové místo

Pole:

- ID,
- název,
- hřbitov,
- obec,
- oddíl,
- řada,
- číslo hrobu,
- GPS souřadnice,
- přepis nápisu,
- popis,
- stav místa,
- externí odkaz,
- datum vytvoření,
- datum poslední změny.

Spojení osoba–hrobové místo je samostatná vazba, aby jedno místo mohlo patřit více osobám.

## 8. Příloha

Pole:

- ID,
- typ souboru,
- MIME typ,
- původní název,
- interní název,
- název pro uživatele,
- popis,
- cesta nebo objektové úložiště,
- velikost,
- kontrolní součet,
- datum vzniku,
- datum nahrání,
- nahrál uživatel,
- autor,
- původ,
- vlastník originálu,
- přístupová úroveň,
- technická metadata,
- stav archivace.

Příloha může být propojena s více objekty.

## 9. Zdroj

Pole:

- ID,
- typ zdroje,
- název,
- citace,
- archiv nebo instituce,
- signatura,
- odkaz,
- poznámka,
- míra důvěryhodnosti,
- přístupová úroveň.

Zdroj se má vázat na konkrétní tvrzení nebo záznam, nikoli pouze na celou osobu.

## 10. Zdravotní záznam

Pole:

- ID,
- osoba,
- datum,
- název,
- typ,
- popis,
- lékař nebo zařízení,
- poznámka,
- přístupová úroveň,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Výchozí přístupová úroveň zdravotního záznamu je omezená.

## 11. Místo

Pole:

- ID,
- název,
- typ místa,
- nadřazené místo,
- země,
- souřadnice,
- historické názvy,
- popis.

## 12. Uživatel

Pole:

- ID,
- jméno,
- e-mail,
- role,
- stav účtu,
- datum posledního přihlášení,
- datum vytvoření.

## 13. Změna

Pole:

- ID,
- uživatel,
- typ objektu,
- ID objektu,
- změněné pole,
- původní hodnota,
- nová hodnota,
- datum změny,
- komentář.

## 14. Odvozené hodnoty

Aplikace dopočítává:

- stav žijící/zemřelý,
- věk,
- věk při úmrtí,
- římskou číslici,
- opačný směr vazby,
- chronologické řazení,
- počet fotografií, dokumentů a událostí.

## 15. Zásady

- stejná informace se nemá ukládat dvakrát,
- přílohy a zdroje mají být znovu použitelné,
- důležitá fakta se ukládají strukturovaně,
- neúplná data nesmí být maskována falešnou přesností,
- fyzické mazání se nepoužívá jako výchozí operace.
