from http import HTTPStatus

import requests, logging, os, time
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

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


class Logging:
    # А тут установлены настройки логгера для текущего файла - example_for_log.py
    logger = logging.getLogger(__name__)

    # Устанавливаем уровень, с которого логи будут сохраняться в файл
    logger.setLevel(logging.INFO)

    # Указываем обработчик логов
    handler = RotatingFileHandler('homework.py.log', maxBytes=50000000, backupCount=5, encoding='utf-8')
    logger.addHandler(handler)


def send_message(bot: telegram.Bot, message: str) -> requests.request:
    """Отправляет сообщение в Telegram чат"""
    bot.send_message(
        chat_id=TELEGRAM_CHAT_ID,
        text=message)
    Logging.logger.info(f'Бот отправил сообщение "{message}"')


def get_api_answer(current_timestamp: int) -> requests.request:
    """Делает запрос к эндпоинту API-сервиса"""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if response.status_code != HTTPStatus.OK:
        Logging.logger.error(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. Код ответа API: {response.status_code}')
        raise ConnectionError(
            f'Сбой в работе программы: Эндпоинт {ENDPOINT} недоступен. Код ответа API: {response.status_code}')
    return response.json()


def check_response(response: requests.request) -> list:
    """Проверяет ответ API на корректность"""
    if isinstance(response["homeworks"], list):
        return response['homeworks']
    Logging.logger.error(f'Сбой в работе программы: От сервера не получили домашние работы')
    raise TypeError


def parse_status(homework: requests.request) -> str:
    """Извлекает из информации конкретную домашнюю работу и статус этой работы"""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    old_homework_and_status = []
    verdict = HOMEWORK_STATUSES[homework_status]
    if homework_status not in HOMEWORK_STATUSES:
        Logging.logger.error(f'недокументированный "{homework_status}" статус домашней работы')
        raise ValueError
    if homework_name in old_homework_and_status and old_homework_and_status[homework_name] == verdict:
        return f'Статус "{homework_name}" проверки не изменился. {verdict}'
    old_homework_and_status.append({f'{homework_name}': verdict})
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверяет доступность переменных окружения."""
    all_token = (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    for TOKEN in all_token:
        if TOKEN == None:
            Logging.logger.critical(f'Отсутствует обязательная переменная окружения: {TOKEN}')
            return False
    return True


def main() -> None:
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    old_homeworks = [None]
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if old_homeworks[0] != homeworks:
                old_homeworks[0] = homeworks
                for homework in homeworks:
                    status_homework = parse_status(homework)
                    send_message(bot, status_homework)
            current_timestamp = 1
            time.sleep(RETRY_TIME)
            Logging.logger.info(f'Бот делает повторный запрос на сервер, после {RETRY_TIME}с. сна', exc_info=True)
            Logging.logger.debug(f'Нет новых статусов в ответе')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)
            Logging.logger.error(f'Ошибка при запросе: {error}', exc_info=True)
        else:
            time.sleep(RETRY_TIME)
            Logging.logger.info(f'Бот делает повторный запрос на сервер, после {RETRY_TIME}с. сна', exc_info=True)


if __name__ == '__main__':
    main()
