import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()


MESSAGE_DEBUG = 'Отладочное сообщение: {}'
MESSAGE_DEBUG_WITH_ERROR = 'Отладочное сообщение: {} - {}'
KEY_ANSWER = 'Ошибка {}'
API_ERROR = 'Ошибка API: {}'
ERROR_CHEK_RESPONSE = 'Ошибка типа овета: {}'
KEY_HOMEWORK_IS_NOT = 'Ключ homeworks отсутствует'
HOMEWORKS_LIST_TYPE = 'Неверный тип списка заданий.' \
                      'Ожидался тип list, получен:'
STATUS_HOMEWORK_VERDICT = 'не соответствует справочнику статусов {}'
KEY_STATUS = 'Ключ status отсутствует в homework'
KEY_HOMEWORK_NAME = 'Ключ homework_name отсутствует в homework'
TOKEN_CHEK = 'Проверка токенов прошла успешно'
HOMEWORK_FOR_PERIOD = 'Список работ за запрашиваемый период пустой'
BOT_NOT_WORK = 'Сбой в работе бота: {}'
NOT_TOKENS_ERROR = 'Некоторые токены отсутствуют:{}'
STATUS_HOMEWORK_MSG = 'Изменился статус проверки работы "{}". {}'
REQUSET_PARAMETRS = 'Эндпоинт {} недоступен. Параметры запроса:' \
                    'headers - {}, params - {}.'
REQUEST_STATUS_CODE = 'Неверный код {} returned from }. ' \
                      'Params: {} - Headers: {}'
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
        logging.debug(MESSAGE_DEBUG.format(message))
    except Exception as error:
        logging.exception(
            logging.debug(MESSAGE_DEBUG_WITH_ERROR.format(
                MESSAGE_DEBUG, error))
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    rq_pars = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    try:
        response = requests.get(**rq_pars)
    except requests.exceptions.RequestException as error:
        error_msg = REQUSET_PARAMETRS.format(error)
        raise requests.exceptions.RequestException(error_msg)
    if response.status_code != HTTPStatus.OK:
        raise ValueError(REQUEST_STATUS_CODE.format(response.status_code,
                                                    rq_pars['url'],
                                                    rq_pars['params'],
                                                    rq_pars['headers']))
    api_response = response.json()
    for key in ('code', 'error'):
        if key in api_response:
            error_msg = API_ERROR.format(api_response[key])
            raise ValueError(error_msg)
    return api_response


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(ERROR_CHEK_RESPONSE.format(type(response)))
    homeworks_list = response.get('homeworks')
    if 'homeworks' not in response:
        raise KeyError(KEY_HOMEWORK_IS_NOT)
    if not isinstance(homeworks_list, list):
        raise TypeError(HOMEWORKS_LIST_TYPE.format(type(homeworks_list)))
    return homeworks_list


def parse_status(homework):
    """Извлекает статус работы."""
    if 'status' not in homework:
        raise KeyError(KEY_STATUS)
    if 'homework_name' not in homework:
        raise KeyError(KEY_HOMEWORK_NAME)
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_HOMEWORK_VERDICT.format(status))
    return STATUS_HOMEWORK_MSG.format(homework.get('homework_name'),
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
                if last_error != HOMEWORK_FOR_PERIOD:
                    last_error = HOMEWORK_FOR_PERIOD
                    send_message(bot, HOMEWORK_FOR_PERIOD)
            else:
                message = parse_status(homeworks[0])
                send_message(bot, message)
                logging.info(message)
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            error_description = BOT_ERROR.format(error)
            if last_error != error_description:
                last_error = error_description
                send_message(bot, BOT_ERROR.format(error_description))
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()],
        level=logging.INFO,
    )
    main()
