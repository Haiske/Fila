import streamlit as st
import pandas as pd
from datetime import datetime, date
import io
import plotly.express as px
from workalendar.america import Brazil

st.set_page_config('ESTOQUE • FILA', page_icon='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png', layout='wide')
st.logo('https://raw.githubusercontent.com/Haiske/Fila/main/attachments/logo.png', icon_image='https://raw.githubusercontent.com/Haiske/Fila/main/attachments/icon.png')

st.sidebar.title('MÓDULOS')
st.sidebar.page_link('dash.py', label="CONTRATOS", disabled=True)
st.sidebar.page_link('pages/tabelas.py', label="DADOS BRUTOS")

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

    if endereço:
        n_df = df[df['ENDEREÇO'] == endereço].copy()
    else:
        n_df = df.copy()
    n_df = n_df.groupby(['CLIENTE', 'EQUIPAMENTO'])[['SERIAL']].count().reset_index()
    n_df.rename(columns={'SERIAL':'QUANTIDADE'}, inplace=True)

    try:
        n_df.sort_values(['CLIENTE', 'EQUIPAMENTO'], inplace=True)
    except:
        pass

    return n_df


def create_df_filtrado(df_filtro, df_alvo, points_critico='', points_status='', points_data='', endereço='FILA'):

    # Geramos um novo dataframe que será filtrado de acordo com as linhas selecionadas
    # no nosso dataframe resumido.

    df_selecao = df_filtro.copy()

    critic_points = list(i['y'][1:7] for i in points_critico)
    status_points = list(i['y'] for i in points_status)
    data_points = list(i['x'][0:4] + '-' + i['x'][5:7] + ',' + i['legendgroup'] for i in points_data)

    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = df_alvo.copy()
        if endereço:
            df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    else:
        df_detalhado = df_alvo.copy()
        if endereço:
            df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]

    if len(critic_points) > 0:
        df_detalhado = df_detalhado[df_detalhado['CAIXA'].isin(critic_points)]
        
    if len(status_points) > 0:
        df_detalhado = df_detalhado[df_detalhado['STATUS'].isin(status_points)]

    if len(data_points) > 0:
        df_detalhado['CONCATENADO 2'] = pd.to_datetime(df_detalhado['DT ENVIO LAB']).dt.strftime("%Y-%m") + ',' + df_detalhado['STATUS']
        df_detalhado = df_detalhado[df_detalhado['CONCATENADO 2'].isin(data_points)]

    return df_detalhado


def create_df_liberado(data_liberacao):

    # Essa função exige uma data, e a partir dessa data geramos um dataframe
    # dos equipamentos que foram liberados na data informada.

    try:
        df = pd.read_csv(f'https://raw.githubusercontent.com/Haiske/Fila/main/tables/liberados/{data_liberacao}.csv', sep='	',
                         converters={'SERIAL':str,
                                     'ORDEM DE SERVIÇO':str})
    except:
        return pd.DataFrame()
    
    df = df[df['FLUXO'] == 'CONTRATO']
    df = df.join(st.session_state['historico_fila'].set_index(['SERIAL', 'ORDEM DE SERVIÇO'])[['ENDEREÇO',
                                                                                               'CAIXA',
                                                                                               'STATUS',
                                                                                               'DT ENVIO LAB',
                                                                                               'AGING TOTAL']],
                    on=['SERIAL', 'ORDEM DE SERVIÇO'],
                    how='left')

    df.loc[df['ENDEREÇO'] == 'LAB', 'ENDEREÇO'] = 'EM LABORATÓRIO'
    df.loc[df['ENDEREÇO'] == 'FILA', 'ENDEREÇO'] = 'EM ESTOQUE'
    df.loc[df['ENDEREÇO'].isna(), 'ENDEREÇO'] = 'NÃO LOCALIZADO'

    return df


