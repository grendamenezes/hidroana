# Hidroana

Biblioteca Python para consulta, download e processamento de dados hidrológicos da **Agência Nacional de Águas e Saneamento Básico (ANA)**.

A biblioteca permite acessar automaticamente serviços web da ANA para obter:

* Inventário de estações hidrológicas
* Séries telemétricas (chuva, nível e vazão)
* Séries históricas convencionais
* Seleção espacial de estações por shapefile / GeoPackage
* Exportação automática em CSV
* Resumos de disponibilidade de dados

---

# Instalação

```bash
pip install hidroana
```

## Dependências

* pandas 
* tqdm 
* zeep 
* geopandas 

Instalação manual das dependências:

```bash
pip install pandas tqdm zeep geopandas
```

---

# Importação

```python
import hidroana
```

---

# Funções

---

# 1. get_inventory()

Consulta o inventário oficial de estações hidrológicas da ANA e retorna os metadados em formato tabular.

## Sintaxe

```python
hidroana.get_inventory(
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

---

## Parâmetros

| Parâmetro       | Tipo | Default                | Descrição                                           |
| --------------- | ---- | ---------------------- | --------------------------------------------------- |
| caminho_saida   | str  | `"inventario_ana.csv"` | Nome/caminho do arquivo CSV de saída                |
| var_codEstDE    | str  | `""`                   | Código inicial da estação para filtro por intervalo |
| var_codEstATE   | str  | `""`                   | Código final da estação para filtro por intervalo   |
| var_tpEst       | str  | `""`                   | Tipo de estação                                     |
| var_nmEst       | str  | `""`                   | Nome da estação                                     |
| var_nmRio       | str  | `""`                   | Nome do rio                                         |
| var_codSubBacia | str  | `""`                   | Código da sub-bacia                                 |
| var_codBacia    | str  | `""`                   | Código da bacia hidrográfica                        |
| var_nmMunicipio | str  | `""`                   | Nome do município                                   |
| var_nmEstado    | str  | `""`                   | Unidade federativa (UF)                             |
| var_sgResp      | str  | `""`                   | Sigla da entidade responsável                       |
| var_sgOper      | str  | `""`                   | Sigla da entidade operadora                         |
| var_telemetrica | str  | `""`                   | Filtrar estações telemétricas                       |
| save            | bool | `False`                | Salva o resultado em CSV                            |

---

## Valores específicos

### `var_tpEst`

| Valor | Tipo          |
| ----- | ------------- |
| `"1"` | Fluviométrica |
| `"2"` | Pluviométrica |

Se vazio (`""`), retorna todos os tipos disponíveis.

---

### `var_telemetrica`

| Valor | Significado              |
| ----- | ------------------------ |
| `"1"` | Somente telemétricas     |
| `"0"` | Somente não telemétricas |
| `""`  | Todas                    |

---

## Retorno

```python
pandas.DataFrame
```

Tabela contendo os registros do inventário da ANA conforme os filtros aplicados.

---

## Exemplos

### 1. Estações pluviométricas do Paraná

```python
df = hidroana.get_inventory(
    var_nmEstado="PR",
    var_tpEst="2",
    save=True,
    caminho_saida="inventario_pr.csv"
)
```

---

## Observação importante sobre códigos de estações telemétricas

Na base da ANA, algumas estações possuem:

* código **pluviométrico (plu)**
* código **fluviométrico (flu)**
* ou ambos

Para consultas telemétricas, o comportamento do serviço pode variar:

* Se a estação for **apenas pluviométrica**, normalmente a consulta funciona com o código pluviométrico.
* Se a estação possuir **código pluviométrico e fluviométrico**, o serviço da ANA geralmente retorna as séries corretamente **quando a requisição é feita com o código fluviométrico**.

### Recomendação

Sempre que a estação possuir ambos os códigos, prefira utilizar o **código fluviométrico** nas funções telemétricas.

Se o objetivo for baixar dados telemétricos pelo inventário, recomenda-se gerar o inventário **sem definir var_tpEst**.

Isso é especialmente importante para:

* `get_telemetric_inventory()`
* `get_telemetric_list()`

Caso contrário, a estação pode ser encontrada no inventário, mas não retornar dados telemétricos.

---

# 2. get_telemetric_inventory()

Baixa dados telemétricos de todas as estações contidas em um inventário.

## Sintaxe

```python
hidroana.get_telemetric_inventory(df, caminho="", save_info=False)
```

## Parâmetros

| Parâmetro | Tipo      | Default     |
| --------- | --------- | ----------- |
| df        | DataFrame | obrigatório |
| caminho   | str       | ""          |
| save_info | bool      | False       |

## Saída

* Um CSV por estação
* DataFrame resumo com disponibilidade de:

  * chuva
  * nível
  * vazão

## Exemplo

```python
inv = hidroana.get_inventory(var_nmEstado="SC", var_telemetrica="1")

