# Databázový návrh

**Dokument:** 11  
**Verze:** 0.12
**Stav:** schválený technický návrh v implementaci
**Datum revize:** 20. 7. 2026

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

Model `Place` dědí společné abstraktní modely `TimestampedModel`,
`AccessControlledModel`, `VerifiableModel`, `AuthoredModel` a `LifecycleModel`.
Nedědí `PartialDateModel`.

Vlastní pole modelu jsou:

- `place_type` — volitelný `ForeignKey` na `PlaceType`, `null=True`,
  `blank=True`, `on_delete=models.PROTECT`, `related_name="places"`,
- `name` — povinný `CharField(max_length=255)`,
- `normalized_name` — povinný `CharField(max_length=255, db_index=True)`;
  zatím se zadává explicitně a automatický normalizační algoritmus není
  součástí tohoto kroku,
- `parent` — volitelný `ForeignKey` na `self`, `null=True`, `blank=True`,
  `on_delete=models.SET_NULL`, `related_name="children"`,
- `country` — `CharField(max_length=100, blank=True)` pro zobrazovanou textovou
  hodnotu země nebo historického státního útvaru; samostatný model ani
  číselník zemí se zatím nevytváří,
- `description` — `TextField(blank=True)`,
- `latitude` — `DecimalField(max_digits=8, decimal_places=6, null=True,
  blank=True)`,
- `longitude` — `DecimalField(max_digits=9, decimal_places=6, null=True,
  blank=True)`,
- `coordinate_precision_m` — volitelný `PositiveIntegerField(null=True,
  blank=True)` vyjadřující odhadovanou přesnost souřadnic v metrech.

Model uplatňuje tato validační pravidla:

- zeměpisná šířka a délka musí být zadány buď obě, nebo ani jedna,
- zeměpisná šířka musí být v rozsahu −90 až 90,
- zeměpisná délka musí být v rozsahu −180 až 180,
- přesnost souřadnic lze vyplnit pouze při zadaných obou souřadnicích,
- místo nesmí být samo sobě rodičem,
- hierarchie `parent` nesmí obsahovat přímý ani nepřímý cyklus.

Metadata modelu jsou `verbose_name = "Místo"`,
`verbose_name_plural = "Místa"` a `ordering = ("name",)`. Textová
reprezentace vrací `name`.

Hierarchie míst nesmí obsahovat cyklus. Detailní adresní údaje se primárně ukládají u bydliště nebo události. Samostatné místo pro dům nebo budovu vznikne pouze tehdy, pokud se opakovaně používá nebo má vlastní historii a materiály.

Historické, jazykové a alternativní názvy mohou být vedeny v samostatném modelu `PlaceName`.

## 8. Události

### 8.1 Typ události

Číselník `EventType` je přímým potomkem `LookupModel`. Vedle zděděných
polí obsahuje tato povinná pole s `null=False` a `blank=False`:

- `supports_date_range` — `BooleanField(default=False)`; určuje, zda typ
  podporuje `DatePrecision.RANGE`,
- `allows_place` — `BooleanField(default=True)`; určuje, zda událost může
  mít přiřazené místo,
- `default_show_in_overview` — `BooleanField(default=False)`; určuje výchozí
  hodnotu příznaku zobrazení nové události v přehledu osoby,
- `default_access_level` — `CharField(max_length=20,
  choices=AccessLevel.choices, default=AccessLevel.PUBLIC)`; určuje výchozí
  přístupovou úroveň nové události.

Změna výchozích hodnot typu nemění již existující události. Metadata
modelu jsou `verbose_name = "Typ události"`,
`verbose_name_plural = "Typy událostí"` a zděděné
`ordering = ("sort_order", "name", "code")`. Textová reprezentace vrací
`name`.

Systémové hodnoty mají `is_active=True`, `is_system=True` a následující
konfiguraci:

