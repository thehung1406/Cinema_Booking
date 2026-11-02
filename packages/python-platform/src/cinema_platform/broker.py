"""AMQP transport. Topology/permissions are provisioned separately from services."""

import pika

from .events import EventEnvelope

PUBLIC_EXCHANGE = "cinema.events.v1"
PRIVATE_EXCHANGE = "cinema.notifications.v1"
EMAIL_QUEUE = "notification.email.v1"
DEAD_QUEUE = "notification.email.dead.v1"


def connect(url):
    params = pika.URLParameters(url)
    params.heartbeat = 30
    params.socket_timeout = 5
    params.stack_timeout = 10
    params.blocked_connection_timeout = 5
    params.connection_attempts = 1
    return pika.BlockingConnection(params)


class Publisher:
    def __init__(self, public_url: str, notification_url: str):
        self.urls = {"public": public_url, "notification": notification_url}
        self.connections = {}

    def __call__(self, destination: str, event: EventEnvelope):
        connection = self.connections.get(destination)
        if connection is None or connection.is_closed:
            connection = connect(self.urls[destination])
            self.connections[destination] = connection
        channel = connection.channel()
        try:
            channel.confirm_delivery()
            channel.basic_publish(
                exchange=PUBLIC_EXCHANGE if destination == "public" else PRIVATE_EXCHANGE,
                routing_key=(event.event_type+"."+event.producer if event.event_type in {"ReportFactChanged.v1","ReportCheckpoint.v1"} else event.event_type), body=event.model_dump_json().encode(), mandatory=True,
                properties=pika.BasicProperties(
                    content_type="application/json", delivery_mode=2,
                    message_id=str(event.event_id), type=event.event_type,
                    correlation_id=event.correlation_id,
                ),
            )
        finally:
            if channel.is_open:
                channel.close()

    def close(self):
        for connection in self.connections.values():
            if connection.is_open:
                connection.close()
