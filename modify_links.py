import sqlite3
import re

# Path to your SQLite database
db_path = '/Users/alex/git/GPTrivia/db.sqlite3'

# Regular expression to match the old format and extract necessary parts
old_format_regex = re.compile(r'https://docs\.google\.com/presentation/d/([^/]+)/edit#slide=id\.(\w+)')

def modify_link(old_link):
    match = old_format_regex.match(old_link)
    if match:
        presentation_id = match.group(1)
        slide_id = match.group(2)
        new_link = f"https://docs.google.com/presentation/d/{presentation_id}/embed?start=false&slide=id.{slide_id}"
        return new_link
    return old_link

def update_links_in_db():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Select all links from the database
        cursor.execute("SELECT id, link FROM GPTrivia_gptriviaround")
        rows = cursor.fetchall()

        for row in rows:
            record_id = row[0]
            old_link = row[1]
            new_link = modify_link(old_link)
            if new_link != old_link:
                cursor.execute("UPDATE GPTrivia_gptriviaround SET link = ? WHERE id = ?", (new_link, record_id))
                print(f"Updated link for record ID {record_id}")

        # Commit the changes to the database
        conn.commit()

    except sqlite3.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_links_in_db()