| Kód | Název | Popis | Pořadí | Rozmezí | Místo | Přehled | Výchozí přístup |
|---|---|---|---:|:---:|:---:|:---:|---|
| `birth` | Narození | Narození osoby. | 10 | ne | ano | ano | `AccessLevel.PUBLIC` |
| `baptism` | Křest | Křest osoby. | 20 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `marriage` | Sňatek | Uzavření manželství. | 30 | ne | ano | ano | `AccessLevel.PUBLIC` |
| `divorce` | Rozvod | Ukončení manželství rozvodem. | 40 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `relocation` | Stěhování | Přestěhování osoby nebo domácnosti. | 50 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `education` | Studium | Studium na škole nebo v jiném vzdělávacím programu. | 60 | ano | ano | ne | `AccessLevel.PUBLIC` |
| `graduation` | Maturita | Složení maturity nebo obdobné závěrečné zkoušky. | 70 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `military_service` | Vojenská služba | Výkon vojenské služby. | 80 | ano | ano | ne | `AccessLevel.PUBLIC` |
| `employment` | Zaměstnání | Pracovní nebo profesní působení. | 90 | ano | ano | ne | `AccessLevel.PUBLIC` |
| `death` | Úmrtí | Úmrtí osoby. | 100 | ne | ano | ano | `AccessLevel.PUBLIC` |
| `funeral` | Pohřeb | Pohřeb nebo jiné rozloučení se zemřelým. | 110 | ne | ano | ne | `AccessLevel.PUBLIC` |
| `other` | Jiná událost | Jiná životní událost. | 120 | ano | ano | ne | `AccessLevel.PUBLIC` |

Úraz, operace, očkování a další zdravotní skutečnosti se ukládají jako zdravotní záznamy.

### 8.2 Role účastníka a povolené role

Účast osoby na události je samostatný spojovací model.

`ParticipantRole` je spravovatelný číselník, který dědí pouze
`LookupModel` a nepřidává vlastní databázová pole. Metadata jsou
`verbose_name = "Role účastníka"`,
`verbose_name_plural = "Role účastníků"` a zděděné
`ordering = ("sort_order", "name", "code")`. Textová reprezentace vrací
`name`.

Systémové role mají `is_active=True`, `is_system=True`:

| Kód | Název | Popis | Pořadí |
|---|---|---|---:|
| `subject` | Hlavní osoba | Osoba, které se událost primárně týká. | 10 |
| `born_person` | Narozená osoba | Osoba, jejíž narození událost eviduje. | 20 |
| `baptized_person` | Křtěná osoba | Osoba, jejíž křest událost eviduje. | 30 |
| `deceased_person` | Zemřelá osoba | Osoba, jejíž úmrtí nebo pohřeb událost eviduje. | 40 |
| `spouse` | Manželský partner | Partner při sňatku nebo rozvodu. | 50 |
| `parent` | Rodič | Rodič hlavní osoby nebo jiného účastníka. | 60 |
| `child` | Dítě | Dítě hlavní osoby nebo jiného účastníka. | 70 |
| `godparent` | Kmotr nebo kmotra | Kmotr nebo kmotra při křtu. | 80 |
| `witness` | Svědek | Svědek události. | 90 |
| `participant` | Účastník | Další osoba přímo účastná události. | 100 |
| `other` | Jiná role | Jiná role osoby v události. | 110 |

Používá se jediná genderově neutrální role `spouse`. Označení
ženich, nevěsta, manžel nebo manželka je pouze budoucí zobrazovací logika
odvozená z osoby a kontextu.

`AllowedEventRole` je konfigurační spojovací model bez common mixinů.
Obsahuje:

- `event_type` — `ForeignKey` na `EventType`, `on_delete=models.PROTECT`,
  `related_name="allowed_roles"`,
- `participant_role` — `ForeignKey` na `ParticipantRole`,
  `on_delete=models.PROTECT`, `related_name="event_type_rules"`,
- `min_count` — `PositiveSmallIntegerField(default=0)`,
- `max_count` — `PositiveSmallIntegerField(null=True, blank=True)`,
- `sort_order` — `PositiveIntegerField(default=0)`,
- `is_active` — `BooleanField(default=True)`,
- `is_system` — `BooleanField(default=False, editable=False)`.

