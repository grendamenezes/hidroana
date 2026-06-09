"""Ferramentas para baixar, organizar e avaliar séries hidrológicas da ANA."""

import os
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import geopandas as gpd
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from geovoronoi import voronoi_regions_from_coords
from matplotlib.colors import ListedColormap
from tqdm import tqdm
from zeep import Client, Settings

logging.getLogger("zeep").setLevel(logging.ERROR)

ANA_WSDL = "https://telemetriaws1.ana.gov.br/ServiceANA.asmx?WSDL"
SOAP_NAMESPACES = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "mrcs": "http://MRCS/",
}
DIFFGRAM_PATH = ".//{urn:schemas-microsoft-com:xml-diffgram-v1}diffgram"
TELEMETRIC_VARS = ["Chuva", "Nivel", "Vazao"]
TELEMETRIC_UNITS = {"Vazao": "(m3/s)", "Chuva": "(mm)", "Nivel": "(m)"}
CONV_TYPES = {"1": "Cota", "2": "Chuva", "3": "Vazao"}
CONV_SHAPE_TYPES = {"1": "Nivel", "2": "Chuva", "3": "Vazao"}
CONV_UNITS = {"Vazao": "(m3/s)", "Chuva": "(mm)", "Cota": "(m)"}
CONV_PERIOD_NAMES = {
    "1": "RegistradorNivel",
    "2": "Pluviometro",
    "3": "DescLiquida",
}
INVENTORY_COLUMNS = [
    "BaciaCodigo", "SubBaciaCodigo", "RioCodigo", "RioNome", "nmEstado",
    "nmMunicipio", "ResponsavelSigla", "Codigo", "Nome", "Latitude",
    "Longitude", "Altitude", "AreaDrenagem", "PeriodoTelemetricaInicio",
    "PeriodoTelemetricaFim", "Operando",
]
SERIE_RE = re.compile(
    r'<SerieHistorica diffgr:id="SerieHistorica[0-9]+" '
    r'msdata:rowOrder="[0-9]+">(.*?)</SerieHistorica>'
)
INVENTORY_RE = re.compile(
    r'<Table diffgr:id="Table[0-9]+" '
    r'msdata:rowOrder="[0-9]+">(.*?)</Table>',
    re.DOTALL
)
TAG_RE = re.compile(r"<([a-zA-Z0-9]+)>(.*?)</[a-zA-Z0-9]+>")

settings = Settings(raw_response=True)
client = Client(wsdl=ANA_WSDL, settings=settings)

__all__ = [
    "calcular_pesos_thiessen",
    "media_thiessen",
    "plot_disp",
    "plot_map_estacoes",
    "n_anos_perc",
    "get_inventory",
    "get_telemetric_inventory",
    "get_telemetric_list",
    "get_conv_data_list",
    "get_conv_inventory",
    "get_series_by_shape",
    "voronoi_finite_polygons_2d",
]

def _parse_xml_tables(xml_text, pattern):
    return pd.DataFrame(dict(TAG_RE.findall(table)) for table in pattern.findall(xml_text))

def _datas_validas(d_i, d_f):
    try:
        datetime.strptime(d_i, "%Y-%m-%d")
        datetime.strptime(d_f, "%Y-%m-%d")
    except ValueError:
        print("\nErro: Formato de data inválido. Use YYYY-MM-DD.")
        return False
    return True

def _tipo_conv_valido(tipo):
    if tipo not in CONV_TYPES:
        print("\nErro: Tipo de dado inválido. Use '1' para Cota, '2' para Chuva ou '3' para Vazão.")
        return False
    return True

def _colunas_existentes(df, colunas):
    return [col for col in colunas if col in df.columns]

def _avisar_estacoes(mensagem, estacoes):
    if estacoes:
        print(f"\nAviso: {mensagem}: {', '.join(estacoes)}")

def _dados_hidrometeorologicos_df(response):
    root = ET.fromstring(response.content.decode("utf-8"))
    result_node = root.find(".//mrcs:DadosHidrometeorologicosResult", SOAP_NAMESPACES)
    if result_node is None:
        return None

    diffgram_node = result_node.find(DIFFGRAM_PATH)
    if diffgram_node is None:
        return None

    return pd.DataFrame(
        {child.tag: child.text for child in dado}
        for dado in diffgram_node.findall(".//DocumentElement/*")
    )

def _serie_telem_dia(df):
    df = df[["DataHora", *TELEMETRIC_VARS]].copy()
    df["DataHora"] = pd.to_datetime(df["DataHora"])
    for var in TELEMETRIC_VARS:
        df[var] = pd.to_numeric(df[var], errors="coerce")

    inicio_real = df["DataHora"].min().date()
    fim_real = df["DataHora"].max().date()
    df = df.set_index("DataHora").sort_index()

    df_diario = pd.DataFrame(index=pd.date_range(start=inicio_real, end=fim_real, freq="D"))
    df_diario.index.name = "DataHora"
    df_diario["Chuva"] = df["Chuva"].resample("D").sum(min_count=1)
    df_diario["Nivel"] = df["Nivel"].resample("D").mean()
    df_diario["Vazao"] = df["Vazao"].resample("D").mean()
    return df, df_diario

