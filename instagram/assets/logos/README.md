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

## Woher die Logos? (Claude soll dort zuerst suchen)
**Bevorzugt von der offiziellen Unternehmensseite** — in dieser Reihenfolge:
1. **Brand-/Media-/Newsroom-/Presse-Portal** der AG (oft „Brand Assets",
   „Media Kit", „Logo Download"). Beispiele: `amplify.amd.com` (AMD),
   `nvidianews.nvidia.com` (NVIDIA), `news.microsoft.com` → „Brand & Logos".
2. **Investor-Relations-Seite** (Footer/Presse → Logo-Pack).
3. Notfalls neutraler Logo-Dienst (z. B. logo.dev/Clearbit über die Firmendomain).

Bevorzugt **PNG mit Transparenz** (oder SVG → als PNG exportieren), heller
Logo-Look für den dunklen Cover-Hintergrund.

> **Hinweis Claude-Cloud:** Der direkte Download ist in der Cloud durch die
> Firewall blockiert (`Host not in allowlist`). Claude soll das passende Logo
> **auf der Firmenseite suchen und die URL nennen**; die eigentliche Bilddatei
> lädt der Nutzer dann im Chat hoch (oder besorgt sie lokal mit offenem Netz).
> Claude legt sie anschließend hier als `<TICKER>.png` ab und committet sie.

> Markenrechte beachten: Firmenlogos sind geschützt. Nutzung im redaktionellen
> Kontext (Aktienanalyse, Berichterstattung) ist i. d. R. zulässig; keine
> Verfälschung, kein Eindruck einer Partnerschaft/Empfehlung durch das
> Unternehmen.
