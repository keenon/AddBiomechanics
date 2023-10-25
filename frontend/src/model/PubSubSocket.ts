import { Signer, Credentials } from '@aws-amplify/core';
import mqtt, { MqttClient, IClientOptions } from 'mqtt';

const SERVICE_NAME = 'iotdevicegateway';

type PubSubMessage = {
    topic: string;
    message: string;
};

abstract class PubSubSocket {
    deployment: "PROD" | "DEV" = "DEV";

    /**
     * This attempts to establish a PubSub connection. Because PubSub is a "nice to have" feature, none of its methods throw errors.
     * If connecting fails, it will fail quietly and attempt to reconnect.
     */
    abstract connect(): void;
    /**
     * This attempts to publish a PubSub message. Because PubSub is a "nice to have" feature, none of its methods throw errors.
     * If sending fails, it will queue the message to be sent later.
     */
    abstract publish(msg: PubSubMessage): Promise<void>;
    /**
     * This attempts to establish a PubSub connection. Because PubSub is a "nice to have" feature, none of its methods throw errors.
     * If subscribing fails, it will attempt to resubscribe later when we reconnect.
     */
    abstract subscribe(topic: string, callback: (msg: PubSubMessage) => void): () => void;
    /**
     * This strips any illegal characters from a PubSub path (or subset of a path), and returns what's left
     * 
     * @param path The raw input path we'd like to make safe for PubSub
     * @returns a legal PubSub path (or subset of a legal path)
     */
    makeTopicPubSubSafe(topic: string): string {
        let path = '/' + this.deployment + topic;

        const MAX_TOPIC_LEN = 80;
        if (path.length > MAX_TOPIC_LEN) {
            let segments = path.split("/");
            if (segments[0].length > MAX_TOPIC_LEN) {
                return segments[0].substring(0, MAX_TOPIC_LEN);
            }
            let reconstructed = '';
            let segmentCursor = 0;
            while (segmentCursor < segments.length) {
                let proposedNext = reconstructed;
                if (segmentCursor > 0) {
                    proposedNext += '/';
                }
                proposedNext += segments[segmentCursor];
                segmentCursor++;

                if (proposedNext.length < MAX_TOPIC_LEN) {
                    reconstructed = proposedNext;
                }
                else {
                    break;
                }

                if (segmentCursor > 7) {
                    break;
                }
            }
            return reconstructed;
        }
        return path;
    }
}

class PubSubSocketMock extends PubSubSocket {
    mockSentMessagesLog: PubSubMessage[] = [];
    queuedMessages: PubSubMessage[] = [];
    connected: boolean = false;
    listeners: Map<string, (msg: PubSubMessage) => void>;

    constructor(deployment: "DEV" | "PROD") {
        super();
        this.deployment = deployment;
        this.listeners = new Map();

        this.setConnected = this.setConnected.bind(this);
        this.connect = this.connect.bind(this);
        this.publish = this.publish.bind(this);
        this.subscribe = this.subscribe.bind(this);
    }

    setConnected(connected: boolean) {
        this.connected = connected;
    }

    connect(): void {
        this.connected = true;
        // Send all queued messages
        this.queuedMessages.forEach((msg) => {
            this.mockSentMessagesLog.push(msg);
        });
        this.queuedMessages = [];
    }

    publish(msg: PubSubMessage): Promise<void> {
        if (!this.connected) {
            this.queuedMessages.push(msg);
        }
        else {
            this.mockSentMessagesLog.push(msg);
        }
        return Promise.resolve();
    }

    mockReceiveMessage(msg: PubSubMessage) {
        this.listeners.forEach((callback, topic) => {
          if (topic.endsWith("/#")) {
            if (msg.topic.startsWith(topic.substring(0, topic.length - 2)) && (msg.topic.substring(topic.length - 2).length == 0 || msg.topic.substring(topic.length - 2).startsWith("/"))) {
                callback(msg);
            }
          }
          else {
            if (msg.topic === topic) {
                callback(msg);
            }
          }
        });
    }