def create_fig_criticos(df):

    # Criamos um gráfico de barras horizontais que rankeia as caixas de acordo
    # com a % do SLA, levando em consideração apenas a maior dentro de cada caixa.

    df_selecao = df.copy()



    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = historico_fila.copy()
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    
    else:
        df_detalhado = historico_fila.copy()

    n_df = df_detalhado[df_detalhado['ENDEREÇO'] == 'FILA'].copy()
    n_df['CAIXA'] = n_df['CAIXA'].astype('str')
    n_df['CAIXA'] = "ㅤ" + n_df['CAIXA']
    n_df['RÓTULO'] = n_df['CLIENTE'] + ' - ' + n_df['EQUIPAMENTO']
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


def create_fig_status(df_filtro, df_alvo, points_caixa='', points_data='', endereço='FILA'):

    # Criamos um gráfico de rosca que nos mostra a distribuição do status dos equipamentos.

    df_selecao = df_filtro.copy()

    points_list = list(i['y'][1:7] for i in points_caixa)
    data_points = list(i['x'][0:4] + '-' + i['x'][5:7] + ',' + i['legendgroup'] for i in points_data)

    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = df_alvo.copy()
        if endereço:
            df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    
    else:
        df_detalhado = df_alvo
        if endereço:
            df_detalhado = df_detalhado[df_detalhado['ENDEREÇO'] == endereço]

    if len(points_list) > 0:
        df_detalhado = df_detalhado[df_detalhado['CAIXA'].isin(points_list)]

    if len(data_points) > 0:
        df_detalhado['CONCATENADO 2'] = df_detalhado['DT ENVIO LAB'].astype(str).str[:7] + ',' + df_detalhado['STATUS']
        df_detalhado = df_detalhado[df_detalhado['CONCATENADO 2'].isin(data_points)]

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


def create_fig_localizados(df_filtro, df_alvo):

    # Criamos um gráfico de rosca onde nos mostra a relação de equipamentos que ainda estão no fila,
    # equipamentos já foram entregues ao laboratório, e equipamentos que ainda não foram localizados.

    df_selecao = df_filtro.copy()

    if len(df_selecao) > 0:
        df_selecao['CONCATENADO'] = df_selecao['CLIENTE'] + df_selecao['EQUIPAMENTO']

        df_detalhado = df_alvo.copy()
        df_detalhado['CONCATENADO'] = df_detalhado['CLIENTE'] + df_detalhado['EQUIPAMENTO']

        df_detalhado = df_detalhado[df_detalhado['CONCATENADO'].isin(list(df_selecao['CONCATENADO']))]
    
    else:
        df_detalhado = df_alvo

    df_detalhado = df_detalhado.groupby(['ENDEREÇO'])[['SERIAL']].count().reset_index()

    fig = px.pie(df_detalhado,
                                names='ENDEREÇO',
                                values='SERIAL',
                                color='ENDEREÇO',
                                hole=0.4,
                                color_discrete_map={'EM LABORATÓRIO':'#008000',
                                                'EM ESTOQUE':'#FFD700',
                                                'NÃO LOCALIZADO':'#8B0000'},
                            category_orders={'ENDEREÇO':['EM LABORATÓRIO', 'EM ESTOQUE', 'NÃO LOCALIZADO']})
    fig.update_traces(textinfo='value+percent')

    return fig


def create_fig_status_saidas(df):

    # Criamos um gráfico de barras onde temos um agrupamento por meses, e subagrupamentos por status.
    # E por fim, retornamos apenas os últimos 12 meses.

    n_df = df[df['ENDEREÇO'] == 'LAB'].copy()
    n_df['DT ENVIO LAB'] = pd.to_datetime(n_df['DT ENVIO LAB']).dt.strftime('%Y/%m')
    n_df = n_df.groupby(['DT ENVIO LAB', 'STATUS'])['SERIAL'].count().reset_index()
    n_df = n_df[n_df['DT ENVIO LAB'].isin(n_df['DT ENVIO LAB'].sort_values(ascending=False).unique()[:13])]
    n_df.rename(columns={'SERIAL':'QUANTIDADE'}, inplace=True)
    
    fig = px.bar(n_df,
                 x='DT ENVIO LAB',
                 y='QUANTIDADE',
                 color='STATUS',
                 color_discrete_map={
                    'RÁPIDO':'#008000',
                    'MÉDIO':'#32CD32',
                    'LENTO':'#FFD700',
                    'CRÍTICO':'#FF8C00',
                    'SLA ESTOURADO':'#8B0000'
                 },
                 orientation='v',
                 barmode='group',
                 text='QUANTIDADE',
                 category_orders={'STATUS':['RÁPIDO', 'MÉDIO', 'LENTO', 'CRÍTICO', 'SLA ESTOURADO']})
    
    fig.update_traces(textposition='outside',
                      orientation='v')
    
    fig.update_layout(yaxis_title=None,
                      xaxis_title=None,
                      yaxis_visible=False)

    fig.update_xaxes(categoryorder='array',
                     categoryarray=list(n_df['DT ENVIO LAB'].sort_values(ascending=True).unique()))
    
    return fig


