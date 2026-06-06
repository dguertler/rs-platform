# Firmenlogos für Analyse-Cover

Hier liegen die Logos der Aktiengesellschaften, die auf der **ersten Slide**
eines Analyse-Posts angezeigt werden (Grid-Unterscheidung: Wochenpost =
AI-Alpha-Marke, Analyse = Firmenlogo).

## Ablage-Konvention
- Dateiname = **Ticker** wie in `analyses/` (Punkt durch `_` oder weglassen):
  - `AMD.png`, `MU.png`, `NXPI.png`
  - `SIE_DE.png` **oder** `SIE.DE.png` (beides wird gefunden)
- Format: **PNG mit transparentem Hintergrund** bevorzugt (auch `.webp`,
  `.jpg`/`.jpeg` möglich). Groß-/Kleinschreibung egal.
- Empfehlung: möglichst quadratisch oder breit, mind. ~400 px Kantenlänge,
  heller/weißer Logo-Look auf transparent (der Cover-Hintergrund ist dunkles
  Navy). Transparente Ränder werden automatisch beschnitten und das Logo
  proportional in das Cover-Panel eingepasst.

## Fehlt ein Logo?
Dann fällt der Cover automatisch auf eine **Wortmarke** zurück (Ticker groß +
Firmenname). Der Generator gibt beim Lauf einen Hinweis aus, welches Logo fehlt
und unter welchem Dateinamen es erwartet wird.

## Woher die Logos?
Der automatische Download aus dem Netz ist in der Claude-Cloud blockiert
(Firewall). Logos daher manuell besorgen (z. B. von der Investor-Relations-/
Presse-Seite des Unternehmens oder einem Logo-Dienst) und hier ablegen. Lokal
mit offenem Netz lässt sich das später optional automatisieren.

> Markenrechte beachten: Firmenlogos sind geschützt. Nutzung im redaktionellen
> Kontext (Aktienanalyse, Berichterstattung) ist i. d. R. zulässig; keine
> Verfälschung, kein Eindruck einer Partnerschaft/Empfehlung durch das
> Unternehmen.
