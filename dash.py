import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import plotly.express as px
from workalendar.america import Brazil

st.set_page_config('ESTOQUE • FILA', page_icon='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png', layout='wide')
st.logo('https://raw.githubusercontent.com/Haiske/Fila/main/attachments/logo.png', icon_image='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png')

st.sidebar.title('MÓDULOS')
st.sidebar.page_link('dash.py', label="DASHBOARD", disabled=True)
st.sidebar.page_link('pages/tabelas.py', label="TABELAS")

st.sidebar.divider()
st.sidebar.title('AÇÕES')

tabs_saldo, tabs_liberados, tabs_saidas = st.tabs(['Saldo', 'Liberados', 'Saídas'])


def create_df_historico_fila():
    df = pd.read_csv('https://raw.githubusercontent.com/Haiske/Fila/main/tables/historico.csv', converters={'CAIXA':str,
                                                                                                       'SERIAL':str,
                                                                                                       'ORDEM DE SERVIÇO':str})

    # Como preciso deixar meu dashboard de uma forma estática para a data 01/07/2024 (data de criação da minha base de dados),
    # criei a coluna 'ULTIMA DATA' para que no cálculo da % atingida do prazo do SLA (Service Level Agreements) seja sempre considerada
    # a data em que o equipamento foi enviado ao laboratório (já que queremos monitorar apenas o fila aqui) ou a data 01/07/2024.

    calendario = Brazil()
    
    df['ULTIMA DATA'] = df['DT ENVIO LAB']
    df.loc[df['ENDEREÇO'] == 'FILA', 'ULTIMA DATA'] = date(2024, 7, 1)
    df.loc[df['ULTIMA DATA'].isna(), 'ULTIMA DATA'] = date(2024, 7, 1)
    
    df['ULTIMA DATA'] = pd.to_datetime(df['ULTIMA DATA'])
    df['DT RECEBIMENTO'] = pd.to_datetime(df['DT RECEBIMENTO'])
    df.loc[~df['DT ENVIO LAB'].isna(), 'DT ENVIO LAB'] = pd.to_datetime(df.loc[~df['DT ENVIO LAB'].isna(), 'DT ENVIO LAB'])
    
    df['AGING TOTAL'] = df.apply(lambda row: calendario.get_working_days_delta(row['DT RECEBIMENTO'], row['ULTIMA DATA']), axis=1) + 1
    df['AGING TOTAL'] = df['AGING TOTAL'].astype('int')
    
    df['% DO SLA'] = df['AGING TOTAL']/30
    df['STATUS'] = None

    # Classificamos o nível de criticidade dos equipamentos dentro do fila de acordo com a % do SLA. Sendo assim:
    # Até 10%: Rápido
    # Até 30%: Médio
    # Até 50%: Lento
    # Até 100%: Crítico
    # Acima de 100%: SLA Estourado
    
    df.loc[(df['% DO SLA'] > 0.0) & (df['% DO SLA'] <= 0.1), 'STATUS'] = "RÁPIDO"
    df.loc[(df['% DO SLA'] > 0.1) & (df['% DO SLA'] <= 0.3), 'STATUS'] = "MÉDIO"
    df.loc[(df['% DO SLA'] > 0.3) & (df['% DO SLA'] <= 0.5), 'STATUS'] = "LENTO"
    df.loc[(df['% DO SLA'] > 0.5) & (df['% DO SLA'] <= 1.0), 'STATUS'] = "CRÍTICO"
    df.loc[(df['% DO SLA'] > 1.0), 'STATUS'] = "SLA ESTOURADO"

    return df