def create_fig_volume(df):

    # Criamos um gráfico de barras que mostra os 10 maiores clientes em relação
    # ao volume de equipamentos no Fila.

    n_df = df.groupby(['CLIENTE'])['SERIAL'].count().reset_index()
    n_df.rename(columns={'SERIAL':'QUANTIDADE'}, inplace=True)
    n_df = n_df.sort_values(['QUANTIDADE'], ascending=False).head(10)

    fig = px.bar(n_df,
                 x='CLIENTE',
                 y='QUANTIDADE',
                 color_discrete_sequence=['#13399A'],
                 orientation='v',
                 text='QUANTIDADE')
    
    fig.update_traces(textposition='outside',
                      orientation='v')
  
    fig.update_layout(yaxis_title=None,
                      xaxis_title=None,
                      yaxis_visible=False)

    return fig


def create_fig_volume_saida(df, points_data=''):

    # Criamos um gráfico de barras horizontal para rankear os clientes com maior volume de saída

    data_points = list(i['x'][0:4] + '-' + i['x'][5:7] + ',' + i['legendgroup'] for i in points_data)

    n_df = df.copy()
    n_df['DT ENVIO LAB'] = pd.to_datetime(n_df['DT ENVIO LAB']).dt.strftime("%Y-%m")
    n_df = n_df.groupby(['CLIENTE', 'DT ENVIO LAB', 'STATUS'])['SERIAL'].count().reset_index()
    n_df.rename(columns={'SERIAL':'QUANTIDADE'}, inplace=True)

    if len(data_points) > 0:
        n_df['CONCATENADO'] = n_df['DT ENVIO LAB'].astype(str).str[:7] + ',' + n_df['STATUS']
        n_df = n_df[n_df['CONCATENADO'].isin(data_points)]

    n_df = n_df.groupby(['CLIENTE'])['QUANTIDADE'].sum().reset_index()
    n_df = n_df.sort_values(['QUANTIDADE'], ascending=True).tail(10)

    print(n_df.info())
    
    fig = px.bar(n_df,
                 y='CLIENTE',
                 x='QUANTIDADE',
                 color_discrete_sequence=['#13399A'],
                 orientation='h',
                 barmode='relative',
                 text='QUANTIDADE')
    
    fig.update_traces(textposition='outside',
                      orientation='h')
  
    # fig.update_layout(yaxis_title=None,
    #                   xaxis_title=None,
    #                   yaxis_visible=False)

    return fig


