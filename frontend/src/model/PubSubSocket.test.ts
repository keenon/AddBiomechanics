import { PubSubSocket, PubSubSocketMock, PubSubMessage } from './PubSubSocket';

test('Mock constructor', () => {
    const api: PubSubSocketMock = new PubSubSocketMock("DEV");
    expect(api).toBeInstanceOf(PubSubSocket);
});

test('Send before connect', async () => {
    const api: PubSubSocketMock = new PubSubSocketMock("DEV");
    api.publish({
        topic: 'test',
        message: 'test',
    });
    expect(api.queuedMessages.length).toBe(1);
});

test('Message listeners', async () => {
    const api: PubSubSocketMock = new PubSubSocketMock("DEV");
    let counter = {count: 0};

    api.subscribe('test', (message: PubSubMessage) => {
        counter.count++;
    });
    expect(counter.count).toBe(0);

    // This should be received
    api.mockReceiveMessage({
        topic: 'test',
        message: 'test',
    });
    expect(counter.count).toBe(1);

    // This should not be received
    api.mockReceiveMessage({
        topic: 'test2',
        message: 'test',
    });
    expect(counter.count).toBe(1);
});

test('Wildcard message listeners', async () => {
    const api: PubSubSocketMock = new PubSubSocketMock("DEV");
    let counter = {count: 0};

    api.subscribe('test/#', (message: PubSubMessage) => {
        counter.count++;
    });
    expect(counter.count).toBe(0);

    // This should be received
    api.mockReceiveMessage({
        topic: 'test/hello',
        message: 'test',
    });
    expect(counter.count).toBe(1);

    // This should be received
    api.mockReceiveMessage({
        topic: 'test/goodbye',
        message: 'test',
    });
    expect(counter.count).toBe(2);

    // This should be received
    api.mockReceiveMessage({
        topic: 'test',
        message: 'test',
    });
    expect(counter.count).toBe(3);

    // This should not be received
    api.mockReceiveMessage({
        topic: 'test2',
        message: 'test',
    });
    expect(counter.count).toBe(3);

});
