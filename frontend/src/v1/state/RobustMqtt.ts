import { Signer, Credentials } from '@aws-amplify/core';
import mqtt, { MqttClient, IClientOptions } from 'mqtt';

const SERVICE_NAME = 'iotdevicegateway';

export function getSignedEndpoint(region: string, aws_pubsub_endpoint: string): Promise<string> {
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

export function mqttTopicMatch(filter: string, topic: string) {
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

export function connectAWSMqtt(region: string, aws_pubsub_endpoint: string, opts?: IClientOptions): Promise<MqttClient> {
  return getSignedEndpoint(region, aws_pubsub_endpoint).then(url => {
    return mqtt.connect(url, opts);
  });
}

type Handler = {
  pattern: string;
  handler: (topic: string, message: string) => void;
}

type QueuedMessage = {
  topic: string;
  message: string;
  resolve: () => void;
  reject: (err: string) => void;
}

class RobustMqtt {
  region: string;
  aws_pubsub_endpoint: string;
  deployment: string;
  opts?: IClientOptions;
  handlers: Handler[] = [];
  currentClient: MqttClient | null = null;
  connectionListeners: ((connected: boolean) => void)[] = [];
  queuedMessages: QueuedMessage[] = [];
  clientReconnectNumber: number = 0;

  constructor(region: string, aws_pubsub_endpoint: string, deployment: string, opts?: IClientOptions) {
    this.region = region;
    this.aws_pubsub_endpoint = aws_pubsub_endpoint;
    this.deployment = deployment;
    this.opts = opts;
  }

  /**
   * @param listener A function to call when the connection state changes
   */
  addConnectionListener = (listener: (connected: boolean) => void) => {
    this.connectionListeners.push(listener);
  }

  /**
   * @param topic The topic to publish to
   * @param message The message to send
   */
  publish = (topic: string, message: string, nestedResolve?: () => void, nestedReject?: (error: string) => void) => {
    let fullTopic = '/' + this.deployment + topic;
    console.log("Publishing { topic=\"" + fullTopic + "\", message=\"" + message + "\" }");
    return new Promise<void>((resolve, reject) => {
      if (this.currentClient != null) {
        this.currentClient.publish(fullTopic, message, (err) => {
          if (err) reject(err);
          else {
            console.log("Published message!");
            resolve();
          }
        });
      }
      else {
        console.log("MQTT disconnected, so queueing { topic=\"" + topic + "\", message=\"" + message + "\" }");
        this.queuedMessages.push({ topic, message, resolve, reject });
      }
    }).then(() => {
      if (nestedResolve) {
        nestedResolve();
      }
    }).catch((e) => {
      if (nestedReject) {
        nestedReject(e);
      }
    });
  }

  /**
   * @param pattern The pattern to subscribe to
   * @param handler The handler to attach to that pattern
   */
  subscribe = (pattern: string, handler: (topic: string, message: string) => void) => {
    pattern = '/' + this.deployment + pattern;
    this.handlers.push({ pattern, handler });

    if (this.currentClient != null) {
      console.log("Subscribing to pattern \"" + pattern + "\" after connect");
      this.currentClient.subscribe(pattern, function (err) {
        if (err) {
          console.error("Error subscribing to \"" + pattern + "\"");
        }
      });
    }

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
    return unsubscribe;
  }

  /**
   * This attempts to establish a PubSub connection.
   * 
   * First, it gets a signed URL for MQTT from AWS.
   * Next, it connects to that URL and sets up the appropriate listeners.
   */
  connect = () => {
    this.currentClient = null;
    connectAWSMqtt(this.region, this.aws_pubsub_endpoint, {
      clean: true,
      keepalive: 10,
      reconnectPeriod: 0
    }).then((client: MqttClient) => {
      this.clientReconnectNumber++;
      const clientNumber = this.clientReconnectNumber;

      client.on('connect', () => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'connect' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        this.onConnected();

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
        this.onConnectionLost();
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
        this.onConnectionLost();
      });

      client.on('disconnect', () => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'disconnect' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        console.log("MQTT disconnected");
        client.end(true);
        this.onConnectionLost();
      });

      client.on('message', (topic: string, message: Buffer) => {
        if (clientNumber !== this.clientReconnectNumber) {
          console.log("Client number " + clientNumber + " got a 'message' wakeup, but we're on client number '" + this.clientReconnectNumber + "', so ignoring.");
          return;
        }
        const messageStr: string = message.toString();
        console.log('topic: ' + topic + ', message: ' + messageStr);

        this.handlers.forEach(({ pattern, handler }) => {
          if (mqttTopicMatch(pattern, topic)) {
            handler(topic, messageStr);
          }
        })
      });
    }).catch((e) => {
      console.error("Failed to get signed MQTT URL from AWS:", e);
      this.onConnectionLost();
    });
  };

  /**
   * This resets any state we have around connection restart attempts
   */
  onConnected = () => {
    console.log("MQTT Connected!");
    this.connectionListeners.forEach((l) => l(true));

    // Retransmit any messages that we queued while we were disconnected
    let oldQueuedMessages = [...this.queuedMessages];
    this.queuedMessages = [];
    oldQueuedMessages.forEach((m) => {
      console.log("Retransmitting { topic=\"" + m.topic + "\", message=\"" + m.message + "\" }");
      this.publish(m.topic, m.message, m.resolve, m.reject);
    });
  };

  /**
   * This retries the connection, keeping track of connection failures and timeouts.
   */
  onConnectionLost = () => {
    if (this.currentClient != null) {
      this.currentClient.end();
      this.currentClient = null;
    }

    this.connectionListeners.forEach((l) => l(false));

    console.log("Connection lost! Attempting to reconnect in 2 seconds...");
    setTimeout(() => {
      console.log("Attempting to reconnect...");
      this.connect();
    }, 2000);
  };
};