def _serie_convencional_df(response, tipo, cons):
    df = _parse_xml_tables(response.content.decode("utf-8"), SERIE_RE)
    if len(df) == 0:
        return None

    var = CONV_TYPES[tipo]
    df["DataHora"] = pd.to_datetime(df["DataHora"])
    df.columns = df.columns.str.strip()

    colunas_dado = [c for c in df.columns if c.startswith(var) and not c.endswith("Status")]
    df_melt = df.melt(
        id_vars=["DataHora", "NivelConsistencia"],
        value_vars=colunas_dado,
        var_name="Dia",
        value_name=var,
    )
    df_melt["Dia"] = df_melt["Dia"].str.extract(r"(\d+)").astype(int)
    df_melt["Data"] = df_melt["DataHora"] + pd.to_timedelta(df_melt["Dia"] - 1, unit="D")
    df_melt = df_melt.sort_values(["Data", "NivelConsistencia"], ascending=[True, False])

    if cons == 2:
        df_melt = df_melt[df_melt["NivelConsistencia"] == 2]
    else:
        df_melt = df_melt.drop_duplicates(subset="Data", keep="first")

    if len(df_melt) == 0:
        return df_melt

    df_final = df_melt[["Data", var]].sort_values("Data").reset_index(drop=True)
    df_final[var] = pd.to_numeric(df_final[var], errors="coerce")
    return df_final

def _completar_calendario(df, coluna_data="Data"):
    datas = pd.date_range(start=df[coluna_data].min(), end=df[coluna_data].max(), freq="D")
    df = df.set_index(coluna_data).reindex(datas)
    df.index.name = coluna_data
    return df.reset_index()

def _adicionar_disponibilidade(disponibilidade, codigo, df, coluna):
    for data, valor in zip(pd.to_datetime(df["Data"]), df[coluna]):
        disponibilidade.append({
            "Codigo": codigo,
            "Data": data,
            "Valor": 1 if pd.notna(valor) else 0,
        })

def voronoi_finite_polygons_2d(vor, radius=None):

    if vor.points.shape[1] != 2:
        raise ValueError("Necessita coordenadas 2D")

    new_regions = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)

    if radius is None:
        radius = vor.points.ptp().max() * 2

    all_ridges = {}

    for (p1, p2), (v1, v2) in zip(vor.ridge_points,
                                  vor.ridge_vertices):

        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    for p1, region_idx in enumerate(vor.point_region):

        vertices = vor.regions[region_idx]

        if all(v >= 0 for v in vertices):
            new_regions.append(vertices)
            continue

        ridges = all_ridges[p1]

        new_region = [v for v in vertices if v >= 0]

        for p2, v1, v2 in ridges:

            if v2 < 0:
                v1, v2 = v2, v1

            if v1 >= 0:
                continue

            t = vor.points[p2] - vor.points[p1]
            t /= np.linalg.norm(t)

            n = np.array([-t[1], t[0]])

            midpoint = vor.points[[p1, p2]].mean(axis=0)

            direction = np.sign(
                np.dot(midpoint - center, n)
            ) * n

            far_point = vor.vertices[v2] + direction * radius

            new_vertices.append(far_point.tolist())

            new_region.append(len(new_vertices) - 1)

        vs = np.asarray([new_vertices[v] for v in new_region])

        c = vs.mean(axis=0)

        angles = np.arctan2(
            vs[:, 1] - c[1],
            vs[:, 0] - c[0]
        )

        new_region = np.array(new_region)[np.argsort(angles)]

        new_regions.append(new_region.tolist())

    return new_regions, np.asarray(new_vertices)

def calcular_pesos_thiessen(
    gdf_estacoes,
    area_interesse,
    coluna_codigo="Codigo"
):
    if len(gdf_estacoes) == 1:
        codigo = str(gdf_estacoes.iloc[0][coluna_codigo])
        return {codigo: 1.0}
    if len(gdf_estacoes) == 2:
        codigos = (gdf_estacoes[coluna_codigo].astype(str).tolist())
        return {codigos[0]: 0.5,codigos[1]: 0.5}

    coords = np.array([(geom.x, geom.y) for geom in gdf_estacoes.geometry])
    region_polys, _ = voronoi_regions_from_coords(coords,area_interesse)
    area_total = area_interesse.area
    pesos = {}

    for idx, pol in region_polys.items():
        codigo = str(gdf_estacoes.iloc[idx][coluna_codigo])
        pesos[codigo] = pol.area / area_total
    return pesos

def media_thiessen(
    df_dados,
    gdf_estacoes,
    area_interesse,
    coluna_codigo="Codigo"
):
    mask = ~df_dados.isna()
    assinaturas = mask.apply(lambda row: tuple(mask.columns[row]),  axis=1)
    media = pd.Series(index=df_dados.index,dtype=float)
    pesos_cache = {}

    for comb in assinaturas.unique():
        if len(comb) == 0:
            continue
        gdf_sub = gdf_estacoes[
            gdf_estacoes[coluna_codigo]
            .astype(str)
            .isin(comb)
        ]

        pesos = calcular_pesos_thiessen(
            gdf_sub,
            area_interesse,
            coluna_codigo
        )
        pesos_cache[comb] = pesos
        dias = assinaturas == comb
        dados = df_dados.loc[dias, list(comb)]
        vetor_pesos = np.array([
            pesos[c]
            for c in comb
        ])
        media.loc[dias] = (
            dados.values @ vetor_pesos
        )

    return media

