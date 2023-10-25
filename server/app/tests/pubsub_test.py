import unittest
from src.reactive_s3.pubsub import PubSubMock, PubSubSocket


class TestInitialization(unittest.TestCase):
    def test_mock_constructor(self):
        api = PubSubMock("DEV")
        self.assertTrue(isinstance(api, PubSubSocket))

    def test_send_before_connect(self):
        api = PubSubMock("DEV")
        api.publish('test', {"message": 'test'})
        self.assertEqual(api.message_queue.qsize(), 1)


class TestMessaging(unittest.TestCase):
    def test_message_listeners(self):
        api = PubSubMock("DEV")
        counter = {"count": 0}

        def message_callback(msg):
            nonlocal counter
            counter["count"] += 1

        api.subscribe('test', message_callback)
        self.assertEqual(counter["count"], 0)

        # This should be received
        api.mock_receive_message({
            "topic": 'test',
            "message": 'test',
        })
        self.assertEqual(counter["count"], 1)

        # This should not be received
        api.mock_receive_message({
            "topic": 'test2',
            "message": 'test',
        })
        self.assertEqual(counter["count"], 1)

    def test_wildcard_message_listeners(self):
        api = PubSubMock("DEV")
        counter = {"count": 0}

        def message_callback(msg):
            nonlocal counter
            counter["count"] += 1

        api.subscribe('test/#', message_callback)
        self.assertEqual(counter["count"], 0)

        # This should be received
        api.mock_receive_message({
            "topic": 'test/hello',
            "message": 'test',
        })
        self.assertEqual(counter["count"], 1)

        # This should be received
        api.mock_receive_message({
            "topic": 'test/goodbye',
            "message": 'test',
        })
        self.assertEqual(counter["count"], 2)

        # This should be received
        api.mock_receive_message({
            "topic": 'test',
            "message": 'test',
        })
        self.assertEqual(counter["count"], 3)

        # This should not be received
        api.mock_receive_message({
            "topic": 'test2',
            "message": 'test',
        })
        self.assertEqual(counter["count"], 3)


class TestPubSubStatus(unittest.TestCase):
    def test_pubsub_status(self):
        api = PubSubMock("DEV")
        api.alive = False

        def on_status_received(msg):
            api.alive = True

        api.subscribe('status', on_status_received)
        self.assertFalse(api.alive)

        # This status check should 'succeed'.
        api.mock_receive_message({
            "topic": 'status',
            "message": 'im_alive',
        })
        self.assertTrue(api.alive)

        # This status check should 'fail'.
        api.alive = False
        api.mock_receive_message({
            "topic": 'status2',
            "message": 'im_dead',
        })
        self.assertFalse(api.alive)


class TestTopicLength(unittest.TestCase):
    def test_topic_length(self):
        api = PubSubMock("DEV")
        topic_too_long = "a" * (api.max_topic_length + 5)

        def topic_callback(msg):
            pass

        self.assertRaises(ValueError, api.subscribe, topic_too_long, {})
        api.subscribe('test', topic_callback)

        api.connect()
        self.assertRaises(ValueError, api.publish, topic_too_long, {})

        api.publish('test', {})
        self.assertEqual(len(api.mock_sent_messages_log), 1)
        self.assertEqual(api.mock_sent_messages_log[0], 'test')


if __name__ == '__main__':
    unittest.main()
