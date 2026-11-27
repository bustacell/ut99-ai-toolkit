r"""Fun career stats over all scanned demo archives (just for fun, not used for tracking).

usage: python fun_stats.py OUT.json
Reads output\scans\*.events.json (+ .rich.log via assess_archive.demo_stats), output\moments-all.json and the
archive folders (or their triage json when the external drive is unplugged). File dates are cached in
output\demo-dates.json so the external archives still have dates when the drive is not connected.
"""
import collections, datetime, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from assess_archive import demo_stats  # noqa: E402
from ddconfig import ME, OUT, SCANS, UT, DEMO_DIRS, demo_id  # noqa: E402


def _archives():
    """(name, folder, external) for every config demo folder; "DemosArchive8" -> "Archive 8".
    external = on another drive than UT (it may be unplugged; then the triage json stands in)."""
    out, seen = [], set()
    for d in DEMO_DIRS:
        key = os.path.normcase(os.path.normpath(d))
        if key in seen:
            continue
        seen.add(key)
        base = os.path.basename(os.path.normpath(d))
        m = re.search(r"Archive(\d+)$", base, re.I)
        out.append((f"Archive {m.group(1)}" if m else base, d,
                    os.path.splitdrive(d)[0].lower() != os.path.splitdrive(UT)[0].lower()))
    return out


ARCHIVES = _archives()  # name, folder, external
NAME_T = re.compile(r"_(\d{1,2})-(\d{1,2})_(\d{1,2})-(\d{1,2})-(\d{1,2})(-\d+)?$")


def load_json(p, default):
    try:
        return json.load(open(p, encoding="utf-8-sig"))
    except Exception:
        return default


