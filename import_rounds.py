import csv
import os
import sys
import django

# Set up the Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GPTrivia.settings')
django.setup()

# Import the GPTriviaRound model
from GPTrivia.models import GPTriviaRound

# Path to the CSV file
csv_file_path = './rounds.csv'

# Read the CSV file and create GPTriviaRound instances
with open(csv_file_path, newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    for row in reader:
        gptrivia_round = GPTriviaRound(
            major_category=row['Major Category'],
            creator=row['Creator'],
            title=row['Round Name'],
            minor_category1=row['Minor Category'],
            minor_category2=row['Minor Category 2'],
            date=row['date'],
            round_number=int(row['Round Number']),
            # THe scores can be floats
            max_score=float(row['Possible Points']),
            # if the score is empty, set it to a None value
            score_alex=float(row['Alex']) if row['Alex'] else None,
            score_ichigo=float(row['Ichigo']) if row['Ichigo'] else None,
            score_megan=float(row['Megan']) if row['Megan'] else None,
            score_zach=float(row['Zach']) if row['Zach'] else None,
            score_jenny=float(row['Jenny']) if row['Jenny'] else None,
            score_debi=float(row['Debi']) if row['Debi'] else None,
            score_dan=float(row['Dan']) if row['Dan'] else None,
            score_chris=float(row['Chris']) if row['Chris'] else None,
            score_drew=float(row['Drew']) if row['Drew'] else None,
        )
        # if the creator is equal to the player's name, set the score to None using a loop
        for player in ['alex', 'ichigo', 'megan', 'zach', 'jenny', 'debi', 'dan', 'chris', 'drew']:
            if gptrivia_round.creator.lower() == player:
                setattr(gptrivia_round, f'score_{player}', None)

        gptrivia_round.save()

print("Data imported successfully.")