resumo = hidroana.get_telemetric_inventory(
    inv,
    caminho="./dados/",
    save_info=True
)
```

---

# 3. get_telemetric_list()

Baixa dados telemétricos de uma lista de estações.

## Sintaxe

```python
hidroana.get_telemetric_list(
    list_est,
    d_i,
    d_f,
    caminho=""
)
```

## Parâmetros

| Parâmetro | Descrição               |
| --------- | ----------------------- |
| list_est  | Lista de códigos        |
| d_i       | Data inicial YYYY-MM-DD |
| d_f       | Data final YYYY-MM-DD   |
| caminho   | Pasta saída             |

## Exemplo

```python
hidroana.get_telemetric_list(
    ["74355000"],
    "2020-01-01",
    "2020-12-31",
    "./dados/"
)
```

---

# 4. get_conv_data_list()

Baixa séries históricas convencionais de estações específicas.

## Sintaxe

```python
hidroana.get_conv_data_list(
    list_est,
    d_i,
    d_f,
    tipo,
    caminho="",
    cons=1
)
```

## Tipo de dado (`tipo`)

* `"1"` = Cota
* `"2"` = Chuva
* `"3"` = Vazão

## Consistência (`cons`)

* `1` = Prioriza dados consistidos quando existirem
* `2` = Apenas nível de consistência 2

## Exemplo

```python
hidroana.get_conv_data_list(
    ["02549000"],
    "1990-01-01",
    "2020-12-31",
    tipo="3",
    caminho="./vazao/",
    cons=1
)
```

---

# 5. get_conv_inventory()

Baixa séries convencionais de todas as estações de um inventário.

## Sintaxe

```python
hidroana.get_conv_inventory(
    df,
    tipo,
    caminho="",
    cons=1,
    save_info=False
)
```

## Saída

* CSV por estação
* Resumo indicando disponibilidade

## Exemplo

```python
inv = hidroana.get_inventory(var_nmEstado="PR")

hidroana.get_conv_inventory(
    inv,
    tipo="2",
    caminho="./chuva/",
    save_info=True
)
```

---

# 6. get_series_by_shape()

Seleciona estações da ANA localizadas dentro de uma área espacial (Shapefile ou GeoPackage), com opção de buffer, e realiza o download automático das séries hidrológicas.

---

## Sintaxe

```python
hidroana.get_series_by_shape(
    arquivo,
    d_i,
    d_f,
    buffer_km=0,
    layer=None,
    rede="conv",
    tipo_dado="2",
    caminho="",
    save_inventory=True
)
```

---

## Parâmetros

| Parâmetro      | Tipo       | Default     | Descrição                                       |
| -------------- | ---------- | ----------- | ----------------------------------------------- |
| arquivo        | str        | obrigatório | Caminho para arquivo `.shp` ou `.gpkg`          |
| d_i            | str        | obrigatório | Data inicial no formato `YYYY-MM-DD`            |
| d_f            | str        | obrigatório | Data final no formato `YYYY-MM-DD`              |
| buffer_km      | float      | `0`         | Distância de buffer ao redor da geometria (km)  |
| layer          | str / None | `None`      | Nome da camada, quando `arquivo` for GeoPackage |
| rede           | str        | `"conv"`    | Tipo de rede: convencional ou telemétrica       |
| tipo_dado      | str        | `"2"`       | Tipo de dado a baixar                           |
| caminho        | str        | `""`        | Pasta de saída                                  |
| save_inventory | bool       | `True`      | Salva inventário filtrado em CSV                |

---

## Valores específicos

### `rede`

| Valor    | Significado       |
| -------- | ----------------- |
| `"conv"` | Rede convencional |
| `"tele"` | Rede telemétrica  |

---

### `tipo_dado`

| Valor | Tipo  |
| ----- | ----- |
| `"1"` | Cota  |
| `"2"` | Chuva |
| `"3"` | Vazão |

---

## Saída

Dependendo dos parâmetros informados, a função pode gerar:

* Inventário filtrado espacialmente
* Um arquivo CSV por estação selecionada
* Arquivo `info_estacoes.csv` com resumo de disponibilidade

---

## Exemplo

### Selecionar estações de chuva em uma bacia hidrográfica

```python
hidroana.get_series_by_shape(
    arquivo="bacia.shp",
    d_i="2000-01-01",
    d_f="2020-12-31",
    buffer_km=10,
    rede="conv",
    tipo_dado="2",
    caminho="./saida/"
)
```

---

### Usando GeoPackage com layer específica

```python
hidroana.get_series_by_shape(
    arquivo="bacias.gpkg",
    layer="rio_principal",
    d_i="2010-01-01",
    d_f="2020-12-31",
    rede="tele",
    caminho="./dados/"
)
```


---

# Observações

* Requer internet
* Depende da disponibilidade dos serviços da ANA
* Algumas estações podem não possuir dados
* Datas devem estar em formato:

```text
YYYY-MM-DD
```

---

# Autora

**Grenda Menezes**

E-mail: grenda.menezes@gmail.com

---

# Fonte dos Dados

Agência Nacional de Águas e Saneamento Básico (ANA)

https://www.gov.br/ana/
