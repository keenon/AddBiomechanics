import { ReactiveIndex, ReactiveCursor } from '../src';
import { autorun } from 'mobx';

test("not exists", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const cursor: ReactiveCursor = new ReactiveCursor(index, FILE);

    expect(cursor.getExists()).toBeFalsy();
});

test("exists before attach", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });
    const cursor: ReactiveCursor = new ReactiveCursor(index, FILE);

    expect(cursor.getExists()).toBeTruthy();
});

test("create after attach", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const cursor: ReactiveCursor = new ReactiveCursor(index, FILE);

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    expect(cursor.getExists()).toBeTruthy();
});

test('autorun on existence change', () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const cursor: ReactiveCursor = new ReactiveCursor(index, FILE);

    let result = [false];

    autorun(() => {
        result[0] = cursor.getExists();
    });

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    expect(result[0]).toBeTruthy();
});

test("child exists before attach", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const PATH = "/hello/there";
    const CHILDREN = ['world'];

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });
    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    expect([...cursor.children.keys()].sort()).toEqual(CHILDREN);
});

test("child created after attach", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const PATH = "/hello/there";
    const CHILDREN = ['world'];

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);
    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    expect([...cursor.children.keys()].sort()).toEqual(CHILDREN);
});

test("autorun on child create", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);
    const FILE = "/hello/there/world";
    const PATH = "/hello/there";
    const CHILDREN = ['world'];

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    let result = [false];
    autorun(() => {
        result[0] = cursor.getChildMetadata("world") != null;
    });

    index._onReceivedPubSubUpdate({
        key: FILE,
        lastModified: new Date(),
        size: 0
    });

    expect(result[0]).toBeTruthy();
});

test("compute child folder one file", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);

    const PATH = "/hello/there";
    const FOLDER = "/hello/there/world";

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    let date = new Date();
    index._onReceivedPubSubUpdate({
        key: FOLDER + '/a',
        lastModified: date,
        size: 10
    });

    let folders = cursor.getImmediateChildFolders();

    expect(folders.length).toEqual(1);
    expect(folders[0].key).toEqual('world');
    expect(folders[0].lastModified).toEqual(date);
    expect(folders[0].size).toEqual(10);
});

test("compute child folder two files", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);

    const PATH = "/hello/there";
    const FOLDER = "/hello/there/world";

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    let date = new Date();
    let date2 = new Date(date.getTime() + 60000);
    index._onReceivedPubSubUpdate({
        key: FOLDER + '/a',
        lastModified: date2,
        size: 10
    });
    index._onReceivedPubSubUpdate({
        key: FOLDER + '/b',
        lastModified: date,
        size: 10
    });

    let folders = cursor.getImmediateChildFolders();

    expect(folders.length).toEqual(1);
    expect(folders[0].key).toEqual('world');
    expect(folders[0].lastModified).toEqual(date2);
    expect(folders[0].size).toEqual(20);
});

test("compute child folder three files", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);

    const PATH = "/hello/there";
    const FOLDER1 = "/hello/there/world";
    const FOLDER2 = "/hello/there/zzz";

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    let date = new Date();
    let date2 = new Date(date.getTime() + 60000);
    index._onReceivedPubSubUpdate({
        key: FOLDER1 + '/a',
        lastModified: date2,
        size: 10
    });
    index._onReceivedPubSubUpdate({
        key: FOLDER1 + '/b',
        lastModified: date,
        size: 10
    });
    index._onReceivedPubSubUpdate({
        key: FOLDER2 + '/b',
        lastModified: date,
        size: 10
    });

    let folders = cursor.getImmediateChildFolders();

    expect(folders.length).toEqual(2);

    expect(folders[0].key).toEqual('world');
    expect(folders[0].lastModified).toEqual(date2);
    expect(folders[0].size).toEqual(20);

    expect(folders[1].key).toEqual('zzz');
    expect(folders[1].lastModified).toEqual(date);
    expect(folders[1].size).toEqual(10);
});

test("has children", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);

    const PATH = "/hello/there";
    const FILE1 = "/hello/there/a";
    const FILE2 = "/hello/there/b";

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    let result = [false];
    autorun(() => {
        result[0] = cursor.hasChildren(["a", "b"]);
    });

    expect(result[0]).toBeFalsy();

    index._onReceivedPubSubUpdate({
        key: FILE1,
        lastModified: new Date(),
        size: 10
    });
    expect(result[0]).toBeFalsy();

    index._onReceivedPubSubUpdate({
        key: FILE2,
        lastModified: new Date(),
        size: 10
    });
    expect(result[0]).toBeTruthy();
});

test("has grandchildren children", () => {
    const index: ReactiveIndex = new ReactiveIndex('test_bucket', 'public', false);

    const PATH = "/hello";
    const FILE1 = "/hello/there/a";
    const FILE2 = "/hello/there/b";

    const cursor: ReactiveCursor = new ReactiveCursor(index, PATH);

    let result = [false];
    autorun(() => {
        result[0] = cursor.childHasChildren("there", ["a", "b"]);
    });

    expect(result[0]).toBeFalsy();

    index._onReceivedPubSubUpdate({
        key: FILE1,
        lastModified: new Date(),
        size: 10
    });
    expect(result[0]).toBeFalsy();

    index._onReceivedPubSubUpdate({
        key: FILE2,
        lastModified: new Date(),
        size: 10
    });
    expect(result[0]).toBeTruthy();
});