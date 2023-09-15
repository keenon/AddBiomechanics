import { LiveDirectory, LiveDirectoryImpl, PathData } from "./LiveDirectory";
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
        expect(result.folders.length).toBe(0);
        expect(result.files.length).toBe(9);
        expect(result.files.map(f => f.key)).toContain("ASB2023/S01/_subject.json");
    });

    test("Loading recursively with real paths prevents nested loads from hitting the network", async () => {
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
        expect(result.folders.length).toBe(0);
        expect(result.files.length).toBe(9);
        expect(result.files.map(f => f.key)).toContain("ASB2023/S01/_subject.json");

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
        // We should have executed the autorun twice more, once for the initial value with loading:true, and then again for loading:false
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

        await api.getPath("ASB2023/", false);

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
        expect(result.folders.length).toBe(0);
        expect(result.files.length).toBe(8);

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
        expect(newPath.files.length).toBe(9);
        expect(newPath.files.map(f => f.key)).toContain("ASB2023/S01/_subject.json");
    });

});