from datetime import datetime, timedelta
import csv
import io
import re
from bs4 import BeautifulSoup
import requests
from zoneinfo import ZoneInfo  # Built-in Python 3.9+ timezone support

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
  ny_tz = ZoneInfo("America/New_York")
  utc_tz = ZoneInfo("UTC")

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

            # Construct local New York datetime and convert to UTC explicitly
            local_start = datetime(
                current_date.year,
                current_date.month,
                current_date.day,
                time_obj.hour,
                time_obj.minute,
                tzinfo=ny_tz,
            )
            utc_start = local_start.astimezone(utc_tz)
            utc_end = utc_start + timedelta(hours=1)

            events.append({
                "summary": row_text,
                "start": utc_start,
                "end": utc_end,
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
    f.write("PRODID:-//Boca Soccer UTC Shifted Scraper//EN\n")

    for i, ev in enumerate(unique_events.values()):
      start_str = ev["start"].strftime("%Y%m%dT%H%M%SZ")
      end_str = ev["end"].strftime("%Y%m%dT%H%M%SZ")
      f.write("BEGIN:VEVENT\n")
      f.write(f"UID:boca-utc-game-{i}-{start_str}@sisc\n")
      f.write(f"DTSTAMP:{datetime.now(utc_tz).strftime('%Y%m%dT%H%M%SZ')}\n")
      f.write(f"DTSTART:{start_str}\n")
      f.write(f"DTEND:{end_str}\n")
      f.write(f"SUMMARY:{ev['summary']}\n")
      f.write(
          f"DESCRIPTION:Auto-synced from Syracuse Indoor Sports Center"
          " Schedule\n"
      )
      f.write("END:VEVENT\n")

    f.write("END:VCALENDAR\n")
  print(f"Generated {ics_filename} with UTC-shifted times.")


if __name__ == "__main__":
  scrape_and_generate_ics()
