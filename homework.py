import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()


UNSUCCESSFUL_MESSAGE_SEND_WUTH_ERROR = ('Не удалось отправить сообщение "{}".'
                                        'Ошибка: {}')
SUCCESSFUL_MESSAGE_SEND = 'Сообщение успешно отправлено: {}'
KEY_ANSWER = 'Ошибка {}'
API_ERROR = ('Ошибка API: {}. Ключ: {}. Эндпоинт {url} недоступен.'
             'Параметры запроса: headers - {headers}, params - {params}.')
ERROR_CHEK_RESPONSE = 'Ошибка типа овета: {}'
KEY_HOMEWORK_IS_NOT = 'Ключ homeworks отсутствует'
HOMEWORKS_LIST_TYPE = ('Неверный тип списка заданий.'
                       'Ожидался тип list, получен: {}')
STATUS_HOMEWORK_VERDICT = 'не соответствует справочнику статусов {}'
KEY_STATUS = 'Ключ status отсутствует в homework'
KEY_HOMEWORK_NAME = 'Ключ homework_name отсутствует в homework'
TOKEN_CHEK = 'Проверка токенов прошла успешно'
HOMEWORK_FOR_PERIOD = 'Список работ за запрашиваемый период пустой'
BOT_NOT_WORK = 'Сбой в работе бота: {}'
NOT_TOKENS_ERROR = 'Некоторые токены отсутствуют:{}'
STATUS_HOMEWORK_MESSAGE = 'Изменился статус проверки работы "{}". {}'
REQUEST_PARAMETRS = ('Ошибка {}. Эндпоинт {url} недоступен. Параметры запроса:'
                     'headers - {headers}, params - {params}.')
REQUEST_STATUS_CODE = ('Неверный код {} returned from {url} '
                       'params: {params} - Headers: {headers}')
BOT_ERROR = 'Сбой в работе бота: {}!'

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
    'PRACTICUM_TOKEN',
    'TELEGRAM_TOKEN',
    'TELEGRAM_CHAT_ID',
}


def check_tokens():
    """Проверка доступности токенов."""
    missing_tokens = [name for name in TOKENS if not globals()[name]]
    if missing_tokens:
        logging.critical(NOT_TOKENS_ERROR.format(missing_tokens))
        raise ValueError(TOKEN_CHEK)


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(SUCCESSFUL_MESSAGE_SEND.format(message))
        return True
    except Exception as error:
        logging.exception(
            logging.debug(UNSUCCESSFUL_MESSAGE_SEND_WUTH_ERROR .format(
                message, error))
        )
        return False


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    request_parameters = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response = requests.get(**request_parameters)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(REQUEST_PARAMETRS.format(
            error, **request_parameters))
    if response.status_code != HTTPStatus.OK:
        raise ValueError(REQUEST_STATUS_CODE.format(
            response.status_code, **request_parameters)
        )
    api_response = response.json()
    for key in ('code', 'error'):
        if key in api_response:
            raise ValueError(API_ERROR.format(
                api_response[key], key, **request_parameters
            ))
    return api_response


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(ERROR_CHEK_RESPONSE.format(type(response)))
    homeworks = response.get('homeworks')
    if 'homeworks' not in response:
        raise KeyError(KEY_HOMEWORK_IS_NOT)
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORKS_LIST_TYPE.format(type(homeworks)))
    return homeworks


def parse_status(homework):
    """Извлекает статус работы."""
    if 'status' not in homework:
        raise KeyError(KEY_STATUS)
    if 'homework_name' not in homework:
        raise KeyError(KEY_HOMEWORK_NAME)
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_HOMEWORK_VERDICT.format(status))
    return STATUS_HOMEWORK_MESSAGE.format(homework.get('homework_name'),
                                          HOMEWORK_VERDICTS[status])


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
                error_message = HOMEWORK_FOR_PERIOD
            else:
                error_message = parse_status(homeworks[0])
            if last_error != error_message:
                message_sent = send_message(bot, error_message)
                if message_sent:
                    timestamp = response.get('current_date', timestamp)
                    last_error = error_message
            else:
                last_error = None
        except Exception as error:
            error_description = BOT_ERROR.format(error)
            send_message(bot, BOT_ERROR.format(error_description))
            last_error = error_description
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        filemode='w',
        handlers=[
            logging.FileHandler(__file__ + '.log')
        ],
        level=logging.INFO
    )
    main()