Hodnota `min_count=0` znamená nepovinnou roli a vyšší hodnota minimální
povinný počet. `max_count=None` znamená počet bez horního omezení.
Maximum nesmí být nižší než minimum. `sort_order` určuje pořadí
v rozhraní, `is_active=False` pravidlo deaktivuje a `is_system` rozlišuje
systémovou konfiguraci.

Metadata modelu jsou `verbose_name = "Povolená role události"`,
`verbose_name_plural = "Povolené role událostí"` a:

```python
ordering = (
    "event_type__sort_order",
    "sort_order",
    "participant_role__sort_order",
    "participant_role__code",
)
```

Dvojice `event_type` a `participant_role` je jedinečná pomocí constraintu
`events_unique_allowed_role`. Constraint
`events_valid_allowed_role_counts` vyžaduje, aby `max_count` bylo `NULL`
nebo větší či rovné `min_count`. Textová reprezentace vrací
`"{event_type} – {participant_role}"`.

Systémová matice používá `is_active=True`, `is_system=True`. Zápis
`minimum..maximum / pořadí` používá `∞` pro neomezené maximum:

| Typ události | Povolené role |
|---|---|
| `birth` | `born_person` 1..1 / 10; `parent` 0..2 / 20; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `baptism` | `baptized_person` 1..1 / 10; `parent` 0..2 / 20; `godparent` 0..∞ / 30; `witness` 0..∞ / 40; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `marriage` | `spouse` 2..2 / 10; `parent` 0..∞ / 20; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `divorce` | `spouse` 1..2 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `relocation` | `subject` 1..∞ / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `education` | `subject` 1..1 / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `graduation` | `subject` 1..1 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `military_service` | `subject` 1..1 / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `employment` | `subject` 1..1 / 10; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `death` | `deceased_person` 1..1 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `funeral` | `deceased_person` 1..1 / 10; `witness` 0..∞ / 30; `participant` 0..∞ / 80; `other` 0..∞ / 90 |
| `other` | `subject` 1..∞ / 10; `parent` 0..∞ / 20; `child` 0..∞ / 30; `spouse` 0..∞ / 40; `godparent` 0..∞ / 50; `witness` 0..∞ / 60; `participant` 0..∞ / 80; `other` 0..∞ / 90 |

Systémová pravidla jsou současně chráněna aplikační validací:

- narození má právě jednu narozenou osobu,
- úmrtí má právě jednu zemřelou osobu,
- sňatek má dva hlavní partnery.

### 8.3 Událost

`Event` je hlavní historická entita a dědí abstraktní modely
`TimestampedModel`, `AccessControlledModel`, `VerifiableModel`,
`AuthoredModel`, `LifecycleModel` a `PartialDateModel`.

Vlastní pole modelu jsou:

- `event_type` — povinný `ForeignKey` na `EventType`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`, `related_name="events"`,
- `place` — volitelný `ForeignKey` na `places.Place`, `null=True`,
  `blank=True`, `on_delete=models.PROTECT`, `related_name="events"`,
- `location_detail` — `CharField(max_length=255, blank=True)` pro dobový
  adresní nebo lokalizační detail, který nenahrazuje strukturované místo,
- `title` — `CharField(max_length=255, blank=True)` pro volitelný vlastní
  zobrazovaný název bez automatického odvozování z typu,
- `description` — `TextField(blank=True)`,
- `show_in_overview` — `BooleanField(default=False)` jako uložené rozhodnutí
  konkrétní události.

Časový údaj používá úplnou strukturu `PartialDateModel`.
`DatePrecision.UNKNOWN` je platný stav. Pokud typ nepodporuje rozmezí,
`DatePrecision.RANGE` je odmítnuto na poli `date_precision` s kódem
`date_range_not_supported`. Typ s `allows_place=False` odmítne
strukturované místo s kódem `place_not_allowed` a neprázdný oříznutý
`location_detail` s kódem `location_detail_not_allowed`. Kalendářní
validace a odvození technických mezí zůstávají v `PartialDateModel`.

Hodnoty `EventType.default_access_level` a
`EventType.default_show_in_overview` jsou návrhy pro novou událost.
Budoucí doménová služba je při založení zkopíruje pouze tehdy, pokud
uživatel neuvede vlastní hodnotu. Změna typu ani jeho defaultů existující
události zpětně nemění. M2.4c snapshotovou službu neimplementuje;
`access_level` proto používá modelový default `AccessLevel.PUBLIC` a
`show_in_overview` modelový default `False`.

Metadata modelu jsou `verbose_name = "Událost"`,
`verbose_name_plural = "Události"` a
`ordering = ("sort_date", "sort_date_end", "pk")`. Textová reprezentace
vrací neprázdný oříznutý `title`, jinak dostupný název typu a bez
dostupného typu text `"Událost"`.

Účastníci nejsou přímými poli `Event`; `EventParticipant` je samostatný
spojovací model. Přílohy a zdroje budou používat samostatné
explicitní spojovací modely.

Příčina a okolnosti úmrtí se ukládají v samostatném modelu `DeathDetail` ve vztahu jedna ku jedné k události úmrtí.

Jedna osoba smí mít nejvýše jednu aktivní účast jako narozená osoba a jednu jako zemřelá osoba.

### 8.4 Účastník události

`EventParticipant` představuje účast konkrétní existující osoby v jedné
události v jedné konkrétní roli. Jde o spojovací model dědící pouze z
`models.Model`; přístup, ověření a lifecycle se odvozují z nadřazeného
`Event`.

Model obsahuje:

- `event` — povinný `ForeignKey` na `Event`, `null=False`, `blank=False`,
  `on_delete=models.CASCADE`, `related_name="participants"`,
- `person` — povinný `ForeignKey` na `people.Person`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`,
  `related_name="event_participations"`,
- `role` — povinný `ForeignKey` na `ParticipantRole`, `null=False`,
  `blank=False`, `on_delete=models.PROTECT`,
  `related_name="event_participations"`,
- `note` — `TextField(blank=True)` pro volitelnou poznámku ke konkrétní
  účasti; poznámka nemění identitu účasti.

Osoba musí být založeným záznamem `Person`. Prázdná osoba ani samostatný
textový účastník nejsou součástí současného návrhu. Stejná osoba může mít
v jedné události více různých rolí, stejnou roli může mít více osob a
jedna osoba může být účastníkem více událostí.

Trojice `event`, `person` a `role` je jedinečná pomocí constraintu
`events_unique_participation`. Odlišná poznámka nepovoluje duplicitní
trojici.

Metadata modelu jsou `verbose_name = "Účastník události"`,
`verbose_name_plural = "Účastníci událostí"` a:

```python
ordering = (
    "role__sort_order",
    "person__last_name",
    "person__first_name",
    "person_id",
)
```

Textová reprezentace vrací `"{person} – {role} – {event}"`. Pro
nedostupnou vazbu používá bezpečné texty `"Neznámá osoba"`,
`"Neznámá role"` a `"Událost"`.

Model dynamicky nekontroluje aktuální `AllowedEventRole`. Budoucí
transakční doménová služba při vytvoření nebo změně účasti ověří aktivní
konfiguraci, aktivitu role a počty účastníků. Změna konfigurace sama
nezneplatňuje již uložené historické účasti.

### 8.5 Doménová služba účastníků

Změnu účastníků jedné události zajišťuje služba v `events/services.py`:

```python
@dataclass(frozen=True, slots=True)
class EventParticipantInput:
    person: Person
    role: ParticipantRole
    note: str = ""


def replace_event_participants(
    *,
    event: Event,
    participants: Iterable[EventParticipantInput],
    require_complete: bool = False,
) -> list[EventParticipant]:
    ...
```