    subscribe(topic: string, callback: (msg: PubSubMessage) => void): () => void
    {
        this.listeners.set(topic, callback);
        let unsubscribe = () => {
            this.listeners.delete(topic);
        };

        return unsubscribe;
    }
}

type Handler = {
  pattern: string;
  handler: (msg: PubSubMessage) => void;
}

type QueuedMessage = {
  msg: PubSubMessage;
  resolve: () => void;
  reject: (err: string) => void;
}

class PubSubSocketImpl extends PubSubSocket {
  region: string;
  aws_pubsub_endpoint: string;
  opts?: IClientOptions;
  handlers: Handler[] = [];
  currentClient: MqttClient | null = null;
  queuedMessages: QueuedMessage[] = [];
  clientReconnectNumber: number = 0;

  constructor(region: string, aws_pubsub_endpoint: string, deployment: "DEV" | "PROD", opts?: IClientOptions) {
    super();
    this.region = region;
    this.aws_pubsub_endpoint = aws_pubsub_endpoint;
    this.deployment = deployment;
    this.opts = opts;

    this.connect = this.connect.bind(this);
    this.publish = this.publish.bind(this);
    this.subscribe = this.subscribe.bind(this);
    this._onConnected = this._onConnected.bind(this);
    this._onConnectionLost = this._onConnectionLost.bind(this);
    this._mqttTopicMatch = this._mqttTopicMatch.bind(this);
    this._getSignedEndpoint = this._getSignedEndpoint.bind(this);
  }

  /**
   * @param topic The topic to publish to
   * @param message The message to send
   */
  publish(msg: PubSubMessage): Promise<void> {
    let fullTopic = msg.topic;
    console.log("Publishing { topic=\"" + fullTopic + "\", message=\"" + msg.message + "\" }");
    return new Promise<void>((resolve, reject) => {
      if (this.currentClient != null) {
        this.currentClient.publish(fullTopic, msg.message, (err) => {
          if (err) {
            console.log("MQTT error, so queueing { topic=\"" + msg.topic + "\", message=\"" + msg.message + "\" }");
            console.log(err);
            this.queuedMessages.push({ msg, resolve, reject });
            resolve();
          }
          else {
            console.log("Published message!");
            resolve();
          }
        });
      }
      else {
        console.log("MQTT disconnected, so queueing { topic=\"" + msg.topic + "\", message=\"" + msg.message + "\" }");
        this.queuedMessages.push({ msg, resolve, reject });
      }
    });
  }

  /**
   * @param pattern The pattern to subscribe to
   * @param handler The handler to attach to that pattern
   */
  subscribe(pattern: string, handler: (msg: PubSubMessage) => void): () => void {
    this.handlers.push({ pattern, handler });
    let unsubscribe = () => {
        this.handlers = this.handlers.filter((h) => {
            return h.pattern !== pattern || h.handler !== handler
        });

        let stillHasPattern = this.handlers.find((h) => {
            return h.pattern === pattern;
        }) != null;

        if (!stillHasPattern && this.currentClient != null) {
            this.currentClient.unsubscribe(pattern);
        }
    };
    if (this.currentClient != null) {
        console.log("Subscribing to pattern \"" + pattern + "\" after connect");
        this.currentClient.subscribe(pattern, (err) => {
            if (err) {
                console.error("Error subscribing to \"" + pattern + "\"");
            }
        });
    }
    else {
        console.log("MQTT disconnected, so queueing subscription to \"" + pattern + "\"");
    }

    return unsubscribe;
  }

