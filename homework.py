import logging
import os
import time
from http import HTTPStatus
from pathlib import Path

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()


MESSAGE_DEBUG = 'Отладочное сообщение: {}'
KEY_ANSWER = 'Ошибка {}'
API_ERROR = 'Ошибка API: {}'
ERROR_CHEK_RESPONSE = 'Ошибка типа овета: {}'
KEY_HOMEWORK_IS_NOT = 'Ключ homeworks отсутствует'
HOMEWORK_IS_NOT_TYPE = 'Объект homeworks может ялвяться не списком, а словарем'
STATUS_HOMEWORK_VERDICT = 'не соответствует справочнику статусов {}'
KEY_STATUS = 'Ключ status отсутствует в homework'
KEY_HOMEWORK_NAME = 'Ключ homework_name отсутствует в homework'
TOKEN_CHEK = 'Проверка токенов прошла успешно'
HOMEWORK_FOR_PERIOD = 'Список работ за запрашиваемый период пустой'
BOT_NOT_WORK = 'Сбой в работе бота: {}'
NOT_TOKENS_ERROR = 'Некоторые токены отсутствуют: %s'
STATUS_HOMEWORK_MSG = 'Изменился статус проверки работы "{}". {}'
REQUSET_PARAMETRS = 'Эндпоинт {} недоступен. Параметры запроса:' \
                    'headers - {}, params - {}.'
REQUEST_STATUS_CODE = 'Неверный код {} returned from }. ' \
                      'Params: {} - Headers: {}'

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

TOKENS = {
    'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
    'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
    'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
}


def check_tokens():
    """Проверка доступности токенов."""
    missing_tokens = [name for name in TOKENS if not globals()[name]]
    if missing_tokens:
        logging.critical(NOT_TOKENS_ERROR % missing_tokens)
        raise ValueError(TOKEN_CHEK)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(MESSAGE_DEBUG)
    except Exception as error:
        logging.exception(
            MESSAGE_DEBUG.format(error),
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException:
        raise ValueError(REQUSET_PARAMETRS.format(ENDPOINT, params, HEADERS))
    if response.status_code != HTTPStatus.OK:
        raise ValueError(REQUEST_STATUS_CODE.format(response.status_code,
                                                    ENDPOINT, params, HEADERS))
    api_response = response.json()
    if 'code' in api_response or 'error' in api_response:
        error_msg = None
        if 'code' in api_response:
            error_msg = API_ERROR.format(api_response('code'))
        if 'error' in api_response:
            error_msg = API_ERROR.format(api_response('error'))
        raise ValueError(error_msg)
    return api_response


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(ERROR_CHEK_RESPONSE.format(type(response)))
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
    return STATUS_HOMEWORK_MSG.format(homework_name,
                                      HOMEWORK_VERDICTS[homework_status])


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                if last_error != HOMEWORK_FOR_PERIOD:
                    last_error = HOMEWORK_FOR_PERIOD
                    send_message(bot, HOMEWORK_FOR_PERIOD)
            else:
                last_error = None
                timestamp = response.get('current_date', timestamp)
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logging.info(message)
        except Exception as error:
            if last_error != str(error):
                last_error = str(error)
                send_message(bot, str(error))
                logging.error(str(error))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w',
        filename=f'{Path(__file__).stem}.log',
        level=logging.INFO,
    )
    logging.getLogger().addHandler(logging.StreamHandler())
    main()
