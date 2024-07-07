import streamlit as st
import pandas as pd
from datetime import datetime
import io
import plotly.express as px
from workalendar.america import Brazil
from time import sleep

st.set_page_config('ESTOQUE • FILA', page_icon='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png', layout='wide')
st.logo('https://raw.githubusercontent.com/Haiske/Fila/main/attachments/logo.png', icon_image='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png')

st.sidebar.title('MÓDULOS')
st.sidebar.page_link('dash.py', label="DASHBOARD", disabled=True)
st.sidebar.page_link('pages/tabelas.py', label="TABELAS")

df = pd.read_csv('https://raw.githubusercontent.com/Haiske/Fila/main/tables/historico.csv', converters={'CAIXA':'str',
                                                                                                       'SERIAL':'str',
                                                                                                       'ORDEM DE SERVIÇO':'str',
                                                                                                       'DT RECEBIMENTO':pd.to_datetime,
                                                                                                       'DT SAÍDA FILA':pd.to_datetime})
st.dataframe(df)
