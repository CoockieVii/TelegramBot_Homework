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

RETRY_TIME = 6
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    'homework.py.log',
    maxBytes=50000000,
    backupCount=5,
    encoding='utf-8')
logger.addHandler(handler)

LOG_SEND_SUCCESSFUL = 'Успешная отправка сообщения: '
LOG_SEND_ERROR = 'Ошибка при отправке сообщения: '
LOG_CONNECTION_TRY = 'Попытка запроса к: '
LOG_CONNECTION_SUCCESSFUL = 'Успешный запрос с '
LOG_CONNECTION_ERROR = 'Ошибка при запросе: '
LOG_CODE_ERROR = '\n Код ошибки: '
LOG_KEY_ERROR = 'Не найден ключ: '
LOG_NOT_HOMEWORKS = 'В ответе сервера не нашел: '
LOG_NOT_TOKEN = 'Нет обязательной переменной для запуска программы'
LOG_LOOP_REPEAT = f'Бот делает повторный запрос, после {RETRY_TIME}с. сна'
LOG_NO_STATUS_CHANGED = (f'Статусы не изменены, '
                         f'повторная проверка через {RETRY_TIME}с.')


def send_message(bot: telegram.Bot, message: str) -> requests.request:
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(LOG_SEND_SUCCESSFUL + message)
    except ConnectionError:
        logger.error(LOG_SEND_ERROR + message)
        raise ConnectionError(LOG_SEND_ERROR + message)


def get_api_answer(current_timestamp: int) -> requests.get:
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        logger.info(LOG_CONNECTION_SUCCESSFUL + ENDPOINT)
        if response.status_code == HTTPStatus.OK:
            logger.info(LOG_CONNECTION_SUCCESSFUL + ENDPOINT)
            return response.json()
    except ConnectionError:
        logger.error(LOG_CONNECTION_ERROR + ENDPOINT)
        raise ConnectionError(LOG_CONNECTION_ERROR + ENDPOINT)
    logger.error(LOG_CONNECTION_ERROR + ENDPOINT
                 + LOG_CODE_ERROR + str(response.status_code))
    raise ConnectionError(LOG_CONNECTION_ERROR + ENDPOINT
                          + LOG_CODE_ERROR + str(response.status_code))


def check_response(response: requests.request) -> list:
    """Проверяет ответ API на корректность."""
    KEY = 'homeworks'
    if KEY not in response:
        logger.error(LOG_KEY_ERROR, KEY)
        raise KeyError(LOG_KEY_ERROR, KEY)
    if isinstance(response[KEY], list):
        return response[KEY]
    logger.error(LOG_NOT_HOMEWORKS + KEY)
    raise TypeError(LOG_NOT_HOMEWORKS + KEY)


def parse_status(homework: requests.request) -> str:
    """Извлекает из информации конкретную домашнюю работу и его статус."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in VERDICTS:
        logger.error(LOG_KEY_ERROR + homework_status)
        raise KeyError(LOG_KEY_ERROR + homework_status)
    verdict = VERDICTS[homework_status]
    logger.info(f'Успешно извлекли и передали: \n'
                f' имя: "{homework_name}", \n'
                f' статус: {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    all_token = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for TOKEN in all_token:
        if TOKEN is None:
            logger.critical(LOG_NOT_TOKEN + str(TOKEN))
            return False
    return True


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical(LOG_NOT_TOKEN)
        raise Warning(LOG_NOT_TOKEN)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_error = [None]
    last_message = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:  # Лучше ничего не смог придумать((
                if homework['homework_name'] not in last_message:
                    status_homework = parse_status(homework)
                    send_message(bot, status_homework)
                    last_message[homework['homework_name']] = status_homework

            current_timestamp = 1
            time.sleep(RETRY_TIME)
            logger.info(LOG_LOOP_REPEAT, exc_info=True)
            logger.debug(LOG_NO_STATUS_CHANGED)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_error[0] != message:
                send_message(bot, message)
                last_error[0] = message
                logger.error(LOG_CONNECTION_ERROR + str(error), exc_info=True)
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)
            logger.info(LOG_LOOP_REPEAT, exc_info=True)


if __name__ == '__main__':
    main()