Služba materializuje vstupní iterable právě jednou a v
`transaction.atomic()` atomicky nahradí celou sadu účastníků. Událost,
aktuální účasti, použité osoby, role a relevantní konfiguraci načítá z
databáze a podle možností databáze zamyká pomocí `select_for_update()`.
Celý požadovaný výsledný stav ověří před prvním zápisem. Zachované
trojici událost, osoba a role ponechá primární klíč, případně aktualizuje
její poznámku; odstraní jen vynechané a vytvoří jen nové účasti. Výsledkem
je seznam uložených účastí v modelovém pořadí.

Při každé náhradě se ověřuje, že osoby a role jsou uložené, role jsou
aktivní, pro typ události existuje aktivní `AllowedEventRole`, vstup
neobsahuje duplicitní dvojici osoby a role a počet nepřekračuje
`max_count`. Při `require_complete=False` se `min_count` nekontroluje a
událost může zůstat rozpracovaná. Při `require_complete=True` musí být
splněna minima všech aktivních pravidel; neaktivní pravidla se do minima
nezapočítávají. Aktivní povinné pravidlo odkazující na neaktivní roli je
neplatnou konfigurací.

Samotná změna konfigurace historické účasti automaticky nemění. Při
pozdějším volání služby však každý záznam zahrnutý do nové výsledné sady
musí projít aktuální konfigurací. Dnes nepovolenou historickou účast lze
odstranit jejím vynecháním, ale nelze ji ponechat ani pouze změnit její
poznámku. Grandfathering se nepoužívá.

Validační chyby používají `django.core.exceptions.ValidationError`, klíče
`event` a `participants` a stabilní kódy `event_unsaved`,
`participant_person_unsaved`, `participant_role_unsaved`,
`participant_role_inactive`, `role_not_allowed_for_event_type`,
`duplicate_event_person_role`, `participant_count_above_maximum` a
`participant_count_below_minimum`. Dostupný kontext je předáván v
`params`. Implementace M2.4e nemění modely a nevytváří migraci.

## 9. Vazby mezi osobami

### 9.1 Kategorie a typ vazby

`RelationshipCategory` je pevný `TextChoices` výčet:

| Technická hodnota | Český název |
|---|---|
| `parent_child` | Rodič a dítě |
| `partner` | Partnerství |
| `sibling` | Sourozenectví |
| `godparent` | Kmotrovství |
| `care` | Péče a poručenství |
| `social` | Sociální vazba |
| `other` | Jiná vazba |

`RelationshipType` je konkrétní uživatelsky rozšiřitelný číselník, který
dědí pouze z `LookupModel`. Vedle zděděných polí obsahuje:

| Pole | Typ a pravidla |
|---|---|
| `forward_label_male` | `CharField(max_length=100)`, povinné |
| `forward_label_female` | `CharField(max_length=100)`, povinné |
| `forward_label_unknown` | `CharField(max_length=100)`, povinné |
| `reverse_label_male` | `CharField(max_length=100)`, povinné |
| `reverse_label_female` | `CharField(max_length=100)`, povinné |
| `reverse_label_unknown` | `CharField(max_length=100)`, povinné |
| `category` | `CharField(max_length=20)`, `RelationshipCategory.choices`, výchozí `other` |
| `is_symmetric` | `BooleanField`, výchozí `False` |
| `supports_date_range` | `BooleanField`, výchozí `False` |
| `is_derivable` | `BooleanField`, výchozí `False` |

Objekt se řadí podle zděděného `("sort_order", "name", "code")`, má
jednotné číslo „Typ vazby“ a množné číslo „Typy vazeb“.

### 9.2 Směr, genderované názvy a symetrie

Vazba se ukládá jednou mezi osobami A a B. Osoba A je výchozí osoba a osoba
B cílová osoba. `forward_label_*` popisuje osobu B z pohledu osoby A
a genderová varianta se vybírá podle genderu osoby B. `reverse_label_*`
popisuje osobu A z pohledu osoby B a varianta se vybírá podle genderu osoby
A. Varianta `unknown` se používá při `Gender.UNKNOWN` nebo chybějícím údaji.

