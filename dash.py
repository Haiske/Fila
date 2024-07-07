import streamlit as st
import pandas as pd
from office365.sharepoint.files.file import File
from office365.sharepoint.client_context import ClientContext
from office365.runtime.auth.authentication_context import AuthenticationContext
from datetime import datetime
import io
import plotly.express as px
from workalendar.america import Brazil
from time import sleep

st.set_page_config('ESTOQUE • FILA', page_icon='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png', layout='wide')

st.logo('https://raw.githubusercontent.com/Haiske/Fila/main/attachments/logo.png', icon_image='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png')

st.image('https://raw.githubusercontent.com/Haiske/Fila/main/attachments/logo.png', width=400)
st.divider()

st.sidebar.title('MÓDULOS')
st.sidebar.page_link('dash.py', label="DASHBOARD", disabled=True)
st.sidebar.page_link('pages/tabelas.py', label="TABELAS")
