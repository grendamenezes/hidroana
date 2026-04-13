from zeep import Client, Settings
import xml.etree.ElementTree as ET
import pandas as pd
from tqdm import tqdm
from datetime import datetime
import re

def get_inventory (caminho_saida="inventario_ana.csv",
                   var_codEstDE="", 
                   var_codEstATE="", 
                   var_tpEst="2", 
                   var_nmEst="", 
                   var_nmRio="", 
                   var_codSubBacia="", 
                   var_codBacia="", 
                   var_nmMunicipio="", 
                   var_nmEstado="", 
                   var_sgResp="", 
                   var_sgOper="", 
                   var_telemetrica="",
                   save = False):
    # URL do serviço SOAP da ANA
    wsdl = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx?WSDL" 
    # Configuração do cliente SOAP
    # O parâmetro `raw_response=True` retorna o XML completo da resposta,
    # permitindo manipulação manual com regex ou xml.etree.
    settings = Settings(raw_response=True)
    client = Client(wsdl=wsdl, settings=settings)

    # ---------------------------------------------------------------
    # CONSULTA AO SERVIÇO HIDROINVENTARIO
    # Alterar os parâmetros de filtro conforme desejado.
    # ---------------------------------------------------------------
    response = client.service.HidroInventario(
        codEstDE=var_codEstDE,       # Código inicial da estação (opcional)
        codEstATE=var_codEstATE,     # Código final da estação (opcional)
        tpEst=var_tpEst,             # Tipo da estação: 1 = Fluviométrica, 2 = Pluviométrica
        nmEst=var_nmEst,             # Nome da estação (opcional)
        nmRio=var_nmRio,             # Nome do rio (opcional)
        codSubBacia=var_codSubBacia, # Código da sub-bacia (opcional)
        codBacia=var_codBacia,       # Código da bacia (opcional)
        nmMunicipio=var_nmMunicipio, # Nome do município (opcional)
        nmEstado=var_nmEstado,       # Estado (opcional)
        sgResp=var_sgResp,           # Sigla do responsável (opcional)
        sgOper=var_sgOper,           # Sigla da operadora (opcional)
        telemetrica=var_telemetrica  # 1 = Sim / 0 = Não (opcional)
    )

    # ---------------------------------------------------------------
    # PARTE 2 — PROCESSAMENTO DO XML RETORNADO
    # ---------------------------------------------------------------

    # Decodifica o conteúdo da resposta em UTF-8
    xml_text = response.content.decode('utf-8')

    # A estrutura XML da ANA contém múltiplas tags <Table> com os dados.
    # Vamos extrair cada uma delas usando expressões regulares.

    tables = re.compile(r'<Table diffgr:id="Table[0-9]+" msdata:rowOrder="[0-9]+">(.*?)</Table>')
    extract_vals = re.compile(r'<([a-zA-Z0-9]+)>(.*?)</[a-zA-Z0-9]+>')

    # Cria uma lista de dicionários (cada dicionário = 1 estação)
    linhas = []
    for table in tqdm(tables.findall(xml_text), desc="Extraindo registros"):
        linhas.append(dict(extract_vals.findall(table)))

    # Converte para DataFrame
    df = pd.DataFrame(linhas)

    # ---------------------------------------------------------------
    # PARTE 3 — SALVAMENTO DOS RESULTADOS
    # ---------------------------------------------------------------
    if save:
        df.to_csv(caminho_saida, index=False)
        print(f"\nInventário salvo em: {caminho_saida}")  
    return df