def plot_disp(disponibilidade, disp, caminho, dado, tipo):
    df_disp = pd.DataFrame(disponibilidade)
    df_disp['Data'] = pd.to_datetime(df_disp['Data'])

    matriz = df_disp.pivot_table(
        index='Codigo',
        columns='Data',
        values='Valor',
        fill_value=0
    )

    matriz = matriz.reindex(columns=sorted(matriz.columns))

    fig = px.imshow(
        matriz,
        aspect='auto',
        color_continuous_scale=[
            [0.0, "white"],
            [1.0, "#08306b"]
        ],
        labels=dict(x='Data', y='Estação'),
        title=f'Disponibilidade de Dados - {dado}'
    )

    fig.update_coloraxes(showscale=False)
    fig.update_layout(
        height=max(600, len(matriz) * 18),
        width=1400
    )

    if disp:
        fig.write_html(f"{caminho}giant_plot_disponibilidade_{dado}_{tipo}.html")
        
        fig_h = max(8, len(matriz) * 0.22)
        fig, ax = plt.subplots(figsize=(20, fig_h))

        cmap = ListedColormap(["white", "#0d47a1"])

        datas_num = mdates.date2num(matriz.columns)
        
        if len(datas_num) > 1:
            passo_medio = np.mean(np.diff(datas_num))
            x_coords = np.append(datas_num, datas_num[-1] + passo_medio)
        else:
            x_coords = np.array([datas_num[0], datas_num[0] + 1])

        y_coords = np.arange(len(matriz.index) + 1)

        ax.pcolormesh(
            x_coords,
            y_coords,
            matriz.values,
            cmap=cmap,
            shading='flat'
        )

        ax.set_yticks(np.arange(len(matriz.index)) + 0.5)
        ax.set_yticklabels(matriz.index.astype(str), fontsize=8)
        
        ax.invert_yaxis()

        data_min = df_disp['Data'].min()
        data_max = df_disp['Data'].max()
        ax.set_xlim(mdates.date2num(data_min), mdates.date2num(data_max))

        total_anos = data_max.year - data_min.year
        if total_anos > 40:
            intervalo_anos = 5
        elif total_anos > 20:
            intervalo_anos = 2
        else:
            intervalo_anos = 1

        ax.xaxis.set_major_locator(mdates.YearLocator(base=intervalo_anos))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

        plt.setp(ax.get_xticklabels(), rotation=45, ha='right')

        ax.grid(
            axis='x',
            linestyle='--',
            linewidth=0.6,
            alpha=0.5
        )

        ax.set_title(
            f'Disponibilidade de Dados - {dado}',
            fontsize=18,
            weight='bold',
            pad=20
        )

        ax.set_xlabel("Data", fontsize=12)
        ax.set_ylabel("Estação", fontsize=12)

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        plt.tight_layout()

        plt.savefig(
            f"{caminho}giant_plot_disponibilidade_{dado}_{tipo}.png",
            dpi=300,
            bbox_inches='tight'
        )
        plt.close(fig)
        print(f"Giant plot salvo em {caminho}giant_plot_disponibilidade_{dado}_{tipo}.html e .png")