@st.experimental_dialog("Filtros", width='large')
def open_dialog_filtros():

    # Essa é uma caixa de diálogo que nos permitirá adicionar alguns filtros ao nosso dashboard.
    st.write('Para resetar os filtros, basta clicar em "aplicar filtros" sem filtros selecionados.')

    df = st.session_state['historico_fila'].copy()
    df = df[(df['FLUXO'] == 'CONTRATO')]

    fr1c1, fr1c2 = st.columns(2)
    fr2c1, fr2c2 = st.columns(2)
    fr3c1, fr3c2 = st.columns(2)
    fr4c1, fr4c2 = st.columns(2)
    fr5c1, fr5c2 = st.columns(2)

    ft_cliente = fr1c1.multiselect('CLIENTE', df['CLIENTE'].unique())
    ft_equip = fr1c2.multiselect('EQUIPAMENTO', df['EQUIPAMENTO'].unique())

    ft_os = fr2c1.multiselect('ORDEM DE SERVIÇO', df['ORDEM DE SERVIÇO'].unique())
    ft_ns = fr2c2.multiselect('SERIAL', df['SERIAL'].unique())

    ft_end = fr3c1.multiselect('ENDEREÇO', df['ENDEREÇO'].unique())
    ft_caixa = fr3c2.multiselect('CAIXA', df['CAIXA'].unique())

    ft_dtent_min = fr4c1.date_input('DATA RECEBIMENTO', value=min(df['DT RECEBIMENTO']), format='DD/MM/YYYY')
    ft_dtent_max = fr4c2.date_input('', value=max(df['DT RECEBIMENTO']), format='DD/MM/YYYY')

    ft_dtsai_min = fr5c1.date_input('DATA ENVIO LAB', value=min(df.loc[~df['DT ENVIO LAB'].isna(), 'DT ENVIO LAB']), format='DD/MM/YYYY')
    ft_dtsai_max = fr5c2.date_input(' ', value=max(df.loc[~df['DT ENVIO LAB'].isna(), 'DT ENVIO LAB']), format='DD/MM/YYYY')

    if st.button('APLICAR FILTROS', use_container_width=True):
        if ft_cliente:
            df = df[df['CLIENTE'].isin(ft_cliente)]
        if ft_equip:
            df = df[df['EQUIPAMENTO'].isin(ft_equip)]
        if ft_os:
            df = df[df['NUM OS'].isin(ft_os)]
        if ft_ns:
            df = df[df['SERIAL'].isin(ft_ns)]
        if ft_end:
            df = df[df['ENDEREÇO'].isin(ft_end)]
        if ft_caixa:
            df = df[df['CAIXA'].isin(ft_caixa)]

        df = df[(df['DT RECEBIMENTO'] >= pd.to_datetime(ft_dtent_min)) & (df['DT RECEBIMENTO'] <= pd.to_datetime(ft_dtent_max))]
        df = df[((df['DT ENVIO LAB'] >= pd.to_datetime(ft_dtsai_min)) & (df['DT ENVIO LAB'] <= pd.to_datetime(ft_dtsai_max))) | (df['DT ENVIO LAB'].isna())]

        st.session_state['historico_fila_filtro'] = df

        st.rerun()

# Salvamos o histórico do fila na memória do navegador.
if 'historico_fila' not in st.session_state:
    st.session_state['historico_fila'] = create_df_historico_fila()
    historico_fila = st.session_state['historico_fila']
    historico_fila = historico_fila[historico_fila['FLUXO'] == 'CONTRATO']
else:
    historico_fila = st.session_state['historico_fila']
    historico_fila = historico_fila[historico_fila['FLUXO'] == 'CONTRATO']

### Adicionamos um botão de filtragem e um de remover os filtros no nosso dashboard.
if st.sidebar.button('FILTROS', use_container_width=True):
    open_dialog_filtros()

if 'historico_fila_filtro' in st.session_state:
    historico_fila = st.session_state['historico_fila_filtro'][st.session_state['historico_fila_filtro']['FLUXO'] == 'CONTRATO']


