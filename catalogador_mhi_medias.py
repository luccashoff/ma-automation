from iqoptionapi.stable_api import IQ_Option
from configobj import ConfigObj
from tabulate import tabulate
import time
import sys

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
    wma = []
    weights = list(range(1, n + 1))

    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        wma_value = sum(w * close for w, close in zip(weights, close_prices)) / sum(weights)
        wma.append(wma_value)

    return wma

# Função para calcular a média móvel exponencial (EMA)
def calculate_ema(velas, n):
    ema = []
    alpha = 2 / (n + 1)
    ema_value = sum(float(vela['close']) for vela in velas[:n]) / n

    for i in range(n, len(velas)):
        ema_value = alpha * float(velas[i]['close']) + (1 - alpha) * ema_value
        ema.append(ema_value)

    return ema

# Função para calcular a média móvel Poisson (PMA)
def calculate_pma(velas, n):
    pma = []
    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        pma_value = sum(p * close for p, close in zip(range(1, n + 1), close_prices)) / sum(range(1, n + 1))
        pma.append(pma_value)

    return pma

# Função para calcular a média móvel harmônica (HMA)
def calculate_hma(velas, n):
    hma = []
    weights = [2 / i for i in range(1, n + 1)]
    weights_sum = sum(weights)

    for i in range(n, len(velas)):
        close_prices = [float(vela['close']) for vela in velas[i - n:i]]
        hma_value = weights_sum / sum(w / close for w, close in zip(weights, close_prices))
        hma.append(hma_value)

    return hma

# Configurações
config = ConfigObj('config.txt')
email = config['LOGIN']['email']
senha = config['LOGIN']['senha']

print('Iniciando Conexão com a IQOption')
API = IQ_Option(email, senha)

# Conectar na IQOption
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

# Função para verificar a tendência da estratégia MHI
def check_mhi_trend(velas):
    mhi_trend = 'None'

    try:
        vela1 = 'Verde' if velas[-3]['open'] < velas[-3]['close'] else 'Vermelha' if velas[-3]['open'] > velas[-3]['close'] else 'Doji'
        vela2 = 'Verde' if velas[-2]['open'] < velas[-2]['close'] else 'Vermelha' if velas[-2]['open'] > velas[-2]['close'] else 'Doji'
        vela3 = 'Verde' if velas[-1]['open'] < velas[-1]['close'] else 'Vermelha' if velas[-1]['open'] > velas[-1]['close'] else 'Doji'

        cores = vela1, vela2, vela3

       # print(f"Velas: {vela1}, {vela2}, {vela3}")  # Adicione esta linha para depuração

        if cores.count('Verde') > cores.count('Vermelha') and cores.count('Doji') == 0:
            mhi_trend = 'Vermelha'
        elif cores.count('Vermelha') > cores.count('Verde') and cores.count('Doji') == 0:
            mhi_trend = 'Verde'
    except:
        pass

    return mhi_trend

# Função para realizar a análise em lotes de 1000 velas com a média móvel e estratégia MHI
def analyze_candles_with_ma_and_mhi(API, par, timeframe, total_candles, ma_function, ma_period):
    win_total = 0
    loss_total = 0
    velas_analisadas_total = 0

    print(f"Iniciando análise de velas para o par {par} com média móvel {ma_function.__name__.replace('calculate_', '').upper()} ({ma_period} períodos)")

    batch_size = 1000
    velas_analisadas = []  # Lista para armazenar velas na janela deslizante

    # Loop até atingir o total desejado
    while velas_analisadas_total < total_candles:
        try:
            endtime = time.time()
            velas_temp = API.get_candles(par, timeframe, batch_size, endtime=endtime)
        except Exception as e:
            #print(f"Erro ao recuperar velas para {par}: {e}")
            return [par, 0, 0, 0.0, 0]

        velas_analisadas.extend(velas_temp)  # Adiciona novas velas à lista
        velas_analisadas_total += len(velas_temp)

        if len(velas_analisadas) < batch_size + ma_period:
            continue  # Continue até ter velas suficientes para análise

        mhi_trend = check_mhi_trend(velas_analisadas[-3:])  # Últimas 3 velas para MHI
        ma_values = ma_function(velas_analisadas[-batch_size:], ma_period)  # Últimas 'batch_size' velas para média

        batch_win = 0
        batch_loss = 0

        for j in range(len(ma_values) - 1):
            current_close = float(velas_analisadas[j + len(velas_analisadas) - len(ma_values)]['close'])
            next_close = float(velas_analisadas[j + len(velas_analisadas) - len(ma_values) + 1]['close'])
            ma_value = ma_values[j]

            # Verificação da tendência e resultados
            if current_close > ma_value and mhi_trend == 'Verde':
                trend = 'CALL'
            elif current_close < ma_value and mhi_trend == 'Vermelha':
                trend = 'PUT'
            else:
                continue  # Pular para a próxima vela se as tendências não coincidirem

            if (trend == 'CALL' and next_close > current_close) or (trend == 'PUT' and next_close < current_close):
                batch_win += 1
            else:
                batch_loss += 1

        win_total += batch_win
        loss_total += batch_loss

        # Atualiza a janela deslizante removendo as velas mais antigas
        velas_analisadas = velas_analisadas[batch_size:]

    total_trades = win_total + loss_total
    if total_trades > 0:
        assertividade_total = round(win_total / total_trades * 100, 2)
    else:
        assertividade_total = 0.0

    print(f"Análise para o par {par} concluída. Resultados:")
    print(f"Wins: {win_total}, Loss: {loss_total}, Assertividade: {assertividade_total}%")
    print(f"Total de velas analisadas: {velas_analisadas_total}\n")

    return [par, win_total, loss_total, assertividade_total, velas_analisadas_total]

# Filtrar ativos que não são OTC (digitais)
all_assets = API.get_all_open_time()
pares_nao_otc = [par for par in all_assets['digital'] if 'OTC' not in par]

# Agora, ao escolher o tipo de média móvel desejada, basta chamar a função correspondente
ma_type = input("Escolha o tipo de média móvel (SMA, WMA, EMA, PMA, HMA): ").upper()

if ma_type == "SMA":
    ma_function = calculate_sma
elif ma_type == "WMA":
    ma_function = calculate_wma
elif ma_type == "EMA":
    ma_function = calculate_ema
elif ma_type == "PMA":
    ma_function = calculate_pma
elif ma_type == "HMA":
    ma_function = calculate_hma
else:
    print("Tipo de média móvel inválido. Utilizando SMA por padrão.")
    ma_function = calculate_sma

# Solicite o período da média móvel ao usuário
ma_period = int(input("Informe o período da média móvel: "))

timeframe = 60
qnt_velas = 43200  # 30 dias * 1440 velas por dia
all_results = []
velas_analisadas_dict = {par: [] for par in pares_nao_otc}

for par in pares_nao_otc:
    # Calcula o número de lotes necessários
    total_candles = qnt_velas
    batch_size = 1000
    num_batches = total_candles // batch_size

    # Realiza a análise em lotes e acumula os resultados totais
    all_results.append(analyze_candles_with_ma_and_mhi(API, par, timeframe, total_candles, ma_function, ma_period))


# Exibe os resultados
print(tabulate(all_results, headers=['PAR', 'WINS', 'LOSS', 'ASSERTIVIDADE', 'VELAS ANALISADAS TOTAL']))