# ===============================================================
# Função: get_telemetric_inventory(df, caminho)
# ---------------------------------------------------------------
# Objetivo:
#   Faz o download automático dos dados de todas as estações
#   telemétricas listadas em um inventário (DataFrame).
#   Para cada estação, são baixadas as séries de chuva, nível e vazão.
#
# Observação importante:
#   - Se a estação for apenas pluviométrica, o serviço SOAP da ANA
#     identifica/retorna séries quando a requisição é feita com o
#     código plu (código da estação pluviométrica).
#   - Se a estação for hidrológica (fluviométrica e pluviométrica), o serviço SOAP só
#     encontra as séries quando a requisição é feita com o código flu
#     (código da estação fluviométrica).
#   Portanto, o ideal é usar um inventário que contenha estações mistas (plu +
#   flu).
#
# Entradas:
#   df       -> DataFrame com o inventário de estações fluviométricas (obtido da ANA) -> https://telemetriaws1.ana.gov.br/ServiceANA.asmx?op=HidroInventario 
#   caminho  -> Caminho onde os arquivos CSV serão salvos
#
# Saídas:
#   - Um arquivo CSV por estação, contendo as séries de dados.
#   - Um arquivo 'info_estacoes.csv' com informações gerais e
#     indicadores de disponibilidade de variáveis.
# ===============================================================

def get_telemetric_inventory (df, caminho="", save_info = False):
    if df == None:
        print("\nErro: DataFrame de inventário não fornecido.")
        return
    # URL do serviço SOAP da ANA
    wsdl = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx?WSDL"

    # Configuração do cliente SOAP (resposta bruta em XML)
    settings = Settings(raw_response=True)
    client = Client(wsdl=wsdl, settings=settings)

    # Colunas principais de interesse no inventário
    lista_colum = [
        'BaciaCodigo', 'SubBaciaCodigo', 'RioCodigo', 'RioNome', 'nmEstado',
        'nmMunicipio', 'ResponsavelSigla', 'Codigo', 'Nome', 'Latitude',
        'Longitude', 'Altitude', 'AreaDrenagem', 'PeriodoTelemetricaInicio',
        'PeriodoTelemetricaFim', 'Operando'
    ]

    # Filtra apenas as estações telemétricas
    df = df[df['TipoEstacaoTelemetrica'] == 1]
    df_info = df[lista_colum]

    # Listas auxiliares
    lista_datas = pd.to_datetime(df['PeriodoTelemetricaInicio']).dt.date.astype(str).tolist()
    lista_codigos = df['Codigo'].astype(str).tolist()

    # Listas para registrar disponibilidade de variáveis
    st_chuva, st_nivel, st_vazao = [], [], []

    # Loop principal com barra de progresso
    for cod, dat in tqdm(zip(lista_codigos, lista_datas), total=len(lista_codigos), desc="Baixando estações"):

        # Se não houver data inicial válida, usa um valor padrão
        if dat == 'NaT':
            dat = '2000-01-01'

        # Requisição ao serviço SOAP
        response = client.service.DadosHidrometeorologicos(
            codEstacao=cod,
            dataInicio=dat,
            dataFim=''
        )

        # Decodifica a resposta XML
        xml_text = response.content.decode('utf-8')
        root = ET.fromstring(xml_text)

        # Define os namespaces usados no XML
        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "mrcs": "http://MRCS/"
        }

        # Localiza o nó de resultado
        result_node = root.find(".//mrcs:DadosHidrometeorologicosResult", ns)
        if result_node is None:
            print(f'\nEstação {cod} não encontrada.')
            st_chuva.append('Erro')
            st_nivel.append('Erro')
            st_vazao.append('Erro')
            continue

        # Localiza o bloco diffgram (dados)
        diffgram_node = result_node.find(".//{urn:schemas-microsoft-com:xml-diffgram-v1}diffgram")
        if diffgram_node is None:
            print(f'\nEstação {cod} não encontrada.')
            st_chuva.append('Erro')
            st_nivel.append('Erro')
            st_vazao.append('Erro')
            continue

        # Extrai os dados do diffgram
        dados = []
        for dado in diffgram_node.findall(".//DocumentElement/*"):
            linha = {child.tag: child.text for child in dado}
            dados.append(linha)

        df = pd.DataFrame(dados)

        # Se a estação não tiver dados, marca como indisponível
        if len(df) == 1:
            print(f"\nEstação {cod} não possui dados disponíveis.")
            st_chuva.append('Não')
            st_nivel.append('Não')
            st_vazao.append('Não')
            continue

        # Mantém apenas as colunas desejadas
        colunas_desejadas = ['DataHora', 'Chuva', 'Nivel', 'Vazao']
        df = df[colunas_desejadas]

        # Verifica disponibilidade de variáveis
        st_chuva.append('Sim' if df['Chuva'].count() > 0 else 'Não')
        st_nivel.append('Sim' if df['Nivel'].count() > 0 else 'Não')

        df['Vazao'] = pd.to_numeric(df['Vazao'], errors='coerce')
        st_vazao.append('Sim' if (df['Vazao'].count() > 0 and df['Vazao'].sum() > 0) else 'Não')

        # Conversões e ordenamento
        df['DataHora'] = pd.to_datetime(df['DataHora'])
        df.set_index('DataHora', inplace=True)
        df.sort_index(inplace=True)

        # Salva arquivo CSV da estação
        df.to_csv(f"{caminho}{cod}.csv", index=True)

    # Mensagem final
    caminho_final = caminho if caminho != "" else "./"
    print(f"\nDownload concluído! Arquivos salvos em: {caminho_final}")

    # Adiciona colunas de disponibilidade e salva resumo geral
    df_info['TemChuva'] = st_chuva
    df_info['TemVazao'] = st_vazao
    df_info['TemNivel'] = st_nivel

    if save_info:
        df_info.to_csv(f"{caminho}info_estacoes.csv", index=False)
        print(f"\nResumo geral salvo em: {caminho}info_estacoes.csv")
    return df_info