U symetrické vazby pořadí osob význam nemění a budoucí konkrétní
`Relationship` uloží dvojici v normalizovaném pořadí. U směrové vazby je
pořadí významové. Symetrický typ musí mít shodné dopředné a zpětné názvy
pro mužskou, ženskou i neznámou variantu. `RelationshipType.clean()` hlásí
chybu na příslušném zpětném poli s kódem `symmetric_labels_mismatch`.
Stejné pravidlo vynucuje databázový constraint
`people_symmetric_relationship_labels_match`.

`supports_date_range=False` znamená, že budoucí konkrétní `Relationship`
nesmí používat `DatePrecision.RANGE`; hodnota `True` rozmezí povoluje.
Příznak nevyžaduje vyplnění data a neomezuje ostatní podporované přesnosti.
`RelationshipType` samo datum neobsahuje.

`is_derivable=True` označuje vztah, který lze odvodit z jiných
strukturovaných údajů a běžně se nemá ukládat duplicitně, jsou-li zdrojová
data dostupná. Příznak v M2.5a nic automaticky neodvozuje, nezakazuje
explicitní záznam a neimplementuje algoritmus odvození.

### 9.3 Systémové typy

Všechny systémové typy mají `is_active=True` a `is_system=True`.

| Kód | Název a popis | Kategorie | Pořadí | Symetrický | Rozmezí | Odvoditelný |
|---|---|---|---:|---:|---:|---:|
| `biological_parent` | Biologický rodič — Vztah biologického rodiče a dítěte. | `parent_child` | 10 | ne | ne | ne |
| `adoptive_parent` | Adoptivní rodič — Vztah adoptivního rodiče a adoptovaného dítěte. | `parent_child` | 20 | ne | ne | ne |
| `step_parent` | Nevlastní rodič — Vztah nevlastního rodiče a nevlastního dítěte. | `parent_child` | 30 | ne | ano | ne |
| `foster_parent` | Pěstoun — Vztah pěstouna a dítěte v pěstounské péči. | `parent_child` | 40 | ne | ano | ne |
| `guardian` | Poručník — Vztah poručníka a osoby v poručenství. | `care` | 50 | ne | ano | ne |
| `spouse` | Manželství — Manželský vztah mezi dvěma osobami. | `partner` | 60 | ano | ano | ne |
| `partner` | Partnerství — Partnerský vztah mezi dvěma osobami. | `partner` | 70 | ano | ano | ne |
| `sibling` | Biologické sourozenectví — Biologické sourozenectví. | `sibling` | 80 | ano | ne | ano |
| `adoptive_sibling` | Adoptivní sourozenectví — Sourozenectví vzniklé adopcí. | `sibling` | 90 | ano | ne | ne |
| `step_sibling` | Nevlastní sourozenectví — Nevlastní sourozenectví. | `sibling` | 100 | ano | ano | ne |
| `social_sibling` | Sourozenecká sociální vazba — Sourozenecká sociální vazba bez biologického nebo právního základu. | `sibling` | 110 | ano | ano | ne |
| `godparent` | Kmotrovství — Vztah kmotra nebo kmotry a kmotřence. | `godparent` | 120 | ne | ne | ne |
| `family_friend` | Rodinné přátelství — Blízká přátelská vazba osoby k rodině. | `social` | 130 | ano | ano | ne |
| `other` | Jiná vazba — Jiná rodinná nebo sociální vazba. | `other` | 140 | ano | ano | ne |

Genderované názvy obou směrů jsou:

