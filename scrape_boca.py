from datetime import datetime, timedelta
import re
from urllib.parse import urljoin
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
  links = {BASE_URL}
  for a_tag in soup.find_all("a", href=True):
    href = a_tag["href"]
    if "schedule" in href.lower() or "standings" in href.lower():
      links.add(urljoin(BASE_URL, href))

  events = []
  target_string = "BOCA"

  for link in links:
    try:
      print(f"Checking: {link}")
      res = requests.get(link, timeout=10)
      if res.status_code != 200:
        continue
      page_soup = BeautifulSoup(res.text, "html.parser")

      # Walk through the text line by line, keeping track of the last seen valid date
      text_content = page_soup.get_text(separator="\n")
      lines = text_content.split("\n")

      current_date = None
      for line in lines:
        line = line.strip()
        if not line:
          continue

        # Look for date headers in the text (e.g., 11/5/26, 10/31/2026, etc.)
        date_match = re.search(
            r"\b(0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])[-/](\d{2,4})\b", line
        )
        if date_match:
          date_str = date_match.group(0)
          for fmt in ("%m/%d/%y", "%m-%d-%y", "%m/%d/%Y", "%m-%d-%Y"):
            try:
              parsed = datetime.strptime(date_str, fmt)
              # Handle 2-digit year conversion if needed
              if parsed.year < 2000:
                parsed = parsed.replace(year=parsed.year + 2000)
              current_date = parsed
              break
            except ValueError:
              continue

        # If we find BOCA and have a valid date context, extract the game
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
                f"  [FOUND] {line} -> Date Assigned: {game_start.strftime('%Y-%m-%d %I:%M %p')}"
            )

    except Exception as e:
      print(f"Error reading {link}: {e}")

  # Deduplicate events based on exact summary and start time
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
          f"DESCRIPTION:Syracuse Indoor Sports Center - Boca Schedule\n"
      )
      f.write("END:VEVENT\n")

    f.write("END:VCALENDAR\n")
  print(f"Generated {ics_filename} with {len(unique_events)} unique events.")


if __name__ == "__main__":
  scrape_and_generate_ics()
