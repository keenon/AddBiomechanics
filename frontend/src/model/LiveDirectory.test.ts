import { FaultIn, LiveDirectory, LiveDirectoryImpl, PathData } from "./LiveDirectory";
import { S3APIMock } from "./S3API";
import { PubSubSocketMock } from "./PubSubSocket";
import { autorun, spy, trace, observable, action } from "mobx";

describe("LiveDirectory", () => {
    test("Constructor", () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("test", s3, pubsub);

        expect(api).toBeInstanceOf(LiveDirectory);
    });

    test("Loading a path respects the prefix", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);

        const path = api.getPath("dataset2/", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.files.map(f => f.key)).toContain("dataset2/");
    });

    test("Loading a folder works with the slash", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);

        const path = api.getPath("dataset1/", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders).toContain("dataset1/subject1/");
    });

    test("Loading a folder works without the slash", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);

        const path = api.getPath("dataset1", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders).toContain("dataset1/subject1/");
    });

    test("Loading with real paths", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        const path = api.getPath("ASB2023", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders).toContain("ASB2023/S01/");
    });

    test("Loading recursively with real paths", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        const path = api.getPath("ASB2023", true);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders.length).toBe(2);
        expect(result.files.length).toBe(3);
        expect(result.files.map(f => f.key)).toContain("ASB2023/S01");
        expect(result.files.map(f => f.key)).toContain("ASB2023/TestProsthetic");

        const childPath = api.getPath("ASB2023/S01", true);
        expect(childPath.loading).toBe(false);
        expect(childPath.path).toBe("ASB2023/S01/");
        expect(childPath.folders.length).toBe(1);
        expect(childPath.files.length).toBe(2);
        expect(childPath.files.map(f => f.key)).toContain("ASB2023/S01/_subject.json");
    });

    test("Loading the folder, then loading recursively", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        const path = api.getPath("ASB2023", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.files.length).toBe(2);
        expect(result.folders.length).toBe(2);

        const path2 = api.getPath("ASB2023", true);
        // When we return from this call, we should still not have marked loading, and also not be recursive, 
        // but we should have a promise that is non-null. This behavior works this way because then the `loading` flag
        // can be safely interpreted by the rendering code as meaning that the data has not arrived yet. It allows
        // us to do a loading pattern where we rapidly load the folder, then load the contents recursively which may take
        // some more time.
        expect(path2.loading).toBe(false);
        expect(path2.recursive).toBe(false);
        expect(path2.promise).toBeDefined();
        const result2: PathData | null = await path2.promise;
        if (result2 == null) {
            fail("Promise returned null");
            return;
        }
        expect(result2.files.length).toBe(3);
        expect(result2.folders.length).toBe(2);
        expect(result2.files.map(f => f.key)).toContain("ASB2023/S01");
    });

    test("Faulting in the root folder does the correct sequence of loads", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        await api.faultInPath("ASB2023").promise;
        // We want to separately load the child folders, to give a nice user experience of folders coming in rapidly when they load the page
        // Each subject gets a non-recursive load, and then a recursive load if it is a subject
        expect(s3.networkCallCount).toBe(8);

        // Redundant calls should do nothing
        await api.faultInPath("ASB2023").promise;
        expect(s3.networkCallCount).toBe(8);

        // We want the root node to be recursive, after the progressive faulting in of all its children, so that subsequent 
        // file creations get registered correctly.
        const cachedRootNode = api.getPath("ASB2023", false);
        expect(cachedRootNode.recursive).toBe(true);

        // We want to ensure we get exactly the same thing as if we had loaded recursively from the start
        const api2 = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        let cachedRootNode2 = api2.getPath("ASB2023", true);
        if (cachedRootNode2.promise != null) {
            cachedRootNode2 = await cachedRootNode2.promise;
        }
        expect(cachedRootNode.folders).toStrictEqual(cachedRootNode2.folders);
        // TODO: I'm not sure why the recursive load on the mocks returns the ASB2023 object as a file, but the fault-in load doesn't
        expect(new Set(cachedRootNode.files.map(f => f.key))).toStrictEqual(new Set(cachedRootNode2.files.map(f => f.key).filter(k => k != "ASB2023")));
    });

    test("Fault in and then cancel before it finishes", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist([
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
        s3.mockLoadBeforeHalt = 1;
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const abortController: AbortController = new AbortController();

        const faultIn: FaultIn = dir.faultInPath("", abortController);
        const errorThrown = [false];
        faultIn.promise.catch(() => {
            console.log("Caught error in faultInPath Promise");
            errorThrown[0] = true;
        });

        await faultIn.firstLoadPromise;

        let rootNode = dir.getPath("", false);
        const promise = rootNode.promise;
        if (promise != null) {
            rootNode = await promise;
        }
        expect(rootNode.recursive).toBe(false);
        expect(rootNode.loading).toBe(false);
        expect(rootNode.folders).toStrictEqual(["ASB2023/"]);

        // No timing guarantees for this test

        // const childNode = dir.getCachedPath("ASB2023/");
        // expect(childNode).toBeDefined();
        // expect(childNode?.loading).toBe(true);

        abortController.abort();

        try {
            await faultIn.promise;
        }
        catch (e) {
            console.log("Caught error in await");
        }

        expect(errorThrown[0]).toBe(true);
        const updatedChildNode = dir.getCachedPath("ASB2023/");
        expect(updatedChildNode).toBeUndefined();
    });

    test("Loading recursively prevents nested loads from hitting the network, with real paths", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        const path = api.getPath("ASB2023", true);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(s3.networkCallCount).toBe(1);
        expect(result.folders.length).toBe(2);
        expect(result.files.length).toBe(3);
        expect(result.files.map(f => f.key)).toContain("ASB2023/S01");

        const childPath = api.getPath("ASB2023/S01/", false);
        expect(s3.networkCallCount).toBe(1);
        expect(childPath.loading).toBe(false);
        expect(childPath.files.length).toBe(2);
        expect(childPath.files.map(f => f.key)).toContain('ASB2023/S01/_subject.json');
        expect(childPath.files.map(f => f.key)).toContain('ASB2023/S01/trials');
        expect(childPath.folders.length).toBe(1);
        expect(childPath.folders).toContain('ASB2023/S01/trials/');
    });

    test("observable does what it's supposed to with a simple object", async () => {
        const obs = observable({ count: 0 })
        const counter = { count: 0 }
        // Sets up the autorun and prints 0.
        const disposer = autorun(() => {
            obs.count;
            counter.count++
        })
        expect(counter.count).toBe(1);

        // Increments the counter
        action(() => {
            obs.count++
        })();
        expect(counter.count).toBe(2);

        // Stops the autorun.
        disposer()

        // Will not increment
        action(() => {
            obs.count++
        })();
        expect(counter.count).toBe(2);
    });

    test("The LiveDirectoryImpl's map is observable", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const counter = { count: 0 }
        // Sets up the autorun and prints 0.
        const disposer = autorun(() => {
            api.pathCache.get("test");
            counter.count++
        })
        expect(counter.count).toBe(1);

        // Increments the counter
        action(() => {
            api.pathCache.set("test", 1 as any);
        })();
        expect(counter.count).toBe(2);

        // Stops the autorun.
        disposer()

        // Will not increment
        action(() => {
            api.pathCache.set("test2", 1 as any);
        })();
        expect(counter.count).toBe(2);
    });

    test("Autorun should pick up changes on the path", async () => {
        const counter: {count: number} = {count: 0};

        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        const disposer = autorun(() => {
            api.getCachedPath("ASB2023/");
            // Count how many times this autorun has been called
            counter.count++;
        });
        expect(counter.count).toBe(1);

        const path = api.getPath("ASB2023/", false);
        await path.promise;
        // Once for loading: true, again for loading: false
        expect(counter.count).toBe(3);

        disposer();
    });

    test("Autorun should pick up changes to child paths if we load recursively above them", async () => {
        const counter: {count: number} = {count: 0};

        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
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

        const disposer = autorun(() => {
            api.getCachedPath("ASB2023/S01/trials");
            // Count how many times this autorun has been called
            counter.count++;
        });
        expect(counter.count).toBe(1);

        const path = api.getPath("ASB2023/", true);
        await path.promise;
        // Changes once for loading: true, again for loading: false
        expect(counter.count).toBe(3);

        disposer();
    });

    test("Change listeners should run as we load data", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/1",
        ]);

        const counter: {count: number} = {count: 0};
        api.addPathChangeListener("ASB2023/", (data: PathData) => {
            counter.count++;
        });
        expect(counter.count).toBe(0);

        await api.getPath("ASB2023/", false).promise;

        // Changes once for loading=true, again for fully loaded
        expect(counter.count).toBe(2);
    });

    test("Uploading data sends PubSub messages", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        await api.uploadText("READY_TO_PROCESS", "");
        expect(pubsub.mockSentMessagesLog.length).toBe(1);
        expect(pubsub.mockSentMessagesLog[0].topic).toBe("/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data");
    });

    test("Receiving PubSub message with nothing loaded is a no-op", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        expect(api.pathCache.size).toBe(0);
        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });
        expect(api.pathCache.size).toBe(0);
    });

    test("Receiving PubSub message with a file loaded causes an update", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        expect(api.pathCache.size).toBe(0);
        // We expect the LiveDirectory to have registered 2 PubSub listeners when it was created, one for deletes, and one for updates
        expect(pubsub.listeners.size).toBe(2);

        const data = await api.getPath("ASB2023/S01/", false);
        expect(api.pathCache.size).toBe(1);
        expect(data.files.length).toBe(0);
        expect(data.folders.length).toBe(0);

        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });

        expect(api.pathCache.size).toBe(1);
        const updatedData = api.getCachedPath("ASB2023/S01/");
        if (updatedData) {
            expect(updatedData.files.length).toBe(1);
        }
        else {
            // This will always fail
            expect(updatedData).toBeDefined();
        }
    });

    test("Receiving PubSub message with a file loaded causes a delete", async () => {
        const s3 = new S3APIMock();
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json"
        ]);
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        expect(api.pathCache.size).toBe(0);
        // We expect the LiveDirectory to have registered 2 PubSub listeners when it was created, one for deletes, and one for updates
        expect(pubsub.listeners.size).toBe(2);

        const data: PathData = await (await api.getPath("ASB2023/S01/", false)).promise as any;
        expect(api.pathCache.size).toBe(1);
        expect(data.files.length).toBe(1);
        expect(data.folders.length).toBe(0);

        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });

        expect(api.pathCache.size).toBe(1);
        const updatedData = api.getCachedPath("ASB2023/S01/");
        if (updatedData) {
            expect(updatedData.files.length).toBe(0);
        }
        else {
            // This will always fail
            expect(updatedData).toBeDefined();
        }
    });

    test("Receiving a PubSub update that updates something nested within a recursive load causes a file to be created", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/1",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/1",
        ]);

        const path = api.getPath("ASB2023", true);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders.length).toBe(2);
        expect(result.files.length).toBe(3);

        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });

        const newPath = api.getPath("ASB2023", true);
        expect(newPath.loading).toBe(false);
        expect(newPath.files.length).toBe(3);
        expect(newPath.files.map(f => f.key)).toContain("ASB2023/S01");
    });

    test("Receiving a PubSub update that is in a new folder path causes new folders to be created in a subfolder", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/1",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/1",
        ]);

        const path = api.getPath("ASB2023", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders.length).toBe(2);
        expect(result.files.length).toBe(2);

        let counter: {count: number} = {count: 0};
        const disposer = autorun(() => {
            // Count how many times this autorun has been called
            counter.count++;
            const data = api.getCachedPath("ASB2023");
            expect(data).toBeDefined();
        });
        expect(counter.count).toBe(1);

        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/NewSubject/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });

        expect(counter.count).toBe(2);

        const newPath = api.getPath("ASB2023", false);
        expect(newPath.loading).toBe(false);
        expect(newPath.folders.length).toBe(3);
        expect(newPath.files.length).toBe(2);
        expect(newPath.folders).toContain("ASB2023/NewSubject/");

        disposer();
    });

    test("Receiving a PubSub update that is in a new folder path causes new folders to be created in root", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/1",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/1",
        ]);

        const path = api.getPath("", false);
        expect(path.loading).toBe(true);
        expect(path.promise).toBeDefined();
        const result: PathData | null = await path.promise;
        if (result == null) {
            fail("Promise returned null");
            return;
        }
        expect(result.folders.length).toBe(1);
        expect(result.files.length).toBe(1);

        let counter: {count: number} = {count: 0};
        const disposer = autorun(() => {
            // Count how many times this autorun has been called
            counter.count++;
            const data = api.getCachedPath("");
            expect(data).toBeDefined();
        });
        expect(counter.count).toBe(1);

        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/NewSubject/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });

        expect(counter.count).toBe(2);

        const newPath = api.getPath("", false);
        expect(newPath.loading).toBe(false);
        expect(newPath.folders.length).toBe(2);
        expect(newPath.files.length).toBe(1);
        expect(newPath.folders).toContain("NewSubject/");

        disposer();
    });

    test("Receiving a PubSub delete that is the only child of a recursively loaded folder should delete a folder", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/NewSubject/_dataset.json",
        ]);

        const path = api.getPath("ASB2023", true);
        await path.promise;

        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/NewSubject/_dataset.json",
                size: 0,
                dateModified: new Date().toString(),
            })
        });

        const newPath = api.getPath("ASB2023", false);
        expect(newPath.loading).toBe(false);
        expect(newPath.recursive).toBe(true);
        expect(newPath.folders.length).toBe(0);
        expect(newPath.files.length).toBe(1);
    });

    test("Delete by prefix works as expected with a recursive root parent", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1",
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset1/subject2",
            "protected/us-west-2:test/data/dataset1/subject2/_subject.json",
            "protected/us-west-2:test/data/dataset1/subject2/trials/1/markers.c3d",
            "protected/us-west-2:test/data/dataset1/subject3/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);
        const root = api.getPath("", true);
        await root.promise;

        await api.deleteByPrefix("dataset1/");
        expect(s3.files.length).toBe(3);

        const rootAfterDelete = api.getPath("", true);
        expect(rootAfterDelete.loading).toBe(false);
        expect(rootAfterDelete.folders.length).toBe(2);
    });

    test("Delete by prefix works as expected with a non-recursive root parent", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1",
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset1/subject2",
            "protected/us-west-2:test/data/dataset1/subject2/_subject.json",
            "protected/us-west-2:test/data/dataset1/subject2/trials/1/markers.c3d",
            "protected/us-west-2:test/data/dataset1/subject3/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);
        const root = api.getPath("", false);
        await root.promise;

        await api.deleteByPrefix("dataset1/");
        expect(s3.files.length).toBe(3);

        const rootAfterDelete = api.getPath("", false);
        expect(rootAfterDelete.loading).toBe(false);
        expect(rootAfterDelete.folders.length).toBe(2);
    });

    test("Delete by prefix works as expected with a non-recursive non-root parent", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1",
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset1/subject2",
            "protected/us-west-2:test/data/dataset1/subject2/_subject.json",
            "protected/us-west-2:test/data/dataset1/subject2/trials/1/markers.c3d",
            "protected/us-west-2:test/data/dataset1/subject3/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);
        const root = api.getPath("dataset1/", false);
        await root.promise;

        await api.deleteByPrefix("dataset1/subject2");
        expect(s3.files.length).toBe(6);

        const rootAfterDelete = api.getPath("dataset1/", false);
        expect(rootAfterDelete.loading).toBe(false);
        expect(rootAfterDelete.folders.length).toBe(2);
    });

    test("Receiving a PubSub deletes of all children of a folder should eventually delete that folder", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial1/plot.csv",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial1/preview.bin.zip",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial7/plot.csv",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial7/preview.bin.zip",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial9/plot.csv",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial9/preview.bin.zip",
        ]);

        const subjectPath = api.getPath("Tiziana2019_Standard/Subject32", true);
        await subjectPath.promise;
        const trialsPath = api.getPath("/Tiziana2019_Standard/Subject32/trials/", true);
        expect(trialsPath.folders.length).toBe(3);

        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial7/plot.csv",
                size: 0,
                dateModified: new Date().toString(),
            })
        });
        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial7/preview.bin.zip",
                size: 0,
                dateModified: new Date().toString(),
            })
        });

        const trialsPathUpdated = api.getPath("Tiziana2019_Standard/Subject32/trials/", true);
        expect(trialsPathUpdated.folders.length).toBe(2);
    });

    test("Delete by prefix in non-root with multiple files should still calculate correct folder structure", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial1/plot.csv",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial1/preview.bin.zip",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial7/plot.csv",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial7/preview.bin.zip",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial9/plot.csv",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/Tiziana2019_Standard/Subject32/trials/Trial9/preview.bin.zip",
        ]);

        let trialsPath = api.getPath("Tiziana2019_Standard/Subject32/trials", true);
        if (trialsPath.promise != null) {
            trialsPath = await trialsPath.promise;
        }
        expect(trialsPath.path).toBe('Tiziana2019_Standard/Subject32/trials');
        expect(trialsPath.folders.length).toBe(3);

        await api.deleteByPrefix("Tiziana2019_Standard/Subject32/trials/Trial7/");

        const trialsPathUpdated = api.getCachedPath("Tiziana2019_Standard/Subject32/trials");
        expect(trialsPathUpdated).toBeDefined();
        if (trialsPathUpdated != null) {
            expect(trialsPathUpdated.folders.length).toBe(2);
            expect(trialsPathUpdated.folders).toContain("Tiziana2019_Standard/Subject32/trials/Trial1/");
            expect(trialsPathUpdated.folders).toContain("Tiziana2019_Standard/Subject32/trials/Trial9/");
        }
    });

    /*
{
    "loading": false,
    "promise": null,
    "path": "TestCreate2/trials/",
    "folders": [
        "TestCreate2/trials/DJ1/",
        "TestCreate2/trials/DJ2/",
        "TestCreate2/trials/STS1/",
        "TestCreate2/trials/walkingTS3/",
        "TestCreate2/trials/walkingTS4/"
    ],
    "files": [
        {
            "key": "TestCreate2/trials/DJ1/DJ1/segment_1/data.csv",
            "lastModified": "2023-09-19T03:03:38.000Z",
            "size": 506344
        },
        {
            "key": "TestCreate2/trials/DJ1/DJ1/segment_1/preview.bin",
            "lastModified": "2023-09-19T03:03:39.000Z",
            "size": 2991917
        },
        {
            "key": "TestCreate2/trials/DJ1/_trial.json",
            "lastModified": "2023-09-18T14:51:42.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/DJ1/markers.trc",
            "lastModified": "2023-09-23T01:26:13.000Z",
            "size": 489171
        },
        {
            "key": "TestCreate2/trials/DJ2/_trial.json",
            "lastModified": "2023-09-22T18:23:16.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/DJ2/markers.trc",
            "lastModified": "2023-09-22T18:23:17.000Z",
            "size": 627580
        },
        {
            "key": "TestCreate2/trials/STS1/_trial.json",
            "lastModified": "2023-09-22T19:52:16.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/STS1/markers.trc",
            "lastModified": "2023-09-22T19:52:18.000Z",
            "size": 1874086
        },
        {
            "key": "TestCreate2/trials/walkingTS3/_trial.json",
            "lastModified": "2023-09-22T18:24:25.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/walkingTS3/grf.mot",
            "lastModified": "2023-09-22T18:24:27.000Z",
            "size": 1363510
        },
        {
            "key": "TestCreate2/trials/walkingTS3/markers.trc",
            "lastModified": "2023-09-22T18:23:25.000Z",
            "size": 272263
        },
        {
            "key": "TestCreate2/trials/walkingTS4/_trial.json",
            "lastModified": "2023-09-22T18:24:25.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/walkingTS4/grf.mot",
            "lastModified": "2023-09-22T18:24:27.000Z",
            "size": 1251230
        },
        {
            "key": "TestCreate2/trials/walkingTS4/markers.trc",
            "lastModified": "2023-09-22T18:23:25.000Z",
            "size": 251128
        }
    ],
    "recursive": true
}

{
    "loading": false,
    "promise": null,
    "path": "TestCreate2/trials/",
    "folders": [
        "TestCreate2/trials/"
    ],
    "files": [
        {
            "key": "TestCreate2/trials/DJ1/DJ1/segment_1/data.csv",
            "lastModified": "2023-09-19T03:03:38.000Z",
            "size": 506344
        },
        {
            "key": "TestCreate2/trials/DJ1/DJ1/segment_1/preview.bin",
            "lastModified": "2023-09-19T03:03:39.000Z",
            "size": 2991917
        },
        {
            "key": "TestCreate2/trials/DJ1/_trial.json",
            "lastModified": "2023-09-18T14:51:42.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/DJ1/markers.trc",
            "lastModified": "2023-09-23T01:26:13.000Z",
            "size": 489171
        },
        {
            "key": "TestCreate2/trials/DJ2/_trial.json",
            "lastModified": "2023-09-22T18:23:16.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/DJ2/markers.trc",
            "lastModified": "2023-09-22T18:23:17.000Z",
            "size": 627580
        },
        {
            "key": "TestCreate2/trials/STS1/_trial.json",
            "lastModified": "2023-09-22T19:52:16.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/walkingTS3/_trial.json",
            "lastModified": "2023-09-22T18:24:25.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/walkingTS3/grf.mot",
            "lastModified": "2023-09-22T18:24:27.000Z",
            "size": 1363510
        },
        {
            "key": "TestCreate2/trials/walkingTS3/markers.trc",
            "lastModified": "2023-09-22T18:23:25.000Z",
            "size": 272263
        },
        {
            "key": "TestCreate2/trials/walkingTS4/_trial.json",
            "lastModified": "2023-09-22T18:24:25.000Z",
            "size": 2
        },
        {
            "key": "TestCreate2/trials/walkingTS4/grf.mot",
            "lastModified": "2023-09-22T18:24:27.000Z",
            "size": 1251230
        },
        {
            "key": "TestCreate2/trials/walkingTS4/markers.trc",
            "lastModified": "2023-09-22T18:23:25.000Z",
            "size": 251128
        }
    ],
    "recursive": true
}
    */

    test("Loading the root recursively and then loading a single file path exactly should return a PathData with that single file", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);

        const path = api.getPath("", true);
        await path.loading;

        const fileResult: PathData = api.getPath("dataset1/subject1/_subject.json", false);
        expect(fileResult.files.length).toBe(1);
    });

    test("Loading a non-root folder recursively and then loading a single file path exactly should return a PathData with that single file", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);

        const path = api.getPath("dataset1", true);
        await path.loading;

        const fileResult: PathData = api.getPath("dataset1/subject1/_subject.json", false);
        expect(fileResult.files.length).toBe(1);
    });

    test("Receiving a PubSub for a different prefix gets ignored", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:test/data/", s3, pubsub);
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);

        await api.getPath("", true);

        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/NewSubject/_subject.json",
                size: 10,
                dateModified: new Date().toString(),
            })
        });

        const result = api.getPath("", true);
        expect(result.loading).toBe(false);
        expect(result.folders.length).toBe(3);
    });
});