def create_df_resumido(df, endereço='FILA'):

    # Criamos um dataframe resumo que mostra a quantidade de equipamentos no endereço que definimos.
    # Neste exemplo trabalhamos apenas com "FILA" e "LAB", mas podemos facilmente adaptar isso para mais
    # tipos de endereços.

    n_df = df[df['ENDEREÇO'] == endereço].copy()
    n_df = n_df.groupby(['CLIENTE', 'EQUIPAMENTO'])[['SERIAL']].count().reset_index()
    n_df.rename(columns={'SERIAL':'QUANTIDADE'}, inplace=True)

    try:
        n_df.sort_values(['CLIENTE', 'EQUIPAMENTO'], inplace=True)
    except:
        pass

    return n_df


def create_df_historico_filtrado(df, points_critico, points_status, endereço='FILA'):

    # Geramos um novo dataframe que será filtrado de acordo com as linhas selecionadas
    # no nosso dataframe resumido.

    df_selecao = df.copy()

    critic_points = list(i['y'][1:7] for i in points_critico)
    status_points = list(i['y'][1:7] for i in points_status)

    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = st.session_state['historico_fila_contratos'].copy()
        df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    else:
        df_detalhado = st.session_state['historico_fila_contratos']
        df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]

    if len(critic_points) > 0:
        df_detalhado = df_detalhado[df_detalhado['CAIXA'].isin(critic_points)]
        
    if len(status_points) > 0:
        df_detalhado = df_detalhado[df_detalhado['STATUS'].isin(status_points)]

    return df_detalhado


def create_fig_criticos(df, points_status):

    # Criamos um gráfico de barras horizontais que rankeia as caixas de acordo
    # com a % do SLA, levando em consideração apenas a maior dentro de cada caixa.

    df_selecao = df.copy()

    status_points = list(i['y'][1:7] for i in points_status)

    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = st.session_state['historico_fila_contratos'].copy()
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    
    else:
        df_detalhado = st.session_state['historico_fila_contratos'].copy()

    if len(status_points) > 0:
        df_detalhado = df_detalhado[df_detalhado['STATUS'].isin(status_points)]

    n_df = df_detalhado[df_detalhado['ENDEREÇO'] == 'FILA'].copy()
    n_df['CAIXA'] = n_df['CAIXA'].astype('str')
    n_df['CAIXA'] = "ㅤ" + n_df['CAIXA']
    n_df['RÓTULO'] = n_df['CLIENTE'] + ' - ' + n_df['ENDEREÇO']
    n_df = n_df.groupby(['CAIXA', 'RÓTULO'])['% DO SLA'].max().reset_index()
    n_df = n_df.sort_values('% DO SLA').drop_duplicates(['CAIXA'], keep='last')
    n_df = n_df.sort_values('% DO SLA').tail(10)

    fig = px.bar(n_df,
                    x='% DO SLA',
                    y='CAIXA',
                    color='% DO SLA',
                    orientation='h',
                    text='RÓTULO',
                    color_continuous_scale=[(0, "#008000"),
                                            (0.3, "#32CD32"),
                                            (0.5, "#FFD700"),
                                            (0.99, "#FF8C00"),
                                            (1, "#8B0000")],
                    range_color=[0,1])
    
    return fig


def create_fig_status(df, endereço='FILA'):

    df_selecao = df.copy()

    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = st.session_state['historico_fila_contratos'].copy()
        df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    
    else:
        df_detalhado = st.session_state['historico_fila_contratos']
        df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]

    df_detalhado = df_detalhado.groupby(['STATUS'])[['SERIAL']].count().reset_index()

    fig = px.pie(df_detalhado,
                                names='STATUS',
                                values='SERIAL',
                                color='STATUS',
                                hole=0.4,
                                color_discrete_map={'RÁPIDO':'#008000',
                                                'MÉDIO':'#32CD32',
                                                'LENTO':'#FFD700',
                                                'CRÍTICO':'#FF8C00',
                                                'SLA ESTOURADO':'#8B0000'},
                            category_orders={'STATUS':['RÁPIDO', 'MÉDIO', 'LENTO', 'CRÍTICO', 'SLA ESTOURADO']})
    fig.update_traces(textinfo='value+percent')

    return fig