with tabs_saldo:

    ### Criamos o layout da tabs de saldo dos Contratos.
    st.title('SALDO DE EQUIPAMENTOS')
    r0c1, r0c2, r0c3, r0c4 = st.columns(4)
    st.write('')
    r1c1, r1c2 = st.columns([0.3, 0.7], gap='large')
    st.write('')
    r2c1, r2c2 = st.columns([0.6, 0.4], gap='large')
    st.write('')
    r3c1 = st.container()

    # Criamos um dataframe com o saldo agrupado por cliente e modelo
    # e trazemos a quantidade de equipamentos para cada grupo.
    # Por fim, adicionamos esse dataframe a nossa página permitindo a seleção de linhas.
    df_saldo_resumido = create_df_resumido(historico_fila)

    r1c1.write('Saldo resumido de equipamentos.')
    st_saldo_resumido = r1c1.dataframe(df_saldo_resumido,
                                       use_container_width=True,
                                       hide_index=True,
                                       on_select='rerun')

    # Criamos um gráfico de barras para mostrar as caixas que estão mais críticas em relação
    # ao SLA, permitindo a filtragem através das linhas selecionadas no dataframe resumido.
    # Adicionamos esse gráfico a nossa página e permitimos a seleção das barras.
    r1c2.write('Caixas rankeadas de acordo com a % do SLA do equipamento mais antigo.')
    st_criticos = r1c2.plotly_chart(create_fig_criticos(df_saldo_resumido.loc[st_saldo_resumido.selection.rows]),
                                    on_select='rerun',
                                    use_container_width=True)

    # Criamos um gráfico de roscas que vai nos mostrar a distribuição do status dos equipamentos.
    # Esse gráfico pode ser filtrado de acordo com a seleção das linhas no dataframe resumo e 
    # de acordo com as barras selecionadas no gráfico de caixas críticas.
    r2c2.write('Distribuição do status dos equipamentos.')
    st_status = r2c2.plotly_chart(create_fig_status(df_saldo_resumido.loc[st_saldo_resumido.selection.rows],
                                                    historico_fila,
                                                    points_caixa=st_criticos.selection.points),
                                  on_select='rerun',
                                  use_container_width=True)

    # Criamos um dataframe que é filtrado a partir das linhas selecionadas no dataframe resumo e das 
    # barras selecionadas no gráfico de caixas críticas. Esse dataframe traz informações mais detalhadas
    # dos equipamentos.
    df_saldo_filtrado = create_df_filtrado(df_saldo_resumido.loc[st_saldo_resumido.selection.rows],
                                                    historico_fila,
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
        'AGING TOTAL',
        'STATUS'
    ]]

    # Adicionamos o dataframe filtrado a nossa página.
    r2c1.write('Saldo detalhado de equipamentos.')
    r2c1.dataframe(df_saldo_filtrado,
                   use_container_width=True,
                   hide_index=True,
                   column_config={'DT RECEBIMENTO':st.column_config.DateColumn('DT RECEBIMENTO', format='DD/MM/YYYY')})
    
    # Adicionamos um gráfico de barras que mostra os 10 maiores clientes de acordo com o volume de equipamentos.
    # Esse gráfico pode ser filtrado através das linhas selecionadas no gráfico de resumo.
    r3c1.write('Ranking dos contratos de acordo com o volume de equipamentos no fila.')
    r3c1 = st.plotly_chart(create_fig_volume(df_saldo_filtrado))

    # Além disso, adicionamos algumas métricas a nossa página.
    r0c1.metric('Total de equipamentos:', value='{:,}'.format(len(df_saldo_filtrado['SERIAL'])).replace(',','.'))
    r0c2.metric('Dentro da garantia:', value='{:,}'.format(len(df_saldo_filtrado[df_saldo_filtrado['GARANTIA'] == 'S'])).replace(',','.'))
    r0c3.metric('Fora da garantia:', value='{:,}'.format(len(df_saldo_filtrado[df_saldo_filtrado['GARANTIA'] == 'N'])).replace(',','.'))
    r0c4.metric('Equipamentos com atraso:', value='{:,}'.format(len(df_saldo_filtrado[df_saldo_filtrado['STATUS'].isin(['LENTO', 'CRÍTICO', 'SLA ESTOURADO'])])).replace(',','.'))


