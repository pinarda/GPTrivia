import sqlite3
import re
from datetime import datetime

# Path to your SQLite database
db_path = '/Users/alex/git/GPTrivia/db.sqlite3'

# Regular expression to match the new format and extract necessary parts
new_format_regex = re.compile(r'https://docs\.google\.com/presentation/d/([^/]+)/embed\?start=false&slide=id\.(\w+)')


def extract_presentation_id(link):
    match = new_format_regex.match(link)
    if match:
        presentation_id = match.group(1)
        return presentation_id
    return None


def convert_date_format(date_str):
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        return date_obj.strftime('%m.%d.%Y')
    except ValueError:
        return date_str


def extract_presentation_ids():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Select all links and dates from the database
        cursor.execute("SELECT link, date FROM GPTrivia_gptriviaround")
        rows = cursor.fetchall()

        presentation_data = []
        seen_ids = set()

        for row in rows:
            link = row[0]
            date = row[1]
            presentation_id = extract_presentation_id(link)
            if presentation_id and presentation_id not in seen_ids:
                formatted_date = convert_date_format(date)
                presentation_data.append((formatted_date, presentation_id))
                seen_ids.add(presentation_id)

        # Write unique presentation IDs and dates to a text file
        with open('presentation_ids.txt', 'w') as f:
            for date, pid in presentation_data:
                f.write(f"{date}\t{pid}\n")

        print("Presentation IDs and dates have been extracted and saved to presentation_ids.txt")

    except sqlite3.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    extract_presentation_ids()
