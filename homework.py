import logging
import os
import time
import sys
from http import HTTPStatus
from pathlib import Path

import requests
import telegram
from dotenv import load_dotenv

from exceptions import RequestError, StatusCodeError


load_dotenv()


MSG_IS_SENT = 'Сообщение отправлено: {message}'
MSG_IS_NOT_SENT = 'Сообщение не отправлено:'
KEY_ANSWER = 'Ошибка {response.status_code}'
ERROR_API = 'Ошибка при запросе к API'
ERROR_CHEK_RSPONSE = 'Ошибка типа овета:'
KEY_HOMEWORK_IS_NOT = 'Ключ homeworks отсутствует'
HOMEWORK_IS_NOT_TYPE = 'Объект homeworks может ялвяться не списком, а словарем'
STATUS_HOMEWORK_VERDICT = 'не соответствует справочнику статусов'
TOKEN_IS_NOT = '{} токен не найден'
KEY_STATUS = 'Ключ status отсутствует в homework'
KEY_HOMEWORK_NAME = 'Ключ homework_name отсутствует в homework'
TOKEN_CHEK = 'Проверка токенов прошла успешно'
WORK_BOT = 'Бот запущен'
HOMEWORK_FOR_PERIOD = 'Список работ за запрашиваемый период пустой'
BOT_NOT_WORK = 'Сбой в работе бота: {error}'
NOT_TOKENS_ERROR = 'Некоторые токены отсутствуют: %s'
STATUS_HOMEWORK_MSG = 'Изменился статус проверки работы "{}". {}'


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


def check_tokens():
    """Проверка доступности токенов."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = []
    for name in tokens:
        if not globals()[name]:
            logging.critical(TOKEN_IS_NOT.format(name))
            missing_tokens.append(name)
    if missing_tokens:
        logging.critical(NOT_TOKENS_ERROR, missing_tokens)
        sys.exit()
    else:
        logging.info(TOKEN_CHEK)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(MSG_IS_SENT)
    except Exception as error:
        logging.exception(
            MSG_IS_NOT_SENT.format(error),
            exc_info=True
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        response.raise_for_status
    except requests.exceptions.RequestException:
        raise RequestError(ERROR_API)
    if response.status_code != HTTPStatus.OK:
        raise StatusCodeError(KEY_ANSWER)
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    return response.json()


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(ERROR_CHEK_RSPONSE.format(type(response)))
    homework_response = response.get('homeworks')
    if not 'homeworks':
        raise KeyError(KEY_HOMEWORK_IS_NOT)
    if not isinstance(homework_response, list):
        raise TypeError(HOMEWORK_IS_NOT_TYPE)
    return homework_response


def parse_status(homework):
    """Извлекает статус работы."""
    if 'status' not in homework:
        raise KeyError(KEY_STATUS)
    if 'homework_name' not in homework:
        raise KeyError(KEY_HOMEWORK_NAME)
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_HOMEWORK_VERDICT.format(homework_status))
    verdict = HOMEWORK_VERDICTS[homework_status]
    return STATUS_HOMEWORK_MSG.format(homework_name, verdict)


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, WORK_BOT)
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logging.debug(HOMEWORK_FOR_PERIOD)
            timestamp = response.get('current_date', timestamp)
            message = parse_status(homeworks[0])
            send_message(bot, message)
            logging.info(message)
        except Exception as error:
            logging.error(BOT_NOT_WORK.format(error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w',
        filename=f'{Path(__file__).stem}.log',
        level=logging.INFO,
    )
    main()