def create_fig_volume(df):
    n_df = df.groupby(['CLIENTE'])['QUANTIDADE'].sum().reset_index().sort_values(['QUANTIDADE'], ascending=False).head(10)

    fig = px.bar(n_df,
                 x='CLIENTE',
                 y='QUANTIDADE',
                 color_discrete_sequence=['#13399A'],
                 orientation='v',
                 text='QUANTIDADE')
    
    fig.update_traces(textposition='inside',
                      orientation='v')
  
    fig.update_layout(yaxis_title=None,
                      xaxis_title=None,
                      yaxis_visible=False)

    return fig

# Salvamos o histórico do fila na memória do navegador.
if 'historico_fila' not in st.session_state:
    st.session_state['historico_fila'] = create_df_historico_fila()
    historico_fila = st.session_state['historico_fila']
else:
    historico_fila = st.session_state['historico_fila']

if 'historico_fila_contratos' not in st.session_state:
    st.session_state['historico_fila_contratos'] = historico_fila[historico_fila['FLUXO'] == 'CONTRATO']
    historico_contratos = st.session_state['historico_fila_contratos']
else:
    historico_contratos = st.session_state['historico_fila_contratos']


with tabs_saldo:

    st.title('SALDO DE EQUIPAMENTOS')
    r0c1, r0c2, r0c3, r0c4 = st.columns(4)
    st.write('')
    r1c1, r1c2 = st.columns([0.3, 0.7], gap='large')
    st.write('')
    r2c1, r2c2 = st.columns([0.6, 0.4], gap='large')
    st.write('')
    r3c1 = st.container()

    df_saldo_resumido = create_df_resumido(historico_contratos)

    r1c1.write('Saldo resumido de equipamentos.')
    st_saldo_resumido = r1c1.dataframe(df_saldo_resumido,
                                       use_container_width=True,
                                       hide_index=True,
                                       on_select='rerun')

    r2c2.write('Distribuição do status dos equipamentos.')
    st_status = r2c2.plotly_chart(create_fig_status(df_saldo_resumido.loc[st_saldo_resumido.selection.rows]),
                                  on_select='rerun',
                                  use_container_width=True)

    r1c2.write('Caixas rankeadas de acordo com a % do SLA do equipamento mais antigo.')
    st_criticos = r1c2.plotly_chart(create_fig_criticos(df_saldo_resumido.loc[st_saldo_resumido.selection.rows],
                                                        points_status=st_status.selection.points),
                                    on_select='rerun',
                                    use_container_width=True)

    df_saldo_filtrado = create_df_historico_filtrado(df_saldo_resumido.loc[st_saldo_resumido.selection.rows],
                                                points_critico=st_criticos.selection.points,
                                                points_status=st_status.selection.points)[[
        'ENDEREÇO',
        'CAIXA',
        'SERIAL',
        'CLIENTE',
        'EQUIPAMENTO',
        'ORDEM DE SERVIÇO',
        'GARANTIA',
        'DT RECEBIMENTO',
        'STATUS'
    ]]

    r2c1.write('Saldo detalhado de equipamentos.')
    r2c1.dataframe(df_saldo_filtrado,
                   use_container_width=True,
                   hide_index=True,
                   column_config={'DT RECEBIMENTO':st.column_config.DateColumn('DT RECEBIMENTO', format='DD/MM/YYYY')})
    
    r3c1.write('Ranking dos contratos de acordo com o volume de equipamentos no fila.')
    if st_saldo_resumido.selection.rows:
        r3c1 = st.plotly_chart(create_fig_volume(df_saldo_resumido.loc[st_saldo_resumido.selection.rows]))
        r0c1.metric('Total de equipamentos:', value='{:,}'.format(sum(df_saldo_resumido.loc[st_saldo_resumido.selection.rows, 'QUANTIDADE'])).replace(',','.'))
    else:
        r3c1 = st.plotly_chart(create_fig_volume(df_saldo_resumido))
        r0c1.metric('Total de equipamentos:', value='{:,}'.format(sum(df_saldo_resumido['QUANTIDADE'])).replace(',','.'))

    r0c2.metric('Dentro da garantia:', value='{:,}'.format(len(df_saldo_filtrado[df_saldo_filtrado['GARANTIA'] == 'S'])).replace(',','.'))
    r0c3.metric('Fora da garantia:', value='{:,}'.format(len(df_saldo_filtrado[df_saldo_filtrado['GARANTIA'] == 'N'])).replace(',','.'))
    r0c4.metric('Equipamentos com atraso:', value='{:,}'.format(len(df_saldo_filtrado[df_saldo_filtrado['STATUS'].isin(['LENTO', 'CRÍTICO', 'SLA ESTOURADO'])])).replace(',','.'))