def plot_map_estacoes(
    df_info,
    dic_disp,
    dado,
    caminho="",
    shape_area=None
):
    df_map = df_info.copy()

    anos, perc, status = [], [], []

    for cod in df_map["Codigo"].astype(str):
        if cod in dic_disp:
            a, p = dic_disp[cod]
            anos.append(a)
            perc.append(p)
            status.append("Com dados")
        else:
            anos.append(0)
            perc.append(0)
            status.append("Sem dados")

    df_map["Anos"] = anos
    df_map["Perc"] = perc
    df_map["Status"] = status

    df_map["Latitude"] = pd.to_numeric(df_map["Latitude"], errors="coerce")
    df_map["Longitude"] = pd.to_numeric(df_map["Longitude"], errors="coerce")
    df_map = df_map.dropna(subset=["Latitude", "Longitude"])
    
    if "Rede" not in df_map.columns:

        df_map["Rede"] = "Convencional"
    def classe_tamanho(x):
        if x == 0:
            return 8
        elif x <= 10:
            return 7
        elif x <= 20:
            return 11
        elif x <= 30:
            return 15
        else:
            return 19

    df_map["Size"] = df_map["Anos"].apply(classe_tamanho)

    lat_c = df_map["Latitude"].mean()
    lon_c = df_map["Longitude"].mean()

    span = max(
        df_map["Latitude"].max() - df_map["Latitude"].min(),
        df_map["Longitude"].max() - df_map["Longitude"].min()
    )

    if span < 1:
        zoom = 10
    elif span < 3:
        zoom = 7
    elif span < 6:
        zoom = 6
    elif span < 12:
        zoom = 5
    elif span < 25:
        zoom = 4
    else:
        zoom = 3
    df_sem = df_map[df_map["Status"] == "Sem dados"]
    df_com = df_map[df_map["Status"] == "Com dados"]

    fig = go.Figure()

    if shape_area is not None:

        area_gdf = shape_area.copy().to_crs("EPSG:4326")

        geom_area = area_gdf.union_all()

        if geom_area.geom_type == "Polygon":

            x, y = geom_area.exterior.xy

            fig.add_trace(go.Scattermapbox(
                lon=list(x),
                lat=list(y),
                mode="lines",
                line=dict(width=2),
                name="Área",
                hoverinfo="skip"
            ))

        elif geom_area.geom_type == "MultiPolygon":

            geom_area = max(
                geom_area.geoms,
                key=lambda p: p.area
            )

            x, y = geom_area.exterior.xy

            fig.add_trace(go.Scattermapbox(
                lon=list(x),
                lat=list(y),
                mode="lines",
                line=dict(width=2),
                name="Área",
                hoverinfo="skip"
            ))

    if len(df_sem) > 0:
        fig.add_trace(go.Scattermapbox(
            lat=df_sem["Latitude"],
            lon=df_sem["Longitude"],
            mode="markers",
            marker=dict(
                size=8,
                color="red",
                opacity=0.75
            ),
            text=df_sem["Codigo"],
            name="Sem dados",
            hovertemplate="<b>Código:</b> %{text}<br>Sem dados<extra></extra>"
        ))

    for rede_nome in ["Convencional", "Telemétrica"]:

        df_r = df_com[
            df_com["Rede"] == rede_nome
        ]
        if len(df_r) == 0:
            continue

        fig.add_trace(

            go.Scattermapbox(

                lat=df_r["Latitude"],
                lon=df_r["Longitude"],

                mode="markers",

                marker=dict(

                    size=df_r["Size"],

                    color=df_r["Perc"],

                    colorscale="Greens",

                    cmin=0,
                    cmax=100,

                    opacity=0.85,

                    symbol="circle",

                    colorbar=dict(
                        title="%<br>Completude",
                        thickness=10,
                        len=0.40,
                        y=0.5
                    )
                ),

                text=df_r["Codigo"],

                customdata=df_r[
                    ["Anos", "Perc"]
                ],

                name=rede_nome,

                hovertemplate=

                    "<b>Código:</b> %{text}<br>" +

                    "<b>Rede:</b> " +
                    rede_nome + "<br>" +

                    "<b>Anos:</b> %{customdata[0]:.0f}<br>" +

                    "<b>Completude:</b> %{customdata[1]:.1f}%<extra></extra>"
            )
        )

    legendas = [
        ("0–10 anos", 7),
        ("10–20 anos", 11),
        ("20–30 anos", 15),
        (">30 anos", 19),
    ]

    for nome, tam in legendas:
        fig.add_trace(go.Scattermapbox(
            lat=[None],
            lon=[None],
            mode="markers",
            marker=dict(
                size=tam,
                color="gray",
                opacity=0.7
            ),
            name=nome,
            showlegend=True
        ))

    fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_zoom=zoom,
        mapbox_center={"lat": lat_c, "lon": lon_c},
        height=750,
        title=f"Disponibilidade de Dados - {dado}",
        legend_title="Tamanho = anos",
        margin=dict(l=0, r=0, t=60, b=0)
    )

    arq = f"{caminho}mapa_estacoes_{dado}.html"
    fig.write_html(arq,
        config={'scrollZoom': True})
    print(f"Mapa salvo em {arq}")

    df_csv = df_map[["Codigo", "Latitude", "Longitude", "Perc", "Anos"]].copy()
    df_csv = df_csv.rename(columns={
        "Perc": "Completude",
        "Anos": "Quantidade_Anos"
    })

    arq_csv = os.path.join(caminho, f"mapa_estacoes_{dado}.csv")
    df_csv.to_csv(arq_csv, index=False, sep=";", decimal=",")
    print(f"CSV salvo em {arq_csv}")

def n_anos_perc(df_final,dado):
    df_final['Data'] = pd.to_datetime(df_final['Data'])

    df_validos = df_final.dropna(subset=[dado]).copy()

    if len(df_validos) > 0:

        data_ini = df_validos['Data'].min()
        data_fim = df_validos['Data'].max()

        ano_f = data_fim.year
        ano_i = data_ini.year
        anos_total = int(ano_f-ano_i+1)

        dias_total = (data_fim - data_ini).days + 1

        periodo = df_final[
            (df_final['Data'] >= data_ini) &
            (df_final['Data'] <= data_fim)
        ]

        n_validos = periodo[dado].notna().sum()

        perc = (n_validos / dias_total) * 100
    else:
        anos_total = 0
        perc = 0

    return anos_total, perc

