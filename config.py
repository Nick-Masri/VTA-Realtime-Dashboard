import streamlit as st
import yaml
import json

def show_config():
    # get config settings from YAML
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Convert the data to a JSON string
    config_json = json.dumps(config)

    st.write("Current Config Settings")

    # display jsons
    st.json(config_json)