with tabs_saidas:

    st.title('HISTÓRICO DE SAÍDAS')
    r0c1, r0c2, r0c3, r0c4 = st.columns(4)
    st.write('')
    r1c1, r1c2 = st.columns([0.3, 0.7], gap='large')
    st.write('')
    r2c1, r2c2 = st.columns([0.6, 0.4], gap='large')
    st.write('')
    r3c1 = st.container()

    df_saldo_resumido = r1c1.dataframe(create_df_resumido(historico_contratos, 'LAB'),
                                       use_container_width=True,
                                       hide_index=True,
                                       on_select='rerun')


# def create_fig_status_saidas():
#     df = st.session_state['saidas_contratos_selecao'].copy()
#     df['SAÍDA FILA'] = df['SAÍDA FILA'].dt.strftime('%Y/%m')
#     df = df.groupby(['SAÍDA FILA', 'STATUS'])['EQUIPAMENTO'].count().reset_index()
#     df.rename(columns={'EQUIPAMENTO':'QUANTIDADE'}, inplace=True)
    
#     fig = px.bar(df,
#                  x='SAÍDA FILA',
#                  y='QUANTIDADE',
#                  color='STATUS',
#                  color_discrete_map={
#                     'RÁPIDO':'#008000',
#                     'MÉDIO':'#32CD32',
#                     'LENTO':'#FFD700',
#                     'CRÍTICO':'#FF8C00',
#                     'SLA ESTOURADO':'#8B0000'
#                  },
#                  orientation='v',
#                  barmode='group',
#                  text='QUANTIDADE',
#                  category_orders={'STATUS':['RÁPIDO', 'MÉDIO', 'LENTO', 'CRÍTICO', 'SLA ESTOURADO']})
    
#     fig.update_traces(textposition='inside',
#                       orientation='v')
    
#     fig.update_layout(yaxis_title=None,
#                       xaxis_title=None,
#                       yaxis_visible=False)
    
#     return fig


# def html_saldo_contrato():
#     df = st.session_state['df_saldo_atual_contratos_resumido'].copy()
#     df.loc[df['CLIENTE'].str.startswith('COBRA'), 'CLIENTE'] = 'COBRA'
#     df.loc[df['CLIENTE'].str.startswith('BB'), 'CLIENTE'] = 'COBRA'
#     df.loc[df['CLIENTE'].str.startswith('MERCADO'), 'CLIENTE'] = 'MERCADO PAGO'

#     df.loc[df['EQUIPAMENTO'].str.contains('PPC930'), 'EQUIPAMENTO'] = 'PPC930'

#     df = df.groupby(['CLIENTE', 'EQUIPAMENTO'])[['QTD OS', 'QTD FILA']].sum().reset_index()

#     html_contratos = df[['CLIENTE', 'EQUIPAMENTO', 'QTD OS', 'QTD FILA']].to_html(index=False, index_names=False, justify='left', na_rep='')
#     html_contratos = html_contratos.replace('<table border="1" class="dataframe">',
#                                         '<style>\ntable {\n  border-collapse: collapse;\n  width: 100%;\n}\n\nth, td {\n  text-align: center;\n  padding-top: 2px;\n  padding-bottom: 1px;\n  padding-left: 8px;\n  padding-right: 8px;\n}\n\ntr:nth-child(even) {\n  background-color: #DCDCDC;\n}\n\ntable, th, td {\n  border: 2px solid black;\n  border-collapse: collapse;\n}\n</style>\n<table border="1" class="dataframe">')
    
