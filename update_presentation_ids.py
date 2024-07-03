import sqlite3

# Path to your SQLite database
db_path = '/Users/alex/git/GPTrivia/db.sqlite3'

def read_presentation_ids(file_path):
    presentation_data = []
    try:
        with open(file_path, 'r') as f:
            for line in f:
                date, presentation_id = line.strip().split('\t')
                presentation_data.append((date, presentation_id))
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
    return presentation_data

def update_presentation_ids_in_db(presentation_data):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        for date, presentation_id in presentation_data:
            cursor.execute(
                "UPDATE GPTrivia_mergedpresentation SET presentation_id = ? WHERE name = ?",
                (presentation_id, date)
            )
            print(f"Updated presentation ID for date {date}")

        # Commit the changes to the database
        conn.commit()

    except sqlite3.Error as err:
        print(f"Error: {err}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # Path to the presentation IDs file
    file_path = 'presentation_ids.txt'

    # Read the presentation IDs from the file
    presentation_data = read_presentation_ids(file_path)

    # Update the database with the presentation IDs
    update_presentation_ids_in_db(presentation_data)
