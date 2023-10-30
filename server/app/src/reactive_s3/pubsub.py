from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
from uuid import uuid4
import json
from typing import Callable, Any, Dict
import datetime
import os
import queue
from abc import ABC, abstractmethod
import traceback

received_count = 0

CERT_HOME = os.getenv("CERT_HOME", "/root/certs")

# AWS IoT supports 443 and 8883
PORT = 443
# File path to your client certificate, in PEM format
CERT = CERT_HOME+"/device.pem.crt"
# File path to your private key, in PEM format
KEY = CERT_HOME+"/private.pem.key"
# File path to root certificate authority, in PEM format.
ROOT_CA = CERT_HOME+"/Amazon-root-CA-1.pem"
# Your AWS IoT custom endpoint, not including a port.
ENDPOINT = "adup0ijwoz88i-ats.iot.us-west-2.amazonaws.com"
# Client ID for MQTT connection.
CLIENT_ID = "processing-server-" + str(uuid4())

# Callback when connection is accidentally lost.


class PubSubSocket(ABC):
    def __init__(self):
        print('Creating a PubSub object...')
        self.deployment = "DEV"
        self.alive = True
        # This is the maximum length of a topic supported by PubSub, including the deployment name.
        self.max_topic_length = 70

    def validate_topic_length(self, topic):
        if len(topic) > self.max_topic_length:
            raise ValueError(f'Topic "{topic}" is too long: ')

    # This attempts to establish a PubSub connection. Because PubSub is a "nice to have" feature, none of its
    # methods throw errors. If connecting fails, it will fail quietly and attempt to reconnect.
    @abstractmethod
    def connect(self):
        pass

    # This attempts to publish a PubSub message. Because PubSub is a "nice to have" feature, none of its methods
    # throw errors. If sending fails, it will queue the message to be sent later.
    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any] = {}):
        pass

    # This attempts to establish a PubSub connection. Because PubSub is a "nice to have" feature, none of its
    # methods throw errors. If subscribing fails, it will attempt to resubscribe later when we reconnect.
    @abstractmethod
    def subscribe(self, topic: str, callback: Callable[[str, Any], None]):
        pass


class PubSubMock(PubSubSocket):

    listeners = Dict[str, Callable[[str, Any], None]]

    def __init__(self, deployment: str):
        super().__init__()
        self.deployment = deployment
        self.message_queue = queue.Queue()
        self.mock_sent_messages_log = []
        self.connected = False
        self.listeners = {}

    def connect(self):
        self.connected = True

        for topic, payload in list(self.message_queue.queue):
            self.mock_sent_messages_log.append(topic)

        self.message_queue = queue.Queue()

    def publish(self, topic: str, payload: Dict[str, Any] = {}):
        """
        Adds a message to the queue to be sent
        """
        self.validate_topic_length(topic)
        if self.connected:
            self.mock_sent_messages_log.append(topic)
        else:
            self.message_queue.put((topic, payload))

    def subscribe(self, topic: str, callback: Callable[[str, Any], None]):
        self.validate_topic_length(topic)
        self.listeners[topic] = callback

        def unsubscribe():
            del self.listeners[topic]

        return unsubscribe

    def mock_receive_message(self, msg):
        for topic, callback in self.listeners.items():
            if topic.endswith("/#"):
                if msg['topic'].startswith(topic[:-2]) and (
                        len(msg['topic'][len(topic) - 2:]) == 0 or msg['topic'][len(topic) - 2:].startswith("/")):
                    callback(msg)
            else:
                if msg['topic'] == topic:
                    callback(msg)


