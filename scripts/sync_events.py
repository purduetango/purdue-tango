#!/usr/bin/env python3
"""Optionally refresh data/events.js from a feed. Standard library only.

Set FEED_URL to the RSS feed https://boilerlink.purdue.edu/events.rss (HOST_FILTER keeps only your club), or:
  * an .ics calendar URL (e.g. an iCal export your BoilerLink org page offers), or
  * a BoilerLink/Engage JSON endpoint (items under "value": name, startsOn, endsOn, ...).
If FEED_URL is unset, nothing happens and events.js is edited by hand.

"""
import html, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Indiana/Indianapolis")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "events.js")
BASE = "https://boilerlink.purdue.edu"

def local(dt_utc):
    return dt_utc.astimezone(TZ).strftime("%Y-%m-%dT%H:%M")

def from_json(raw):
    items = raw.get("value", raw) if isinstance(raw, dict) else raw
    out = []
    for it in items:
        s = datetime.fromisoformat(it["startsOn"].replace("Z", "+00:00"))
        e = datetime.fromisoformat((it.get("endsOn") or it["startsOn"]).replace("Z", "+00:00"))
        if s.tzinfo is None: s = s.replace(tzinfo=timezone.utc)
        if e.tzinfo is None: e = e.replace(tzinfo=timezone.utc)
        img = it.get("imagePath")
        out.append({"id": str(it["id"]), "title": it["name"], "start": local(s), "end": local(e),
                    "location": it.get("location") or "TBA",
                    "description": re.sub(r"<[^>]+>", "", it.get("description") or "")[:400].strip(),
                    "url": f"{BASE}/event/{it['id']}",
                    "image": f"https://se-images.campuslabs.com/clink/images/{img}" if img else ""})
    return out

def from_rss(text):
    """BoilerLink/Engage RSS (https://boilerlink.purdue.edu/events.rss)."""
    out = []
    for it in ET.fromstring(text).iter("item"):
        tag = lambda n: [x.text or "" for x in it if x.tag.split("}")[-1] == n]
        gmt = lambda v: datetime.strptime(v, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
        st, en = gmt(tag("start")[0]), gmt(tag("end")[0])
        m = re.search(r'p-description description">(.*?)</div>', it.findtext("description") or "", re.S)
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(1) if m else "")).replace("\xa0", " ")).strip()
        enc = it.find("enclosure")
        guid = it.findtext("guid")
        out.append({"id": guid.rsplit("/", 1)[-1], "title": it.findtext("title"), "start": local(st), "end": local(en),
                    "location": (tag("location") or ["TBA"])[0] or "TBA", "description": desc, "url": guid,
                    "image": enc.get("url").split("?")[0] + "?preset=med-w" if enc is not None else "",
                    "hosts": tag("host")})
    return out

def from_ics(text):
    text = re.sub(r"\r?\n[ \t]", "", text)
    out = []
    for blk in re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", text, re.S):
        def g(k):
            m = re.search(rf"^{k}[^:\n]*:(.*)$", blk, re.M)
            return m.group(1).strip() if m else ""
        def dt(v):
            v = v.strip()
            if v.endswith("Z"):
                return local(datetime.strptime(v, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc))
            return datetime.strptime(v[:15], "%Y%m%dT%H%M%S").strftime("%Y-%m-%dT%H:%M")
        un = lambda s: s.replace("\\n", " ").replace("\\,", ",").replace("\\;", ";")
        out.append({"id": g("UID"), "title": un(g("SUMMARY")), "start": dt(g("DTSTART")),
                    "end": dt(g("DTEND") or g("DTSTART")), "location": un(g("LOCATION")) or "TBA",
                    "description": un(g("DESCRIPTION"))[:400], "url": g("URL") or BASE + "/events?query=tango", "image": ""})
    return out

def main():
    url = os.environ.get("FEED_URL", "").strip()
    if not url:
        print("FEED_URL not set; leaving events.js untouched."); return
    req = urllib.request.Request(url, headers={"User-Agent": "PurdueTangoClubSync/1.0"})
    try:
        body = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    except Exception as ex:
        print("Feed fetch failed (%s); keeping existing events." % ex); return
    if "BEGIN:VCALENDAR" in body[:200]: events = from_ics(body)
    elif body.lstrip().startswith("<"): events = from_rss(body)
    else: events = from_json(json.loads(body))
    host = os.environ.get("HOST_FILTER", "La Milonguera").lower()
    q = os.environ.get("FILTER", "").lower()
    now = datetime.now(TZ).strftime("%Y-%m-%dT%H:%M")
    events = [e for e in events if e["end"] >= now
              and (not host or any(host in h.lower() for h in e.get("hosts", [])) )
              and q in (e["title"] + e["description"]).lower()]
    if not events:
        print("Feed returned no matching events; keeping existing file."); return
    for e in events: e.pop("hosts", None)
    events.sort(key=lambda e: e["start"])
    open(OUT, "w").write("// Edit this list. Keep the window.EVENTS = [...] wrapper.\nwindow.EVENTS = " + json.dumps(events, indent=2) + ";\n")
    print(f"Wrote {len(events)} events.")

if __name__ == "__main__":
    main()
