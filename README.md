# Hidroana

Biblioteca Python para consulta, download, processamento e visualização de dados hidrológicos da **Agência Nacional de Águas e Saneamento Básico (ANA)**.

O projeto acessa os serviços SOAP da ANA e organiza séries de estações convencionais e telemétricas em arquivos CSV, mapas, gráficos de disponibilidade e médias de chuva por Thiessen.

## Recursos

- Consulta do inventário oficial de estações da ANA.
- Download de séries telemétricas de chuva, nível e vazão.
- Download de séries históricas convencionais de cota, chuva e vazão.
- Seleção espacial por Shapefile ou GeoPackage, com buffer opcional.
- Mapas interativos de estações e completude.
- Gráficos de disponibilidade em HTML e PNG.
- Cálculo de chuva média por polígonos de Thiessen.
- Exportação automática em CSV.


## Instalação

```bash
pip install hidroana
```

## Dependências Principais

- `pandas`
- `numpy`
- `tqdm`
- `zeep`
- `geopandas`
- `shapely`
- `geovoronoi`
- `plotly`
- `matplotlib`

## Importação

```python
import hidroana
```


## Funções

## `get_inventory`

Consulta o inventário oficial de estações hidrológicas da ANA.

```python
df = hidroana.get_inventory(
    caminho_saida="inventario_ana.csv",
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
    save=False
)
```

### Parâmetros

| Parâmetro | Descrição | Default |
| --- | --- | --- |
| `caminho_saida` | Nome ou caminho do CSV de saída quando `save=True` | `"inventario_ana.csv"` |
| `var_codEstDE` | Código inicial da estação para filtro por intervalo | `""` |
| `var_codEstATE` | Código final da estação para filtro por intervalo | `""` |
| `var_tpEst` | Tipo de estação: `"1"` fluviométrica, `"2"` pluviométrica | `""` |
| `var_nmEst` | Nome da estação | `""` |
| `var_nmRio` | Nome do rio | `""` |
| `var_codSubBacia` | Código da sub-bacia | `""` |
| `var_codBacia` | Código da bacia hidrográfica | `""` |
| `var_nmMunicipio` | Nome do município | `""` |
| `var_nmEstado` | Nome do estado usado como filtro | `""` |
| `var_sgResp` | Sigla da entidade responsável | `""` |
| `var_sgOper` | Sigla da entidade operadora | `""` |
| `var_telemetrica` | Filtro telemétrico: `"1"` sim, `"0"` não, `""` todas | `""` |
| `save` | Salva o resultado em CSV | `False` |

### Exemplo

```python
inventario = hidroana.get_inventory(
    var_nmEstado="Santa Catarina",
    var_telemetrica="1",
    save=True,
    caminho_saida="inventario_sc_tele.csv"
)
```
## `get_conv_data_list`

Baixa séries históricas convencionais de uma lista de estações.

```python
hidroana.get_conv_data_list(
    list_est=['70150000','72300000'],
    d_i='1990-01-01',
    d_f='2020-12-31',
    tipo='3',
    disp=True
)
```

### Parâmetros

| Parâmetro | Descrição | Default |
| --- | --- | --- |
| `list_est` | Lista de códigos de estações | Obrigatório |
| `d_i` | Data inicial no formato `YYYY-MM-DD` | Obrigatório |
| `d_f` | Data final no formato `YYYY-MM-DD` | Obrigatório |
| `tipo` | `"1"` cota, `"2"` chuva, `"3"` vazão | Obrigatório |
| `caminho` | Pasta de saída dos CSVs e gráficos | `""` |
| `cons` | `1` prioriza consistido quando houver; `2` mantém apenas consistência 2 | `1` |
| `disp` | Gera gráficos de disponibilidade em HTML e PNG | `False` |
| `byshape` | Retorna dados auxiliares para seleção espacial | `False` |

### Exemplo

```python
hidroana.get_conv_data_list(
    ["2549000"],
    "1990-01-01",
    "2020-12-31",
    tipo="3",
    caminho="./vazao/",
    cons=1,
    disp=True
)
```

### Gráfico de disponibilidade gerado

