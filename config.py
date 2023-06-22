import streamlit as st
import yaml
import json


def show_config():
    # Load config settings from YAML
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    st.write("Current Config Settings")

    # Display the current config as JSON
    config_json = json.dumps(config)
    st.json(config_json)

    st.write("Edit Config Settings")

    # Create input components for each config setting
    for key, value in config.items():
        new_value = st.text_input(key, value)
        config[key] = new_value

    # Save the updated config to the YAML file
    with open('config.yaml', 'w') as f:
        yaml.dump(config, f)
