import pandas as pd
import ta
from binance.client import Client
from binance.exceptions import BinanceAPIException
import requests
import time
import logging
import numpy as np

# Configura tu API Key y Secret
API_KEY = '19SEwu5mB9w4tNNnBpfArbenyBs9CnYCV7GPkqfz1I8bsCGl91mu34inL36zCgA1'
API_SECRET = 'mQ5Fvc62Zc0UwVzRr6PpnX3Q0cJnK98EnFyaaUCyc1snB2RJqGj0oguQLxdmwFZ1'

# Configura tu bot de Telegram
TELEGRAM_TOKEN = '7610957102:AAFKZE_NcFhUfGDlo3uRiVaXXGQftyvlTNM'
TELEGRAM_CHAT_ID = '-1002480885898'
THREAD_ID = '518564'

# Initialize the Binance client
client = Client(API_KEY, API_SECRET)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define the rate limit (adjust as per Binance API limits)
RATE_LIMIT_SECONDS = 10  # 1 request every 0.5 seconds

def get_futures_symbols():
    """Get available futures symbols on Binance."""
    exchange_info = client.futures_exchange_info()
    symbols = [symbol['symbol'] for symbol in exchange_info['symbols'] if symbol['status'] == 'TRADING']
    return symbols

def calculate_zemna(close_price, zemna_multiplier):
    """Calculate ZEMNA zones based on the closing price and volatility multiplier."""
    upper_zone = close_price * (1 + zemna_multiplier)
    lower_zone = close_price * (1 - zemna_multiplier)
    return upper_zone, lower_zone

def calculate_rsi(prices, period=14):
    """Calculate RSI for a list of prices."""
    if len(prices) < period:
        return None
    rsi = ta.momentum.RSIIndicator(pd.Series(prices), window=period)
    return rsi.rsi().iloc[-1]

def detect_divergence(prices, rsi_values):
    """Detect possible bullish divergences and bearish convergences."""
    if len(prices) < 2 or len(rsi_values) < 2:
        return None

    if prices[-1] < prices[-2] and rsi_values[-1] > rsi_values[-2]:
        return "Possible Bullish Divergence"
    elif prices[-1] > prices[-2] and rsi_values[-1] < rsi_values[-2]:
        return "Possible Bearish Convergence"
    return None

def calculate_volatility(prices):
    """Calculate historical volatility using standard deviation."""
    returns = pd.Series(prices).pct_change().dropna()
    volatility = returns.std() * np.sqrt(len(returns))
    return volatility

def adapt_to_market_conditions(volatility):
    """Adjust strategy parameters based on market volatility."""
    # Example: Modify ZEMNA zones and stop loss/take profit levels
    if volatility > 0.05:  # High volatility threshold (adjust as needed)
        zemna_multiplier = 0.04  # Increase zones during high volatility
        sl_tp_multiplier = 0.05  # Wider stop loss and take profit
    else:
        zemna_multiplier = 0.02  # Decrease zones during low volatility
        sl_tp_multiplier = 0.03  # Tighter stop loss and take profit
    return zemna_multiplier, sl_tp_multiplier

def calculate_stop_loss_take_profit(close_price, sl_tp_multiplier):
    """Calculate stop loss and take profit levels."""
    take_profit = close_price * (1 + sl_tp_multiplier)
    stop_loss = close_price * (1 - sl_tp_multiplier)
    return take_profit, stop_loss

def send_telegram_message(message):
    """Send a message to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',  # Allows Markdown formatting
        'reply_to_message_id': THREAD_ID
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logging.error(f"Failed to send message: {e}")

def scan_futures_pairs():
    """Analyze all futures pairs and display results."""
    futures_symbols = get_futures_symbols()

    while True:
        for symbol in futures_symbols:
            logging.info(f"Analyzing {symbol}...")
            try:
                klines = client.futures_klines(symbol=symbol, interval='5m', limit=50)
                prices = [float(kline[4]) for kline in klines]  # Closing prices
                close_price = prices[-1]

                # Calculate market volatility
                volatility = calculate_volatility(prices)
                zemna_multiplier, sl_tp_multiplier = adapt_to_market_conditions(volatility)

                # Adjust ZEMNA zones based on volatility
                upper_zone, lower_zone = calculate_zemna(close_price, zemna_multiplier)

                # Calculate RSI
                rsi_value = calculate_rsi(prices)
                rsi_message = f"RSI: {rsi_value:.2f}" if rsi_value is not None else "RSI not available"

                # Detect divergences
                rsi_values = ta.momentum.RSIIndicator(pd.Series(prices), window=14).rsi().tolist()
                divergence_signal = detect_divergence(prices, rsi_values)

                # Calculate stop loss and take profit levels
                take_profit, stop_loss = calculate_stop_loss_take_profit(close_price, sl_tp_multiplier)

                # Determine trend
                trend = 'Bullish' if close_price > prices[-2] else 'Bearish'

                # Customize Telegram message
                message = (
                    f"📊 *{symbol} Analysis*\n\n"
                    f"💰 *Price*: `{close_price:.2f}`\n"
                    f"📈 *Volatility*: `{volatility:.2%}`\n"
                    f"🔼 *ZEMNA Upper*: `{upper_zone:.2f}`\n"
                    f"🔽 *ZEMNA Lower*: `{lower_zone:.2f}`\n"
                    f"📊 *{rsi_message}*\n"
                    f"📈 *Trend*: *{trend}*\n"
                    f"🎯 *Take Profit*: `{take_profit:.2f}`\n"
                    f"🛡️ *Stop Loss*: `{stop_loss:.2f}`\n"
                )
                if divergence_signal:
                    message += f"⚠️ *{divergence_signal}*\n"

                # Add custom message or alerts
                custom_message = "🚀 *Action*: Monitor this pair for potential trading opportunities.\n"

                # Final message to send
                final_message = message + custom_message

                send_telegram_message(final_message)

            except BinanceAPIException as e:
                logging.error(f"Binance API error for {symbol}: {e}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Network error when analyzing {symbol}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error when analyzing {symbol}: {e}")

            # Respectar el límite de tasa
            time.sleep(RATE_LIMIT_SECONDS)

        print("\nResumen de patrones encontrados:")
        for symbol, pats in patterns.items():
            print(f"{symbol}: {', '.join(pats)}")

        # Esperar antes del siguiente escaneo completo
        print("Esperando 5 minutos antes del siguiente escaneo...")
        time.sleep(10)  # Esperar 300 segundos (5 minutos)

        # Agregar pausa de 10 segundos aquí (después de cada ciclo completo)
        print("Esperando 10 segundos adicionales antes de reiniciar el escaneo...")
        time.sleep(120)

# Ejecutar el escáner
if __name__ == "__main__":
    scan_futures_pairs()
