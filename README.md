# Purdue Tango Club site

Free site on GitHub Pages plus a weekly email via GitHub Actions.

## Setup (about 10 minutes)
1. Create a GitHub repo, push this folder to `main`.
2. Settings > Pages > Source: **GitHub Actions**. The site deploys automatically.
3. Gmail: turn on 2-step verification, then create an **App password** (myaccount.google.com/apppasswords).
4. Repo Settings > Secrets > Actions: add `GMAIL_USER` and `GMAIL_APP_PASSWORD`.
5. **Authorize that Gmail address as a poster on tangoannouncements@lists.purdue.edu**, or posts are held or rejected by the list.
6. Actions > "Tango email" > Run workflow with dry_run=1 and download the `email-previews` artifact. Then try dry_run=0.

The workflow runs every morning at 9 AM Eastern (8 AM after Nov 1, clocks change) and emails the list on the day of each event. Edit `cron` in `weekly-email.yml` to change it. A manual run takes an optional `to` address for test sends.

## Content
- Events: `data/events.js`. Entries marked `"sample": true` are never emailed. Delete them.
- Photos: drop files in `photos/` and list them in `data/photos.js`. Only post photos of people who have agreed.
- Emails: wording lives in `data/email.json`: greeting, signature, and one template per class type (`match` is a word in the event title; `{time}`, `{location}`, `{title}`, `{description}` are filled in). Events that match no class use `fallback`. Set `MODE: digest` in the workflow for one Monday email covering the week instead.

## Event sync
Each Monday the workflow reads https://boilerlink.purdue.edu/events.rss, keeps upcoming events hosted by La Milonguera Argentine Tango Club, and rewrites `data/events.js` before the emails go out. If the feed can't be reached, the existing events are kept. BoilerLink sometimes lists a weekly class as one entry spanning the whole term; the sync splits it into weekly sessions (start's time to end's time, same weekday) and drops duplicates, preferring a one-off entry for the same title and start time, since that carries room changes. A range ending on a different weekday (e.g. a weekend festival) stays one multi-day event. To use another feed, set the `FEED_URL` secret (RSS, .ics or JSON). Change the club filter with the `HOST_FILTER` env var.