<img src="https://raw.githubusercontent.com/grendamenezes/hidroana/refs/heads/main/hidroana/giant_plot_disponibilidade_Vazao_convencional.png"/>


## `get_conv_inventory`

Baixa séries convencionais para todas as estações compatíveis de um inventário.

```python
resumo = hidroana.get_conv_inventory(
    df,
    tipo,
    caminho="",
    cons=1,
    save_info=False,
    disp=False,
    loc=False
)
```

### Parâmetros

| Parâmetro | Descrição | Default |
| --- | --- | --- |
| `df` | DataFrame de inventário retornado por `get_inventory` | Obrigatório |
| `tipo` | `"1"` cota, `"2"` chuva, `"3"` vazão | Obrigatório |
| `caminho` | Pasta de saída dos CSVs, mapas e gráficos | `""` |
| `cons` | `1` prioriza consistido quando houver; `2` mantém apenas consistência 2 | `1` |
| `save_info` | Salva `info_estacoes.csv` com resumo das estações | `False` |
| `disp` | Gera gráficos de disponibilidade em HTML e PNG | `False` |
| `loc` | Gera mapa interativo de estações | `False` |

### Exemplo

```python
inventario = hidroana.get_inventory(var_nmEstado="Alagoas")

resumo = hidroana.get_conv_inventory(
    inventario,
    tipo="2",
    caminho="./chuva/",
    cons=1,
    save_info=True,
    disp=False,
    loc=True
)

```

### Mapa de disponibilidade gerado

<img src="https://raw.githubusercontent.com/grendamenezes/hidroana/refs/heads/main/hidroana/mapa_alagoas.png"/>


## `get_telemetric_inventory`

Baixa dados telemétricos para todas as estações telemétricas presentes em um inventário.

```python
resumo = hidroana.get_telemetric_inventory(
    df,
    caminho="",
    save_info=False,
    disp=False,
    loc=False,
    shape_area=None
)
```

### Parâmetros

| Parâmetro | Descrição | Default |
| --- | --- | --- |
| `df` | DataFrame de inventário retornado por `get_inventory` | Obrigatório |
| `caminho` | Pasta de saída dos CSVs, mapas e gráficos | `""` |
| `save_info` | Salva `info_estacoes.csv` com resumo das estações | `False` |
| `disp` | Gera gráficos de disponibilidade em HTML e PNG | `False` |
| `loc` | Gera mapas interativos de estações | `False` |
| `shape_area` | GeoDataFrame usado como contorno no mapa | `None` |

### Exemplo

```python
inventario = hidroana.get_inventory(var_nmEstado="Alagoas")

resumo = hidroana.get_telemetric_inventory(
    inventario,
    caminho="./dados_tele/",
    save_info=True,
    disp=True,
    loc=True
)
```


## `get_telemetric_list`

Baixa dados telemétricos de uma lista específica de estações.

```python
hidroana.get_telemetric_list(
    list_est,
    d_i,
    d_f,
    caminho="",
    disp=False,
    byshape=False
)
```

### Parâmetros

| Parâmetro | Descrição | Default |
| --- | --- | --- |
| `list_est` | Lista de códigos de estações | Obrigatório |
| `d_i` | Data inicial no formato `YYYY-MM-DD` | Obrigatório |
| `d_f` | Data final no formato `YYYY-MM-DD` | Obrigatório |
| `caminho` | Pasta de saída dos CSVs e gráficos | `""` |
| `disp` | Gera gráficos de disponibilidade em HTML e PNG | `False` |
| `byshape` | Retorna dicionários internos usados por `get_series_by_shape` | `False` |

### Exemplo

```python
hidroana.get_telemetric_list(
    ["74355000", "74270000"],
    "2020-01-01",
    "2020-12-31",
    caminho="./dados_tele/",
    disp=True
)
```


## `get_series_by_shape`

Seleciona estações dentro de uma área espacial e baixa automaticamente as séries.

```python
hidroana.get_series_by_shape(
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
)
```

### Parâmetros

