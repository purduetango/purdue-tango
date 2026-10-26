#!/usr/bin/env python3
"""Generate (and optionally send) tango announcement emails. Standard library only.

Wording comes from data/email.json (greeting, signature, one template per class type).

Env:
  MODE            per_event (default: on the day of each event, one email per event) | digest
                  (one email for the next DAYS days; only sends on Mondays unless FORCE=1)
  DRY_RUN         "1" (default) writes previews to out/ and sends nothing; "0" sends
  GMAIL_USER, GMAIL_APP_PASSWORD   Gmail address + 16-char app password
  TO_ADDR         default tangoannouncements@lists.purdue.edu
  SITE_URL        public URL of the site
  DAYS            digest look-ahead window, default 7
  TODAY           pretend today is this date (YYYY-MM-DD), for previews
  ALLOW_SAMPLE    "1" to include entries flagged "sample": true
"""
import html, json, os, re, smtplib, ssl
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from zoneinfo import ZoneInfo

ROOT = os.path.join(os.path.dirname(__file__), "..")
TZ = ZoneInfo("America/Indiana/Indianapolis")
TO = os.environ.get("TO_ADDR", "tangoannouncements@lists.purdue.edu")
SITE = os.environ.get("SITE_URL", "https://YOUR-USER.github.io/purdue-tango/")
MODE = os.environ.get("MODE", "per_event")
DRY = os.environ.get("DRY_RUN", "1") != "0"
DAYS = int(os.environ.get("DAYS", "7"))
TODAY = date.fromisoformat(os.environ["TODAY"]) if os.environ.get("TODAY") else datetime.now(TZ).date()
CFG = json.load(open(os.path.join(ROOT, "data", "email.json")))
h = html.escape

def load():
    raw = open(os.path.join(ROOT, "data", "events.js")).read()
    ev = json.loads(raw[raw.rindex("window.EVENTS =") + 15:].rsplit(";", 1)[0])
    last = TODAY + timedelta(days=DAYS - 1 if MODE == "digest" else 0)
    keep = [e for e in ev if TODAY <= datetime.fromisoformat(e["start"]).date() <= last
            and (not e.get("sample") or os.environ.get("ALLOW_SAMPLE") == "1")]
    return sorted(keep, key=lambda e: e["start"])

def span(e):
    """7.00-8.30pm, or 11.00am-1.00pm when the halves differ."""
    s, f = datetime.fromisoformat(e["start"]), datetime.fromisoformat(e.get("end") or e["start"])
    t = lambda d: f"{d:%-I}.{d:%M}"
    ap = lambda d: f"{d:%p}".lower()
    return f"{t(s)}-{t(f)}{ap(f)}" if ap(s) == ap(f) else f"{t(s)}{ap(s)}-{t(f)}{ap(f)}"

def template(e):
    title = e["title"].lower()
    return next((c for c in CFG["classes"] if c["match"].lower() in title), CFG["fallback"])

def fill(s, e):
    return s.format(time=span(e), location=e.get("location") or "TBA", title=e["title"],
                    description=e.get("description", "")).strip()

def para(s):
    # Escape, then turn bare links into clickable ones.
    return re.sub(r"(https?://\S+)", r'<a href="\1" style="color:#7a1f2e">\1</a>', h(s))

def card(e, kicker):
    img = e.get("image", "")
    pic = f'<img src="{h(img)}" alt="" width="498" style="display:block;width:100%;height:auto;border:0">' if img.startswith("http") else ""
    return f'''<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e6dccf;border-left:3px solid #7a1f2e;margin:6px 0 22px"><tr><td>{pic}
<div style="padding:16px 20px 18px"><div style="font:11px Arial,sans-serif;letter-spacing:3px;text-transform:uppercase;color:#a8842f">{h(kicker)}</div>
<div style="font:22px Georgia,serif;color:#2a1a1d;padding:6px 0 2px">{h(e["title"])}</div>
<div style="font:14px Arial,sans-serif;color:#7a6a6c">{h(e.get("location") or "TBA")}</div>
<div style="padding-top:12px"><a href="{h(e["url"])}" style="font:11px Arial,sans-serif;letter-spacing:3px;text-transform:uppercase;color:#7a1f2e;text-decoration:none;border-bottom:1px solid #7a1f2e">Details &amp; RSVP</a></div></div></td></tr></table>'''

def letter(paragraphs, cards):
    p = lambda s: f'<p style="margin:0 0 16px;font:16px/1.6 Georgia,serif;color:#2a1a1d">{s}</p>'
    body = (p(h(CFG["greeting"])) + "".join(p(para(x)) for x in paragraphs) + cards
            + p("<br>".join(h(x) for x in CFG["signature"])))
    return f'''<!doctype html><html><body style="margin:0;background:#f3ece4"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fffdfa">
<tr><td style="background:#1a1214;padding:16px 30px;font:11px Arial,sans-serif;letter-spacing:5px;color:#c9a45c;text-align:center">PURDUE LA MILONGUERA TANGO CLUB</td></tr>
<tr><td style="padding:30px">{body}</td></tr>
<tr><td style="padding:20px 30px;background:#f3ece4;font:12px Arial,sans-serif;color:#7a6a6c;text-align:center">See every event and photo at <a href="{h(SITE)}" style="color:#7a1f2e">{h(SITE)}</a></td></tr>
</table></td></tr></table></body></html>'''

def text(paragraphs, events):
    links = "".join(f"{e['title']} ({span(e)}, {e.get('location') or 'TBA'}): {e['url']}\n" for e in events)
    return "\n\n".join([CFG["greeting"], *paragraphs, links.strip(), "\n".join(CFG["signature"])]) + f"\n\nAll events & photos: {SITE}\n"

def messages(events):
    """(subject, html, text) per email."""
    if MODE == "digest":
        intro = ["Here is what we have coming up this week:"]
        kick = lambda e: f"{datetime.fromisoformat(e['start']):%A, %b} {datetime.fromisoformat(e['start']).day} · {span(e)}"
        cards = "".join(card(e, kick(e)) for e in events)
        return [(f"Tango this week: {len(events)} event{'s' if len(events) > 1 else ''}", letter(intro, cards), text(intro, events))]
    out = []
    for e in events:
        t = template(e)
        paras = [fill(x, e) for x in t["paragraphs"]]
        subj = f"{fill(t['subject'], e)} · {span(e)} · {e.get('location') or 'TBA'}"
        out.append((subj, letter(paras, card(e, f"Today · {span(e)}")), text(paras, [e])))
    return out

def main():
    if MODE == "digest" and TODAY.weekday() != 0 and os.environ.get("FORCE") != "1":
        print("Digest mode only sends on Mondays."); return
    events = load()
    if not events:
        print("No events in the window; nothing to send."); return
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    user = os.environ.get("GMAIL_USER", "club@example.com")
    msgs = []
    for i, (subj, body, plain) in enumerate(messages(events), 1):
        m = EmailMessage()
        m["Subject"], m["To"] = subj, TO
        m["From"] = formataddr(("Purdue La Milonguera Tango Club", user))
        m["Message-ID"] = make_msgid()
        m.set_content(plain)
        m.add_alternative(body, subtype="html")
        open(os.path.join(ROOT, "out", f"email-{i}.html"), "w").write(body)
        msgs.append(m)
    print(f"Generated {len(msgs)} email(s) in out/.")
    if DRY:
        print("DRY_RUN is on; not sending."); return
    user, pw = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pw)
        for m in msgs:
            s.send_message(m); print("Sent:", m["Subject"])

if __name__ == "__main__":
    main()
