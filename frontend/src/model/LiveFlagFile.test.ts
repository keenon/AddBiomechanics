import { LiveDirectoryImpl, PathData } from "./LiveDirectory";
import { S3APIMock } from "./S3API";
import { PubSubSocketMock } from "./PubSubSocket";
import LiveFlagFile from "./LiveFlagFile";

describe("LiveFlagFile", () => {
    test("Simple download", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/PROCESSING",
        ]);

        const file = new LiveFlagFile(api, "ASB2023/S01/PROCESSING");
        await file.refreshFile();
        expect(file.exists).toBe(true);
    });

    test("Simple download with leading slash", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/PROCESSING",
        ]);

        const file = new LiveFlagFile(api, "/ASB2023/S01/PROCESSING");
        await file.refreshFile();
        expect(file.exists).toBe(true);
    });

    test("Simple upload", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const file = new LiveFlagFile(api, "ASB2023/S01/PROCESSING");
        await file.upload();
        expect(file.exists).toBe(true);
        expect(pubsub.mockSentMessagesLog.length).toBe(1); // we should have updated PubSub with the changes
        expect(s3.files.length).toBe(1);
        expect(s3.files[0].key).toBe("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/PROCESSING");
    });

    test("Check and delete", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/PROCESSING",
        ]);

        const file = new LiveFlagFile(api, "ASB2023/S01/PROCESSING");
        await file.refreshFile();
        expect(file.exists).toBe(true);
        await file.delete();
        expect(file.exists).toBe(false);
        expect(pubsub.mockSentMessagesLog.length).toBe(1);
        expect(s3.files.length).toBe(3);
    });

    test("Get pub-sub notification of existence", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        const api = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const file = new LiveFlagFile(api, "ASB2023/S01/PROCESSING");
        await file.refreshFile();
        expect(file.exists).toBe(false);

        s3.setFileContents("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/PROCESSING", "test");
        pubsub.mockReceiveMessage({
            topic: "/DEV/UPDATE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/PROCESSING",
                size: 10,
                dateModified: new Date().getTime().toString(),
            })
        });
        if (file.loading) {
            await file.loading;
        }
        expect(file.exists).toBe(true);
    });

});