import logging
import os
import time
import sys
from http import HTTPStatus
from pathlib import Path

import requests
import telegram
from dotenv import load_dotenv


load_dotenv()


MESSAGE_IS_SENT = 'Сообщение отправлено:'
MESSAGE_IS_NOT_SENT = 'Сообщение не отправлено:'
ERROR_JSON = 'Ошибка получения json'
KEY_ANSWER = 'код ответа'
ERROR_API = 'Ошибка при запросе к API'
ERROR_CHEK_RSPONSE = 'Ошибка типа овета:'
KEY_HOMEWORK_IS_NOT = 'Ключ homeworks отсутствует'
HOMEWORK_IS_NOT_LIST = 'Объект homeworks не является листом'
WORK_STATUS = 'Работа не на проверке:'
STATUS_HOMEWORK_VERDICT = 'не соответствует справочнику статусов'
TOKEN_IS_NOT = 'Отсутсвует токен'
KEY_STATUS = 'Ключ status отсутствует в homework'
KEY_HOMEWORK_NAME = 'Ключ homework_name отсутствует в homework'
HOMEWOR_STATUS = 'Изменился статус проверки работы'

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
    tokens = ('PRACTICUM_TOKEN',
              'TELEGRAM_TOKEN',
              'TELEGRAM_CHAT_ID')
    for name in tokens:
        if not globals()[name]:
            logging.critical(TOKEN_IS_NOT.format(name))
            sys.exit()
    logging.error('Проверка токенов прошла успешно')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(MESSAGE_IS_SENT.format(message))
    except Exception as error:
        logging.error(
            MESSAGE_IS_NOT_SENT.format(error),
            exc_info=True
        )


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        try:
            response_json = response.json()
        except Exception as error:
            raise Exception(ERROR_JSON.format(error))
        if response.status_code != HTTPStatus.OK:
            raise Exception(KEY_ANSWER.format(response.status_code))
    except Exception as error:
        raise Exception(ERROR_API.format(error))
    else:
        return response_json


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(ERROR_CHEK_RSPONSE.format(type(response)))
    homework_response = response.get('homeworks')
    if 'homeworks' not in response:
        raise KeyError(KEY_HOMEWORK_IS_NOT)
    if not isinstance(homework_response, list):
        raise TypeError(HOMEWORK_IS_NOT_LIST)
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
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    check_tokens()
    send_message(bot, 'Бот запущен')
    status_non = None
    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', timestamp)
            homeworks = check_response(response)
            if len(homeworks) == 0:
                if parse_status(homeworks) != status_non:
                    status_non = parse_status(homeworks)
                    send_message(bot, WORK_STATUS.format(homeworks))
                else:
                    logging.info('Без обновлений')
            message = parse_status(homeworks[0])
            send_message(bot, message)
            logging.info(message)
        except Exception as error:
            message = f'Сбой в работе бота: {error}'
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(message)s, %(lineno)d, %(name)s',
        filemode='w',
        filename=f'{Path(__file__).stem}.log',
        level=logging.INFO,
    )
    main()