# ===============================================================
# Função: get_telemetric_list(list_est, d_i, d_f, caminho)
# ---------------------------------------------------------------
# Objetivo:
#   Baixar dados hidrometeorológicos de uma lista específica
#   de estações e intervalo de datas definido pelo usuário.
#
# Entradas:
#   list_est -> Lista de códigos de estações (ex: ['74355000'])
#   d_i      -> Data inicial (YYYY-MM-DD)
#   d_f      -> Data final (YYYY-MM-DD ou vazio para mais recente)
#   caminho  -> Caminho onde os arquivos CSV serão salvos
# ===============================================================

def get_telemetric_list (list_est, d_i, d_f, caminho=""):
    if len(list_est) == 0 or list_est == None:
        print("\nErro: Lista de estações não fornecida.")
        return
    try:
        datetime.strptime(d_i, "%Y-%m-%d")
        datetime.strptime(d_f, "%Y-%m-%d")
    except ValueError:
        print("\nErro: Formato de data inválido. Use YYYY-MM-DD.")
        return

    # URL do serviço SOAP da ANA
    wsdl = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx?WSDL"

    # Configuração do cliente SOAP (resposta bruta em XML)
    settings = Settings(raw_response=True)
    client = Client(wsdl=wsdl, settings=settings)

    for est in tqdm(list_est, total=len(list_est), desc="Baixando estações"):
        # Requisição SOAP
        response = client.service.DadosHidrometeorologicos(
            codEstacao=est,
            dataInicio=d_i,
            dataFim=d_f,
        )

        # Decodifica e analisa o XML retornado
        xml_text = response.content.decode('utf-8')
        root = ET.fromstring(xml_text)

        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "mrcs": "http://MRCS/"
        }

        result_node = root.find(".//mrcs:DadosHidrometeorologicosResult", ns)
        if result_node is None:
            print(f'\nEstação {est} não encontrada.')
            continue

        diffgram_node = result_node.find(".//{urn:schemas-microsoft-com:xml-diffgram-v1}diffgram")
        if diffgram_node is None:
            print(f'\nEstação {est} não encontrada.')
            continue

        dados = []
        for dado in diffgram_node.findall(".//DocumentElement/*"):
            linha = {child.tag: child.text for child in dado}
            dados.append(linha)

        df = pd.DataFrame(dados)

        if len(df) == 1:
            print(f"\nEstação {est} não possui dados disponíveis.")
            continue

        # Seleciona colunas e organiza temporalmente
        colunas_desejadas = ['DataHora', 'Chuva', 'Nivel', 'Vazao']
        df = df[colunas_desejadas]
        df['DataHora'] = pd.to_datetime(df['DataHora'])
        df.set_index('DataHora', inplace=True)
        df.sort_index(inplace=True)
        # Exporta CSV
        df.to_csv(f"{caminho}{est}.csv", index=True)
    # Mensagem final
    caminho_final = caminho if caminho != "" else "./"
    print(f"\nDownload concluído! Arquivos salvos em: {caminho_final}")
    return 