class PubSub(PubSubSocket):
    """
    Here's a PubSub object
    """
    resumeListeners = []
    lock: threading.Lock

    def __init__(self, deployment: str):
        super().__init__()

        self.deployment = deployment
        self.lock = threading.Lock()

        self.connect()

        # Create a queue for messages
        self.message_queue = queue.Queue()

        # Create a worker thread for sending messages
        self.worker_thread = threading.Thread(target=self._message_sender, daemon=True)
        self.worker_thread.start()

    def connect(self):
        # Spin up resources
        eventLoopGroup = io.EventLoopGroup(1)
        hostResolver = io.DefaultHostResolver(eventLoopGroup)
        clientBootstrap = io.ClientBootstrap(eventLoopGroup, hostResolver)

        self.mqttConnection = mqtt_connection_builder.mtls_from_path(
            endpoint=ENDPOINT,
            port=PORT,
            cert_filepath=CERT,
            pri_key_filepath=KEY,
            client_bootstrap=clientBootstrap,
            ca_filepath=ROOT_CA,
            on_connection_interrupted=self._onConnectionInterrupted,
            on_connection_resumed=self._onConnectionResumed,
            client_id=CLIENT_ID,
            clean_session=False,
            keep_alive_secs=30,
            http_proxy_options=None)

        print("Connecting to {} with client ID '{}'...".format(ENDPOINT, CLIENT_ID))
        connectFuture = self.mqttConnection.connect()
        print('Waiting for connection...')
        # Future.result() waits until a result is available
        connection_result = connectFuture.result()
        if connection_result is not None and 'session_present' in connection_result and connection_result['session_present']:
            print('Connected to PubSub')
        else:
            print('Got exception trying to reconnect PubSub: ')
            print(connection_result)
            print('Will try again to reconnect PubSub in 5 seconds...')
            time.sleep(5)
            self.connect()

    def _message_sender(self):
        while True:
            topic, payload = self.message_queue.get()
            if self.mqttConnection:
                print('Acquiring PubSub_lock: SEND_A_MESSAGE')
                self.lock.acquire()
                try:
                    payloadWithTopic = payload.copy()
                    payloadWithTopic['topic'] = topic
                    payload_json = json.dumps(payloadWithTopic)
                    full_topic = '/' + self.deployment + topic
                    if len(full_topic) > 100:
                        print('Topic too long, not sending: ' + full_topic)
                        self.message_queue.task_done()
                        continue

                    # Publish the topic and payload
                    sendFuture, packetId = self.mqttConnection.publish(
                        topic=full_topic,
                        payload=payload_json,
                        qos=mqtt.QoS.AT_MOST_ONCE)  # AT_LEAST_ONCE
                    # Future.result() waits until a result is available
                    sendFuture.result(timeout=5.0)

                    # Mark the task as done in the queue
                    self.message_queue.task_done()
                    # Rate limit the sending of messages on the PubSub queue to 20 per second
                    time.sleep(0.05)
                except Exception as e:
                    print('PubSub got an error sending message to topic: ' + topic)
                    print(e)
                    traceback.print_exc()
                    print('Will try again to send a message to topic ' + topic + ' in 5 seconds...')
                    # Put the task back in the queue
                    self.message_queue.put((topic, payload))

                    time.sleep(5)
                finally:
                    print('Releasing PubSub_lock: SEND_A_MESSAGE')
                    self.lock.release()
            else:
                print('PubSub is not connected, cannot send message to topic: ' + topic+', with queue len: ' +
                      str(self.message_queue.qsize()))
                print('Will try again to send a message to topic '+topic+' in 5 seconds...')
                time.sleep(5)

    def subscribe(self, topic: str, callback: Callable[[str, Any], None]):
        """
        Subscribe to a topic
        """
        self.validate_topic_length(topic)
        print('Acquiring PubSub_lock: SUBSCRIBE_TO_TOPIC '+topic)
        traceback.print_stack()
        self.lock.acquire()
        try:
            subscribeFuture, packetId = self.mqttConnection.subscribe(
                topic=('/' + self.deployment + topic),
                qos=mqtt.QoS.AT_MOST_ONCE,  # AT_LEAST_ONCE
                callback=callback)
            # Future.result() waits until a result is available
            subscribeFuture.result()
        finally:
            print('Releasing PubSub_lock: SUBSCRIBE_TO_TOPIC '+topic)
            self.lock.release()

    def publish(self, topic: str, payload: Dict[str, Any] = {}):
        """
        Adds a message to the queue to be sent
        """
        self.validate_topic_length(topic)
        self.message_queue.put((topic, payload))

    def disconnect(self):
        print('Disconnecting PubSub...')
        print('Acquiring PubSub_lock: DISCONNECT')
        self.lock.acquire()
        try:
            """
            Disconnect the PubSub pipe
            """
            disconnect_future = self.mqttConnection.disconnect()
            # Wait for the async op to complete
            disconnect_future.result()
        finally:
            print('Releasing PubSub_lock: DISCONNECT')
            self.lock.release()

    def addResumeListener(self, listener):
        self.resumeListeners.append(listener)

    def _onConnectionInterrupted(self, connection, error, **kwargs):
        """
        The connection is interrupted
        """
        print("Connection interrupted at {}. error: {}".format(
            datetime.datetime.now().strftime("%H:%M:%S"), error))
        self.mqttConnection = None
        print('Sleeping for 5 seconds, then attempting to recreate the connection')
        time.sleep(5)
        self.connect()

    def _onConnectionResumed(self, connection, returnCode=None, sessionPresent=None, **kwargs):
        """
        The connection is resumed from an interrupt
        """
        print("Connection resumed at {}. connection: {} return_code: {} session_present: {}".format(datetime.datetime.now().strftime("%H:%M:%S"),
                                                                                                    connection, returnCode, sessionPresent))

        self.mqttConnection = connection

        if returnCode == mqtt.ConnectReturnCode.ACCEPTED and not sessionPresent:
            print("Session did not persist. Resubscribing to existing topics...")
            resubscribeFuture, _ = connection.resubscribe_existing_topics()

            # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
            # evaluate result with a callback instead.
            resubscribeFuture.add_done_callback(self._onResubscribeComplete)

        for listener in self.resumeListeners:
            listener()

    def _onResubscribeComplete(self, resubscribeFuture):
        """
        We've resubscribed to results
        """
        resubscribeResults = resubscribeFuture.result()
        print("Resubscribe results: {}".format(resubscribeResults))

        for topic, qos in resubscribeResults['topics']:
            if qos is None:
                sys.exit("Server rejected resubscribe to topic: {}".format(topic))
