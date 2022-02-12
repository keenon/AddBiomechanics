from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
from uuid import uuid4
import json
from typing import Callable, Any, Dict
import datetime

received_count = 0

# AWS IoT supports 443 and 8883
PORT = 443
# File path to your client certificate, in PEM format
CERT = "/root/certs/device.pem.crt"
# File path to your private key, in PEM format
KEY = "/root/certs/private.pem.key"
# File path to root certificate authority, in PEM format.
ROOT_CA = "/root/certs/Amazon-root-CA-1.pem"
# Your AWS IoT custom endpoint, not including a port.
ENDPOINT = "adup0ijwoz88i-ats.iot.us-west-2.amazonaws.com"
# Client ID for MQTT connection.
CLIENT_ID = "processing-server-" + str(uuid4())

# Callback when connection is accidentally lost.


class PubSub:
    """
    Here's a PubSub object
    """

    resumeListeners = []

    def __init__(self):
        print('creating PubSub object')
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
        # Future.result() waits until a result is available
        connectFuture.result()

    def subscribe(self, topic: str, callback: Callable[[str, Any], None]):
        """
        Subscribe to a topic
        """
        subscribeFuture, packetId = self.mqttConnection.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_MOST_ONCE,  # AT_LEAST_ONCE
            callback=callback)
        # Future.result() waits until a result is available
        subscribeFuture.result()

    def sendMessage(self, topic: str, payload: Dict[str, Any] = {}):
        """
        Sends a message to PubSub
        """
        payloadWithTopic = payload.copy()
        payloadWithTopic['topic'] = topic
        payload_json = json.dumps(payloadWithTopic)
        sendFuture, packetId = self.mqttConnection.publish(
            topic=topic,
            payload=payload_json,
            qos=mqtt.QoS.AT_LEAST_ONCE)  # AT_LEAST_ONCE
        # Future.result() waits until a result is available
        sendFuture.result()

    def disconnect(self):
        """
        Disconnect the PubSub pipe
        """
        disconnect_future = self.mqtt_connection.disconnect()
        # Wait for the async op to complete
        disconnect_future.result()

    def addResumeListener(self, listener):
        self.resumeListeners.append(listener)

    def _onConnectionInterrupted(self, connection, error, **kwargs):
        """
        The connection is interrupted
        """
        print("Connection interrupted at {}. error: {}".format(
            datetime.datetime.now().strftime("%H:%M:%S"), error))

    def _onConnectionResumed(self, connection, returnCode=None, sessionPresent=None, **kwargs):
        """
        The connection is resumed from an interrupt
        """
        print("Connection resumed at {}. connection: {} return_code: {} session_present: {}".format(datetime.datetime.now().strftime("%H:%M:%S"),
                                                                                                    connection, returnCode, sessionPresent))

        self.mqtt_connection = connection

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
