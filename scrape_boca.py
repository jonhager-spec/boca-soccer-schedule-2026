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

  # Automatically find all links on the page pointing to Google Sheets
  for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    # Look for Google Docs / Sheets URL patterns
    if "docs.google.com/spreadsheets" in href:
      # Extract the unique Spreadsheet ID from the URL using Regex
      match = re.search(r"/d/([a-zA-Z0-9-_]+)", href)
      if match:
        s_id = match.group(1)
        sheet_ids.add(s_id)
        print(f"  [DISCOVERED SHEET LINK] -> ID: {s_id}")

  print(f"Found {len(sheet_ids)} total spreadsheet links to scan.\n")

  events = []
  target_string = "BOCA"

  for s_id in sheet_ids:
    csv_url = f"https://docs.google.com/spreadsheets/d/{s_id}/export?format=csv"
    try:
      print(f"Downloading data for sheet {s_id}...")
      res = requests.get(csv_url, timeout=10)
      if res.status_code != 200:
        continue

      reader = csv.reader(io.StringIO(res.text))
      current_date = None

      for row in reader:
        row_text = " ".join([cell.strip() for cell in row if cell.strip()])
        if not row_text:
          continue

        # Look for a date in the row
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

        # Check for BOCA games
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
            print(
                f"    -> [FOUND MATCH] {row_text} on"
                f" {game_start.strftime('%Y-%m-%d %I:%M %p')}"
            )

    except Exception as e:
      print(f"Error processing sheet {s_id}: {e}")

  # Deduplicate events
  unique_events = {}
  for ev in events:
    key = (ev["summary"], ev["start"])
    unique_events[key] = ev

  ics_filename = "boca_soccer_schedule.ics"
  with open(ics_filename, "w", encoding="utf-8") as f:
    f.write("BEGIN:VCALENDAR\n")
    f.write("VERSION:2.0\n")
    f.write("PRODID:-//Boca Soccer Auto-Discover Scraper//EN\n")

    for i, ev in enumerate(unique_events.values()):
      start_str = ev["start"].strftime("%Y%m%dT%H%M%S")
      end_str = ev["end"].strftime("%Y%m%dT%H%M%S")
      f.write("BEGIN:VEVENT\n")
      f.write(f"UID:boca-auto-game-{i}-{start_str}@sisc\n")
      f.write(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}\n")
      f.write(f"DTSTART:{start_str}\n")
      f.write(f"DTEND:{end_str}\n")
      f.write(f"SUMMARY:{ev['summary']}\n")
      f.write(
          f"DESCRIPTION:Auto-synced from Syracuse Indoor Sports Center"
          " Schedule\n"
      )
      f.write("END:VEVENT\n")

    f.write("END:VCALENDAR\n")
  print(
      f"\nSuccessfully generated {ics_filename} with {len(unique_events)}"
      " games."
  )


if __name__ == "__main__":
  scrape_and_generate_ics()
