import { ReactiveIndex, type ReactiveFileMetadata } from '../src';

test("no children", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    expect([...index.getChildren("/hello/there/world").keys()]).toEqual([]);
});

test("one child", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    let expectedChildren = ["world"];
    expect([...index.getChildren("/hello/there/").keys()]).toEqual(expectedChildren);
});

test("two children", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    index._onReceivedPubSubUpdate({
        key: "/hello/there/worldB",
        lastModified: new Date(),
        size: 0
    });
    index._onReceivedPubSubUpdate({
        key: "/hello/there/worldA",
        lastModified: new Date(),
        size: 0
    });

    let expectedChildren = ["worldA", "worldB"];
    expect([...index.getChildren("/hello/there").keys()].sort()).toEqual(expectedChildren);
});

test("child listener", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";

    let ch: Map<string, ReactiveFileMetadata>[] = [new Map()];
    index.addChildrenListener("/hello/", (children: Map<string, ReactiveFileMetadata>) => {
        ch[0] = children;
    });

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    let expectedChildren = ["there/world"]
    expect([...ch[0].keys()].sort()).toEqual(expectedChildren);
});

test("child listener on delete", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    const PATH = "/hello/";
    let ch: Map<string, ReactiveFileMetadata>[] = [new Map()];
    index.addChildrenListener(PATH, (children: Map<string, ReactiveFileMetadata>) => {
        ch[0] = children;
    });

    index._onReceivedPubSubDelete({
        key: FILE
    });

    expect([...ch[0].keys()].sort()).toEqual([]);
});

test("delete unregistered listener is no-op", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    const listener = (children: Map<string, ReactiveFileMetadata>) => {
    };
    index.removeChildrenListener(FILE, listener);
    expect(index.getNumChildrenListeners()).toEqual(0);
});

test("don't re-notify when nothing has changed", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const PATH = "/hello/";
    let ch: Map<string, ReactiveFileMetadata>[] = [index.getChildren(PATH)];
    let count = [0];
    const listener = (children: Map<string, ReactiveFileMetadata>) => {
        ch[0] = children;
        count[0]++;
    };
    index.addChildrenListener(PATH, listener);

    const file = {
        key: FILE,
        lastModified: new Date(),
        size: 0
    };
    // This should only send one update
    index._onReceivedPubSubUpdate(file);
    index._onReceivedPubSubUpdate(file);

    expect([...ch[0].keys()].sort()).toEqual(["there/world"]);
    expect(count[0]).toEqual(1);
});

test("change while listener is unregistered, then change back", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const PATH = "/hello/";
    let ch: Map<string, ReactiveFileMetadata>[] = [index.getChildren(PATH)];
    const listener = (children: Map<string, ReactiveFileMetadata>) => {
        ch[0] = children;
    };
    index.addChildrenListener(PATH, listener);

    // This should cache that the latest update we got from the listener was ["there"]
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    // Delete the file while the listener isn't present, reset the state to the true state
    index.removeChildrenListener(PATH, listener);
    index._onReceivedPubSubDelete({
        key: FILE
    });
    ch[0] = new Map();

    // Re-attach the listener, and re-create the file.
    index.addChildrenListener(PATH, listener);
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    // We should still have received the notification of the change
    expect([...ch[0].keys()].sort()).toEqual(["there/world"]);
});

test("remove child listener", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";

    let ch: Map<string, ReactiveFileMetadata>[] = [new Map()];
    let listener = (children: Map<string, ReactiveFileMetadata>) => {
        ch[0] = children;
    };
    index.addChildrenListener("/hello/", listener);
    index.removeChildrenListener("/hello/", listener);

    // We shouldn't see this update, because we removed our listener
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    expect([...ch[0].keys()].sort()).toEqual([]);
});

test("remove first child listener", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";

    let ch1: Map<string, ReactiveFileMetadata>[] = [new Map()];
    let listener1 = (children: Map<string, ReactiveFileMetadata>) => {
        ch1[0] = children;
    };
    let ch2: Map<string, ReactiveFileMetadata>[] = [new Map()];
    let listener2 = (children: Map<string, ReactiveFileMetadata>) => {
        ch2[0] = children;
    };
    index.addChildrenListener("/hello/", listener1);
    index.addChildrenListener("/hello/", listener2);
    index.removeChildrenListener("/hello/", listener1);

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    let expectedChildren = ["there/world"];
    expect([...ch1[0].keys()].sort()).toEqual([]);
    expect([...ch2[0].keys()].sort()).toEqual(expectedChildren);
});

test("remove second child listener", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";

    let ch1: Map<string, ReactiveFileMetadata>[] = [new Map()];
    let listener1 = (children: Map<string, ReactiveFileMetadata>) => {
        ch1[0] = children;
    };
    let ch2: Map<string, ReactiveFileMetadata>[] = [new Map()];
    let listener2 = (children: Map<string, ReactiveFileMetadata>) => {
        ch2[0] = children;
    };
    index.addChildrenListener("/hello/", listener1);
    index.addChildrenListener("/hello/", listener2);
    index.removeChildrenListener("/hello/", listener2);

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    let expectedChildren = ["there/world"];
    expect([...ch1[0].keys()].sort()).toEqual(expectedChildren);
    expect([...ch2[0].keys()].sort()).toEqual([]);
});