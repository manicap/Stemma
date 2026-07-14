# Návrh datového modelu

**Dokument:** 03  
**Verze:** 0.1  
**Stav:** koncept  
**Datum revize:** 14. 7. 2026

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

## 3. Událost

Pole:

- ID,
- typ události,
- název,
- přesnost data,
- datum od,
- datum do,
- textová podoba data,
- ID místa,
- popis,
- příčina úmrtí,
- stav ověření,
- přístupová úroveň,
- datum vytvoření,
- datum poslední změny,
- stav archivace.

Pravidla:

- každá osoba může mít nejvýše jednu aktivní událost Narození,
- každá osoba může mít nejvýše jednu aktivní událost Úmrtí,
- sňatek je jedna společná událost propojená s více osobami,
- neznámé datum se nenahrazuje vymyšleným přesným datem.

## 4. Účast osoby na události

Spojovací entita:

- osoba,
- událost,
- role osoby v události,
- poznámka.

Příklady rolí:

- narozená osoba,
- zemřelá osoba,
- manžel,
- manželka,
- svědek,
- účastník,
- dítě,
- rodič.

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
