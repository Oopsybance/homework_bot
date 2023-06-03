import logging
import os
import time
import telegram
import requests
import sys
import exceptions

from dotenv import load_dotenv


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
        logging.error(f'Не удалось отправить сообщение - {error}')


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к API {error}')
        raise exceptions.ResponseException(error)
    if response.status_code != 200:
        logging.error(f'Ошибка {response.status_code}')
        raise exceptions.ResponseException(response.status_code)
    return response.json


def check_response(response):
    """Проверка ответа API на корректность."""
    logging.debug('Начало проверки')
    if not isinstance(response, dict):
        raise TypeError('Несоответствие типа ответа API')
    if 'homeworks' not in response or 'current_date' not in response:
        raise exceptions.EmptyResponseFromAPI('Пустой ответ от API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Homeworks не является списком')
    return homeworks


def parse_status(homework):
    """Извлекает статус работы."""
    for homework_name, status in HOMEWORK_VERDICTS.items():
        homework_name = homework['homework_name']
        homework_status = homework['status']
    if not isinstance(homework, dict):
        raise TypeError('homework не соответствует типу dict')
    if homework_status not in (HOMEWORK_VERDICTS):
        raise KeyError(f'Отсутствуи ожидаемого ключа {status} в ответе API')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.error('Изменился статус проверки работы')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    logging.info('Бот запущен')
    if not check_tokens():
        logging.critical('Отсутсвют токены')
        sys.exit('Отсутсвуют токены')
    prev_message = ''
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            new_homework = check_response(api_answer)
            timestamp = api_answer.get('timestamp',
                                       timestamp)
            if new_homework:
                message = parse_status(new_homework[0])
                if message != prev_message:
                    send_message(bot, message)
                    prev_message = message
            else:
                logging.error('Статус проверки работы изменился')
        except exceptions.SendMessageError as error:
            logging.error(f'Ошибка при отпраке сообщения в Telegramm: {error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
