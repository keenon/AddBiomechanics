import unittest
from pubsub import PubSubMock, PubSubSocket


class TestInitialization(unittest.TestCase):
    def test_mock_constructor(self):
        api = PubSubMock("DEV")
        assert isinstance(api, PubSubSocket)

    def test_send_before_connect(self):
        api = PubSubMock("DEV")
        api.publish('test', {"message": 'test'})
        assert api.message_queue.qsize() == 1


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
        api.mock_receive_message({
            "topic": 'test',
            "message": 'test',
        })
        assert counter["count"] == 1

        # This should not be received
        api.mock_receive_message({
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
        api.mock_receive_message({
            "topic": 'test/hello',
            "message": 'test',
        })
        assert counter["count"] == 1

        # This should be received
        api.mock_receive_message({
            "topic": 'test/goodbye',
            "message": 'test',
        })
        assert counter["count"] == 2

        # This should be received
        api.mock_receive_message({
            "topic": 'test',
            "message": 'test',
        })
        assert counter["count"] == 3

        # This should not be received
        api.mock_receive_message({
            "topic": 'test2',
            "message": 'test',
        })
        assert counter["count"] == 3


if __name__ == '__main__':
    unittest.main()