| Kód | A → B: muž / žena / neznámé | B → A: muž / žena / neznámé |
|---|---|---|
| `biological_parent` | syn / dcera / dítě | otec / matka / rodič |
| `adoptive_parent` | adoptovaný syn / adoptovaná dcera / adoptované dítě | adoptivní otec / adoptivní matka / adoptivní rodič |
| `step_parent` | nevlastní syn / nevlastní dcera / nevlastní dítě | nevlastní otec / nevlastní matka / nevlastní rodič |
| `foster_parent` | pěstounský syn / pěstounská dcera / dítě v pěstounské péči | pěstoun / pěstounka / pěstoun nebo pěstounka |
| `guardian` | svěřenec / svěřenkyně / osoba v poručenství | poručník / poručnice / poručník nebo poručnice |
| `spouse` | manžel / manželka / manžel nebo manželka | shodné s A → B |
| `partner` | partner / partnerka / partner nebo partnerka | shodné s A → B |
| `sibling` | bratr / sestra / sourozenec | shodné s A → B |
| `adoptive_sibling` | adoptivní bratr / adoptivní sestra / adoptivní sourozenec | shodné s A → B |
| `step_sibling` | nevlastní bratr / nevlastní sestra / nevlastní sourozenec | shodné s A → B |
| `social_sibling` | blízký jako bratr / blízká jako sestra / blízký jako sourozenec | shodné s A → B |
| `godparent` | kmotřenec / kmotřenka / kmotřenec nebo kmotřenka | kmotr / kmotra / kmotr nebo kmotra |
| `family_friend` | rodinný přítel / rodinná přítelkyně / rodinný přítel nebo přítelkyně | shodné s A → B |
| `other` | související osoba / související osoba / související osoba | shodné s A → B |

`family_friend` je v první verzi symetrická vazba mezi dvěma osobami;
nevyjadřuje vztah osoby k rodině jako samostatnému objektu. Pouze biologické
sourozenectví `sibling` má `is_derivable=True`.

### 9.4 Budoucí konkrétní vazba

`Relationship` je samostatná historická doménová entita a dědí v tomto
pořadí:

```python
TimestampedModel,
AccessControlledModel,
VerifiableModel,
AuthoredModel,
LifecycleModel,
PartialDateModel,
models.Model,
```

Vlastní pole jsou:

| Pole | Typ a pravidla |
|---|---|
| `relationship_type` | povinný `ForeignKey` na `RelationshipType`, `on_delete=PROTECT`, `related_name="relationships"` |
| `person_a` | povinný `ForeignKey` na `Person`, `on_delete=PROTECT`, `related_name="relationships_as_a"` |
| `person_b` | povinný `ForeignKey` na `Person`, `on_delete=PROTECT`, `related_name="relationships_as_b"` |
| `note` | `TextField(blank=True)`, běžná doménová poznámka |

Poznámka se řídí přístupovou úrovní celé vazby. Zděděné `date_note` je
vyhrazené poznámce k časovému údaji. Model nepřidává vlastní `save()`;
technické meze nadále přepočítává zděděný `PartialDateModel`.

### 9.5 Časový význam a opakovaná období

Jeden `Relationship` představuje jedno souvislé období vztahu:

- `UNKNOWN` znamená neznámý čas vztahu,
- `EXACT` přesné datum vzniku vztahu,
- `MONTH` měsíc vzniku vztahu,
- `YEAR` rok vzniku vztahu,
- `RANGE` známé období platnosti se začátkem a koncem.

U `EXACT`, `MONTH` a `YEAR` technické `sort_date_end` neznamená konec
vztahu. Je pouze horní technickou mezí přesnosti pro řazení a porovnání.
`RANGE` je povoleno pouze při
`relationship_type.supports_date_range=True`; `UNKNOWN` je vždy platné.

Stejné osoby mohou mít více záznamů stejného typu s odlišným časovým
vymezením. Překrývající se, ale neidentická období se v M2.5b nezakazují.
Poznámka, přístupová úroveň, stav ověření ani původní text data nemění
identitu období.

### 9.6 Modelová validace

`Relationship.clean()` zachová a agreguje chyby `PartialDateModel` a dále
kontroluje:

- `person_a == person_b` — chyba na `person_b` s kódem
  `relationship_to_self`,
- nepodporované `DatePrecision.RANGE` — chyba na `date_precision` s kódem
  `date_range_not_supported`,
- symetrický typ s `person_a_id > person_b_id` — chyba na `person_b`
  s kódem `symmetric_relationship_not_normalized`.

