import logging
import os
import time
import sys

import requests
import telegram
from logging import Formatter, StreamHandler
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from json.decoder import JSONDecodeError

from exceptions import RequestError

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    filename=__file__ + '.log',
    filemode='w',
    formatter=Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
handler = RotatingFileHandler(
    filename='homework_bot.log',
)
stream_handler = StreamHandler()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.addHandler(stream_handler)


def check_tokens():
    """Проверка доступности токенов."""
    tokens = {'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
              'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
              'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    for name, value in tokens.items():
        if value is None:
            logging.critical(f'Отсутсвует токен {name}')
            sys.exit('Отсутсвует токены')
    logging.error('Проверка токенов прошла успешно')
    return bool


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение отправлено: {message}')
    except Exception as error:
        logging.error(
            f'Не удалось отправить сообщение - {error}',
            exc_info=True
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise ConnectionError(f'код ответа {response.status_code}')
        return response.json()
    except JSONDecodeError:
        raise JSONDecodeError('Запрос к API вернулся не в формате JSON')
    except Exception as error:
        raise RequestError(f'Ошибка при запросе к API{error}')


def check_response(response):
    """Проверка ответа API на корректность."""
    logging.debug('Начало проверки')
    if not isinstance(response, dict):
        raise TypeError(f'Ошибка типа овета: {response}')
    if 'homeworks' not in response:
        raise KeyError('Ключ homeworks отсутствует')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Объект homeworks не является списком')
    return response['homeworks']


def parse_status(homework):
    """Извлекает статус работы."""
    if 'status' not in homework:
        raise KeyError('Ключ status отсутствует в homework')
    if 'homework_name' not in homework:
        raise KeyError('Ключ homework_name отсутствует в homework')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError({homework_status}.format(homework_status))
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, 'Бот запущен')
    last_send = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date')
            homeworks = check_response(response)
            if not homeworks:
                continue
            message = parse_status(homeworks[0])
            send_message(bot, message)
            logging.info(message)
        except Exception as error:
            error_message = f'Сбой в работе бота: {error}'
            logging.error(error_message)
            if error_message != last_send:
                last_send = error_message
                send_message(bot, error_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
