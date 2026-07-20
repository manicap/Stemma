# Návrh datového modelu

**Dokument:** 03  
**Verze:** 0.6
**Stav:** koncept  
**Datum revize:** 20. 7. 2026

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
