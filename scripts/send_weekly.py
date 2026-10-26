#!/usr/bin/env python3
"""Generate (and optionally send) weekly announcement emails. Standard library only.

Env:
  MODE            per_event (default: one email per event in the next 7 days) | digest
  DRY_RUN         "1" (default) writes previews to out/ and sends nothing; "0" sends
  GMAIL_USER, GMAIL_APP_PASSWORD   Gmail address + 16-char app password
  TO_ADDR         default tangoannouncements@lists.purdue.edu
  SITE_URL        public URL of the site
  DAYS            look-ahead window, default 7
  ALLOW_SAMPLE    "1" to include entries flagged "sample": true
"""
import html, json, os, smtplib, ssl, sys
from datetime import datetime, timedelta
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
h = html.escape

def load():
    raw = open(os.path.join(ROOT, "data", "events.js")).read()
    ev = json.loads(raw[raw.rindex("window.EVENTS =") + 15:].rsplit(";", 1)[0])
    now = datetime.now(TZ).replace(tzinfo=None)
    end = now + timedelta(days=DAYS)
    keep = []
    for e in ev:
        if e.get("sample") and os.environ.get("ALLOW_SAMPLE") != "1":
            continue
        s = datetime.fromisoformat(e["start"])
        if now <= s <= end:
            keep.append(e)
    return sorted(keep, key=lambda e: e["start"])

def when(e):
    s, f = datetime.fromisoformat(e["start"]), datetime.fromisoformat(e.get("end") or e["start"])
    return f"{s:%A, %B} {s.day} · {s:%-I:%M %p} – {f:%-I:%M %p}"

def block(e):
    img = e.get("image", "")
    if img.startswith("http"):
        pic = f'<img src="{h(img)}" alt="" width="520" style="display:block;width:100%;height:auto;border:0">'
    else:
        pic = ""
    return f'''<tr><td style="padding:0 0 28px">{pic}
<div style="font:11px Arial,sans-serif;letter-spacing:3px;text-transform:uppercase;color:#a8842f;padding-top:16px">{h(when(e))}</div>
<div style="font:26px Georgia,serif;color:#2a1a1d;padding:6px 0">{h(e["title"])}</div>
<div style="font:14px Arial,sans-serif;color:#7a6a6c">{h(e["location"])}</div>
<div style="font:15px/1.6 Georgia,serif;color:#4a3b3d;padding-top:10px">{h(e.get("description",""))}</div>
<div style="padding-top:14px"><a href="{h(e["url"])}" style="font:11px Arial,sans-serif;letter-spacing:3px;text-transform:uppercase;color:#7a1f2e;text-decoration:none;border-bottom:1px solid #7a1f2e">Details &amp; RSVP</a></div></td></tr>'''

def wrap(title, events):
    body = "".join(block(e) for e in events)
    return f'''<!doctype html><html><body style="margin:0;background:#f3ece4"><table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:28px 12px">
<table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;background:#fffdfa">
<tr><td style="background:#1a1214;padding:30px;text-align:center"><div style="font:11px Arial,sans-serif;letter-spacing:5px;color:#c9a45c">PURDUE TANGO CLUB</div><div style="font:30px Georgia,serif;color:#f4ece6;padding-top:8px">{h(title)}</div></td></tr>
<tr><td style="padding:30px"><table role="presentation" width="100%">{body}</table></td></tr>
<tr><td style="padding:20px 30px;background:#f3ece4;font:12px Arial,sans-serif;color:#7a6a6c;text-align:center">See every event and photo at <a href="{h(SITE)}" style="color:#7a1f2e">{h(SITE)}</a></td></tr>
</table></td></tr></table></body></html>'''

def text(events):
    parts = [f"{e['title']}\n{when(e)}\n{e['location']}\n{e.get('description','')}\n{e['url']}\n" for e in events]
    return "\n".join(parts) + f"\nAll events & photos: {SITE}\n"

def messages(events):
    if MODE == "digest":
        d = datetime.fromisoformat(events[0]["start"])
        return [(f"Tango this week: {len(events)} event{'s' if len(events)>1 else ''}", "This week in tango", events)]
    return [(f"Tango: {e['title']} – {datetime.fromisoformat(e['start']):%a %b} {datetime.fromisoformat(e['start']).day}", e["title"], [e]) for e in events]

def main():
    events = load()
    if not events:
        print("No events in the next window; nothing to send."); return
    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    msgs = []
    for i, (subj, title, evs) in enumerate(messages(events), 1):
        m = EmailMessage()
        m["Subject"], m["To"] = subj, TO
        user = os.environ.get("GMAIL_USER", "club@example.com")
        m["From"] = formataddr(("Purdue Tango Club", user))
        m["Message-ID"] = make_msgid()
        m.set_content(text(evs))
        m.add_alternative(wrap(title, evs), subtype="html")
        open(os.path.join(ROOT, "out", f"email-{i}.html"), "w").write(wrap(title, evs))
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
