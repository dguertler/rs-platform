# Social-Media-Content-Pipeline (The Traffic Machine)

> Quelle: Gemini-Spezifikation (Nutzer-Input). Traffic = Treibstoff für alle
> 5 Umsatz-Säulen (`MONETARISIERUNG.md`). Der technische Generator dazu liegt in
> `instagram/` — Abgleich am Ende dieser Datei.

---

## 🎥 REELS — AI-Doppelmotor für Reichweite (1–2 Videos/Woche)

**Tools**
1. **CapCut (Desktop)** — primäre Produktionszentrale. Export 1080p/4K ohne
   Wasserzeichen. „**Script-to-Video**" für automatische B-Roll, flüssige
   deutsche AI-Stimmen und dynamische **Wort-für-Wort-Untertitel**.
   → Input: das automatisch erzeugte **`reel_script.txt`** aus dem Generator.
2. **Luma Dream Machine** — Spezial-Effekt-Motor (30 Gratis-Generationen/Monat).
   Cineastische, düstere 5-Sek-Clips im Cyberpunk-/Hedgefonds-Look (z. B.
   „glühender Quantencomputer im Serverraum") als High-End-Hintergrund in CapCut.

**Reel-Typen**
- **Typ A — Die Analyse:** teasert eine fundamentale Anomalie an (z. B.
  AMD-Inflexion). **Outro:** „Die komplette Bilanzanalyse mit allen Kurszielen
  findest du im aktuellen Karussell auf meinem Profil!" → speist Säule 0/2/4.
- **Typ B — Der Bot-Beweis:** Aufnahme, wie ein valides Signal **live im
  Telegram-Kanal** aufpoppt, gefolgt vom Chart-Ausbruch. **Outro:** „Link zum
  Premium-Telegram-Kanal in der Bio." → speist **Säule 1** (Hauptumsatz).

## 📑 KARUSSELLS — standardisierter Deep Dive (1 Post/Woche)

**Prinzip:** identisches, standardisiertes Template als Corporate Identity —
nur Text/Zahlen je Aktie tauschen. (Gemini-Vorgabe: Dunkelgrau #121212, weiße
Schrift, Akzent Orange/Neon-Cyan. **Unser Generator** nutzt aktuell Navy #0E1320
+ Royalblau/Grün — Design-Entscheid offen, siehe Abgleich unten.)

**Feste Slide-Architektur (Gemini, 8 Slides):**
1. Cover (aggressiver Click-Hook)
2. Investment-Case (struktureller Kern)
3. Bewertung (historisches KGV vs. Forward-PE & Marge)
4. Das Nadelöhr (größte Risiken & Bremsen)
5. Die 3 Markt-Szenarien (Bull/Base/Bear mit Kurszielen)
6. Technik & Momentum (SMA 50/200, Beta/Volatilität, Einstiegs-Zonen)
7. Profi-Fazit & Peer-Vergleich (Positionsgröße, Alternativen)
8. CTA (Speichern 📌 + Kommentar-Frage + Haftungsausschluss)

---

## Abgleich mit dem vorhandenen Generator (`instagram/`)
Der Generator erzeugt bereits **automatisch** aus `analyses/TICKER.md`:
Karussell (10 Slides) + Reel-Teaser (4 Frames) + `reel.mp4` + `caption.txt` +
**`reel_script.txt`** (genau der CapCut-Input). Befehl:
`python3 -m instagram.generate --analysis TICKER --headline "<Frage/These>"`.

**Deckungsgleich:** Cover-Hook, Investment-Case, Bewertung („KGV-Illusion"),
Nadelöhr/Risiko, 3 Szenarien mit Kurszielen, Profi-Fazit+Peers, Speichern/
Community-CTA, Reel-Outro „Analyse im Karussell".

**Bewusste Abweichungen (Entscheid des Nutzers, ggf. künftig anpassbar):**
- **Kein aktueller Kurs** auf den Slides (Gemini nutzt „$516"). → zeitlos/Compliance.
- **Slide 6 „Technik & Momentum" (SMA/Beta) NICHT enthalten:** GWS-Ampel &
  Breakout werden bewusst herausgefiltert. *Offen:* eine reine Technik-Slide
  (SMA 50/200, Beta, Einstiegszone) **ohne** GWS wäre nachrüstbar, falls gewünscht.
- **Design-Farben:** Navy/Blau statt #121212/Orange — CI-Entscheid offen.
- **Reel Typ B (Bot-Beweis):** erfordert den **Live-Telegram-Kanal** (Säule 1) —
  erst nach dessen Launch produzierbar.

**Nächste mögliche Generator-Aufgaben (für künftige Sessions):**
- Optionale Technik-Slide (ohne GWS) + Orange/Cyan-Theme-Variante.
- PDF-Export der Analyse für den Newsletter (Säule 4).
- Feste Affiliate-Outro-Slide im Wochenpost (Säule 3).
