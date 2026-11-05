from datetime import datetime, timedelta
import csv
import io
import re
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://www.syracuseindoorsportscenter.com/schedule.html"


def scrape_and_generate_ics():
  print(f"Fetching main schedule page: {BASE_URL}")
  response = requests.get(BASE_URL)
  if response.status_code != 200:
    print("Failed to fetch main page.")
    return

  soup = BeautifulSoup(response.text, "html.parser")
  sheet_ids = set()

  for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    if "docs.google.com/spreadsheets" in href:
      match = re.search(r"/d/([a-zA-Z0-9-_]+)", href)
      if match:
        sheet_ids.add(match.group(1))

  events = []
  target_string = "BOCA"

  for s_id in sheet_ids:
    csv_url = f"https://docs.google.com/spreadsheets/d/{s_id}/export?format=csv"
    try:
      res = requests.get(csv_url, timeout=10)
      if res.status_code != 200:
        continue

      reader = csv.reader(io.StringIO(res.text))
      current_date = None

      for row in reader:
        row_text = " ".join([cell.strip() for cell in row if cell.strip()])
        if not row_text:
          continue

        date_match = re.search(
            r"\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](\d{2,4})\b",
            row_text,
        )
        if date_match:
          date_str = date_match.group(0)
          for fmt in ("%m/%d/%y", "%m-%d-%y", "%m/%d/%Y", "%m-%d-%Y"):
            try:
              parsed = datetime.strptime(date_str, fmt)
              if parsed.year < 2000:
                parsed = parsed.replace(year=parsed.year + 2000)
              current_date = parsed
              break
            except ValueError:
              continue

        if target_string.lower() in row_text.lower():
          time_match = re.search(
              r"\b(1[0-2]|0?[1-9]):([0-5][0-9])\s*(AM|PM|am|pm)\b", row_text
          )
          if time_match and current_date:
            time_str = f"{time_match.group(1)}:{time_match.group(2)} {time_match.group(3).upper()}"
            time_obj = datetime.strptime(time_str, "%I:%M %p")

            game_start = current_date.replace(
                hour=time_obj.hour, minute=time_obj.minute
            )
            game_end = game_start + timedelta(hours=1)

            events.append({
                "summary": row_text,
                "start": game_start,
                "end": game_end,
            })
    except Exception as e:
      print(f"Error processing sheet {s_id}: {e}")

  unique_events = {}
  for ev in events:
    key = (ev["summary"], ev["start"])
    unique_events[key] = ev

  ics_filename = "boca_soccer_schedule.ics"
  with open(ics_filename, "w", encoding="utf-8") as f:
    f.write("BEGIN:VCALENDAR\n")
    f.write("VERSION:2.0\n")
    f.write("PRODID:-//Boca Soccer Timezone Fixed Scraper//EN\n")
    # Define America/New_York timezone rules inside the ICS so Google maps local times perfectly
    f.write("BEGIN:VTIMEZONE\n")
    f.write("TZID:America/New_York\n")
    f.write("BEGIN:STANDARD\n")
    f.write("DTSTART:20071104T020000\n")
    f.write("RRULE:FREQ=YEARLY;BYDAY=1SU;BYMONTH=11\n")
    f.write("TZOFFSETFROM:-0400\n")
    f.write("TZOFFSETTO:-0500\n")
    f.write("TZNAME:EST\n")
    f.write("END:STANDARD\n")
    f.write("BEGIN:DAYLIGHT\n")
    f.write("DTSTART:20070311T020000\n")
    f.write("RRULE:FREQ=YEARLY;BYDAY=2SU;BYMONTH=3\n")
    f.write("TZOFFSETFROM:-0500\n")
    f.write("TZOFFSETTO:-0400\n")
    f.write("TZNAME:EDT\n")
    f.write("END:DAYLIGHT\n")
    f.write("END:VTIMEZONE\n")

    for i, ev in enumerate(unique_events.values()):
      start_str = ev["start"].strftime("%Y%m%dT%H%M%S")
      end_str = ev["end"].strftime("%Y%m%dT%H%M%S")
      f.write("BEGIN:VEVENT\n")
      f.write(f"UID:boca-tz-game-{i}-{start_str}@sisc\n")
      f.write(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n")
      # Explicitly attach the Eastern Time Zone identifier to start/end times
      f.write(f"DTSTART;TZID=America/New_York:{start_str}\n")
      f.write(f"DTEND;TZID=America/New_York:{end_str}\n")
      f.write(f"SUMMARY:{ev['summary']}\n")
      f.write(
          f"DESCRIPTION:Auto-synced from Syracuse Indoor Sports Center"
          " Schedule\n"
      )
      f.write("END:VEVENT\n")

    f.write("END:VCALENDAR\n")
  print(f"Generated {ics_filename} with timezone definitions.")


if __name__ == "__main__":
  scrape_and_generate_ics()
