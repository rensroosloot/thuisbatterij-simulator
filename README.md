# Thuisbatterij Simulator

Lokale simulator voor het analyseren van een thuisbatterij op basis van historische
P1e-, prijs- en Home Assistant-data. Het doel is om batterijmodi en batterijgroottes
te vergelijken voor de situatie waarin salderen stopt.

## Status

Documentatiefase afgerond:

- URS-001 v1.6 goedgekeurd
- FD-001 v1.8 goedgekeurd
- DS-001 v1.2 goedgekeurd
- TP-001 v1.1 goedgekeurd

Implementatie is gestart met de `DataManager` en eerste unit tests.

## Lokaal starten

```powershell
start.bat
```

Of handmatig:

```powershell
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
streamlit run src/main.py
```

## Let op

De map `resources/` bevat persoonlijke brondata en wordt niet in git opgenomen.

