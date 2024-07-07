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

st.set_page_config('ESTOQUE • FILA', page_icon='https://i.imgur.com/TZp66zI.png', layout='wide')
    
st.image('https://i.imgur.com/QgNqMAu.png', width=400)
st.header('', divider='gray')

st.sidebar.title('MÓDULOS')
