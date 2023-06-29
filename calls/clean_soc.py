import supabase
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
import os


# (if local) Load environment variables
load_dotenv()
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(url, key)

# Fetch all entries from the database table
response = supabase.table('soc').select('*').order("created_at", desc=True).execute()
entries = response.data
df = pd.DataFrame(entries)
# print(df.head())
# # List to store the relevant entry indices
# List to store the relevant entry indices
relevant_indices = []

for vehicle in df['vehicle'].unique():
    vehicle_df = df[df['vehicle'] == vehicle]
    relevant_indices.append(vehicle_df.index[0])  # Append the first index of the vehicle
    relevant_indices.append(vehicle_df.index[-1])  # Append the last index of the vehicle

    for i in range(1, len(vehicle_df) - 1):
        current_entry = vehicle_df.iloc[i]
        previous_entry = vehicle_df.iloc[i - 1]
        next_entry = vehicle_df.iloc[i + 1]

        if current_entry['soc'] != previous_entry['soc'] or current_entry['soc'] != next_entry['soc']:
            relevant_indices.append(vehicle_df.index[i])  # Append the index if there's a change in state

print(relevant_indices)
print(len(relevant_indices))
print(len(df))
print(len(df) - len(relevant_indices))
# Delete irrelevant entries from the database
for i in range(len(entries)):
    if i not in relevant_indices:
        entry_id = entries[i]['id']
        data, error = supabase.table('soc').delete().eq('id', entry_id).execute()
        print(data,error)

print("Irrelevant entries deleted successfully.")