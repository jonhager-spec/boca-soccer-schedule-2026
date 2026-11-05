from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://www.syracuseindoorsportscenter.com/schedule.html"


def scrape_and_generate_ics():
  print(f"Fetching main page: {BASE_URL}")
  response = requests.get(BASE_URL)
  if response.status_code != 200:
    print("Failed to fetch main page.")
    return

  soup = BeautifulSoup(response.text, "html.parser")
  events = []
  target_string = "BOCA"

  # We parse directly from the main schedule text where the actual youth blocks live
  text_content = soup.get_text(separator="\n")
  lines = text_content.split("\n")

  current_date = None
  for line in lines:
    line = line.strip()
    if not line:
      continue

    # Look specifically for valid youth dates mentioned on the main schedule page (e.g. 10/24/26, 10/31/2026, 11/7/2026)
    date_match = re.search(
        r"\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](\d{2,4})\b", line
    )
    if date_match:
      date_str = date_match.group(0)
      for fmt in ("%m/%d/%y", "%m-%d-%y", "%m/%d/%Y", "%m-%d-%Y"):
        try:
          parsed = datetime.strptime(date_str, fmt)
          if parsed.year < 2000:
            parsed = parsed.replace(year=parsed.year + 2000)
          # Only accept 2026 youth schedule dates
          if parsed.year == 2026:
            current_date = parsed
            break
        except ValueError:
          continue

    # Search for BOCA games under the active date context
    if target_string.lower() in line.lower():
      time_match = re.search(
          r"\b(1[0-2]|0?[1-9]):([0-5][0-9])\s*(AM|PM|am|pm)\b", line
      )
      if time_match and current_date:
        time_str = f"{time_match.group(1)}:{time_match.group(2)} {time_match.group(3).upper()}"
        time_obj = datetime.strptime(time_str, "%I:%M %p")

        game_start = current_date.replace(
            hour=time_obj.hour, minute=time_obj.minute
        )
        game_end = game_start + timedelta(hours=1)

        events.append({
            "summary": line,
            "start": game_start,
            "end": game_end,
        })
        print(
            f"  [FOUND YOUTH BOCA GAME] {line} ->"
            f" {game_start.strftime('%Y-%m-%d %I:%M %p')}"
        )

  # Deduplicate events
  unique_events = {}
  for ev in events:
    key = (ev["summary"], ev["start"])
    unique_events[key] = ev

  ics_filename = "boca_soccer_schedule.ics"
  with open(ics_filename, "w", encoding="utf-8") as f:
    f.write("BEGIN:VCALENDAR\n")
    f.write("VERSION:2.0\n")
    f.write("PRODID:-//Boca Soccer Schedule Auto Scraper//EN\n")

    for i, ev in enumerate(unique_events.values()):
      start_str = ev["start"].strftime("%Y%m%dT%H%M%S")
      end_str = ev["end"].strftime("%Y%m%dT%H%M%S")
      f.write("BEGIN:VEVENT\n")
      f.write(f"UID:boca-soccer-game-{i}-{start_str}@sisc\n")
      f.write(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n")
      f.write(f"DTSTART:{start_str}\n")
      f.write(f"DTEND:{end_str}\n")
      f.write(f"SUMMARY:{ev['summary']}\n")
      f.write(
          f"DESCRIPTION:Syracuse Indoor Sports Center - Youth Soccer Schedule\n"
      )
      f.write("END:VEVENT\n")

    f.write("END:VCALENDAR\n")
  print(
      f"Generated {ics_filename} with {len(unique_events)} valid unique events."
  )


if __name__ == "__main__":
  scrape_and_generate_ics()
