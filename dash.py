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

st.set_page_config('ESTOQUE • FILA', page_icon='https://imgur.com/TZp66zI', layout='wide')
    
st.image('https://seeklogo.com/images/G/gertec-logo-D1C911377C-seeklogo.com.png?v=637843433630000000', width=200)
st.header('', divider='gray')

st.sidebar.title('MÓDULOS')
