from http import HTTPStatus

import requests
import logging
import os
import time
from logging.handlers import RotatingFileHandler
import telegram

from dotenv import load_dotenv

load_dotenv()
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class Logging:  # Согласен что мудрено как-то...
    # Пометил настройки логирования в отдельный блок для того,
    # чтобы не смешивать с основными переменными программы
    """Настройки логирования."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        'homework.py.log',
        maxBytes=50000000,
        backupCount=5,
        encoding='utf-8')
    logger.addHandler(handler)

    send_successful = "Успешная отправка сообщения: "
    send_error = "Ошибка при отправке сообщения: "
    connection_try = 'Попытка запроса к: '
    connection_successful = 'Успешный запрос с '
    connection_error = 'Ошибка при запросе: '
    code_error = '\n Код ошибки: '
    key_error = 'Не найден ключ: '
    not_homeworks = "В ответе сервера не нашел: "
    not_token = 'Нет обязательной переменной для запуска программы'
    loop_repeat = f'Бот делает повторный запрос на сервер, ' \
                  f'после {RETRY_TIME}с. сна'
    no_status_change = f'Статусы не изменены, ' \
                       f'повторный запуск через {RETRY_TIME}'


def send_message(bot: telegram.Bot, message: str) -> requests.request:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        Logging.logger.info(Logging.send_successful + message)
    except ConnectionError(Logging.send_error + message):
        Logging.logger.error(Logging.send_error + message)


def get_api_answer(current_timestamp: int) -> requests.get:
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        Logging.logger.info(Logging.connection_error + ENDPOINT)
        if response.status_code == HTTPStatus.OK:
            Logging.logger.info(Logging.connection_successful + ENDPOINT)
            return response.json()
    except ConnectionError(Logging.connection_error + ENDPOINT):
        Logging.logger.error(Logging.connection_error + ENDPOINT)
    else:
        Logging.logger.error(Logging.connection_error + ENDPOINT +
                             Logging.code_error + str(response.status_code))
        raise ConnectionError(Logging.connection_error + ENDPOINT +
                              Logging.code_error + str(response.status_code))


def check_response(response: requests.request) -> list:
    """Проверяет ответ API на корректность."""
    KEY = 'homeworks'
    if KEY not in response:
        Logging.logger.error(Logging.key_error, KEY)
        raise KeyError(Logging.key_error, KEY)
    if isinstance(response[KEY], list):
        return response[KEY]
    Logging.logger.error(Logging.not_homeworks + KEY)
    raise TypeError(Logging.not_homeworks + KEY)


def parse_status(homework: requests.request) -> str:
    """Извлекает из информации конкретную домашнюю работу и его статус."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in VERDICTS:
        Logging.logger.error(Logging.key_error + homework_status)
        raise KeyError(Logging.key_error + homework_status)
    verdict = VERDICTS[homework_status]
    Logging.logger.info(f'Успешно извлекли и передали: \n'
                        f' имя: "{homework_name}", \n'
                        f' статус: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    all_token = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for TOKEN in all_token:
        if TOKEN is None:
            Logging.logger.critical(Logging.not_token + str(TOKEN))
            return False
    return True


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        Logging.logger.critical(Logging.not_token)
        raise Warning(Logging.not_token)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    old_homeworks = [None]
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if old_homeworks[0] != homeworks:
                for homework in homeworks:
                    for old_homework in old_homeworks:
                        if homework != old_homework:
                            status_homework = parse_status(homework)
                            send_message(bot, status_homework)
            old_homeworks[0] = homeworks
            current_timestamp = 1
            time.sleep(RETRY_TIME)
            Logging.logger.info(Logging.loop_repeat, exc_info = True)
            Logging.logger.debug(Logging.no_status_change)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
            Logging.logger.error(Logging.connection_error + str(error),
                                 exc_info=True)
        else:
            time.sleep(RETRY_TIME)
            Logging.logger.info(Logging.loop_repeat, exc_info=True)


if __name__ == '__main__':
    main()
