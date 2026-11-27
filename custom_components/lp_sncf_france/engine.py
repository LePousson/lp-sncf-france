"""Pure data processing for LP SNCF France (no Home Assistant imports).

Everything here is synchronous and CPU-bound: callers run it in the executor.

Sources and join keys
- gares-de-voyageurs   : `id` (Gares & Connexions station id), `codes_uic`
- assistance-psh-pmr   : `id_gare`, `code_uic`
- elevatique           : `gareid`
- GTFS SNCF Voyageurs  : stop ids `StopArea:OCE<uic>` / `StopPoint:OCE<mode>-<uic>`, trip_headsign = train number
- SIRI Lite ET / SX    : `FR:ScheduledStopPoint::<uic>`, TrainNumberRef
"""

from __future__ import annotations

import csv
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timedelta
from typing import Any

from .const import (
    ASSIST_CLOSED,
    ASSIST_MOBILE,
    ASSIST_NONE,
    ASSIST_OPEN,
    ASSIST_UNKNOWN,
    MODE_GTFS,
    MODE_SIRI,
    STATUS_CANCELLED,
    STATUS_DELAYED,
    STATUS_ON_TIME,
    STATUS_SCHEDULED,
    TZ,
)

DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NS = "{http://www.siri.org.uk/siri}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
MINOR_SEVERITIES = {"slight", "noImpact", "verySlight", "unknown", ""}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def norm(text: Any) -> str:
    """Lower-case, accent-free, punctuation-light string for searching."""
    s = unicodedata.normalize("NFKD", str(text or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().replace("-", " ").replace("'", " ").strip()


def parse_dt(value: Any) -> datetime | None:
    """ISO string (naive = Europe/Paris) -> aware datetime in Europe/Paris."""
    if not value:
        return None
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=TZ)
    return d.astimezone(TZ)


def _minute_key(d: datetime | None) -> str:
    return d.strftime("%Y-%m-%dT%H:%M") if d else ""


# ---------------------------------------------------------------------------
# Assistance (PSH/PMR)
# ---------------------------------------------------------------------------
def _hm(text: str) -> int | None:
    text = (text or "").strip()
    if ":" not in text:
        return None
    try:
        h, m = text.split(":", 1)
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def parse_slots(text: str) -> list[tuple[int, int]]:
    """'07:00 - 13:30 / 14:00 - 22:00' -> [(420, 810), (840, 1320)]; end <= start wraps past midnight."""
    out: list[tuple[int, int]] = []
    for part in str(text or "").split("/"):
        if "-" not in part:
            continue
        a, b = part.split("-", 1)
        s, e = _hm(a), _hm(b)
        if s is None or e is None:
            continue
        if e <= s:
            e += 1440
        out.append((s, e))
    return out


def _fmt_hm(minutes: int) -> str:
    minutes %= 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def assistance_from_record(rec: dict | None) -> dict | None:
    if not rec:
        return None
    hours = {d: rec.get(f"horaires_jour_nominal_{d}") or "" for d in DAYS}
    holidays: dict[str, str] = {}
    for i in range(1, 21):
        day = rec.get(f"jour_ferie_{i}")
        if day:
            holidays[str(day)[:10]] = rec.get(f"horaires_jour_ferie_{i}") or ""
    unavailable = [norm(rec.get(f"jour_indisponible_{i}")) for i in range(1, 8) if rec.get(f"jour_indisponible_{i}")]
    return {
        "type": rec.get("typepriseencharge") or "",
        "pricing": rec.get("typetarification") or "",
        "meeting_point": rec.get("lieurendezvousgare") or "",
        "taxi_point": rec.get("lieurendezvoustaxi") or "",
        "first_to_last_train": str(rec.get("premierauderniertrain") or "") == "1",
        "mobile_team": len(unavailable) >= 7,
        "hours": hours,
        "holidays": holidays,
        "unavailable_days": unavailable,
        "since": (rec.get("datestatut") or "")[:10],
    }


def _day_hours(a: dict, d: date) -> tuple[str, bool]:
    iso = d.isoformat()
    if iso in a["holidays"]:
        return a["holidays"][iso], True
    day = DAYS[d.weekday()]
    if day in a["unavailable_days"]:
        return "", False
    return a["hours"].get(day) or "", False


def assistance_status(a: dict | None, when: datetime) -> dict:
    """Assistance state at `when` (aware local datetime)."""
    if not a:
        return {"state": ASSIST_NONE}
    if a["mobile_team"]:
        return {"state": ASSIST_MOBILE}
    today = when.date()
    minute = when.hour * 60 + when.minute
    txt, holiday = _day_hours(a, today)
    slots = parse_slots(txt)
    y_txt, _ = _day_hours(a, today - timedelta(days=1))
    y_slots = [(s - 1440, e - 1440) for (s, e) in parse_slots(y_txt) if e > 1440]
    for s, e in y_slots + slots:
        if s <= minute < e:
            return {"state": ASSIST_OPEN, "until": _fmt_hm(e), "today": txt or "", "holiday": holiday}
    opens = None
    for k in range(8):
        d = today + timedelta(days=k)
        t, _ = _day_hours(a, d)
        for s, _e in parse_slots(t):
            if k > 0 or s > minute:
                opens = datetime(d.year, d.month, d.day, tzinfo=TZ) + timedelta(minutes=s)
                break
        if opens:
            break
    return {
        "state": ASSIST_CLOSED,
        "opens": opens.isoformat() if opens else None,
        "today": txt or "",
        "holiday": holiday,
    }


# ---------------------------------------------------------------------------
# Station reference
# ---------------------------------------------------------------------------
def build_reference(stations: list[dict], assistance: list[dict]) -> dict:
    by_id: dict[str, dict] = {}
    by_uic: dict[str, str] = {}
    amap = {r["id_gare"]: r for r in assistance or [] if r.get("id_gare")}
    for r in stations or []:
        gid = r.get("id")
        if not gid:
            continue
        pos = r.get("position_geographique") or {}
        uics = [u.strip() for u in str(r.get("codes_uic") or "").replace(",", ";").split(";") if u.strip()]
        ar = amap.get(gid)
        if ar and ar.get("code_uic") and str(ar["code_uic"]) not in uics:
            uics.append(str(ar["code_uic"]))
        by_id[gid] = {
            "id": gid,
            "name": r.get("nom") or "",
            "code": r.get("libellecourt") or "",
            "segment": r.get("segment_drg") or "",
            "insee": r.get("codeinsee") or "",
            "uic": uics,
            "latitude": pos.get("lat"),
            "longitude": pos.get("lon"),
            "assistance": assistance_from_record(ar),
            "_n": norm(r.get("nom")),
        }
        for u in uics:
            by_uic[u] = gid
    for gid, ar in amap.items():
        if gid in by_id:
            continue
        u = str(ar.get("code_uic") or "")
        by_id[gid] = {
            "id": gid, "name": ar.get("nom") or "", "code": "", "segment": "", "insee": "",
            "uic": [u] if u else [], "latitude": None, "longitude": None,
            "assistance": assistance_from_record(ar), "_n": norm(ar.get("nom")),
        }
        if u:
            by_uic[u] = gid
    return {"by_id": by_id, "by_uic": by_uic}


def build_lifts(records: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in records or []:
        gid = r.get("gareid")
        if not gid:
            continue
        st = (r.get("etat_de_fonctionnement") or "").upper()
        out.setdefault(gid, []).append({
            "id": r.get("id"),
            "name": r.get("libelle") or "",
            "location": r.get("localisationdescriptive") or "",
            "state": "ok" if st == "OK" else ("ko" if st == "KO" else "unknown"),
        })
    return out


def search_stations(by_id: dict, query: str, limit: int = 15) -> list[dict]:
    toks = [t for t in norm(query).split() if t]
    if not toks:
        return []
    hits = []
    for g in by_id.values():
        n = g["_n"]
        if all(t in n for t in toks):
            hits.append(((0 if n.startswith(toks[0]) else 1, len(n)), g))
    hits.sort(key=lambda x: x[0])
    return [h[1] for h in hits[:limit]]


def public_station(g: dict) -> dict:
    return {k: v for k, v in g.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# GTFS (planned timetable)
# ---------------------------------------------------------------------------
def _uic_of(stop_id: str) -> str:
    s = stop_id or ""
    if s.startswith("StopPoint:") and "-" in s:
        return s.rsplit("-", 1)[1]
    if s.startswith("StopArea:OCE"):
        return s[len("StopArea:OCE"):]
    return s


def _mode_of(stop_id: str) -> str:
    s = stop_id or ""
    if s.startswith("StopPoint:OCE") and "-" in s:
        return s[len("StopPoint:OCE"):].rsplit("-", 1)[0]
    return ""


def gtfs_extract(zip_path: str, uics: list[str], d_from: date, d_to: date) -> dict:
    """Planned calls at the given stations between two dates (local naive ISO times)."""
    want = {(d_from + timedelta(days=i)).strftime("%Y%m%d") for i in range((d_to - d_from).days + 1)}
    uset = set(uics)

    def rd(z: zipfile.ZipFile, name: str):
        return csv.DictReader(io.TextIOWrapper(z.open(name), "utf-8-sig"))

    with zipfile.ZipFile(zip_path) as z:
        feed = next(iter(rd(z, "feed_info.txt")), {}) if "feed_info.txt" in z.namelist() else {}
        services: dict[str, list[str]] = {}
        for r in rd(z, "calendar_dates.txt"):
            if r["date"] in want and r.get("exception_type") == "1":
                services.setdefault(r["service_id"], []).append(r["date"])
        names = {r["stop_id"]: r["stop_name"] for r in rd(z, "stops.txt")}
        routes = {r["route_id"]: r for r in rd(z, "routes.txt")}
        trips = {r["trip_id"]: r for r in rd(z, "trips.txt") if r["service_id"] in services}
        hit = {r["trip_id"] for r in rd(z, "stop_times.txt")
               if r["trip_id"] in trips and _uic_of(r["stop_id"]) in uset}
        seqs: dict[str, list[dict]] = {}
        for r in rd(z, "stop_times.txt"):
            if r["trip_id"] in hit:
                seqs.setdefault(r["trip_id"], []).append(r)

    def to_iso(day: str, hms: str) -> str | None:
        if not hms:
            return None
        h, m, s = (int(x) for x in hms.split(":"))
        base = date(int(day[:4]), int(day[4:6]), int(day[6:8])) + timedelta(days=h // 24)
        return f"{base.isoformat()}T{h % 24:02d}:{m:02d}:{s:02d}"

    out: dict[str, list[dict]] = {u: [] for u in uics}
    for tid, rows in seqs.items():
        rows.sort(key=lambda r: int(r["stop_sequence"]))
        t = trips[tid]
        ro = routes.get(t["route_id"]) or {}
        stops = [(_uic_of(r["stop_id"]), names.get(r["stop_id"], "")) for r in rows]
        for i, r in enumerate(rows):
            u = _uic_of(r["stop_id"])
            if u not in uset:
                continue
            for day in services[t["service_id"]]:
                out[u].append({
                    "date": f"{day[:4]}-{day[4:6]}-{day[6:8]}",
                    "train": (t.get("trip_headsign") or "").strip(),
                    "mode": _mode_of(r["stop_id"]),
                    "line": ro.get("route_long_name") or "",
                    "arr": to_iso(day, r["arrival_time"]) if i > 0 else None,
                    "dep": to_iso(day, r["departure_time"]) if i < len(rows) - 1 else None,
                    "origin": stops[0][1], "origin_uic": stops[0][0],
                    "destination": stops[-1][1], "destination_uic": stops[-1][0],
                    "origin_dep": to_iso(day, rows[0]["departure_time"]),
                    "destination_arr": to_iso(day, rows[-1]["arrival_time"]),
                    "before": [s[1] for s in stops[:i]],
                    "after": [s[1] for s in stops[i + 1:]],
                    "boarding": r.get("pickup_type") != "1",
                    "alighting": r.get("drop_off_type") != "1",
                })
    for u in out:
        out[u].sort(key=lambda c: c["dep"] or c["arr"] or "")
    return {"feed": feed, "stations": out}


# ---------------------------------------------------------------------------
# SIRI Lite (real time)
# ---------------------------------------------------------------------------
def _tx(el: ET.Element | None, name: str) -> str:
    if el is None:
        return ""
    c = el.find(NS + name)
    return (c.text or "").strip() if c is not None else ""


def parse_estimated_timetable(body: bytes, uics: list[str]) -> dict:
    """Journeys calling at at least one of `uics`."""
    us = set(uics)
    ts, out = None, []
    for _ev, el in ET.iterparse(io.BytesIO(body)):
        if ts is None and el.tag == NS + "ResponseTimestamp":
            ts = (el.text or "").strip()
        if el.tag != NS + "EstimatedVehicleJourney":
            continue
        calls, hit = [], False
        for cont in ("RecordedCalls", "EstimatedCalls"):
            ce = el.find(NS + cont)
            if ce is None:
                continue
            for c in ce:
                ref = _tx(c, "StopPointRef")
                u = ref.rsplit("::", 1)[-1] if "::" in ref else ref
                hit = hit or u in us
                try:
                    order = int(_tx(c, "Order") or 0)
                except ValueError:
                    order = 0
                calls.append({
                    "uic": u, "name": _tx(c, "StopPointName"), "o": order,
                    "a_arr": _tx(c, "AimedArrivalTime"), "e_arr": _tx(c, "ExpectedArrivalTime"),
                    "a_dep": _tx(c, "AimedDepartureTime"), "e_dep": _tx(c, "ExpectedDepartureTime"),
                    "p_arr": _tx(c, "ArrivalPlatformName"), "p_dep": _tx(c, "DeparturePlatformName"),
                    "s_arr": _tx(c, "ArrivalStatus"), "s_dep": _tx(c, "DepartureStatus"),
                    "cancelled": _tx(c, "Cancellation") == "true",
                })
        if hit:
            calls.sort(key=lambda c: c["o"])
            fr = el.find(NS + "FramedVehicleJourneyRef")
            trains: list[str] = []
            for t in el.iter(NS + "TrainNumberRef"):
                v = (t.text or "").strip()
                if v and v not in trains:
                    trains.append(v)
                    trains.extend(p for p in v.split("-") if p and p not in trains)
            out.append({
                "key": _tx(fr, "DatedVehicleJourneyRef") or _tx(el, "DatedVehicleJourneyRef") or str(len(out)),
                "date": _tx(fr, "DataFrameRef"),
                "trains": trains,
                "line": _tx(el, "PublishedLineName"),
                "category": _tx(el, "ProductCategoryRef").rstrip(":").split("::")[-1],
                "operator": _tx(el, "OperatorRef").split("::")[-1],
                "origin": _tx(el, "OriginName"), "origin_uic": _tx(el, "OriginRef"),
                "destination": _tx(el, "DestinationName"), "destination_uic": _tx(el, "DestinationRef"),
                "origin_dep": _tx(el, "OriginAimedDepartureTime"),
                "destination_arr": _tx(el, "DestinationAimedArrivalTime"),
                "cancelled": _tx(el, "Cancellation") == "true",
                "calls": calls,
            })
        el.clear()
    return {"timestamp": ts, "journeys": out}


def parse_situations(body: bytes, trains: set[str], uics: set[str]) -> dict:
    """Disruption messages attached to the given trains or stations."""
    out: dict[str, dict[str, list[dict]]] = {"trains": {}, "stations": {}}

    def fr(el: ET.Element, name: str) -> str:
        best = ""
        for s in el.findall(NS + name):
            v = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s.text or "")).strip()
            if s.get(XML_LANG, "").upper() == "FR":
                return v
            best = best or v
        return best

    for _ev, el in ET.iterparse(io.BytesIO(body)):
        if el.tag != NS + "PtSituationElement":
            continue
        if _tx(el, "Progress") not in ("", "published"):
            el.clear()
            continue
        tr = sorted({(t.text or "").strip() for t in el.iter(NS + "TrainNumberRef")} & trains)
        st = set()
        for tag in ("StopPointRef", "StopPlaceRef"):
            for t in el.iter(NS + tag):
                u = (t.text or "").strip().rsplit("::", 1)[-1].split(":")[-1].replace("OCE", "")
                if u in uics:
                    st.add(u)
        if tr or st:
            vp = el.find(NS + "ValidityPeriod")
            msg = {
                "id": _tx(el, "SituationNumber"),
                "severity": _tx(el, "Severity"),
                "summary": fr(el, "Summary")[:200],
                "text": (fr(el, "Detail") or fr(el, "Description"))[:400],
                "start": _tx(vp, "StartTime"),
                "end": _tx(vp, "EndTime"),
            }
            for t in tr:
                out["trains"].setdefault(t, []).append(msg)
            for u in st:
                out["stations"].setdefault(u, []).append(msg)
        el.clear()
    return out


# ---------------------------------------------------------------------------
# Merge planned + real time into a station board
# ---------------------------------------------------------------------------
def _entry(g: dict | None, j: dict | None, c: dict | None) -> dict:
    e: dict[str, Any] = {
        "date": "", "train": "", "mode": "", "line": "", "origin": "", "origin_uic": "",
        "destination": "", "destination_uic": "", "origin_dep": None, "destination_arr": None,
        "destination_arr_exp": None, "before": [], "after": [], "boarding": True, "alighting": True,
        "p_arr": None, "e_arr": None, "p_dep": None, "e_dep": None, "platform": "",
        "x_arr": False, "x_dep": False, "realtime": False, "source": "gtfs" if g else "realtime",
    }
    if g:
        for k in ("date", "train", "line", "origin", "origin_uic", "destination", "destination_uic",
                  "origin_dep", "destination_arr", "before", "after", "boarding", "alighting"):
            e[k] = g[k]
        e["mode"] = MODE_GTFS.get(g["mode"], g["mode"])
        e["p_arr"], e["p_dep"] = g["arr"], g["dep"]
    if j and c:
        e["realtime"] = True
        idx = next((i for i, cc in enumerate(j["calls"]) if cc is c), 0)
        if not g:
            e["date"] = j["date"]
            e["train"] = j["trains"][0] if j["trains"] else ""
            e["mode"] = MODE_SIRI.get(j["category"], j["category"] or "Train")
            for k in ("line", "origin", "origin_uic", "destination", "destination_uic",
                      "origin_dep", "destination_arr"):
                e[k] = j[k]
            e["before"] = [x["name"] for x in j["calls"][:idx]]
            e["after"] = [x["name"] for x in j["calls"][idx + 1:]]
            e["p_arr"] = None if idx == 0 else (c["a_arr"] or None)
            e["p_dep"] = None if idx == len(j["calls"]) - 1 else (c["a_dep"] or None)
        e["line"] = e["line"] or j["line"]
        last = j["calls"][-1] if j["calls"] else None
        if last:
            e["destination_arr_exp"] = last["e_arr"] or last["a_arr"] or None
        e["e_arr"] = c["e_arr"] or c["a_arr"] or None
        e["e_dep"] = c["e_dep"] or c["a_dep"] or None
        e["platform"] = c["p_dep"] or c["p_arr"] or ""
        x = j["cancelled"] or c["cancelled"]
        e["x_arr"] = x or c["s_arr"] == "cancelled"
        e["x_dep"] = x or c["s_dep"] == "cancelled"
    return e


def _messages(sx: dict, train: str, ref: datetime, hide_minor: bool) -> list[dict]:
    out, seen = [], set()
    for m in (sx.get("trains") or {}).get(train) or []:
        if m["id"] in seen or (hide_minor and m["severity"] in MINOR_SEVERITIES):
            continue
        d0, d1 = parse_dt(m["start"]), parse_dt(m["end"])
        if d1 and d1 < ref - timedelta(hours=1):
            continue
        if d0 and d0 > ref + timedelta(hours=12):
            continue
        seen.add(m["id"])
        out.append({"severity": m["severity"], "summary": m["summary"], "text": m["text"]})
    return out


def _assist_at(ref: dict, uic: str, when: datetime | None) -> dict:
    gid = ref["by_uic"].get(str(uic or ""))
    g = ref["by_id"].get(gid) if gid else None
    if not g or when is None:
        return {"state": ASSIST_UNKNOWN}
    return assistance_status(g["assistance"], when)


def build_board(
    uic: str,
    planned: list[dict],
    journeys: list[dict],
    sx: dict,
    ref: dict,
    now: datetime,
    horizon_hours: float,
    rows: int,
    hide_minor: bool,
) -> dict:
    by_train: dict[str, tuple[dict, dict]] = {}
    by_time: dict[str, tuple[dict, dict]] = {}
    for j in journeys:
        c = next((cc for cc in j["calls"] if cc["uic"] == uic), None)
        if c is None:
            continue
        for t in j["trains"]:
            by_train[f"{j['date']}|{t}"] = (j, c)
        for k in ("a_dep", "a_arr"):
            d = parse_dt(c[k])
            if d:
                by_time[_minute_key(d)] = (j, c)

    used: set[str] = set()
    entries = []
    for g in planned:
        m = by_train.get(f"{g['date']}|{g['train']}")
        if not m:
            for k in ("dep", "arr"):
                mk = _minute_key(parse_dt(g[k]))
                if mk and mk in by_time:
                    m = by_time[mk]
                    break
        if m:
            used.add(m[0]["key"])
        entries.append(_entry(g, *(m or (None, None))))
    for j in journeys:
        if j["key"] in used:
            continue
        c = next((cc for cc in j["calls"] if cc["uic"] == uic), None)
        if c is not None:
            entries.append(_entry(None, j, c))

    lo = now - timedelta(minutes=1)
    hi = now + timedelta(hours=horizon_hours)
    result: dict[str, list[dict]] = {}
    for side in ("departures", "arrivals"):
        out = []
        for e in entries:
            if side == "departures":
                if not e["p_dep"] or not e["boarding"]:
                    continue
                tp, te, x = parse_dt(e["p_dep"]), parse_dt(e["e_dep"]), e["x_dep"]
                term, term_uic = e["destination"], e["destination_uic"]
                term_t = parse_dt(e["destination_arr_exp"]) or parse_dt(e["destination_arr"])
                via = e["after"][:8]
            else:
                if not e["p_arr"] or not e["alighting"]:
                    continue
                tp, te, x = parse_dt(e["p_arr"]), parse_dt(e["e_arr"]), e["x_arr"]
                term, term_uic = e["origin"], e["origin_uic"]
                term_t = parse_dt(e["origin_dep"])
                via = e["before"][-8:]
            if tp is None or tp > hi:
                continue
            te = te or tp
            if te < lo and not (x and tp >= lo):
                continue
            delay = int(round((te - tp).total_seconds() / 60)) if e["realtime"] else 0
            if x:
                status = STATUS_CANCELLED
            elif not e["realtime"]:
                status = STATUS_SCHEDULED
            elif delay >= 1:
                status = STATUS_DELAYED
            else:
                status = STATUS_ON_TIME
            out.append({
                "id": f"{e['date']}|{e['train']}",
                "train": e["train"],
                "mode": e["mode"],
                "line": e["line"],
                "terminus": term,
                "via": via,
                "scheduled": tp.isoformat(),
                "expected": te.isoformat(),
                "delay": delay,
                "platform": e["platform"],
                "status": status,
                "realtime": e["realtime"],
                "source": e["source"],
                "messages": _messages(sx, e["train"], tp, hide_minor),
                "assistance_here": _assist_at(ref, uic, te)["state"],
                "assistance_terminus": _assist_at(ref, term_uic, term_t)["state"],
            })
        out.sort(key=lambda r: r["scheduled"])
        result[side] = out[:rows]
    return result
