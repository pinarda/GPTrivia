import requests

url = 'https://hailsciencetrivia.com/api-token-auth/'
data = {
    'username': 'Alex2',
    'password': 'hailpuses',
}

response = requests.post(url, data=data)
auth_token = response.json()['token']
print('Authentication token:', auth_token)