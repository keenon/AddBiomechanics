import { LiveDirectoryImpl } from "./LiveDirectory";
import { PubSubSocketMock } from "./PubSubSocket";
import { S3APIMock } from "./S3API";
import SubjectViewState from "./SubjectViewState";
import UserHomeDirectory from "./UserHomeDirectory";

const flushPromises = () => new Promise(resolve => Promise.resolve().then(resolve));

describe("SubjectViewState", () => {
    const fileList = [
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/grf.mot",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running/markers.trc",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running/grf.mot",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/jumping",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/jumping/markers.trc",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/jumping/grf.mot",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials",
        // Some nasty edge cases
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials/trials/",
    ];

    test("Constructor", () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist(fileList);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        const home = new UserHomeDirectory(dir);
        const subject = home.getSubjectViewState("ASB2023/S01");

        expect(subject).toBeInstanceOf(SubjectViewState);
    });

    test("Autorun reloadState on load", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist(fileList);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        const home = new UserHomeDirectory(dir);

        const subject = home.getSubjectViewState("ASB2023/S01");
        expect(subject.reloadCount).toBe(1);

        await home.getPath("ASB2023/S01", false).promise;
        await home.getPath("ASB2023/S01/trials", false).promise;

        expect(subject.reloadCount).toBe(4);
    });

    test("Autorun reloadState on deletes", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist(fileList);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        const home = new UserHomeDirectory(dir);

        await home.getPath("ASB2023/S01", false).promise;
        await home.getPath("ASB2023/S01/trials", false).promise;

        const subject = home.getSubjectViewState("ASB2023/S01");
        expect(subject.reloadCount).toBe(1);

        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
                size: 0,
                dateModified: new Date().toString(),
            })
        });
        pubsub.mockReceiveMessage({
            topic: "/DEV/DELETE/protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data",
            message: JSON.stringify({
                key: "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
                size: 0,
                dateModified: new Date().toString(),
            })
        });

        expect(subject.reloadCount).toBe(3);
    });

    test("Create trial base case", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist(fileList);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        const home = new UserHomeDirectory(dir);

        await home.getPath("ASB2023/TestProsthetic", false).promise;
        await home.getPath("ASB2023/TestProsthetic/trials", false).promise;

        const subject = home.getSubjectViewState("ASB2023/TestProsthetic");

        expect(subject).toBeInstanceOf(SubjectViewState);
        expect(subject.trials.length).toBe(0);

        // Create a mock file
        const file = new File(['running_trial'], 'running_trial.trc', {
            type: 'text/plain',
        });

        await subject.dropFilesToUpload([file]);

        // We should have auto-updated our trial map
        expect(subject.trials.length).toBe(1);

        const uploadingFile = dir.getLiveFile(subject.trials[0].trcFilePath);
        expect(uploadingFile.uploading).toBeNull();
        expect(uploadingFile.exists).toBe(true);
    });

    /*
    test("Create trial loading", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist(fileList);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        const home = new UserHomeDirectory(dir);

        await home.getPath("ASB2023/TestProsthetic", false).promise;
        await home.getPath("ASB2023/TestProsthetic/trials", false).promise;

        const subject = home.getSubjectViewState("ASB2023/TestProsthetic");

        expect(subject).toBeInstanceOf(SubjectViewState);
        expect(subject.trials.length).toBe(0);

        // Create a mock file
        const file = new File(['running_trial'], 'running_trial.trc', {
            type: 'text/plain',
        });

        s3.setMockFileUploadPartialProgress(true);
        const promise = subject.dropFilesToUpload([file]);

        // We should have auto-updated our trial map
        expect(subject.trials.length).toBe(1);

        const uploadingFile = dir.getLiveFile(subject.trials[0].trcFilePath);
        expect(uploadingFile.exists).toBe(false);
        expect(uploadingFile.uploading).toBeDefined();
        expect(uploadingFile.uploadProgress).toBe(0.5);

        expect(s3.mockFileUploadResolves.length).toBe(1);
        s3.resolveMockFileUploads();
        await promise;
        flushPromises();

        await uploadingFile.uploading;

        expect(uploadingFile.exists).toBe(true);
        expect(uploadingFile.uploading).toBeNull();
    });
    */

    test("Delete trial", async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        pubsub.connect();
        s3.setFilePathsExist(fileList);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);
        const home = new UserHomeDirectory(dir);

        await home.getPath("ASB2023/S01", false).promise;
        await home.getPath("ASB2023/S01/trials", true).promise;

        const subject = home.getSubjectViewState("ASB2023/S01");

        // We should have auto-updated our trial map
        expect(subject.trials.length).toBe(3);

        await subject.deleteTrial(subject.trials[0]);

        // We should have auto-updated our trial map
        expect(subject.trials.length).toBe(2);

        // Loopback the messages
        expect(pubsub.mockSentMessagesLog.length).toBe(3);
        pubsub.mockSentMessagesLog.forEach((message) => {
            pubsub.mockReceiveMessage(message);
        });
        pubsub.mockSentMessagesLog = [];

        // We should have auto-updated our trial map
        expect(subject.trials.length).toBe(2);
    });
});