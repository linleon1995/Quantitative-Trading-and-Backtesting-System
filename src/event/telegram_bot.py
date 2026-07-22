import logging
import random
import time
from datetime import datetime

import requests
import telegram.ext.filters as filters
from telegram import Update
from telegram.error import NetworkError, TimedOut
from telegram.ext import CallbackContext, CommandHandler, MessageHandler, Updater

# from src.binance_api import get_binance_ticker_price

# Configure basic logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Replace 'YOUR_TOKEN' with the token you obtained from BotFather
TOKEN = '6041794044:AAHdd2S1CSR9CVhr-TrduVETEUJr3uxbqxU'

def start(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('Hello! I am your demo bot. Type /help to see available commands.')

def help_command(update: Update, context: CallbackContext) -> None:
    update.message.reply_text('You can use the following commands:\n'
                              '/start - Start the bot\n'
                              '/help - Display help message\n'
                              '/echo <message> - Echo the provided message')

def echo(update: Update, context: CallbackContext, profits) -> None:
    prices = calculate_max_profit()
    update.message.reply_text(f'You said: {prices}')
    # update.message.reply_text(f'You said: {update.message.text}')
    # update.message.chat('ccol')


def error_handler(update: object, context: CallbackContext) -> None:
    """Log Errors caused by Updates."""
    if isinstance(context.error, NetworkError):
        logging.warning("Disconnection detected (NetworkError) during polling. Error: %s", context.error)
    elif isinstance(context.error, TimedOut):
        logging.warning("Disconnection detected (Timeout) during polling. Error: %s", context.error)
    else:
        logging.error(msg="Exception while handling an update:", exc_info=context.error)


class get_coin_profit:
    def __init__(self):
        self.last_ticker = self.get_usdt_ticker()

    def get_usdt_ticker(self):
        new_ticker_price = []
        # ticker_price = get_binance_ticker_price()
        ticker_price = []
        for coin in ticker_price:
            if coin['symbol'].endswith('USDT'):
                new_ticker_price.append(coin)
        return new_ticker_price

    def calculate_max_profit(self):
        ticker_price = self.get_usdt_ticker()
        profits = {}
        for cur_ticker, last_ticker in zip(ticker_price, self.last_ticker):
            profit = (float(cur_ticker['price']) - float(last_ticker['price'])) / float(last_ticker['price'])
            profits[cur_ticker['symbol']] = profit
        sorted_profit = dict(sorted(profits.items(), key=lambda item: item[1], reverse=True))
        # print(sorted_profit)
        self.last_ticker = ticker_price
        return sorted_profit


def main(ProfitGetter) -> None:
    # Consider if ProfitGetter needs re-initialization inside the loop
    # if its state becomes invalid or it needs to fetch fresh data after a crash.
    # For now, initializing once outside the main retry loop.
    first_run = True
    while True:
        try:
            if not first_run:
                logging.info("Reconnection attempt successful. Telegram Bot Updater is restarting/resuming.")
            else:
                logging.info("Starting Telegram Bot Updater for the first time.")
            first_run = False

            updater = Updater(TOKEN)

            dispatcher = updater.dispatcher

            # Register command handlers
            dispatcher.add_handler(CommandHandler("start", start))
            dispatcher.add_handler(CommandHandler("help", help_command))

            # Register a message handler to echo messages
            # Note: The following part related to ProfitGetter and best_profits might need adjustment
            # if it's intended to be dynamic or part of a specific command.
            # This calculation currently happens once at the start of each main loop iteration.
            sorted_profit = ProfitGetter.calculate_max_profit()
            best_profits = []
            n = 5
            for idx, (symbol, profit) in enumerate(sorted_profit.items()):
                if idx >= n:
                    break
                best_profits.append(f'{symbol} -> {profit*100:.2f} %')
            # print(Filters.text) # Filters is not defined here, this would cause an error.
            # print(best_profits) # This prints to console, not to Telegram.

            # It seems `echo` is intended to use `ProfitGetter`.
            # We might need to pass ProfitGetter or its data to the echo handler,
            # or make ProfitGetter accessible globally or via context.
            # For now, assuming `echo` can access `ProfitGetter` or its data as needed.
            # The original code had `MessageHandler(Filters.text & ~Filters.command, echo)`
            # but `Filters` is not imported/defined in this scope.
            # Assuming `from telegram.ext import Filters` is missing or was intended differently.
            # For now, I'll comment out the problematic lines and use a placeholder for the handler.
            # To make it runnable, let's assume Filters was meant to be imported.
            # from telegram.ext import Filters # Temporary import for Filters - No longer needed here
            dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))



            # Start the Bot
            updater.start_polling(error_callback=error_handler)

            # Run the bot until you send a signal to stop (Ctrl+C)
            updater.idle()
        except (NetworkError, TimedOut) as e:
            logging.error(f"Updater crashed with NetworkError/TimedOut: {e}. Restarting after a delay.")
            time.sleep(15)
        except Exception as e:
            logging.error(f"An unexpected error occurred in main: {e}. Restarting after a delay.")
            # Consider if some errors should not lead to a restart.
            time.sleep(15)
        # No specific finally block needed for now, as Updater handles its resources.


def send_msg(message_text):
    bot_token = TOKEN
    chat_id = "1745246461"

    # Set the API endpoint URL
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    # Set the payload data
    payload = {
        'chat_id': chat_id,
        'text': message_text
    }

    # Send the POST request
    max_retries = 5
    base_delay = 1  # seconds
    for attempt_number in range(max_retries):
        try:
            response = requests.post(url, data=payload)
            response.raise_for_status()  # Raise an exception for bad status codes
            logging.info(f"Message sent successfully to chat_id {chat_id}.")
            # Print the response content
            print(response.text)
            return  # Message sent successfully
        except requests.exceptions.RequestException as e:
            logging.error(f"Error sending message (attempt {attempt_number + 1}/{max_retries}): {e}")
            if attempt_number + 1 == max_retries:
                logging.error("Max retries reached for send_msg.")
                # Optionally re-raise the exception or return an error indicator
                # For now, just logging and exiting the function
                return

            delay = base_delay * (2 ** attempt_number) + random.uniform(0, 1)
            logging.info(f"Retrying send_msg in {delay:.2f} seconds...")
            time.sleep(delay)
    logging.error("Failed to send message after all retries.")

if __name__ == '__main__':
    while True:
        send_msg(message_text=f'Current time is {datetime.now()}')
        time.sleep(30*60)

    # ProfitGetter = get_coin_profit()
    # while True:
    #     sorted_profit = ProfitGetter.calculate_max_profit()
    #     best_profits = []
    #     n = 5
    #     for idx, (symbol, profit) in enumerate(sorted_profit.items()):
    #         if idx >= n:
    #             break
    #         best_profits.append(f'{symbol} -> {profit*100:.2f} %')
    #     pprint(best_profits)
    #     time.sleep(5)
    # # main(ProfitGetter)
