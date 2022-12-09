import requests
import json
url = "https://api.goswift.ly/real-time/vta/gtfs-rt-trip-updates"
# url = "https://api.goswift.ly/real-time//vehicles"

# querystring = {"format":"human","version":"3.0"}
querystring = {}

headers = {
    "Content-Type": "application/json",
    "Authorization": "e8201446c114da536ff0a89a4c1c9228"
}

response = requests.request("GET", url, headers=headers, params=querystring)
#
# print(response.text)
#
# with open('output.json', 'w') as f:
#     f.write(response.text)
response_data = json.loads(response.text)

with open('output.json', 'w') as f:
    json.dump(response_data, f)


#%%
with open('output.json', 'r') as f:
    response_data = json.load(f)
    print(response_data['field1'])
    print(response_data['field2'])
    ...