  /**
   * This attempts to establish a PubSub connection.
   * 
   * First, it gets a signed URL for MQTT from AWS.
   * Next, it connects to that URL and sets up the appropriate listeners.
   */
  connect(): void {
    this.currentClient = null;

    this._getSignedEndpoint(this.region, this.aws_pubsub_endpoint).then(url => {
        return mqtt.connect(url, {
            clean: true,
            keepalive: 10,
            reconnectPeriod: 0
        });
    }).then((client: MqttClient) => {
      this.clientReconnectNumber++;
      const clientNumber = this.clientReconnectNumber;

      client.on('connect', () => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'connect' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        this._onConnected();

        this.currentClient = client;
        this.handlers.forEach(({ pattern }) => {
          if (this.currentClient != null) {
            console.log("Subscribing to pattern \"" + pattern + "\" on connect");
            this.currentClient.subscribe(pattern, function (err) {
              if (err) {
                console.error("Error subscribing to \"" + pattern + "\"");
              }
            });
          }
        });
      });

      client.on('error', () => {
        console.log("MQTT Error!");
      });

      client.on('offline', () => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'offline' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        console.log("MQTT Offline!");
        client.end(true);
        this._onConnectionLost();
      });

      client.on('reconnect', () => {
        console.log("MQTT Reconnecting");
      });

      client.on('close', () => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'close' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        console.log("MQTT closed");
        client.end(true);
        this._onConnectionLost();
      });

      client.on('disconnect', () => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'disconnect' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        console.log("MQTT disconnected");
        client.end(true);
        this._onConnectionLost();
      });

      client.on('message', (topic: string, message: Buffer) => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'message' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        const messageStr: string = message.toString();
        console.log('topic: ' + topic + ', message: ' + messageStr);

        this.handlers.forEach(({ pattern, handler }) => {
          if (this._mqttTopicMatch(pattern, topic)) {
            handler({ topic, message: messageStr });
          }
        })
      });
    }).catch((e) => {
      console.error("Failed to get signed MQTT URL from AWS:", e);
      this._onConnectionLost();
    });
  };

  /**
   * This resets any state we have around connection restart attempts
   */
  _onConnected() {
    console.log("MQTT Connected!");

    // Retransmit any messages that we queued while we were disconnected
    let oldQueuedMessages = [...this.queuedMessages];
    this.queuedMessages = [];
    oldQueuedMessages.forEach((m) => {
      console.log("Retransmitting { topic=\"" + m.msg.topic + "\", message=\"" + m.msg.message + "\" }");
      this.publish(m.msg).then(() => {
        m.resolve();
      }).catch((err) => {
        m.reject(err);
      });
    });
  };

    /**
     * This retries the connection, keeping track of connection failures and timeouts.
     */
    _onConnectionLost() {
        if (this.currentClient != null) {
            this.currentClient.end();
            this.currentClient = null;
        }

        console.log("Connection lost! Attempting to reconnect in 2 seconds...");
        setTimeout(() => {
            console.log("Attempting to reconnect...");
            this.connect();
        }, 2000);
    };

    _mqttTopicMatch(filter: string, topic: string) {
        const filterArray = filter.split('/');
        const length = filterArray.length;
        const topicArray = topic.split('/');

        for (let i = 0; i < length; ++i) {
            const left = filterArray[i];
            const right = topicArray[i];
            if (left === '#') return topicArray.length >= length;
            if (left !== '+' && left !== right) return false;
        }
        return length === topicArray.length;
    }

    _getSignedEndpoint(region: string, aws_pubsub_endpoint: string): Promise<string> {
        return (async () => {
            const endpoint = aws_pubsub_endpoint;

            const serviceInfo = {
            service: SERVICE_NAME,
            region: region,
            };
            const {
            accessKeyId: access_key,
            secretAccessKey: secret_key,
            sessionToken: session_token,
            } = await Credentials.get();

            const result = Signer.signUrl(
            endpoint,
            { access_key, secret_key, session_token },
            serviceInfo
            );

            return result;
        })();
    }

};


export type {PubSubMessage}
export {PubSubSocket, PubSubSocketMock, PubSubSocketImpl}