#     return html_contratos


# @st.experimental_dialog("Filtros de Saldo", width='large')
# def open_dialog_filtros_saldo():
#     df = st.session_state['historico_fila']
#     df = df[(df['FLUXO'] == 'CONTRATO') & (df['ENDEREÇO'] != 'LAB')]

#     df2 = st.session_state['df_saldo_atual_contratos_resumido']

#     fr1c1, fr1c2 = st.columns(2)
#     fr2c1, fr2c2 = st.columns(2)
#     fr3c1, fr3c2 = st.columns(2)
#     fr4c1, fr4c2 = st.columns(2)
#     fr5c1, fr5c2 = st.columns(2)

#     ft_cliente = fr1c1.multiselect('CLIENTE', df2['CLIENTE'].unique())
#     ft_equip = fr1c2.multiselect('EQUIPAMENTO', df2['EQUIPAMENTO'].unique())

#     ft_os = fr2c1.multiselect('NUM OS', df['NUM OS'].unique())
#     ft_ns = fr2c2.multiselect('SERIAL', df['SERIAL'].unique())

#     ft_end = fr3c1.multiselect('ENDEREÇO', df['ENDEREÇO'].unique())
#     ft_caixa = fr3c2.multiselect('CAIXA', df['CAIXA'].unique())

#     ft_dtger_min = fr4c1.date_input('DATA ENTRADA GERFLOOR', value=min(df['ENTRADA GERFLOOR']), format='DD/MM/YYYY')
#     ft_dtger_max = fr4c2.date_input('', value=max(df['ENTRADA GERFLOOR']), format='DD/MM/YYYY')

#     ft_dtfila_min = fr5c1.date_input('DATA ENTRADA FILA', value=min(df['ENTRADA FILA']), format='DD/MM/YYYY')
#     ft_dtfila_max = fr5c2.date_input(' ', value=max(df['ENTRADA FILA']), format='DD/MM/YYYY')

#     if st.button('APLICAR FILTROS', use_container_width=True):
#         if ft_cliente:
#             df = df[df['CLIENTE'].isin(ft_cliente)]
#         if ft_equip:
#             df = df[df['EQUIPAMENTO'].isin(ft_equip)]
#         if ft_os:
#             df = df[df['NUM OS'].isin(ft_os)]
#         if ft_ns:
#             df = df[df['SERIAL'].isin(ft_ns)]
#         if ft_end:
#             df = df[df['ENDEREÇO'].isin(ft_end)]
#         if ft_caixa:
#             df = df[df['CAIXA'].isin(ft_caixa)]

#         df = df[(df['ENTRADA GERFLOOR'] >= pd.to_datetime(ft_dtger_min)) & (df['ENTRADA GERFLOOR'] <= pd.to_datetime(ft_dtger_max))]
#         df = df[(df['ENTRADA FILA'] >= pd.to_datetime(ft_dtfila_min)) & (df['ENTRADA FILA'] <= pd.to_datetime(ft_dtfila_max))]

#         st.session_state['df_saldo_atual_contratos'] = create_df_saldo_contratos(df)
#         df_sacr = create_df_saldo_contratos_resumido(st.session_state['df_saldo_atual_contratos'])

#         if ft_cliente:
#             df_sacr = df_sacr[df_sacr['CLIENTE'].isin(ft_cliente)]
#         if ft_equip:
#             df_sacr = df_sacr[df_sacr['EQUIPAMENTO'].isin(ft_equip)]

#         st.session_state['df_saldo_atual_contratos_resumido'] = df_sacr

#         st.rerun()