| Parâmetro | Descrição | Default |
| --- | --- | --- |
| `arquivo` | Caminho para `.shp` ou `.gpkg` | Obrigatório |
| `d_i` | Data inicial no formato `YYYY-MM-DD` | Obrigatório |
| `d_f` | Data final no formato `YYYY-MM-DD` | Obrigatório |
| `buffer_km` | Buffer em quilômetros ao redor da geometria | `0` |
| `atributo` | Nome de uma coluna para filtrar a camada | `None` |
| `valor` | Valor, lista ou conjunto usado no filtro por atributo | `None` |
| `rede` | Rede usada na busca: `"conv"`, `"tele"` ou `"ambos"` | `"ambos"` |
| `tipo_dado` | `"1"` cota/nível, `"2"` chuva, `"3"` vazão | `"2"` |
| `caminho` | Pasta de saída dos arquivos gerados | `""` |
| `save_inventory` | Salva `inventario_filtrado.csv` | `True` |
| `disp` | Gera gráficos de disponibilidade em HTML e PNG | `False` |
| `loc` | Gera mapa interativo de estações | `False` |
| `media` | Para chuva, calcula `chuva_media_thiessen.csv` | `False` |

### Exemplo com Bacia

```python
hidroana.get_series_by_shape(
    arquivo="bacia.shp",
    d_i="2000-01-01",
    d_f="2020-12-31",
    buffer_km=10,
    rede="ambos",
    tipo_dado="2",
    caminho="./saida/",
    save_inventory=True,
    disp=True,
    loc=True,
    media=True
)
```

### Exemplo com Filtro por Atributo

```python
hidroana.get_series_by_shape(
    '../CABra_boundaries.shp',
    '1990-01-01',
    '2026-01-01',  
    buffer_km=2,
    rede="ambos",
    atributo= 'ID_CABra',
    valor=296,
    tipo_dado="2",
    caminho="",
    save_inventory=True,
    disp=True,
    loc=True,
    media=True
)
```

### Mapa de disponibilidade gerado

<img src="https://raw.githubusercontent.com/grendamenezes/hidroana/refs/heads/main/hidroana/mapa_area.png"/>

## Funções de Apoio

### `plot_disp`

Gera gráfico de disponibilidade de dados em HTML e PNG.

### `plot_map_estacoes`

Gera mapa interativo de estações com completude e quantidade de anos.

### `media_thiessen`

Calcula chuva média usando pesos de Thiessen, ajustando os pesos às estações disponíveis em cada dia.

### `calcular_pesos_thiessen`

Calcula os pesos de Thiessen para um conjunto de estações dentro de uma área.

### `n_anos_perc`

Calcula a quantidade de anos cobertos e a completude percentual de uma série.

### `voronoi_finite_polygons_2d`

Converte regiões infinitas de um diagrama de Voronoi em polígonos finitos.

## Arquivos Gerados

Dependendo da função e dos parâmetros usados, a biblioteca pode gerar:

- `{codigo}.csv`: série temporal de uma estação.
- `info_estacoes.csv`: resumo de disponibilidade por estação.
- `inventario_filtrado.csv`: inventário espacialmente filtrado.
- `mapa_estacoes_{dado}.html`: mapa interativo.
- `mapa_estacoes_{dado}.csv`: dados usados no mapa.
- `giant_plot_disponibilidade_{dado}_{tipo}.html`: gráfico interativo de disponibilidade.
- `giant_plot_disponibilidade_{dado}_{tipo}.png`: gráfico estático de disponibilidade.
- `chuva_media_thiessen.csv`: chuva média por Thiessen.

## Observações Importantes

- As funções fazem requisições pela internet aos serviços da ANA.
- A disponibilidade depende do serviço e dos dados publicados pela ANA.
- Datas devem estar no formato `YYYY-MM-DD`.
- Algumas estações podem existir no inventário, mas não retornar séries para o período solicitado.
- Em estações telemétricas com código pluviométrico e fluviométrico, muitas vezes o serviço retorna melhor usando o código fluviométrico.

## Fonte dos Dados

Agência Nacional de Águas e Saneamento Básico (ANA)

https://www.gov.br/ana/

## Autoria

**Grenda Menezes**

E-mail: grenda.menezes@gmail.com