# ===============================================================
# Função: get_conv_data_list(list_est, d_i, d_f, tipo, caminho, cons)
# ---------------------------------------------------------------
# Objetivo:
#     Baixa séries históricas de estações específicas informadas em uma lista.
# 
# Entradas:
#     - list_est (list): Lista de códigos de estações (ex: ['2751018', '2751020']).
#     - d_i (str): Data inicial no formato 'dd-mm-aaaa'.
#     - d_f (str): Data final no formato 'dd-mm-aaaa'. Se vazio, baixa até o dado mais recente.
#     - tipo (str): Tipo de dado a ser baixado:
#         '1' = Cota
#         '2' = Chuva
#         '3' = Vazão
#     - caminho (str): Caminho de destino onde os arquivos CSV serão salvos.
#     - cons (int): Nível de consistência dos dados:
#         1 = mantém todos os níveis, dando preferência ao consistido quando existente
#         2 = mantém apenas dados de nível de consistência 2
# ===============================================================

def get_conv_data_list (list_est, d_i, d_f, tipo,caminho="", cons=1):
    if len(list_est) == 0 or list_est == None:
        print("\nErro: Lista de estações não fornecida.")
        return
    
    try:
        datetime.strptime(d_i, "%Y-%m-%d")
        datetime.strptime(d_f, "%Y-%m-%d")
    except ValueError:
        print("\nErro: Formato de data inválido. Use YYYY-MM-DD.")
        return
    
    if tipo not in ['1', '2', '3']:
        print("\nErro: Tipo de dado inválido. Use '1' para Cota, '2' para Chuva ou '3' para Vazão.")
        return
    
    # Transformar itens da lista em string
    list_est = [str(est) for est in list_est]

    # URL do serviço SOAP da ANA
    wsdl = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx?WSDL"

    # Configuração do cliente SOAP
    # O parâmetro `raw_response=True` retorna o XML completo da resposta,
    # permitindo manipulação manual com regex ou xml.etree.
    settings = Settings(raw_response=True)
    client = Client(wsdl=wsdl, settings=settings)

    dic_tipo = {'1': 'Cota', '2': 'Chuva', '3': 'Vazao'}
    for est in tqdm(list_est, total=len(list_est), desc="Baixando estações"):
        # Requisição SOAP
        response = client.service.HidroSerieHistorica(
            codEstacao=est,   # Código Plu ou Flu
            dataInicio=d_i, 
            dataFim=d_f,             # Caso não preenchido, trará até o último dado mais recente armazenado
            tipoDados=tipo,          # 1-Cotas, 2-Chuvas ou 3-Vazões
            nivelConsistencia=""    # Esta retornando os dois
        )

        # Decodifica e analisa o XML retornado
        xml_text = response.content.decode('utf-8')
        # A estrutura XML da ANA contém múltiplas tags <SerieHistorica> com os dados.
        # Vamos extrair cada uma delas usando expressões regulares.

        tables = re.compile(r'<SerieHistorica diffgr:id="SerieHistorica[0-9]+" msdata:rowOrder="[0-9]+">(.*?)</SerieHistorica>')
        extract_vals = re.compile(r'<([a-zA-Z0-9]+)>(.*?)</[a-zA-Z0-9]+>')

        # Cria uma lista de dicionários (cada dicionário = 1 estação)
        linhas = []
        for table in tables.findall(xml_text):
            linhas.append(dict(extract_vals.findall(table)))

        # Converte para DataFrame
        df = pd.DataFrame(linhas)

        if len(df)==0:
            print(f'\nNão foram encontrados dados para a estação {est} no período solicitado, ou o tipo de dado informado é inválido para esse código.')
            continue

        # Garante que DataHora é datetime
        df['DataHora'] = pd.to_datetime(df['DataHora'])

        # Corrige eventuais espaços e diferenças de capitalização nos nomes
        df.columns = df.columns.str.strip()

        # Seleciona apenas colunas de chuva (sem Status)
        colunas_chuva = [c for c in df.columns if c.startswith(dic_tipo[tipo]) and not c.endswith('Status')]

        # Define colunas fixas
        id_vars = ['DataHora']
        id_vars.append('NivelConsistencia')

        # Faz o melt
        df_melt = df.melt(id_vars=id_vars, value_vars=colunas_chuva,
                        var_name='Dia', value_name=dic_tipo[tipo])

        # Extrai o número do dia
        df_melt['Dia'] = df_melt['Dia'].str.extract('(\d+)').astype(int)

        # Cria a data completa
        df_melt['Data'] = df_melt['DataHora'] + pd.to_timedelta(df_melt['Dia'] - 1, unit='D')

        df_melt = df_melt.sort_values(['Data', 'NivelConsistencia'], ascending=[True, False])
        if cons ==2:
            df_melt = df_melt[df_melt['NivelConsistencia']==2]
        else:
            df_melt = df_melt.drop_duplicates(subset='Data', keep='first')

        if len(df_melt)==0:
            print(f'\nNão há dados disponíveis para a estação {est} no período informado ou com o nível de consistência solicitado.')
            continue
        # Seleciona só as colunas finais
        df_final = df_melt[['Data', dic_tipo[tipo]]].sort_values('Data').reset_index(drop=True)

        # Exporta CSV
        df_final.to_csv(f"{caminho}{est}.csv", index=False)

    # Mensagem final
    caminho_final = caminho if caminho != "" else "./"
    print(f"\nDownload concluído! Arquivos salvos em: {caminho_final}")

    return

