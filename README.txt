# hidroana

Biblioteca Python para download e processamento de dados hidrológicos da Agência Nacional de Águas (ANA), incluindo dados telemétricos e convencionais.

## Descrição

O pacote hidroana permite acessar automaticamente os serviços web da ANA para obtenção de dados hidrológicos. As principais funcionalidades incluem:

* Consulta ao inventário de estações hidrológicas
* Download de dados telemétricos (chuva, nível e vazão)
* Download de séries históricas convencionais
* Exportação dos dados em formato CSV

A biblioteca foi desenvolvida para aplicações em hidrologia, modelagem ambiental e pesquisa científica.

## Instalação

### Instalação local

git clone https://github.com/grendamenezes/hidroana.git
cd hidroana
pip install -e .

### Dependências

* pandas
* tqdm
* zeep

Instalação manual das dependências:

pip install pandas tqdm zeep

## Exemplos de uso

### Obter inventário de estações

```python
import hidroana

df = hidroana.get_inventory(
    var_nmEstado="PR",
    save=True
)
```

### Baixar dados telemétricos a partir de um inventário

```python
df = hidroana.get_inventory(var_nmEstado="PR")

hidroana.get_telemetric_inventory(
    df,
    caminho="./dados/"
)
```

### Baixar dados de uma lista de estações

```python
hidroana.get_telemetric_list(
    list_est=["74355000"],
    d_i="2020-01-01",
    d_f="2020-12-31",
    caminho="./dados/"
)
```

### Baixar dados convencionais

```python
hidroana.get_conv_data_list(
    list_est=["2751018"],
    d_i="2000-01-01",
    d_f="2020-01-01",
    tipo="2",
    caminho="./dados/"
)
```

## Funcionalidades

* Integração com serviços SOAP da ANA
* Processamento automático de respostas XML
* Estruturação dos dados em pandas DataFrame
* Exportação automatizada para arquivos CSV
* Suporte a múltiplas estações

## Observações

* O funcionamento depende da disponibilidade dos serviços da ANA
* Algumas estações podem não possuir dados disponíveis
* Recomenda-se conexão estável com a internet

## Estrutura do projeto

hidroana/
│
├── __init__.py
├── hidroana.py
├── README.md
└── setup.py

## Autora

Grenda Menezes
E-mail: grenda.menezes@gmail.com

## Fonte dos dados

Agência Nacional de Águas e Saneamento Básico (ANA)
https://www.gov.br/ana/
