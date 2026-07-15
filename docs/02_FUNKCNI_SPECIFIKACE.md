# Funkční specifikace

**Dokument:** 02  
**Verze:** 0.2  
**Stav:** pracovní návrh  
**Datum revize:** 15. 7. 2026

## 1. Hlavní obrazovka

Desktopové rozhraní používá dvousloupcový model:

- vlevo je trvale viditelný seznam osob,
- vpravo je detail právě vybrané osoby,
- kliknutí na osobu změní pouze detail vpravo,
- vybraná osoba je v seznamu zřetelně zvýrazněna,
- změny se po uložení bez obnovení stránky promítnou do všech souvisejících částí rozhraní.

Na tabletu zůstává dvousloupcové rozhraní, ale seznam lze sbalit. Na telefonu se seznam otevírá jako panel vysunutý zleva a po výběru osoby se automaticky zavře.

Horní lišta obsahuje piktogram rozvětveného stromu, název Stemma, přepínač světlého a tmavého režimu a přihlášení nebo profilové menu.

## 2. Seznam osob

Každý záznam osoby obsahuje:

- malou fotografii nebo výchozí bustu vlevo přes dva textové řádky,
- jméno a příjmení,
- automatickou římskou číslici u shodných jmen,
- datum nebo rok narození a úmrtí,
- kategorii osoby.

Nad seznamem jsou:

- vyhledávání s našeptávačem,
- filtr kategorie,
- rozbalovací nabídka řazení,
- pro oprávněného uživatele tlačítko + Přidat osobu.

Výchozí řazení je Od nejmladších. Další možnosti:

- Od nejstarších,
- Příjmení A–Z,
- Příjmení Z–A,
- Jméno A–Z,
- Jméno Z–A.

Osoby bez známého data narození se při řazení podle věku zobrazují až za osobami se známým datem.

Vyhledávání pracuje minimálně s:

- jménem,
- příjmením,
- rodným příjmením,
- dalšími jmény,
- přezdívkou,
- rokem narození.

Vyhledávání nerozlišuje velikost písmen a je tolerantní k diakritice.

Archivované osoby se ve výchozím seznamu nezobrazují. Oprávněný uživatel je může zobrazit zvláštní volbou filtru.

## 3. Detail osoby

Záhlaví detailu zůstává viditelné při přepínání karet a obsahuje:

- hlavní fotografii nebo výchozí bustu,
- celé jméno,
- rodné příjmení,
- římskou číslici,
- kategorii osoby,
- pohlaví,
- datum narození,
- datum úmrtí,
- automaticky vypočítaný věk,
- navigaci Zpět a Vpřed v historii zobrazených osob,
- tlačítko Upravit osobu podle oprávnění,
- tlačítko pro vytvoření souhrnného PDF A4.

Pod záhlavím jsou záložky:

- Přehled,
- Vztahy,
- Události,
- Bydliště,
- Zdraví,
- Materiály.

Výchozí záložkou je Přehled. Aktivní záložka je zřetelně označena textem, pozadím a barevnou spodní linkou.

Podrobný vzhled a chování rozhraní definuje `10_UI_UX_NAVRH.md`.

## 4. Osoba

Základní údaje osoby:

- jméno,
- příjmení,
- rodné příjmení,
- další používaná jména,
- přezdívka,
- pohlaví,
- tituly,
- stručná poznámka,
- hlavní fotografie.

Narození a úmrtí nejsou uloženy jako běžná pole osoby, ale jako speciální typy událostí.

## 5. Automatický stav a věk

- Osoba je považována za zemřelou, pokud existuje událost typu Úmrtí.
- Pokud událost Úmrtí neexistuje, osoba je považována za žijící.
- Věk žijící osoby se počítá k aktuálnímu datu.
- Věk zemřelé osoby se počítá k datu úmrtí.
- Při neúplném datu se zobrazí pouze údaj, který lze spolehlivě odvodit.

## 6. Římské číslování

Pokud existuje více osob se stejným jménem a příjmením:

