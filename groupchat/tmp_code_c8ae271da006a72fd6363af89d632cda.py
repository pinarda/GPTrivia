# python3

import requests
import random

def get_word():
    # Wordnik is a online free dictionary which also provide an API to fetch random words.
    wordnik_url = "http://api.wordnik.com/v4/words.json/randomWord"
    headers = {
        'api_key': "YOUR_WORDNIK_API_KEY"
    }

    response = requests.get(wordnik_url, headers=headers)
    if response.status_code == 200:
        word = response.json().get('word')
        return word
    else:
        return None

if __name__ == "__main__":
    words = [get_word() for _ in range(5)]
    words = [word for word in words if word]
    print("\n".join(words))