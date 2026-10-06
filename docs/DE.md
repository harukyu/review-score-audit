# Zusammengefasste Bewertungen nachvollziehbar prüfen

Dieses lokale Entwicklerwerkzeug kontrolliert die Berechnung und ausgewählte Datenangaben eines zusammengefassten Bewertungsscores. Es verwendet manuell eingetragene Plattformdurchschnitte und Bewertungszahlen.

## Start

1. Vorabversion herunterladen und entpacken. Python ab 3.10 wird benötigt.
2. `examples/sources.json` als Vorlage für eine eigene lokale JSON-Datei verwenden.
3. Pro Quelle eine eindeutige Kennung, Bewertung, Anzahl, Skala, Datenstand und gegebenenfalls einen Profil-Link eintragen.
4. Bericht erstellen:

```sh
python3 review_score_audit.py quellen.json --as-of=2026-10-06 --format=json
```

Das Datum legt den Vergleichszeitpunkt fest; ohne Angabe gilt das lokale Tagesdatum. Daten über 90 Tage alt erzeugen eine Warnung. Die Grenze ist mit `--max-age-days` einstellbar.

## Berechnung

Die Gewichtung erfolgt nach den angegebenen Bewertungszahlen. Im erfundenen Beispiel ergeben 120 Bewertungen mit 4,8 und 30 mit 4,2 einen gewichteten Wert von 4,68. Die Quellen haben 80 % beziehungsweise 20 % Gewicht.

Die Standardskala ist 1 bis 5. Andere Skalen werden erst mit `--allow-mixed-scales` linear umgerechnet; die Warnung bleibt sichtbar. Prüfe die tatsächliche Skala jeder Plattform. Unterschiedliche Bewertungssysteme sind durch eine mathematische Umrechnung allein nicht inhaltlich vergleichbar.

## Hinweise lesen

- Fehlende oder alte Datenstände und fehlende Quellenlinks erzeugen Warnungen.
- Zukunftsdaten, mehrfach verwendete Profil-Links und Skalenumrechnung ohne ausdrückliche Freigabe erzeugen Fehler.
- Bei Fehlern wird kein Gesamtscore ausgegeben.
- Quellen ohne Bewertungen werden nicht gewichtet.
- Der Bericht benötigt keine einzelnen Rezensionen, Namen oder E-Mail-Adressen.

Die Summe der Plattformzahlen ist keine Zahl unterschiedlicher Personen. Rezensionen können sich überschneiden, und Plattformdurchschnitte können bereits gerundet sein. Das Werkzeug fragt keine Plattform ab und bestätigt keine Echtheit von Bewertungen.

Version 0.1.0 ist eine Vorabversion. GitHub kontrolliert Syntax und Paketbau; das ersetzt keine umfassenden Funktionstests. Das Tool erzeugt weder ein Website-Widget noch strukturierte Bewertungsdaten für Suchmaschinen.

Entwickelt von [Nakaryu GmbH](https://nakaryu.de), MIT-Lizenz. Das veröffentlichte Werkzeug ist neu implementiert und enthält keinen Code eures kostenpflichtigen Bewertungs-Widgets. Details stehen in der englischen [README](../README.md).
