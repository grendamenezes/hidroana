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

Consulta o inventário oficial de estações da ANA.

## Sintaxe

```python
hidroana.get_inventory(...)
```

## Parâmetros principais

| Parâmetro       | Tipo | Default            | Descrição                |
| --------------- | ---- | ------------------ | ------------------------ |
| caminho_saida   | str  | inventario_ana.csv | Nome do arquivo de saída |
| var_tpEst       | str  | ""                 | Tipo de estação          |
| var_nmEstado    | str  | ""                 | UF                       |
| var_nmMunicipio | str  | ""                 | Município                |
| var_nmRio       | str  | ""                 | Nome do rio              |
| var_telemetrica | str  | ""                 | 1 = sim / 0 = não        |
| save            | bool | False              | Salvar CSV               |

## Tipo de estação (`var_tpEst`)

* `"1"` = Fluviométrica
* `"2"` = Pluviométrica

## Retorno

```python
pandas.DataFrame
```

## Exemplo

```python
df = hidroana.get_inventory(
    var_nmEstado="PR",
    var_tpEst="2"
)
```

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

Seleciona estações dentro de um shapefile / GeoPackage com buffer espacial e faz download automático.

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

## Parâmetros

| Parâmetro | Descrição             |
| --------- | --------------------- |
| arquivo   | shp ou gpkg           |
| d_i       | Data inicial          |
| d_f       | Data final            |
| buffer_km | Buffer em km          |
| layer     | Nome da camada (gpkg) |
| rede      | "conv" ou "tele"      |
| tipo_dado | 1,2,3                 |
| caminho   | Pasta saída           |

## Exemplo com shapefile

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

## O que faz

1. Lê o shapefile
2. Aplica buffer
3. Busca inventário ANA
4. Seleciona estações dentro da área
5. Salva inventário filtrado
6. Baixa séries automaticamente

---

# Estrutura dos Arquivos Gerados

```text
saida/
├── 02549000.csv
├── 74355000.csv
├── info_estacoes.csv
└── inventario_filtrado.csv
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