with tabs_liberados:

    ### Definimos aqui o layout da nossa tabs de liberados.
    st.title('LISTA DE EQUIPAMENTOS LIBERADOS')
    r0c1, r0c2, r0c3, r0c4 = st.columns(4)
    st.write('')
    r1c1, r1c2, r1c3 = st.columns(3, gap='large')
    st.write('')
    r2c1, r2c2, r2c3 = st.columns(3, gap='large')
    st.write('')
    r3c1 = st.container()

    # Criamos um input onde selecionamos uma data dos equipamentos liberados.
    dt_liberacao = r1c1.date_input(label='Data de liberação:',
                                   min_value=date(2024, 7, 1),
                                   max_value=date(2024, 7, 14),
                                   help='Este é um input para selecionar a data que queremos buscar os equipamentos liberados. As datas disponíveis de exemplo são apenas do dia 01/07/2024 até 14/07/2024, sendo que os finais de semana não possuem lista, mas podem ser selecionados.')

    # Geramos um dataframe a partir da data informada no input acima.
    df_lista_liberados = create_df_liberado(dt_liberacao)

    # Verificamos se o dataframe contém informações e o exibimos em um dataframe resumido.
    # Caso contrário, exibimos um aviso na página.
    if len(df_lista_liberados) > 0:
        df_liberados_resumido = create_df_resumido(df_lista_liberados, endereço=False)

        # O dataframe de resumo que criamos aqui permite a seleção de linhas para que 
        # possamos filtrar os próximos visuais da nossa página.
        r2c1.write('Lista resumida de equipamentos liberados.')
        st_lista_liberado = r2c1.dataframe(df_liberados_resumido,
                                        use_container_width=True,
                                        hide_index=True,
                                        on_select='rerun')

        # Criamos um dataframe detalhado que pode ser filtrado pelo dataframe resumido.
        df_liberados_filtrado = create_df_filtrado(df_liberados_resumido.loc[st_lista_liberado.selection.rows],
                                                        df_lista_liberados,
                                                        endereço=False)[[
            'ENDEREÇO',
            'CAIXA',
            'SERIAL',
            'CLIENTE',
            'EQUIPAMENTO',
            'ORDEM DE SERVIÇO',
            'GARANTIA',
            'DT RECEBIMENTO',
            'DT ENVIO LAB',
            'AGING TOTAL',
            'STATUS'
        ]]

        # Criamos um gráfico de rosca que nos mostra a % de equipamentos no fila, enviados para o laboratório e
        # equipamentos não localizados.
        r2c2.write('Status de localização dos equipamentos.')
        r2c2.plotly_chart(create_fig_localizados(df_liberados_resumido.loc[st_lista_liberado.selection.rows],
                                            df_lista_liberados))

        # Criamos um gráfico de rosca que nos mostra a distribuição do status em relação ao SLA dos equipamentos
        # que foram liberados.
        r2c3.write('Distribuição do status dos equipamentos.')
        r2c3.plotly_chart(create_fig_status(df_liberados_resumido.loc[st_lista_liberado.selection.rows],
                                            df_lista_liberados, points_caixa='',
                                            endereço=False))

        # Exibimos o dataframe detalhado na nossa página.
        r3c1.write('Lista detalhada de equipamentos liberados.')
        r3c1.dataframe(df_liberados_filtrado,
                       use_container_width=True,
                       hide_index=True,
                       column_config={'DT RECEBIMENTO':st.column_config.DateColumn('DT RECEBIMENTO', format='DD/MM/YYYY'),
                                      'DT ENVIO LAB':st.column_config.DateColumn('DT ENVIO LAB', format='DD/MM/YYYY')})

        # Criamos uma métrica mostrando a quantidade de equipamentos liberados.
        r0c1.metric('Total liberado:', '{:,}'.format(len(df_liberados_filtrado)).replace(',','.'))

    else:
        r2c1.header('Sem liberação de equipamentos para a data informada.')

        r0c1.metric('Total liberado:', '--')


