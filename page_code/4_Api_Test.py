import pandas as pd
import streamlit as st
import requests

##########################################################
# Tab 5: API tests
##########################################################

st.write("# Vehicles API Fetch")
# Define API endpoint and headers
url = "https://api.goswift.ly/real-time/vta/vehicles"
headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}

# Send GET request to API endpoint and retrieve JSON response
response = requests.get(url, headers=headers)
json_data = response.json()
# st.json(json_data)

# Extract vehicles data from JSON response
vehicles_data = json_data["data"]["vehicles"]

# Create pandas DataFrame from vehicles data
df = pd.DataFrame(vehicles_data)
df.id = df.id.astype('int')
# Filter DataFrame by list of ids
ids_to_filter = [7501, 7502, 7503, 7504, 7505, 9501, 9502, 9503, 9504, 9505]
filtered_df = df[df["id"].isin(ids_to_filter)]

# Display dataframe in Streamlit
# st.dataframe(df)

st.write("See if ebuses show up in vehicles fetch")
st.dataframe(filtered_df)

st.markdown("""<hr style="border-top:2px dashed;color:#000;" /> """, unsafe_allow_html=True)

st.write("# Blocks API Fetch")

url = "https://api.goswift.ly/real-time/vta/active-blocks"
headers = {"Authorization": "e8201446c114da536ff0a89a4c1c9228"}

# Send GET request to API endpoint and retrieve JSON response
response = requests.get(url, headers=headers)
json_data = response.json()

# Extract block data from JSON response
block_data = json_data["data"]["blocksByRoute"]

# Create pandas DataFrame from block data
df = pd.DataFrame(block_data)

# Convert "id" column to numeric type
df["id"] = pd.to_numeric(df["id"], errors="coerce")

# Filter DataFrame by list of ids
ids_to_filter = [70, 71, 77]
filtered_df = df[df["id"].isin(ids_to_filter)]

st.dataframe(filtered_df)

# Explode "block" column into separate rows
exploded_df = filtered_df.explode("block")

# Reset DataFrame index
exploded_df = exploded_df.reset_index(drop=True)

# Create DataFrame from "block" column
block_df = pd.DataFrame(exploded_df["block"].to_list())

# Add prefix to column names of block DataFrame
block_df = block_df.add_prefix("block_")

# Concatenate exploded DataFrame and block DataFrame
final_df = pd.concat([exploded_df.drop("block", axis=1), block_df], axis=1)

# Display final DataFrame
st.dataframe(final_df)