- aplikace je chronologicky seřadí podle narození,
- přidělí jim římské číslice I., II., III. atd.,
- číslice se neukládá ručně,
- zobrazuje se v seznamu i v detailu,
- při doplnění starší osoby se pořadí automaticky přepočítá.

Osoby bez známého data narození se zařadí za osoby s datem narození.

## 7. Události

Událost může být spojena s jednou nebo více osobami.

Podporované typy zahrnují:

- narození,
- křest,
- sňatek,
- rozvod,
- stěhování,
- maturitu,
- studium,
- vojenskou službu,
- zaměstnání,
- úraz,
- operaci,
- očkování,
- úmrtí,
- pohřeb,
- jinou vlastní událost.

Událost může obsahovat:

- přesné, neúplné nebo přibližné datum,
- období od–do,
- název,
- typ,
- místo,
- popis,
- účastníky a jejich role,
- přílohy,
- zdroje,
- přístupovou úroveň.

Speciální pole události Úmrtí:

- příčina úmrtí.

## 8. Vazby mezi osobami

Vazby jsou univerzální a ukládají se pouze jednou.

Příklady:

- biologický rodič,
- adoptivní rodič,
- nevlastní rodič,
- pěstoun,
- dítě,
- partner,
- manžel,
- sourozenec,
- kmotr,
- poručník,
- vlastní typ vazby.

Aplikace automaticky odvodí opačný směr vazby.

Příklad:

- Jan je otcem Petra,
- Petr je synem Jana.

Název opačné vazby se přizpůsobí pohlaví osoby, pokud je známé.

## 9. Bydliště

Osoba může mít libovolný počet záznamů bydliště.

Každý záznam může obsahovat:

- rok nebo období,
- obec,
- ulici,
- číslo domu,
- úplnou adresu,
- poznámku,
- zdroj,
- přílohy.

## 10. Fotografie

Každá osoba může mít:

- jednu hlavní fotografii,
- libovolný počet dalších fotografií.

Pokud hlavní fotografie neexistuje, zobrazí se silueta busty.

Každá fotografie může obsahovat:

- název,
- popis,
- datum nebo přibližný rok,
- autora,
- původ,
- osoby na fotografii,
- místo,
- zdroj,
- přístupovou úroveň.

## 11. Dokumenty a přílohy

Příloha je univerzální objekt pro:

- obrázky,
- PDF,
- textové dokumenty,
- tabulky,
- audio,
- video,
- ZIP a další soubory.

Stejná příloha může být propojena s více osobami, událostmi, zdroji nebo hrobovými místy.

## 12. Zdravotní informace

Zdravotní informace tvoří samostatnou záložku.

Každý záznam může obsahovat:

- datum,
- název,
- typ,
- popis,
- lékaře nebo zařízení,
- přílohy,
- poznámku,
- přístupovou úroveň.

Typy zahrnují:

- očkování,
- diagnózu,
- vyšetření,
- operaci,
- úraz,
- alergii,
- léky,
- jiný zdravotní záznam.

## 13. Hrobová místa

Hrobové místo je samostatný objekt, nikoli událost.

Může obsahovat:

- název,
- hřbitov,
- obec,
- oddíl,
- řadu,
- číslo hrobu,
- GPS souřadnice,
- fotografie,
- přepis nápisu,
- popis,
- stav existující/zaniklý,
- odkazy na externí databáze.

Jedno hrobové místo může být propojeno s více osobami.

## 14. Viditelnost a zamčený obsah

Navržené úrovně viditelnosti:

- veřejné,
- pouze přihlášení,
- omezené,
- pouze správce.

Pokud uživatel nemá oprávnění:

- aplikace může zobrazit, že sekce nebo záznam existuje,
- nezobrazí jeho obsah,
- zobrazí vysvětlení a případně výzvu k přihlášení.

## 15. Historie změn

U důležitých záznamů se eviduje:

- kdo změnu provedl,
- kdy,
- který objekt a pole změnil,
- původní a nová hodnota,
- případný komentář.

## 16. Mazání

Důležité záznamy se fyzicky nemažou okamžitě.

Použije se:

- archivace,
- měkké odstranění,
- možnost obnovy,
- varování při existujících vazbách.
