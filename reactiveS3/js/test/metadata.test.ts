import { ReactiveIndex, type ReactiveFileMetadata } from '../src';

test("not exists", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    expect(index.getMetadata(FILE)).toBeNull();
});

test("exists", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });
    expect(index.getMetadata(FILE)).not.toBeNull();
});

test("exist listener create", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    let ex = [index.getMetadata(FILE)];
    index.addMetadataListener(FILE, (metadata: ReactiveFileMetadata | null) => {
        ex[0] = metadata;
    });
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });
    expect(ex[0]).toBeTruthy();
});

test("exist listener delete", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });
    let ex = [index.getMetadata(FILE)];
    index.addMetadataListener(FILE, (metadata: ReactiveFileMetadata | null) => {
        ex[0] = metadata;
    });
    index._onReceivedPubSubDelete({
        key: FILE
    });
    expect(ex[0]).toBeFalsy();
});

test("delete unregistered listener is no-op", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    const listener = (metadata: ReactiveFileMetadata | null) => {
    };
    index.removeMetadataListener(FILE, listener);
    expect(index.getNumMetadataListeners()).toEqual(0);
});

test("exist remove listener", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there";
    let ex = [index.getMetadata(FILE)];
    const listener = (metadata: ReactiveFileMetadata | null) => {
        ex[0] = metadata;
    };
    index.addMetadataListener(FILE, listener);
    index.removeMetadataListener(FILE, listener);
    // We shouldn't receive this update, since it's happening after we remove the listener
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });
    expect(ex[0]).toBeFalsy();
});