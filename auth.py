import streamlit as st
import supabase

# Connect to Supabase
supabase_url = "https://ztkxpouaswqlomjpjnwl.supabase.co"
supabase_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" \
               ".eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp0a3hwb3Vhc3dxbG9tanBqbndsIiwicm9s" \
               "ZSI6ImFub24iLCJpYXQiOjE2ODY5MDczMTEsImV4cCI6MjAwMjQ4MzMxMX0.w6FazqiQ9BA1oSbPBf4MmXqeye7Y2U2b5Y2ERDWdcA8"

supabase_client = supabase.create_client(supabase_url, supabase_key)


@st.cache(allow_output_mutation=True)
def create_supabase_user(email, password):
    response = supabase_client.auth.sign_up(email=email, password=password)
    if response['status'] == 'SUCCESS':
        return response['user']
    else:
        return None


def login(email, password):
    response = supabase_client.auth.sign_in(email=email, password=password)
    if response['status'] == 'SUCCESS':
        st.success('Logged in successfully!')
        st.session_state.logged_in = True
        st.session_state.user = response['user']
    else:
        st.error('Login failed!')


def logout():
    response = supabase_client.auth.sign_out()
    if response['status'] == 'SUCCESS':
        st.success('Logged out successfully!')
        st.session_state.logged_in = False
        st.session_state.user = None
    else:
        st.error('Logout failed!')