# ===============================================================
# Função: get_conv_data_list(df, caminho, tipo, cons)
# ---------------------------------------------------------------
# Objetivo:
#     Automatizar o download de dados para todas as estações convencionais contidas em um inventário (CSV),
#     gerando arquivos individuais por estação e um resumo geral indicando disponibilidade de dados.

# Entradas:
#     - df (DataFrame): DataFrame do inventário (geralmente lido de um arquivo CSV).
#     - caminho (str): Caminho de saída onde os arquivos CSV e o resumo serão salvos.
#     - tipo (str): Tipo de dado a ser baixado:
#         '1' = Cota
#         '2' = Chuva
#         '3' = Vazão
#     - cons (int): Nível de consistência dos dados:
#         1 = mantém todos os níveis, dando preferência ao consistido quando existente
#         2 = mantém apenas dados de nível de consistência 2
# ===============================================================

def get_conv_inventory (df, tipo, caminho="", cons=1,save_info = False):
    # URL do serviço SOAP da ANA
    wsdl = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx?WSDL"

    # Configuração do cliente SOAP
    # O parâmetro `raw_response=True` retorna o XML completo da resposta,
    # permitindo manipulação manual com regex ou xml.etree.
    settings = Settings(raw_response=True)
    client = Client(wsdl=wsdl, settings=settings)

    if df == None:
        print("\nErro: DataFrame de inventário não fornecido.")
        return
    if tipo not in ['1', '2', '3']:
        print("\nErro: Tipo de dado inválido. Use '1' para Cota, '2' para Chuva ou '3' para Vazão.")
        return
    
    dic_tipo = {'1': 'Cota', '2': 'Chuva', '3': 'Vazao'}
    dic_nome = {'1': 'RegistradorNivel', '2': 'Pluviometro', '3': 'DescLiquida'}
    # Colunas principais de interesse no inventário
    lista_colum = [
        'BaciaCodigo', 'SubBaciaCodigo', 'RioCodigo', 'RioNome', 'nmEstado',
        'nmMunicipio', 'ResponsavelSigla', 'Codigo', 'Nome', 'Latitude',
        'Longitude', 'Altitude', 'AreaDrenagem', 'PeriodoTelemetricaInicio',
        'PeriodoTelemetricaFim', 'Operando'
    ]

    df_info = df[lista_colum]

    # Listas auxiliares
    lista_datas = pd.to_datetime(df[f'Periodo{dic_nome[tipo]}Inicio']).dt.date.astype(str).tolist()
    lista_codigos = df['Codigo'].astype(str).tolist()

    # Listas para registrar disponibilidade de variáveis
    st = []

    # Loop principal com barra de progresso
    for cod, dat in tqdm(zip(lista_codigos, lista_datas), total=len(lista_codigos), desc="Baixando estações"):
        # Se não houver data inicial válida, usa um valor padrão
        if dat == 'NaT':
            dat = '1900-01-01'

        response = client.service.HidroSerieHistorica(
            codEstacao=cod,   # Código Plu ou Flu
            dataInicio=dat, 
            dataFim='',             # Caso não preenchido, trará até o último dado mais recente armazenado
            tipoDados=tipo,          # 1-Cotas, 2-Chuvas ou 3-Vazões
            nivelConsistencia=""    # Esta retornando os dois
        )

        # Decodifica e analisa o XML retornado
        xml_text = response.content.decode('utf-8')
        # A estrutura XML da ANA contém múltiplas tags <SerieHistorica> com os dados.
        # Vamos extrair cada uma delas usando expressões regulares.

        tables = re.compile(r'<SerieHistorica diffgr:id="SerieHistorica[0-9]+" msdata:rowOrder="[0-9]+">(.*?)</SerieHistorica>')
        extract_vals = re.compile(r'<([a-zA-Z0-9]+)>(.*?)</[a-zA-Z0-9]+>')

        # Cria uma lista de dicionários (cada dicionário = 1 estação)
        linhas = []
        for table in tables.findall(xml_text):
            linhas.append(dict(extract_vals.findall(table)))

        # Converte para DataFrame
        df = pd.DataFrame(linhas)

        if len(df)==0:
            print(f'\nNão foram encontrados dados para a estação {cod} no período solicitado, ou o tipo de dado informado é inválido para esse código.')
            st.append('Não')
            continue

        # Garante que DataHora é datetime
        df['DataHora'] = pd.to_datetime(df['DataHora'])

        # Corrige eventuais espaços e diferenças de capitalização nos nomes
        df.columns = df.columns.str.strip()

        # Seleciona apenas colunas de chuva (sem Status)
        colunas_chuva = [c for c in df.columns if c.startswith(dic_tipo[tipo]) and not c.endswith('Status')]

        # Define colunas fixas
        id_vars = ['DataHora']
        id_vars.append('NivelConsistencia')

        # Faz o melt
        df_melt = df.melt(id_vars=id_vars, value_vars=colunas_chuva,
                        var_name='Dia', value_name=dic_tipo[tipo])

        # Extrai o número do dia
        df_melt['Dia'] = df_melt['Dia'].str.extract('(\d+)').astype(int)

        # Cria a data completa
        df_melt['Data'] = df_melt['DataHora'] + pd.to_timedelta(df_melt['Dia'] - 1, unit='D')

        df_melt = df_melt.sort_values(['Data', 'NivelConsistencia'], ascending=[True, False])
        if cons ==2:
            df_melt = df_melt[df_melt['NivelConsistencia']==2]
        else:
            df_melt = df_melt.drop_duplicates(subset='Data', keep='first')

        if len(df_melt)==0:
            print(f'\nNão há dados disponíveis para a estação {cod} no período informado ou com o nível de consistência solicitado.')
            st.append('Não')
            continue
        st.append('Sim')        
        # Seleciona só as colunas finais
        df_final = df_melt[['Data', dic_tipo[tipo]]].sort_values('Data').reset_index(drop=True)

        # Exporta CSV
        df_final.to_csv(f"{caminho}{cod}.csv", index=False)
    # Mensagem final
    caminho_final = caminho if caminho != "" else "./"
    print(f"\nDownload concluído! Arquivos salvos em: {caminho_final}")

    df_info[f'Tem{dic_tipo[tipo]}'] = st

    if save_info:
        df_info.to_csv(f"{caminho}info_estacoes.csv", index=False)
        print(f"\nResumo geral salvo em: {caminho}info_estacoes.csv")
    
    return df_info