def get_inventory (caminho_saida="inventario_ana.csv",
                   var_codEstDE="",
                   var_codEstATE="",
                   var_tpEst="",
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

    xml_text = response.content.decode('utf-8')
    df = pd.DataFrame(
        dict(TAG_RE.findall(table))
        for table in tqdm(INVENTORY_RE.findall(xml_text), desc="Extraindo registros")
    )

    if save:
        df.to_csv(caminho_saida, index=False)
        print(f"\nInventário salvo em: {caminho_saida}")
    return df

def get_telemetric_inventory (
    df,
    caminho="",
    save_info=False,
    disp=False,
    loc=False,
    shape_area=None
):
    if df is None or df.empty:
        print("\nErro: DataFrame de inventário não fornecido.")
        return

    colunas_existentes = _colunas_existentes(df, INVENTORY_COLUMNS)

    df = df[(df['TipoEstacaoTelemetrica'] == 1) | (df['TipoEstacaoTelemetrica'] == '1')]
    if len(df) == 0:
        print(f"\nNão há estações telemétricas no inventário fornecido.")
        return
    df_info = df[colunas_existentes].copy()

    lista_datas = pd.to_datetime(df['PeriodoTelemetricaInicio']).dt.date.astype(str).tolist()
    lista_codigos = df['Codigo'].astype(str).tolist()

    st_chuva, st_nivel, st_vazao = [], [], []

    disponibilidade = []

    estacoes_nao_encontradas = []
    estacoes_sem_dados = []

    dic_disp_chuva = {}
    dic_disp_nivel = {}
    dic_disp_vazao = {}

    for cod, dat in tqdm(zip(lista_codigos, lista_datas), total=len(lista_codigos), desc="Baixando estações"):

        if dat == 'NaT':
            dat = '2000-01-01'

        response = client.service.DadosHidrometeorologicos(
            codEstacao=cod,
            dataInicio=dat,
            dataFim=''
        )

        df = _dados_hidrometeorologicos_df(response)
        if df is None:
            estacoes_nao_encontradas.append(cod)
            st_chuva.append('Erro')
            st_nivel.append('Erro')
            st_vazao.append('Erro')
            continue

        if len(df) <= 1:
            estacoes_sem_dados.append(cod)
            st_chuva.append('Não')
            st_nivel.append('Não')
            st_vazao.append('Não')
            continue

        df = df[["DataHora", *TELEMETRIC_VARS]]

        st_chuva.append('Sim' if df['Chuva'].count() > 0 else 'Não')
        st_nivel.append('Sim' if df['Nivel'].count() > 0 else 'Não')

        for n in TELEMETRIC_VARS:
            df[n] = pd.to_numeric(df[n], errors='coerce')
        st_vazao.append('Sim' if (df['Vazao'].count() > 0 and df['Vazao'].sum() > 0) else 'Não')

        df, df_diario = _serie_telem_dia(df)

        for col in df:
            df = df.rename(columns={col: f'{col} {TELEMETRIC_UNITS[col]}'})

        for var in TELEMETRIC_VARS:
            serie_valida = df_diario[var].dropna()

            if len(serie_valida) == 0:
                continue

            for d in serie_valida.index:
                disponibilidade.append({
                    'Codigo': cod,
                    'Data': d,
                    'Valor': 1,
                    'Tipo': var
                })

            df_tmp = pd.DataFrame({
                "Data": serie_valida.index,
                var: serie_valida.values
            })

            anos, perc = n_anos_perc(df_tmp, var)

            if var == "Chuva":
                dic_disp_chuva[cod] = (anos, perc)
            elif var == "Nivel":
                dic_disp_nivel[cod] = (anos, perc)
            elif var == "Vazao":
                dic_disp_vazao[cod] = (anos, perc)

        df.to_csv(f"{caminho}{cod}.csv", index=True)
    _avisar_estacoes("Estações não encontradas no sistema da ANA", estacoes_nao_encontradas)
    _avisar_estacoes("Estações que não possuem nenhum dado disponível no período", estacoes_sem_dados)
    
    df_info['TemChuva'] = st_chuva
    df_info['TemVazao'] = st_vazao
    df_info['TemNivel'] = st_nivel

    if save_info:
        df_info.to_csv(f"{caminho}info_estacoes.csv", index=False)
        print(f"\nResumo geral salvo em: {caminho}info_estacoes.csv")
    df_info['Rede'] = 'Telemétrica'

    if disp:

        for var in TELEMETRIC_VARS:

            disponibilidade_filtrada = [
                {k: v for k, v in item.items() if k != "Tipo"}
                for item in disponibilidade
                if item["Tipo"] == var
            ]

            if len(disponibilidade_filtrada) > 0:

                plot_disp(
                    disponibilidade_filtrada,
                    disp,
                    caminho,
                    var,
                    tipo = "telemetrica"
                )

    if loc:

        if len(dic_disp_chuva) > 0:
            plot_map_estacoes(
                df_info,
                dic_disp_chuva,
                "Chuva",
                caminho,
                shape_area=shape_area
            )

        if len(dic_disp_nivel) > 0:
            plot_map_estacoes(
                df_info,
                dic_disp_nivel,
                "Nivel",
                caminho,
                shape_area=shape_area
            )

        if len(dic_disp_vazao) > 0:
            plot_map_estacoes(
                df_info,
                dic_disp_vazao,
                "Vazao",
                caminho,
                shape_area=shape_area
            )
    
    return 

def get_telemetric_list(
    list_est,
    d_i,
    d_f,
    caminho="",
    disp=False,
    byshape=False
):
    if len(list_est) == 0 or list_est == None:
        print("\nErro: Lista de estações não fornecida.")
        return
    if not _datas_validas(d_i, d_f):
        return

    disponibilidade = []

    estacoes_nao_encontradas = []
    estacoes_sem_dados = []

    dic_disp_chuva = {}
    dic_disp_nivel = {}
    dic_disp_vazao = {}
    dic_dfs        = {}
    for est in tqdm(list_est, total=len(list_est), desc="Baixando estações"):
        response = client.service.DadosHidrometeorologicos(
            codEstacao=est,
            dataInicio=d_i,
            dataFim=d_f,
        )

        df = _dados_hidrometeorologicos_df(response)
        if df is None:
            estacoes_nao_encontradas.append(est)
            continue

        if len(df) <= 1:
            estacoes_sem_dados.append(est)
            continue

        df, df_diario = _serie_telem_dia(df)

        dic_dfs[est] = df_diario.copy()

        for col in df:
            df = df.rename(columns={col: f'{col} {TELEMETRIC_UNITS[col]}'})

        df.to_csv(f"{caminho}{est}.csv", index=True)

        for var in TELEMETRIC_VARS:
            serie_valida = df_diario[var].dropna()

            if len(serie_valida) == 0:
                continue

            for d in serie_valida.index:
                disponibilidade.append({
                    'Codigo': est,
                    'Data': d,
                    'Valor': 1,
                    'Tipo': var
                })

            df_tmp = pd.DataFrame({
                "Data": serie_valida.index,
                var: serie_valida.values
            })

            anos, perc = n_anos_perc(df_tmp, var)

            if var == "Chuva":
                dic_disp_chuva[est] = (anos, perc)
            elif var == "Nivel":
                dic_disp_nivel[est] = (anos, perc)
            elif var == "Vazao":
                dic_disp_vazao[est] = (anos, perc)
    _avisar_estacoes("Estações não encontradas no sistema da ANA", estacoes_nao_encontradas)
    _avisar_estacoes("Estações que não possuem nenhum dado disponível no período", estacoes_sem_dados)
    
    if disp and len(disponibilidade) > 0:
      for n in TELEMETRIC_VARS:
          disponibilidade_filtrada = [
              {k: v for k, v in item.items() if k != 'Tipo'}
              for item in disponibilidade
              if item['Tipo'] == n
          ]
          if len(disponibilidade_filtrada) > 0:
              plot_disp(disponibilidade_filtrada, disp, caminho, n, tipo = "telemetrica")
    elif disp:
        print('\nNão há dados disponíveis para gerar os gráficos da lista de estações solicitadas.')
    if byshape:
        return dic_disp_chuva, dic_disp_nivel, dic_disp_vazao, dic_dfs
    else:
        return

def get_conv_data_list (list_est, d_i, d_f, tipo,caminho="", cons=1, disp=False, byshape=False):
    if len(list_est) == 0 or list_est == None:
        print("\nErro: Lista de estações não fornecida.")
        return
    if not _datas_validas(d_i, d_f):
        return

    if not _tipo_conv_valido(tipo):
        return

    list_est = [str(est) for est in list_est]
    disponibilidade = []

    estacoes_sem_dados = []
    estacoes_sem_consistencia = []
    dic_disp = {}
    dic_dfs = {}
    for est in tqdm(list_est, total=len(list_est), desc="Baixando estações"):
        response = client.service.HidroSerieHistorica(
            codEstacao=est,   # Código Plu ou Flu
            dataInicio=d_i,
            dataFim=d_f,             # Caso não preenchido, trará até o último dado mais recente armazenado
            tipoDados=tipo,          # 1-Cotas, 2-Chuvas ou 3-Vazões
            nivelConsistencia=""    # Esta retornando os dois
        )

        df_final = _serie_convencional_df(response, tipo, cons)
        if df_final is None:
            estacoes_sem_dados.append(est)
            continue
        if len(df_final) == 0:
            estacoes_sem_consistencia.append(est)
            continue

        var = CONV_TYPES[tipo]
        df_final = _completar_calendario(df_final)

        coluna = f'{var} {CONV_UNITS[var]}'
        df_final = df_final.rename(columns={var: coluna})

        df_final.to_csv(f"{caminho}{est}.csv", index=False)
        dic_dfs[est] = df_final.copy()

        dic_disp[est] = n_anos_perc(df_final,coluna)
        _adicionar_disponibilidade(disponibilidade, est, df_final, coluna)

    _avisar_estacoes(
        "Não foram encontrados dados no período solicitado (ou o tipo de dado é inválido) para as estações",
        estacoes_sem_dados,
    )
    _avisar_estacoes(
        f"Não há dados com o nível de consistência ({cons}) solicitado para as estações",
        estacoes_sem_consistencia,
    )

    if len(disponibilidade) > 0:
        plot_disp(disponibilidade,disp,caminho,CONV_TYPES[tipo],tipo = "convencional")
    else:
        print('\nNão há dados disponíveis para a lista de estações solicitadas.')
    if byshape:
        return dic_disp, dic_dfs
    else:
        return

def get_conv_inventory (df, tipo, caminho="", cons=1,save_info = False, disp = False, loc = False):
    if df is None:
        print("\nErro: DataFrame de inventário não fornecido.")
        return
    if not _tipo_conv_valido(tipo):
        return

    colunas_existentes = _colunas_existentes(df, [*INVENTORY_COLUMNS, "TipoEstacao"])

    if tipo == '2':
      df = df[df['TipoEstacao']=='2']
    else:
      df = df[df['TipoEstacao']=='1']
    
    if len(df) == 0:
        print(f"\nNão há valores para o tipo de dado solicitado.")
        return
        
    df_info = df[colunas_existentes].copy()

    lista_datas = pd.to_datetime(df[f'Periodo{CONV_PERIOD_NAMES[tipo]}Inicio']).dt.date.astype(str).tolist()
    lista_codigos = df['Codigo'].astype(str).tolist()

    st = []
    disponibilidade = []
    estacoes_sem_dados = []
    estacoes_sem_consistencia = []
    dic_disp = {}
    for cod, dat in tqdm(zip(lista_codigos, lista_datas), total=len(lista_codigos), desc="Baixando estações"):
        if dat == 'NaT':
            dat = '1900-01-01'

        response = client.service.HidroSerieHistorica(
            codEstacao=cod,   # Código Plu ou Flu
            dataInicio=dat,
            dataFim='',             # Caso não preenchido, trará até o último dado mais recente armazenado
            tipoDados=tipo,          # 1-Cotas, 2-Chuvas ou 3-Vazões
            nivelConsistencia=""    # Esta retornando os dois
        )

        df_final = _serie_convencional_df(response, tipo, cons)
        if df_final is None:
            estacoes_sem_dados.append(cod)
            st.append('Não')
            continue
        if len(df_final) == 0:
            estacoes_sem_consistencia.append(cod)
            st.append('Não')
            continue
        st.append('Sim')

        var = CONV_TYPES[tipo]
        coluna = f'{var} {CONV_UNITS[var]}'
        df_final = df_final.rename(columns={var: coluna})
        _adicionar_disponibilidade(disponibilidade, cod, df_final, coluna)
        df_final = _completar_calendario(df_final)

        df_final.to_csv(f"{caminho}{cod}.csv", index=False)

        dic_disp[cod] = n_anos_perc(df_final,coluna)

    df_info[f'Tem{CONV_TYPES[tipo]}'] = st

    _avisar_estacoes(
        "Não foram encontrados dados no período solicitado (ou o tipo de dado é inválido) para as estações",
        estacoes_sem_dados,
    )
    _avisar_estacoes(
        f"Não há dados com o nível de consistência ({cons}) solicitado para as estações",
        estacoes_sem_consistencia,
    )

    if save_info:
        df_info.to_csv(f"{caminho}info_estacoes.csv", index=False)
        print(f"\nResumo geral salvo em: {caminho}info_estacoes.csv")
        
    if len(disponibilidade) > 0:
        plot_disp(disponibilidade,disp,caminho,CONV_TYPES[tipo],tipo = "convencional")
    else:
        print('\nNão há dados disponíveis para a lista de estações solicitadas.')
    if loc:
        plot_map_estacoes(df_info, dic_disp, CONV_TYPES[tipo], caminho)
    return 

def get_series_by_shape(
    arquivo,
    d_i,
    d_f,
    buffer_km=0,
    atributo=None,
    valor=None,
    rede="ambos",
    tipo_dado="2",
    caminho="",
    save_inventory=True,
    disp=False,
    loc=False,
    media=False
):
    
    gdf = gpd.read_file(arquivo)

    if atributo is not None and valor is not None:

        if atributo not in gdf.columns:
            raise ValueError(
                f"Atributo '{atributo}' não encontrado. "
                f"Disponíveis: {list(gdf.columns)}"
            )

        if isinstance(valor, (list, tuple, set)):
            gdf = gdf[gdf[atributo].isin(valor)]
        else:
            gdf = gdf[gdf[atributo] == valor]

        if len(gdf) == 0:
            raise ValueError(
                f"Nenhuma feição encontrada com "
                f"{atributo} = {valor}"
            )

    if gdf.crs is None:
        raise ValueError("Arquivo sem CRS definido.")

    gdf = gdf.to_crs(3857)

    if len(gdf) >1:
        print(f"Mais de um polígono encontrado. Serão consideradas as estações dentro de todos os polígonos (união).")
        geom_unida = gdf.union_all()

        gdf = gpd.GeoDataFrame(
            geometry=[geom_unida],
            crs=gdf.crs
        )

    if buffer_km > 0:
        area = gdf.buffer(buffer_km * 1000).union_all()
    else:
        area = gdf.union_all()

    if rede == "conv":
        if tipo_dado == '3' or tipo_dado == '1':
            inv = get_inventory(var_tpEst='1')
        else:
            inv = get_inventory(var_tpEst=tipo_dado)
        inv["Rede"] = "Convencional"

    elif rede == "tele":

        inv = get_inventory()
        inv = inv[inv["TipoEstacaoTelemetrica"] == '1']
        inv["Rede"] = "Telemétrica"

    elif rede == "ambos":

        inv_ori = get_inventory()
        if tipo_dado == '3' or tipo_dado == '1':
            inv_conv = inv_ori[inv_ori["TipoEstacao"] == '1'].copy()
        else:
            inv_conv = inv_ori[inv_ori["TipoEstacao"] == tipo_dado].copy()
        
        inv_conv["Rede"] = "Convencional"

        inv_tele = inv_ori[inv_ori["TipoEstacaoTelemetrica"] == '1'].copy()
        inv_tele["Rede"] = "Telemétrica"

        inv = pd.concat(
            [inv_conv, inv_tele],
            ignore_index=True
        )

    else:
        raise ValueError(
            "Rede deve ser 'conv', 'tele' ou 'ambos'."
        )

    est = gpd.GeoDataFrame(
        inv,
        geometry=gpd.points_from_xy(
            inv["Longitude"].astype(float),
            inv["Latitude"].astype(float)
        ),
        crs="EPSG:4326"
    ).to_crs(3857)

    sel = est[est.geometry.within(area)]

    sel_conv = sel[sel["Rede"] == "Convencional"].copy()
    sel_tele = sel[sel["Rede"] == "Telemétrica"].copy()

    lista = sel["Codigo"].astype(str).tolist()

    print(f"{len(lista)} estações encontradas.")

    if len(lista) == 0:
        return sel
    
    if save_inventory:
        arquivo_inv = os.path.join(caminho, "inventario_filtrado.csv")
        sel.drop(columns="geometry").to_csv(arquivo_inv, index=False)
        print(f"Inventário salvo em: {arquivo_inv}")

    dic_disp_conv = {}

    dic_disp_chuv_tele = {}
    dic_disp_nivel_tele = {}
    dic_disp_vazao_tele = {}
    if len(sel_conv) > 0:

        lista_conv = sel_conv["Codigo"].astype(str).tolist()

        dic_disp_conv, dic_dfs = get_conv_data_list(
            lista_conv,
            d_i,
            d_f,
            tipo_dado,
            caminho,
            disp=disp,
            byshape=True
        )

        df_unificado_conv = pd.concat(
            [
                df.set_index('Data').rename(
                    columns={df.columns[1]: str(est)}
                )
                for est, df in dic_dfs.items()
            ],
            axis=1
        )

        df_unificado_conv = df_unificado_conv.reindex(
            pd.date_range(
                df_unificado_conv.index.min(),
                df_unificado_conv.index.max(),
                freq='D'
            )
        )

        df_unificado_conv.index.name = 'Data'

    if len(sel_tele) > 0:

        lista_tele = sel_tele["Codigo"].astype(str).tolist()

        dic_disp_chuv_tele, dic_disp_nivel_tele, dic_disp_vazao_tele, dic_dfs_tele = get_telemetric_list(
            lista_tele,
            d_i,
            d_f,
            caminho,
            disp=disp,
            byshape=True
        )
        df_unificado_tele = pd.concat(
            [
                df[["Chuva"]].rename(
                    columns={"Chuva": str(est)}
                )
                for est, df in dic_dfs_tele.items()
            ],
            axis=1
        )

        df_unificado_tele = df_unificado_tele.reindex(
            pd.date_range(
                df_unificado_tele.index.min(),
                df_unificado_tele.index.max(),
                freq='D'))

        df_unificado_tele.index.name = 'Data'
    if len(sel_conv) > 0 and len(sel_tele) > 0:
        df_unificado = pd.concat([df_unificado_conv, df_unificado_tele],axis=1)
    elif len(sel_conv) > 0: df_unificado = df_unificado_conv.copy()
    elif len(sel_tele) > 0: df_unificado = df_unificado_tele.copy()

    if loc:
        if tipo_dado == '1':
            dic_disp = {
                **(dic_disp_conv if dic_disp_conv else {}),
                **(dic_disp_nivel_tele if dic_disp_nivel_tele else {})
            }
            plot_map_estacoes(
                sel,
                dic_disp,
                CONV_SHAPE_TYPES[tipo_dado],
                caminho,
                shape_area=gdf
            )
        elif tipo_dado == '2':
            dic_disp = {
                **(dic_disp_conv if dic_disp_conv else {}),
                **(dic_disp_chuv_tele if dic_disp_chuv_tele else {})
            }
            plot_map_estacoes(
                sel,
                dic_disp,
                CONV_SHAPE_TYPES[tipo_dado],
                caminho,
                shape_area=gdf
            )
        elif tipo_dado == '3':
            dic_disp = {
                **(dic_disp_conv if dic_disp_conv else {}),
                **(dic_disp_vazao_tele if dic_disp_vazao_tele else {})
            }
            plot_map_estacoes(
                sel,
                dic_disp,
                CONV_SHAPE_TYPES[tipo_dado],
                caminho,
                shape_area=gdf
            )

    if media and tipo_dado == "2":

        area_interesse = gdf.union_all()

        estacoes_media = sel.copy()

        estacoes_media["Codigo"] = (
            estacoes_media["Codigo"]
            .astype(str)
        )

        colunas_existentes = [
            c for c in df_unificado.columns
            if c in estacoes_media["Codigo"].values
        ]

        estacoes_media = estacoes_media[
            estacoes_media["Codigo"]
            .isin(colunas_existentes)
        ]

        df_media = media_thiessen(
            df_unificado,
            estacoes_media,
            area_interesse,
            coluna_codigo="Codigo"
        )

        df_media = pd.DataFrame({
            "Chuva_Media_Thiessen": df_media,
            "N_estacoes": df_unificado.notna().sum(axis=1)
        })

        arquivo_media = os.path.join(
            caminho,
            "chuva_media_thiessen.csv"
        )

        df_media.to_csv(arquivo_media)

        print(
            f"Média Thiessen salva em: "
            f"{arquivo_media}"
        )

    return
