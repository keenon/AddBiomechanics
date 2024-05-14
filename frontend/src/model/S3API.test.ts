import { S3APIMock, S3API } from "./S3API"; 

test('Mock constructor', () => {
    const api: S3APIMock = new S3APIMock();
    expect(api).toBeInstanceOf(S3API);
});

test('List files success', async () => {
    const api: S3APIMock = new S3APIMock();
    api.setFiles([{
        key: 'test',
        lastModified: new Date(),
        size: 0,
    }]);
    const {files, folders} = await api.loadPathData('', true);

    expect(files.length).toBe(1);
});

test('List files cancel', async () => {
    const api: S3APIMock = new S3APIMock();
    api.mockLoadBeforeHalt = 0;
    api.setFiles([{
        key: 'test',
        lastModified: new Date(),
        size: 0,
    }]);
    const abortController = new AbortController();
    const promise = api.loadPathData('', true, abortController);
    let caught = [false];
    promise.catch(() => {
        console.log("Caught error in loadPathData Promise");
        caught[0] = true;
    });
    abortController.abort();
    try {
        await promise;
    }
    catch (e) {
        console.log("Caught error in await");
    }
    expect(caught[0]).toBe(true);
});

test('List files prefix recursively', async () => {
    const api: S3APIMock = new S3APIMock();
    api.setFiles([{
        key: 'test/test2/test3',
        lastModified: new Date(),
        size: 0,
    }, {
        key: 'test/test2/test4',
        lastModified: new Date(),
        size: 0,
    }, {
        key: 'test/test2/test5',
        lastModified: new Date(),
        size: 0,
    }]);
    const {files, folders} = await api.loadPathData('test/te', true);
    expect(files.length).toBe(3);
});

test('List files with real paths', async () => {
    const api: S3APIMock = new S3APIMock();
    api.setFilePathsExist([
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/1",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/1",
    ]);
    const { files: filesNoSlash, folders: foldersNoSlash } = await api.loadPathData('protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023', false);
    expect(filesNoSlash.length).toBe(1);
    expect(foldersNoSlash.length).toBe(1);

    const { files: filesWithSlash, folders: foldersWithSlash } = await api.loadPathData('protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/', false);
    expect(filesWithSlash.length).toBe(2);
    expect(foldersWithSlash.length).toBe(2);
});

test('List files prefix non-recursively', async () => {
    const api: S3APIMock = new S3APIMock();
    api.setFiles([{
        key: 'test/test2/test3',
        lastModified: new Date(),
        size: 0,
    }, {
        key: 'test/test2/test4',
        lastModified: new Date(),
        size: 0,
    }, {
        key: 'test/test2/test5',
        lastModified: new Date(),
        size: 0,
    }]);

    const {files: filesNoSlash, folders: foldersNoSlash} = await api.loadPathData('test', false);
    expect(filesNoSlash.length).toBe(0);
    expect(foldersNoSlash.length).toBe(1);
    expect(foldersNoSlash[0]).toBe('test/');

    const {files: filesWithSlash, folders: foldersWithSlash} = await api.loadPathData('test/', false);
    expect(filesWithSlash.length).toBe(0);
    expect(foldersWithSlash.length).toBe(1);
    expect(foldersWithSlash[0]).toBe('test/test2/');

    const {files: filesFullPath, folders: foldersFullPath} = await api.loadPathData('test/test2/', false);
    expect(filesFullPath.length).toBe(3);
    expect(foldersFullPath.length).toBe(0);
});
