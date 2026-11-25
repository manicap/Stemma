# Changelog po krocích

Každá úloha (ruční i od agenta v Cezaru) přidá do této složky jeden krátký, lidsky čitelný záznam:
`RRRR-MM-DD-<krátký-název>.md` podle [šablony](_sablona.md).

Proč samostatné soubory: víc úloh může běžet souběžně a jeden společný soubor by si navzájem přepisovaly.
Souhrnný [`docs/CHANGELOG.md`](../CHANGELOG.md) se z těchto záznamů doplní při uzavření verze (např. RC 0.2).

Workflow `slice` v Cezaru úlohu bez nového záznamu vrátí agentovi.
