# LP SNCF France

Home Assistant integration for French railway stations, built **only on SNCF open data — no API key, no account**.

*[Français plus bas](#français)*

## Features

- **Departures & arrivals boards** merging the planned timetable (GTFS) with real time (SIRI Lite): expected time, delay, platform, cancellations, calling points.
- **Trains missing from the SNCF timetable** (e.g. regional trains run by another operator) are added from the real-time feed as they approach.
- **Disruption messages** attached to each train.
- **PSH/PMR assistance**: whether the station's assistance service is open right now, its meeting point and hours — and, for every train, whether assistance is open **at departure and at arrival** at the time of the train.
- **Lifts & escalators**: live working state (hourly), with a problem sensor for notifications.
- One set of downloads shared by all configured stations.

## Installation

### HACS (custom repository)
1. HACS → ⋮ → *Custom repositories* → add `https://github.com/LePousson/lp-sncf-france`, category **Integration**.
2. Install **LP SNCF France**, restart Home Assistant.

### Manual
Copy `custom_components/lp_sncf_france` into your `config/custom_components/` folder and restart.

## Configuration
*Settings → Devices & services → Add integration → LP SNCF France*, type part of the station name, pick it.
Add one entry per station. Options: rows per board, time horizon, hide minor messages.

## Entities (per station)

| Entity | Description |
|---|---|
| `sensor.<station>_next_departure` | Timestamp of the next departure; full board in the `rows` attribute |
| `sensor.<station>_next_arrival` | Same for arrivals |
| `sensor.<station>_psh_pmr_assistance` | `open` / `closed` / `mobile` / `none` + meeting point, hours |
| `sensor.<station>_lifts_out_of_order` | Number of lifts/escalators out of order (+ list) |
| `binary_sensor.<station>_lift_outage` | On when at least one lift is out of order |
| `binary_sensor.<station>_real_time_feed` | Real-time feed availability (diagnostic) |

Each row of a board contains: `train`, `mode`, `line`, `terminus`, `via`, `scheduled`, `expected`, `delay`, `platform`, `status` (`scheduled`, `on_time`, `delayed`, `cancelled`), `realtime`, `messages`, `assistance_here`, `assistance_terminus`.

## Actions
- `lp_sncf_france.get_board` — board on demand (station, direction, rows, horizon) → response.
- `lp_sncf_france.search_stations` — search the national station reference → response.
- `lp_sncf_france.refresh` — force a refresh.

## Data sources
- [SNCF Open Data](https://ressources.data.sncf.com): `gares-de-voyageurs`, `assistance-psh-pmr`, `etat-fonctionnement-elevatique-gare`, GTFS SNCF Voyageurs.
- Real time: SIRI Lite feeds published on [transport.data.gouv.fr](https://transport.data.gouv.fr).

Data © SNCF / SNCF Gares & Connexions — **ODbL**. This project is not affiliated with SNCF.

## Limitations
- Trains absent from the SNCF GTFS only appear once they are in the real-time feed (roughly the coming hour).
- Real-time coverage is guaranteed by SNCF for TGV and Intercités; TER coverage depends on the region.

---

## Français

Intégration Home Assistant pour les gares françaises, **uniquement à partir de l'open data SNCF — sans clé ni compte**.

- **Panneaux départs / arrivées** fusionnant horaires théoriques (GTFS) et temps réel (SIRI Lite) : heure estimée, retard, voie, suppressions, dessertes.
- **Trains absents du GTFS SNCF** (ex. TER d'un autre opérateur) ajoutés depuis le temps réel à leur approche.
- **Messages d'incident** par train.
- **Assistance PSH/PMR** : ouverte ou non à l'instant, point de rendez-vous, horaires — et pour chaque train, ouverture de l'assistance **au départ et à l'arrivée** à l'heure du train.
- **Ascenseurs et escalators** : état en direct (mise à jour horaire), capteur de panne pour les notifications.

Installation : HACS → dépôts personnalisés → `https://github.com/LePousson/lp-sncf-france` (catégorie *Intégration*), puis *Paramètres → Appareils et services → Ajouter → LP SNCF France*.

Données © SNCF / SNCF Gares & Connexions — licence **ODbL**. Projet indépendant, non affilié à la SNCF.