U symetrického typu je kanonické pořadí `person_a_id < person_b_id`.
Model osoby nepřehazuje. Budoucí veřejný zápis bude před vytvořením
normalizovat doménová služba podle PK. Kontrola pořadí proběhne jen při
bezpečně dostupném typu a uložených různých osobách.

Databáze nemůže podmínit constraint hodnotou `is_symmetric` z jiné tabulky.
Přímý ORM zápis bez `full_clean()` proto může uložit nenormalizovanou
symetrickou dvojici. Toto omezení je přijatelné pouze do zavedení veřejné
doménové služby; `clean()` ani `save()` data automaticky nemění.

`RelationshipType.is_derivable=True` explicitní uložení nezakazuje a nic
automaticky neodvozuje.

### 9.7 Databázové constrainty

Vztah osoby k sobě zakazuje:

```text
people_relationship_distinct_persons
```

Unikátnost používá dva podmíněné constrainty. Pro jejich účely znamená
„active“ `deleted_at IS NULL`. Archivovaný záznam zůstává historicky
existující a započítává se; měkce odstraněný záznam se nezapočítává.

`people_unique_active_unknown_relationship` povoluje pro orientovanou
trojici `person_a`, `person_b` a `relationship_type` nejvýše jeden měkce
neodstraněný záznam s `DatePrecision.UNKNOWN`.

`people_unique_active_dated_relationship` zajišťuje u známého času
jedinečnost polí:

```text
person_a,
person_b,
relationship_type,
date_precision,
sort_date,
sort_date_end
```

Oba unikátní constrainty používají při modelové validaci kód
`duplicate_relationship`. Odlišné technické časové vymezení nebo jiná
přesnost mohou vytvořit další období. Po měkkém odstranění lze vytvořit
náhradu; obnovení původního záznamu může narazit na novější aktivní záznam.

### 9.8 Metadata a hranice M2.5b

Metadata jsou:

```python
verbose_name = "Vazba"
verbose_name_plural = "Vazby"
ordering = (
    "relationship_type__sort_order",
    "sort_date",
    "sort_date_end",
    "person_a_id",
    "person_b_id",
    "pk",
)
```

Textová reprezentace vrací
`"{person_a} – {relationship_type} – {person_b}"` a používá fallbacky
`"Neznámá osoba A"`, `"Vazba"` a `"Neznámá osoba B"`.

M2.5b neřeší rodičovské cykly, kontrolu věku, genealogickou
pravděpodobnost, překryvy období, automatický opačný řádek, automatické
vazby z událostí ani algoritmus odvození sourozenců. Tato pravidla patří
do budoucí doménové služby.

Tvrdé chyby zahrnují:

- vazbu osoby sama se sebou,
- přesnou aktivní duplicitu,
- obrácenou duplicitu symetrické vazby,
- cyklus přímého rodičovství,
- konec období před začátkem.

Biologické sourozenectví se primárně odvozuje ze společných biologických
rodičů. Explicitní sourozenecká vazba se používá u neznámých rodičů nebo
u adoptivního, nevlastního či sociálního sourozenectví.

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

Pro účastníky události služba ověří aktivní `AllowedEventRole`, aktivitu
`ParticipantRole`, minimální a maximální počet a úplnost povinných rolí
nad celou sadou účastníků. Model `EventParticipant` tuto měnitelnou
konfiguraci dynamicky nekontroluje.

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

Skutečné pořadí dosavadních a bezprostředně navazujících migrací M2 je:

```text
accounts.0001_initial
people.0001_person_category
people.0002_initial_person_categories
people.0003_person
people.0004_name_type_person_name
people.0005_initial_name_types
places.0001_place_type
places.0002_place
events.0001_event_type
events.0002_initial_event_types
events.0003_participant_role_allowed_event_role
events.0004_initial_participant_roles
events.0005_initial_allowed_event_roles
events.0006_event
events.0007_event_participant
people.0006_relationship_type
people.0007_initial_relationship_types
people.0008_relationship
```

Následující plánované migrace začínají:

```text
places.0003_residence_lookups
places.0004_residences
places.0005_grave_models
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