# @st.experimental_dialog("Filtros de Saída", width='large')
# def open_dialog_filtros_saida():
#     df = st.session_state['historico_fila']
#     df = df[(df['FLUXO'] == 'CONTRATO') & (df['ENDEREÇO'] == 'LAB')]

#     df2 = st.session_state['df_saidas_contratos_resumido']

#     fr1c1, fr1c2 = st.columns(2)
#     fr2c1, fr2c2 = st.columns(2)
#     fr3c1, fr3c2 = st.columns(2)
#     fr4c1, fr4c2 = st.columns(2)
#     fr5c1, fr5c2 = st.columns(2)

#     ft_cliente = fr1c1.multiselect('CLIENTE', df2['CLIENTE'].unique())
#     ft_equip = fr1c2.multiselect('EQUIPAMENTO', df2['EQUIPAMENTO'].unique())

#     ft_os = fr2c1.multiselect('NUM OS', df['NUM OS'].unique())
#     ft_ns = fr2c2.multiselect('SERIAL', df['SERIAL'].unique())

#     ft_end = fr3c1.multiselect('ENDEREÇO', df['ENDEREÇO'].unique())
#     ft_caixa = fr3c2.multiselect('CAIXA', df['CAIXA'].unique())

#     ft_dtger_min = fr4c1.date_input('DATA ENTRADA GERFLOOR', value=min(df['ENTRADA GERFLOOR']), format='DD/MM/YYYY')
#     ft_dtger_max = fr4c2.date_input('', value=max(df['ENTRADA GERFLOOR']), format='DD/MM/YYYY')

#     ft_dtfila_min = fr5c1.date_input('DATA ENTRADA FILA', value=min(df['ENTRADA FILA']), format='DD/MM/YYYY')
#     ft_dtfila_max = fr5c2.date_input(' ', value=max(df['ENTRADA FILA']), format='DD/MM/YYYY')

#     ft_dtsfila_min = fr5c1.date_input('DATA SAÍDA FILA', value=min(df['SAÍDA FILA']), format='DD/MM/YYYY')
#     ft_dtsfila_max = fr5c2.date_input('  ', value=max(df['SAÍDA FILA']), format='DD/MM/YYYY')

#     if st.button('APLICAR FILTROS', use_container_width=True):
#         if ft_cliente:
#             df = df[df['CLIENTE'].isin(ft_cliente)]
#         if ft_equip:
#             df = df[df['EQUIPAMENTO'].isin(ft_equip)]
#         if ft_os:
#             df = df[df['NUM OS'].isin(ft_os)]
#         if ft_ns:
#             df = df[df['SERIAL'].isin(ft_ns)]
#         if ft_end:
#             df = df[df['ENDEREÇO'].isin(ft_end)]
#         if ft_caixa:
#             df = df[df['CAIXA'].isin(ft_caixa)]

#         df = df[(df['ENTRADA GERFLOOR'] >= pd.to_datetime(ft_dtger_min)) & (df['ENTRADA GERFLOOR'] <= pd.to_datetime(ft_dtger_max))]
#         df = df[(df['ENTRADA FILA'] >= pd.to_datetime(ft_dtfila_min)) & (df['ENTRADA FILA'] <= pd.to_datetime(ft_dtfila_max))]
#         df = df[(df['SAÍDA FILA'] >= pd.to_datetime(ft_dtsfila_min)) & (df['SAÍDA FILA'] <= pd.to_datetime(ft_dtsfila_max))]

#         st.session_state['df_saidas_contratos'] = create_df_saidas_contratos(df)
#         df_scr = create_df_saidas_contratos_resumido(st.session_state['df_saidas_contratos'])

#         if ft_cliente:
#             df_scr = df_scr[df_scr['CLIENTE'].isin(ft_cliente)]
#         if ft_equip:
#             df_scr = df_scr[df_scr['EQUIPAMENTO'].isin(ft_equip)]

#         st.session_state['df_saldo_atual_contratos_resumido'] = df_scr

#         st.rerun()
