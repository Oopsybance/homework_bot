class StatusCodeError(Exception):
    """API домшней работы возвращает кот, отличный от 200."""

    pass


class RequestError(Exception):
    """Обрабатываются ошибки при запросе к эндпоинту API домашкей работы."""

    pass