def main():
    dates = load_json(os.path.join(OUT, "demo-dates.json"), {})
    seen = set()
    demos = []  # (archive, external, base name)
    arch_info = []
    for an, folder, ext in ARCHIVES:
        present = os.path.isdir(folder)
        if present:
            names = [n for n in os.listdir(folder) if n.lower().endswith(".dem")]
            for n in names:
                dates[n] = os.path.getmtime(os.path.join(folder, n))
            total_mb = sum(os.path.getsize(os.path.join(folder, n)) for n in names) / 1048576
        else:
            num = re.search(r"(\d+)$", an)
            tri = load_json(os.path.join(OUT, f"archive{num.group(1)}-triage.json"), []) if num else []
            names = [o["name"] for o in tri]
            total_mb = sum(o["mb"] for o in tri)
        scanned = 0
        for n in names:
            # demo ID as the scans are stored (size suffix only when another recording shares the name)
            b = demo_id(os.path.join(folder, n)) if present else os.path.splitext(n)[0]
            if b in seen or not os.path.exists(os.path.join(SCANS, b + ".events.json")):
                continue
            seen.add(b); scanned += 1
            demos.append((an, ext, b))
        arch_info.append(dict(name=an, folder=folder, external=ext, connected=present, files=len(names),
                              gb=round(total_mb / 1024, 1), scanned=scanned))
    json.dump(dates, open(os.path.join(OUT, "demo-dates.json"), "w", encoding="utf-8"))

    C = collections.Counter
    victims, nemesis, weapons, multis, sprees, regulars = C(), C(), C(), C(), C(), C()
    maps_h, maps_k, month_h, month_k, hour_k, wday_h = C(), C(), C(), C(), C(), C()
    mode_n, mode_h = C(), C()
    T = dict(demos=0, hours=0.0, meDemos=0, meHours=0.0, kills=0, deaths=0, suicides=0, caps=0, grabs=0, returns=0,
             covers=0, botKills=0, allKills=0, players=set())
    per_demo, nights = [], collections.defaultdict(lambda: [0, 0, 0.0])
    for an, ext, b in demos:
        ev = load_json(os.path.join(SCANS, b + ".events.json"), {})
        st = demo_stats(b) or {}
        L = float(ev.get("length") or 0)
        mode = st.get("mode", "?")
        T["demos"] += 1; T["hours"] += L / 3600
        mode_n[mode] += 1; mode_h[mode] += L / 3600
        k = d = 0; plist = set()
        for e in ev.get("events", []) or []:
            ty = e.get("type")
            if ty == "kill":
                T["allKills"] += 1
                kk, vv = (e.get("killer") or "").strip(), (e.get("victim") or "").strip()
                plist.update([kk, vv])
                if kk == ME and vv == ME:
                    T["suicides"] += 1
                elif kk == ME:
                    k += 1; victims[vv] += 1; weapons[(e.get("weapon") or "?").strip()] += 1
                    if vv.upper().endswith("-BOT"): T["botKills"] += 1
                elif vv == ME:
                    d += 1; nemesis[kk] += 1
            elif e.get("player", "").strip() == ME:
                if ty == "multikill":
                    lab = e.get("label", "")
                    if re.fullmatch(r"(\S )+\S( (\S ?)+)?", lab):  # "M O N S T E R K I L L" -> "Monster Kill"
                        lab = {"MONSTERKILL": "Monster Kill", "HOLYSHIT": "Holy Shit",
                               "LUDICROUSKILL": "Ludicrous Kill"}.get(lab.replace(" ", ""), lab.replace(" ", ""))
                    multis[lab.title()] += 1
                elif ty == "spree": sprees[e.get("label", "")] += 1
                elif ty == "flag_captured": T["caps"] += 1
                elif ty == "flag_has": T["grabs"] += 1
                elif ty in ("flag_returns", "flag_returned"): T["returns"] += 1
                elif ty == "cover": T["covers"] += 1
        plist.discard(""); T["players"].update(plist)
        me_in = ME in plist
        if not me_in:
            continue
        for p in plist - {ME}: regulars[p] += 1
        T["meDemos"] += 1; T["meHours"] += L / 3600; T["kills"] += k; T["deaths"] += d
        mp = st.get("map") or NAME_T.sub("", b)
        maps_h[mp] += L / 3600; maps_k[mp] += k
        ts = dates.get(b + ".dem")
        m = NAME_T.search(b)
        if ts:
            dt = datetime.datetime.fromtimestamp(ts)
            if m:  # recording start from the name; the year from the file date (the end of the recording)
                try:
                    st_dt = dt.replace(month=int(m.group(1)), day=int(m.group(2)), hour=int(m.group(3)),
                                       minute=int(m.group(4)), second=int(m.group(5)))
                    if st_dt > dt + datetime.timedelta(days=1): st_dt = st_dt.replace(year=dt.year - 1)
                    dt = st_dt
                except ValueError:
                    pass
            month = dt.strftime("%Y-%m"); month_h[month] += L / 3600; month_k[month] += k
            hour_k[dt.hour] += L / 3600; wday_h[dt.strftime("%a")] += L / 3600
            night = (dt - datetime.timedelta(hours=8)).strftime("%Y-%m-%d")  # a night counts from 8:00 to 8:00
            nights[night][0] += k; nights[night][1] += d; nights[night][2] += L / 3600
        per_demo.append(dict(demo=b, archive=an, external=ext, map=mp, mode=mode, minutes=round(L / 60, 1), kills=k, deaths=d))

    mom = [x for x in load_json(os.path.join(OUT, "moments-all.json"), []) if x.get("demo", "")[:-4] in seen]
    by_t = collections.defaultdict(list)
    for x in mom:
        if x.get("me"): by_t[x["type"]].append(x)

    def best(t, key):
        L = [x for x in by_t.get(t, []) if key(x) is not None]
        if not L: return None
        x = max(L, key=key)
        return dict(demo=x["demo"], t=round(x["t"], 1), victims=x.get("victims", []), metrics=x.get("metrics", {}))

    def plausible(x):
        m = x.get("metrics", {}); fl = m.get("flight") or 0
        return fl > 0 and ((m.get("shooterMoveH", 0) ** 2 + m.get("shooterMoveV", 0) ** 2) ** .5) / fl < 2600

    top_demo = max(per_demo, key=lambda r: r["kills"], default=None)
    kd_demo = max((r for r in per_demo if r["kills"] >= 40), key=lambda r: r["kills"] / max(1, r["deaths"]), default=None)
    best_night = max(nights.items(), key=lambda x: x[1][0], default=None)
    R = dict(
        player=ME, generated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), archives=arch_info,
        totals=dict(demos=T["demos"], hours=round(T["hours"], 1), meDemos=T["meDemos"], meHours=round(T["meHours"], 1),
                    kills=T["kills"], deaths=T["deaths"], kd=round(T["kills"] / max(1, T["deaths"]), 2),
                    suicides=T["suicides"], caps=T["caps"], grabs=T["grabs"], returns=T["returns"], covers=T["covers"],
                    botKills=T["botKills"], allKills=T["allKills"], uniquePlayers=len(T["players"]),
                    combos=len(by_t.get("combo", [])), airkills=len(by_t.get("airkill", [])),
                    longshots=len(by_t.get("longshot", [])), saves=len(by_t.get("flagsave", [])),
                    nights=len(nights)),
        modes=[dict(mode=k, demos=mode_n[k], hours=round(mode_h[k], 1)) for k in sorted(mode_n, key=lambda m: -mode_h[m])],
        victims=victims.most_common(15), nemesis=nemesis.most_common(15),
        rivals=sorted(({"name": p, "kills": victims[p], "deaths": nemesis[p]} for p in set(victims) | set(nemesis)
                       if victims[p] + nemesis[p] >= 150), key=lambda r: -(r["kills"] + r["deaths"]))[:20],
        regulars=regulars.most_common(15), weapons=weapons.most_common(8),
        multis=multis.most_common(), sprees=sprees.most_common(),
        maps=[dict(map=k, hours=round(v, 1), kills=maps_k[k]) for k, v in maps_h.most_common(15)],
        months=[dict(month=k, hours=round(month_h[k], 1), kills=month_k[k]) for k in sorted(month_h)],
        hours=[round(hour_k[h], 1) for h in range(24)],
        weekdays=[dict(day=d, hours=round(wday_h[d], 1)) for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]],
        records=dict(
            topDemo=top_demo, kdDemo=kd_demo,
            bestNight=dict(date=best_night[0], kills=best_night[1][0], deaths=best_night[1][1],
                           hours=round(best_night[1][2], 1)) if best_night else None,
            longestDemo=max(per_demo, key=lambda r: r["minutes"], default=None),
            movingCombo=best("combo", lambda x: (x["metrics"].get("ballTravel", 0) + x["metrics"].get("shooterMoveH", 0)
                                                 + 2 * x["metrics"].get("shooterMoveV", 0)) if plausible(x) else None),
            longestShot=best("longshot", lambda x: x["metrics"].get("distance")),
            highestAirKill=best("airkill", lambda x: x["metrics"].get("victimHeight")),
            bestCap=best("capture", lambda x: x["metrics"].get("frags")),
            biggestCombo=best("combo", lambda x: len(x.get("victims", []))),
        ),
    )
    json.dump(R, open(sys.argv[1], "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    t = R["totals"]
    print(f"demos {t['demos']} ({t['hours']} h), with me {t['meDemos']} ({t['meHours']} h), kills {t['kills']}, "
          f"deaths {t['deaths']}, K/D {t['kd']}, caps {t['caps']}, combos {t['combos']}")


if __name__ == "__main__":
    main()
