import { LiveDirectoryImpl, PathData } from "./LiveDirectory";
import { S3APIMock } from "./S3API";
import { PubSubSocketMock } from "./PubSubSocket";
import LiveJsonFile from "./LiveJsonFile";

describe("LiveJsonFile", () => {
    test("Simple download", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("dir/", s3, pubsub);

        s3.setFilePathsExist([
            "dir/test.json",
        ]);
        s3.setFileContents("dir/test.json", JSON.stringify({ test: "hello world" }));

        const file = new LiveJsonFile(api, "test.json");
        await file.refreshFile();
        expect(file.getAttribute("test", "")).toBe("hello world");
    });

    test("Simple upload", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("dir/", s3, pubsub);

        s3.setFilePathsExist([
            "dir/test.json",
        ]);
        s3.setFileContents("dir/test.json", JSON.stringify({ test: "hello world" }));

        const file = new LiveJsonFile(api, "test.json");
        expect(pubsub.mockSentMessagesLog.length).toBe(0);
        await file.refreshFile();
        file.setAttribute("test", "hello moon");
        await file.uploadNow();
        expect(s3.getFileContents("dir/test.json")).toBe(JSON.stringify({ test: "hello moon" }));
        expect(pubsub.mockSentMessagesLog.length).toBe(1); // we should have updated PubSub with the changes
    });

    test("File not found handled gracefully", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("dir/", s3, pubsub);

        const file = new LiveJsonFile(api, "test.json");
        await file.refreshFile();
        expect(file.getAttribute("test", "")).toBe("");
    });

    test("File change notification causes redownload", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("dir/", s3, pubsub);

        s3.setFilePathsExist([
            "dir/test.json",
        ]);
        s3.setFileContents("dir/test.json", JSON.stringify({ test: "hello world" }));

        const file = new LiveJsonFile(api, "test.json");
        await file.refreshFile();
        expect(file.getAttribute("test", "")).toBe("hello world");

        s3.setFileContents("dir/test.json", JSON.stringify({ test: "hello moon" }));
        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/dir/test.json",
            message: JSON.stringify({
                key: "dir/test.json",
                size: 10,
                dateModified: new Date().getTime().toString(),
            })
        });
        // There's a race condition here, if we're still async loading the file then wait for that
        if (file.loading != null) {
            await file.loading;
        }
        expect(file.getAttribute("test", "")).toBe("hello moon");
    });

    test("File delete notification causes redownload", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("dir/", s3, pubsub);

        s3.setFilePathsExist([
            "dir/test.json",
        ]);
        s3.setFileContents("dir/test.json", JSON.stringify({ test: "hello world" }));

        const file = new LiveJsonFile(api, "test.json");
        await file.refreshFile();
        expect(file.getAttribute("test", "")).toBe("hello world");

        s3.files = [];
        s3.fileContents.clear();

        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/dir/test.json",
            message: JSON.stringify({
                key: "dir/test.json",
                size: 10,
                dateModified: new Date().getTime().toString(),
            })
        });
        // There's a race condition here, if we're still async loading the file then wait for that
        if (file.loading != null) {
            await file.loading;
        }
        expect(file.getAttribute("test", "")).toBe("");
    });
});