with tabs_saidas:

    ### Definimos aqui o layout da nossa página.
    st.title('HISTÓRICO DE SAÍDAS')
    r0c1, r0c2, r0c3, r0c4 = st.columns(4)
    st.write('')
    r1c1, r1c2 = st.columns([0.3, 0.7], gap='large')
    st.write('')
    r2c1, r2c2 = st.columns([0.6, 0.4], gap='large')
    st.write('')
    r3c1 = st.container()

    # Criamos um dataframe resumindo as saídas por cliente e equipamento
    # e adicionamos esse dataframe a nossa página, permitindo a seleção de
    # linhas para podermos filtrar os visuais mais a frente.
    df_saidas_resumidas = create_df_resumido(historico_fila, 'LAB')

    r1c1.write('Saídas resumidas por cliente e equipamento.')
    st_saidas_resumidas = r1c1.dataframe(df_saidas_resumidas,
                                       use_container_width=True,
                                       hide_index=True,
                                       on_select='rerun')

    # Criamos um gráfico de barras verticais agrupado por data e subagrupado por status.
    # Também permitimos a seleção de colunas para que possamos filtrar outros visuais.
    r3c1.write('Distribuição do status dos equipamentos entregues nos últimos meses.')
    st_status_saida = r3c1.plotly_chart(create_fig_status_saidas(historico_fila),
                                        use_container_width=True,
                                        on_select='rerun')
    
    # Criamos um dataframe detalhado das saídas que pode ser filtrado pelo dataframe resumido e pelo
    # gráfico de barras acima.
    df_saidas_filtradas = create_df_filtrado(df_saidas_resumidas.loc[st_saidas_resumidas.selection.rows],
                                      historico_fila,
                                      points_data=st_status_saida.selection.points,
                                      endereço='LAB')[[
                                          'CAIXA',
                                          'SERIAL',
                                          'CLIENTE',
                                          'EQUIPAMENTO',
                                          'ORDEM DE SERVIÇO',
                                          'GARANTIA',
                                          'DT RECEBIMENTO',
                                          'DT ENVIO LAB',
                                          'AGING TOTAL',
                                          'STATUS'
                                      ]]

    # Exibimos um gráfico de barras horizontais mostrando os clientes com maior volume
    # de saída de equipamentos. Esse gráfico também pode ser filtrado pelo dataframe resumido
    # e pelo gráfico de barras.
    r1c2.write('Clientes com maior volume de saída.')
    r1c2.plotly_chart(create_fig_volume_saida(df_saidas_filtradas, points_data=st_status_saida.selection.points))

    # Criamos um gráfico de rosca mostrando a distribuição do SLA entregue.
    # Esse gráfico também pode ser filtrado pelo dataframe resumido e pelo gráfico de barras.
    r2c2.write('Distribuição de status do SLA dos equipamentos entregues.')
    r2c2.plotly_chart(create_fig_status(df_saidas_resumidas.loc[st_saidas_resumidas.selection.rows],
                                        historico_fila,
                                        points_data=st_status_saida.selection.points,
                                        endereço='LAB'))

    # Exibimos nosso dataframe detalhado.
    # Esse dataframe também pode ser filtrado pelo dataframe resumido e pelo gráfico de barras.
    r2c1.write('Histórico de saídas detalhado.')
    r2c1.dataframe(df_saidas_filtradas,
                   use_container_width=True,
                   hide_index=True,
                   column_config={'DT RECEBIMENTO':st.column_config.DateColumn('DT RECEBIMENTO', format='DD/MM/YYYY'),
                                  'DT ENVIO LAB':st.column_config.DateColumn('DT ENVIO LAB', format='DD/MM/YYYY')})
    
    # Adicionamos algumas métricas a nossa página.
    r0c1.metric('Quantidade enviada:', '{:,}'.format(len(df_saidas_filtradas['SERIAL'])).replace(',','.'))
    r0c2.metric('Dentro da garantia:', value='{:,}'.format(len(df_saidas_filtradas[df_saidas_filtradas['GARANTIA'] == 'S'])).replace(',','.'))
    r0c3.metric('Fora da garantia:', value='{:,}'.format(len(df_saidas_filtradas[df_saidas_filtradas['GARANTIA'] == 'N'])).replace(',','.'))
    r0c4.metric('Entregues com atraso:', value='{:,}'.format(len(df_saidas_filtradas[df_saidas_filtradas['STATUS'].isin(['LENTO', 'CRÍTICO', 'SLA ESTOURADO'])])).replace(',','.'))

