# RS-Platform — Claude Code Anweisungen

## Git-Regeln

- Alle Änderungen direkt auf `master` pushen (kein Feature-Branch, kein PR, außer explizit gewünscht)
- Bei jedem Commit den Git-Hash im Chat ausgeben, z.B.: `Committed: a3f92c1`
- Commit-Messages auf Deutsch oder Englisch, klar und beschreibend

## Analyse-Workflow

Wenn der Nutzer schreibt `analysiere TICKER … lies analyses/PROMPT.md`:
1. `analyses/PROMPT.md` lesen — dort stehen Prompt, Struktur und Formatregeln
2. `analyses/sndk.md` als Format-Referenz nutzen
3. Fundamentaldaten, Kurs und RS-Score kommen im Prompt mit — nicht selbst recherchieren
4. Fertige Analyse als `analyses/TICKER.md` speichern und direkt auf `master` pushen
5. Git-Hash nach dem Commit ausgeben
