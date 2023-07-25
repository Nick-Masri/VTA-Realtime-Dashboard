import smtplib
from email.mime.text import MIMEText
import os
import datetime
import streamlit as st

@st.cache_data(show_spinner=False, ttl=datetime.timedelta(minutes=60))
def send_email(_error):
    email = st.secrets["EMAIL"]
    password = st.secrets["EMAIL_PASSWD"]
    email = os.getenv('EMAIL')
    password = os.getenv('EMAIL_PASSWD')
    msg = MIMEText(str(_error))
    msg['Subject'] = "VTA EBUS App Down"
    msg['From'] = email
    msg['To'] = email

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
       smtp_server.login(email, password)
       smtp_server.sendmail(email, email, msg.as_string())
    print("Message sent!")
