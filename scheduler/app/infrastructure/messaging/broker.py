"""Топология RabbitMQ scheduler: «пустой» брокер, только целевая очередь.

Подписчиков нет — scheduler лишь производитель. `parse.requests` объявляем
durable (как её объявляет parser-worker), чтобы команды не терялись, даже если
парсер ещё не поднялся.
"""

from faststream.rabbit import RabbitQueue


def parse_requests_queue(name: str) -> RabbitQueue:
    return RabbitQueue(name, durable=True)
