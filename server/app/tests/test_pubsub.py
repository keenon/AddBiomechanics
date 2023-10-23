import unittest
import os
import sys

from pubsub import PubSubMock, PubSubSocket


class TestInitialization(unittest.TestCase):
    def test_mock_constructor(self):
        api = PubSubMock("DEV")
        assert isinstance(api, PubSubSocket)

    def test_send_before_connect(self):
        api = PubSubMock("DEV")
        api.publish('test', {"message": 'test'})
        assert len(api.message_queue) == 1


class TestMessaging(unittest.TestCase):
    def test_message_listeners(self):
        api = PubSubMock("DEV")
        counter = {"count": 0}

        def message_callback(message):
            nonlocal counter
            counter["count"] += 1

        api.subscribe('test', message_callback)
        assert counter["count"] == 0

        # This should be received
        api.mockReceiveMessage({
            "topic": 'test',
            "message": 'test',
        })
        assert counter["count"] == 1

        # This should not be received
        api.mockReceiveMessage({
            "topic": 'test2',
            "message": 'test',
        })
        assert counter["count"] == 1

    def test_wildcard_message_listeners(self):
        api = PubSubMock("DEV")
        counter = {"count": 0}

        def message_callback(message):
            nonlocal counter
            counter["count"] += 1

        api.subscribe('test/#', message_callback)
        assert counter["count"] == 0

        # This should be received
        api.mockReceiveMessage({
            "topic": 'test/hello',
            "message": 'test',
        })
        assert counter["count"] == 1

        # This should be received
        api.mockReceiveMessage({
            "topic": 'test/goodbye',
            "message": 'test',
        })
        assert counter["count"] == 2

        # This should be received
        api.mockReceiveMessage({
            "topic": 'test',
            "message": 'test',
        })
        assert counter["count"] == 3

        # This should not be received
        api.mockReceiveMessage({
            "topic": 'test2',
            "message": 'test',
        })
        assert counter["count"] == 3


if __name__ == '__main__':
    unittest.main()
