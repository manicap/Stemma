# Funkční specifikace

**Dokument:** 02  
**Verze:** 0.1  
**Stav:** pracovní návrh  
**Datum revize:** 14. 7. 2026

## 1. Hlavní obrazovka

Desktopové rozhraní používá dvousloupcový model:

- vlevo je trvale viditelný seznam osob,
- nad seznamem je vyhledávání s našeptávačem,
- vpravo je detail právě vybrané osoby,
- kliknutí na jinou osobu změní pouze detail vpravo,
- vybraná osoba je v seznamu zvýrazněna.

Na mobilním zařízení bude seznam dostupný jako vysouvací nebo sbalitelný panel, bez ztráty kontextu detailu osoby.

## 2. Seznam osob

Každý řádek obsahuje minimálně:

- jméno a příjmení,
- automaticky dopočítanou římskou číslici u shodných jmen,
- rok narození a úmrtí, jsou-li známé,
- označení vybrané osoby.

Výchozí řazení:

1. příjmení,
2. jméno,
3. datum narození.

Vyhledávání pracuje minimálně s:

- jménem,
- příjmením,
- rodným příjmením,
- dalšími jmény,
- přezdívkou,
- rokem narození.

Vyhledávání nerozlišuje velikost písmen a je tolerantní k diakritice.

## 3. Detail osoby

Záhlaví detailu obsahuje:

- hlavní fotografii nebo výchozí siluetu busty,
- celé jméno,
- rodné příjmení,
- římskou číslici,
- roky života,
- automaticky vypočítaný věk.

Navržené záložky:

- Přehled,
- Události,
- Vazby,
- Bydliště,
- Fotografie,
- Dokumenty,
- Zdravotní informace,
- Hrobové místo,
- Zdroje,
- Historie změn.

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
