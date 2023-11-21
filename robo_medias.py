from iqoptionapi.stable_api import IQ_Option
from configobj import ConfigObj
from tabulate import tabulate
import time
import sys

# Configurações
config = ConfigObj('config.txt')
email = config['LOGIN']['email']
senha = config['LOGIN']['senha']

# Função para calcular a média móvel simples (SMA)
def calculate_sma(velas, n):
    sma = []
    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        sma_value = sum(close_prices) / n
        sma.append(sma_value)
    return sma

# Função para calcular a média móvel ponderada (WMA)
def calculate_wma(velas, n):
    weights = list(range(1, n + 1))
    wma = []
    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        wma_value = sum([price * weight for price, weight in zip(close_prices, weights)]) / sum(weights)
        wma.append(wma_value)
    return wma

# Função para calcular a média móvel Poisson (PMA)
def calculate_pma(velas, n):
    pma = []
    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        pma_value = sum([price * (j + 1) for j, price in enumerate(close_prices)]) / sum(range(1, n + 1))
        pma.append(pma_value)
    return pma

# Função para calcular a média móvel ponderada (WMA)
def calculate_wma(velas, n):
    weights = list(range(1, n + 1))
    wma = []
    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        wma_value = sum([price * weight for price, weight in zip(close_prices, weights)]) / sum(weights)
        wma.append(wma_value)
    return wma

# Função para calcular a média móvel harmônica (HMA)
def calculate_hma(velas, n):
    weights = [2 / (i + 1) for i in range(n)]
    hma = []
    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        hma_value = n / sum([1 / (price + 1) for price in close_prices])
        hma.append(hma_value)
    return hma

# Função para realizar a análise em lotes de 1000 velas
def analyze_candles_in_batches(API, par, timeframe, total_candles, batch_size, velas_analisadas_dict, ma_type):
    win_total = 0
    loss_total = 0
    velas_analisadas_total = 0

    while velas_analisadas_total < total_candles:
        try:
            endtime = time.time()
            # Ajuste na chamada da função get_candles
            velas = API.get_candles(par, timeframe, batch_size, endtime=endtime)
        except Exception as e:
            print(f"Erro ao recuperar velas para {par}: {e}")
            continue

        # Ajuste para garantir que estamos considerando as últimas 1000 velas
        velas_analisadas = velas[-(total_candles - velas_analisadas_total):]

        # Remover velas já analisadas
        velas_analisadas = [vela for vela in velas_analisadas if vela not in velas_analisadas_dict[par]]

        # Armazena velas analisadas no dicionário
        velas_analisadas_dict[par] += velas_analisadas

        # Seleciona a função de média móvel com base na escolha do usuário
        if ma_type == 'SMA':
            ma_values = calculate_sma(velas_analisadas_dict[par], 15)
        elif ma_type == 'WMA':
            ma_values = calculate_wma(velas_analisadas_dict[par], 15)
        elif ma_type == 'PMA':
            ma_values = calculate_pma(velas_analisadas_dict[par], 15)
        elif ma_type == 'HMA':
            ma_values = calculate_hma(velas_analisadas_dict[par], 15)
        else:
            print(f"Tipo de média móvel não suportado: {ma_type}")
            sys.exit()

        win = 0
        loss = 0

        for j in range(len(ma_values) - 1):
            current_close = float(velas_analisadas_dict[par][j + 15]['close'])
            next_close = float(velas_analisadas_dict[par][j + 16]['close'])
            ma_value = ma_values[j]

            if current_close > ma_value and next_close < ma_value:
                win += 1
            elif current_close < ma_value and next_close > ma_value:
                win += 1
            else:
                loss += 1

        win_total += win
        loss_total += loss
        velas_analisadas_total = len(velas_analisadas_dict[par])

    assertividade_total = round(win_total / (win_total + loss_total) * 100, 2)

    # Ajuste para garantir que o número exato de velas seja 43200
    if velas_analisadas_total > total_candles:
        velas_analisadas_dict[par] = velas_analisadas_dict[par][:total_candles]

    return [par, win_total, loss_total, assertividade_total, velas_analisadas_total, win_total + loss_total]

# Função para permitir ao usuário escolher o tipo de média móvel
def choose_ma_type():
    valid_types = ['SMA', 'WMA', 'PMA', 'HMA']
    print("Escolha o tipo de média móvel:")
    print("1. SMA (Simple Moving Average)")
    print("2. WMA (Weighted Moving Average)")
    print("3. PMA (Poisson Moving Average)")
    print("4. HMA (Harmonic Moving Average)")

    choice = input("Digite o número correspondente à sua escolha: ")
    if choice.isnumeric() and int(choice) in range(1, 5):
        return valid_types[int(choice) - 1]
    else:
        print("Escolha inválida. Saindo.")
        sys.exit()

# Conectar na IQOption
API = IQ_Option(email, senha)
check, reason = API.connect()

if check:
    print('\nConectado com sucesso')
else:
    if reason == '{"code":"invalid_credentials","message":"You entered the wrong credentials. Please ensure that your login/password is correct."}':
        print('\nEmail ou senha incorreta')
        sys.exit()
    else:
        print('\nHouve um problema na conexão')
        print(reason)
        sys.exit()

# Filtrar ativos que não são OTC (digitais)
all_assets = API.get_all_open_time()
pares_nao_otc = [par for par in all_assets['digital'] if 'OTC' not in par]

timeframe = 60
qnt_velas = 43200  # 30 dias * 1440 velas por dia
all_results = []
velas_analisadas_dict = {par: [] for par in pares_nao_otc}

# Permitir ao usuário escolher o tipo de média móvel
ma_type = choose_ma_type()

for par in pares_nao_otc:
    # Realiza a análise garantindo exatamente 43200 velas
    all_results.append(analyze_candles_in_batches(API, par, timeframe, qnt_velas, 1000, velas_analisadas_dict, ma_type))

# Exibe os resultados
headers = ['PAR', 'WINS', 'LOSS', 'ASSERTIVIDADE', 'VELAS ANALISADAS TOTAL', 'WINS + LOSS']
print(tabulate(all_results, headers=headers))
