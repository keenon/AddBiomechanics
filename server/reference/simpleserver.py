from awscrt import io, mqtt, auth, http
from awsiot import mqtt_connection_builder
import sys
import threading
import time
from uuid import uuid4
import json

received_count = 0
received_all_event = threading.Event()

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


def on_connection_interrupted(connection, error, **kwargs):
  print("Connection interrupted. error: {}".format(error))


# Callback when an interrupted connection is re-established.
def on_connection_resumed(connection, return_code, session_present, **kwargs):
  print("Connection resumed. return_code: {} session_present: {}".format(return_code, session_present))

  if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
    print("Session did not persist. Resubscribing to existing topics...")
    resubscribe_future, _ = connection.resubscribe_existing_topics()

    # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
    # evaluate result with a callback instead.
    resubscribe_future.add_done_callback(on_resubscribe_complete)


def on_resubscribe_complete(resubscribe_future):
  resubscribe_results = resubscribe_future.result()
  print("Resubscribe results: {}".format(resubscribe_results))

  for topic, qos in resubscribe_results['topics']:
    if qos is None:
      sys.exit("Server rejected resubscribe to topic: {}".format(topic))


# Callback when the subscribed topic receives a message
def on_message_received(topic, payload, dup, qos, retain, **kwargs):
  print("Received message from topic '{}': {}".format(topic, payload))
  global received_count
  received_count += 1

  message = "{} [{}]".format("received!", received_count)
  print("Publishing message to topic '{}': {}".format("/", message))
  message_json = json.dumps(message)
  mqtt_connection.publish(
      topic="/",
      payload=message_json,
      qos=mqtt.QoS.AT_LEAST_ONCE)

  if False:
    received_all_event.set()


if __name__ == '__main__':
  # Spin up resources
  event_loop_group = io.EventLoopGroup(1)
  host_resolver = io.DefaultHostResolver(event_loop_group)
  client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)

  mqtt_connection = mqtt_connection_builder.mtls_from_path(
      endpoint=ENDPOINT,
      port=PORT,
      cert_filepath=CERT,
      pri_key_filepath=KEY,
      client_bootstrap=client_bootstrap,
      ca_filepath=ROOT_CA,
      on_connection_interrupted=on_connection_interrupted,
      on_connection_resumed=on_connection_resumed,
      client_id=CLIENT_ID,
      clean_session=False,
      keep_alive_secs=30,
      http_proxy_options=None)

  print("Connecting to {} with client ID '{}'...".format(
      ENDPOINT, CLIENT_ID))

  connect_future = mqtt_connection.connect()

  # Future.result() waits until a result is available
  connect_future.result()
  print("Connected!")

  # Subscribe
  print("Subscribing to topic '{}'...".format("/#"))
  subscribe_future, packet_id = mqtt_connection.subscribe(
      topic="/#",
      qos=mqtt.QoS.AT_LEAST_ONCE,
      callback=on_message_received)

  subscribe_result = subscribe_future.result()
  print("Subscribed with {}".format(str(subscribe_result['qos'])))

  """
  # Publish message to server desired number of times.
  # This step is skipped if message is blank.
  # This step loops forever if count was set to 0.
  if args.message:
    if args.count == 0:
      print("Sending messages until program killed")
    else:
      print("Sending {} message(s)".format(args.count))

    publish_count = 1
    while (publish_count <= args.count) or (args.count == 0):
      message = "{} [{}]".format(args.message, publish_count)
      print("Publishing message to topic '{}': {}".format(args.topic, message))
      message_json = json.dumps(message)
      mqtt_connection.publish(
          topic=args.topic,
          payload=message_json,
          qos=mqtt.QoS.AT_LEAST_ONCE)
      time.sleep(1)
      publish_count += 1

  # Wait for all messages to be received.
  # This waits forever if count was set to 0.
  if args.count != 0 and not received_all_event.is_set():
    print("Waiting for all messages to be received...")
  """

  message_json = json.dumps({})
  mqtt_connection.publish(
      topic="/UPDATE/a/b/c/d/e",
      payload=message_json,
      qos=mqtt.QoS.AT_LEAST_ONCE)

  # This waits forever
  received_all_event.wait()
  print("{} message(s) received.".format(received_count))

  # Disconnect
  print("Disconnecting...")
  disconnect_future = mqtt_connection.disconnect()
  disconnect_future.result()
  print("Disconnected!")