export default RobustMqtt;

/*
class ClientsQueue {
  private promises: Map<string, Promise<any>> = new Map();

  async get(clientId: string, clientFactory: (string) => Promise<any>) {
    let promise = this.promises.get(clientId);
    if (promise) {
      return promise;
    }

    promise = clientFactory(clientId);

    this.promises.set(clientId, promise);

    return promise;
  }

  get allClients() {
    return Array.from(this.promises.keys());
  }

  remove(clientId) {
    this.promises.delete(clientId);
  }
}

const topicSymbol = typeof Symbol !== 'undefined' ? Symbol('topic') : '@@topic';

export class MqttOverWSProvider extends AbstractPubSubProvider {
  private _clientsQueue = new ClientsQueue();

  constructor(options: MqttProvidertOptions = {}) {
    super({ ...options, clientId: options.clientId || uuid() });
  }

  protected get clientId() {
    return this.options.clientId;
  }

  protected get endpoint() {
    return this.options.aws_pubsub_endpoint;
  }

  protected get clientsQueue() {
    return this._clientsQueue;
  }

  protected get isSSLEnabled() {
    return !this.options
      .aws_appsync_dangerously_connect_to_http_endpoint_for_testing;
  }

  protected getTopicForValue(value) {
    return typeof value === 'object' && value[topicSymbol];
  }

  getProviderName() {
    return 'MqttOverWSProvider';
  }

  public onDisconnect({ clientId, errorCode, ...args }) {
    if (errorCode !== 0) {
      logger.warn(clientId, JSON.stringify({ errorCode, ...args }, null, 2));

      const topicsToDelete = [];
      const clientIdObservers = this._clientIdObservers.get(clientId);
      if (!clientIdObservers) {
        return;
      }
      clientIdObservers.forEach(observer => {
        observer.error('Disconnected, error code: ' + errorCode);
        // removing observers for disconnected clientId
        this._topicObservers.forEach((observerForTopic, observerTopic) => {
          observerForTopic.delete(observer);
          if (observerForTopic.size === 0) {
            topicsToDelete.push(observerTopic);
          }
        });
      });

      // forgiving any trace of clientId
      this._clientIdObservers.delete(clientId);

      // Removing topics that are not listen by an observer
      topicsToDelete.forEach(topic => {
        this._topicObservers.delete(topic);
      });
    }
  }

  public async newClient({
    url,
    clientId,
  }: MqttProvidertOptions): Promise<any> {
    logger.debug('Creating new MQTT client', clientId);

    // @ts-ignore
    const client = new Paho.Client(url, clientId);
    // client.trace = (args) => logger.debug(clientId, JSON.stringify(args, null, 2));
    client.onMessageArrived = ({
      destinationName: topic,
      payloadString: msg,
    }) => {
      this._onMessage(topic, msg);
    };
    client.onConnectionLost = ({ errorCode, ...args }) => {
      this.onDisconnect({ clientId, errorCode, ...args });
    };

    await new Promise((resolve, reject) => {
      client.connect({
        useSSL: this.isSSLEnabled,
        mqttVersion: 3,
        onSuccess: () => resolve(client),
        onFailure: reject,
      });
    });

    return client;
  }

  protected async connect(
    clientId: string,
    options: MqttProvidertOptions = {}
  ): Promise<any> {
    return await this.clientsQueue.get(clientId, clientId =>
      this.newClient({ ...options, clientId })
    );
  }

  protected async disconnect(clientId: string): Promise<void> {
    const client = await this.clientsQueue.get(clientId, () => null);

    if (client && client.isConnected()) {
      client.disconnect();
    }
    this.clientsQueue.remove(clientId);
  }

  async publish(topics: string[] | string, msg: any) {
    const targetTopics = ([] as string[]).concat(topics);
    const message = JSON.stringify(msg);

    const url = await this.endpoint;

    const client = await this.connect(this.clientId, { url });

    logger.debug('Publishing to topic(s)', targetTopics.join(','), message);
    targetTopics.forEach(topic => client.send(topic, message));
  }

  protected _topicObservers: Map<
    string,
    Set<SubscriptionObserver<any>>
  > = new Map();

  protected _clientIdObservers: Map<
    string,
    Set<SubscriptionObserver<any>>
  > = new Map();

  private _onMessage(topic: string, msg: any) {
    try {
      const matchedTopicObservers = [];
      this._topicObservers.forEach((observerForTopic, observerTopic) => {
        if (mqttTopicMatch(observerTopic, topic)) {
          matchedTopicObservers.push(observerForTopic);
        }
      });
      const parsedMessage = JSON.parse(msg);

      if (typeof parsedMessage === 'object') {
        parsedMessage[topicSymbol] = topic;
      }

      matchedTopicObservers.forEach(observersForTopic => {
        observersForTopic.forEach(observer => observer.next(parsedMessage));
      });
    } catch (error) {
      logger.warn('Error handling message', error, msg);
    }
  }

  subscribe(
    topics: string[] | string,
    options: MqttProvidertOptions = {}
  ): Observable<any> {
    const targetTopics = ([] as string[]).concat(topics);
    logger.debug('Subscribing to topic(s)', targetTopics.join(','));

    return new Observable(observer => {
      targetTopics.forEach(topic => {
        // this._topicObservers is used to notify the observers according to the topic received on the message
        let observersForTopic = this._topicObservers.get(topic);

        if (!observersForTopic) {
          observersForTopic = new Set();

          this._topicObservers.set(topic, observersForTopic);
        }

        observersForTopic.add(observer);
      });

      // @ts-ignore
      let client: Paho.Client;
      const { clientId = this.clientId } = options;

      // this._clientIdObservers is used to close observers when client gets disconnected
      let observersForClientId = this._clientIdObservers.get(clientId);
      if (!observersForClientId) {
        observersForClientId = new Set();
      }
      observersForClientId.add(observer);
      this._clientIdObservers.set(clientId, observersForClientId);

      (async () => {
        const { url = await this.endpoint } = options;

        try {
          client = await this.connect(clientId, { url });
          targetTopics.forEach(topic => {
            client.subscribe(topic);
          });
        } catch (e) {
          observer.error(e);
        }
      })();

      return () => {
        logger.debug('Unsubscribing from topic(s)', targetTopics.join(','));

        if (client) {
          this._clientIdObservers.get(clientId).delete(observer);
          // No more observers per client => client not needed anymore
          if (this._clientIdObservers.get(clientId).size === 0) {
            this.disconnect(clientId);
            this._clientIdObservers.delete(clientId);
          }

          targetTopics.forEach(topic => {
            const observersForTopic =
              this._topicObservers.get(topic) ||
              (new Set() as Set<SubscriptionObserver<any>>);

            observersForTopic.delete(observer);

            // if no observers exists for the topic, topic should be removed
            if (observersForTopic.size === 0) {
              this._topicObservers.delete(topic);
              if (client.isConnected()) {
                client.unsubscribe(topic);
              }
            }
          });
        }

        return null;
      };
    });
  }
}
*/