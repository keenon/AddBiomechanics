import UserHomeDirectory from "./UserHomeDirectory";
import { LiveDirectoryImpl } from "./LiveDirectory";
import { S3APIMock } from "./S3API";
import { PubSubSocketMock } from "./PubSubSocket";

describe("UserHomeDirectory", () => {
    const s3 = new S3APIMock();
    const pubsub = new PubSubSocketMock("DEV");
    s3.setFilePathsExist([
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running/markers.trc",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running/grf.mot",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/_trial.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/markers.trc",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/grf.mot",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/markers.c3d",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/preview.bin",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/data.csv",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/_results.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_2/markers.c3d",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_2/preview.bin",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_2/data.csv",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_3/markers.c3d",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_3/preview.bin",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_3/data.csv",
        // Some nasty edge cases
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials/_subject.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials/trials",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/trials/trials/trials/",
    ]);

    test("Constructor", () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const dir = new LiveDirectoryImpl("test", s3, pubsub);
        const api = new UserHomeDirectory(dir);

        expect(api).toBeInstanceOf(UserHomeDirectory);
    });

    test("List datasets", async () => {
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const api = new UserHomeDirectory(dir);
        // Incremental loading of folders
        await api.getPath("/ASB2023", false).promise;
        expect(api.getPathType('/ASB2023')).toBe('dataset');
        await api.getPath("/ASB2023/S01", false).promise;
        expect(api.getPathType('/ASB2023/S01')).toBe('subject');
        await api.getPath("/ASB2023/S01/", false).promise;
        expect(api.getPathType('/ASB2023/S01/')).toBe('subject');
        await api.getPath("/ASB2023/S01/trials", false).promise;
        expect(api.getPathType('/ASB2023/S01/trials')).toBe('trials_folder');
        await api.getPath("/ASB2023/S01/trials/", false).promise;
        expect(api.getPathType('/ASB2023/S01/trials/')).toBe('trials_folder');
        await api.getPath("/ASB2023/S01/trials/walking", false).promise;
        expect(api.getPathType('/ASB2023/S01/trials/walking')).toBe('trial');
        // Try some "gotcha" edge cases
        await api.getPath("/trials/trials", false).promise;
        expect(api.getPathType('/trials/trials')).toBe('subject');
        await api.getPath("/trials", false).promise;
        expect(api.getPathType('/trials')).toBe('dataset');
    });

    test("List dataset contents", async () => {
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const api = new UserHomeDirectory(dir);
        // Incremental loading of folders
        await api.getPath("/ASB2023", false).promise;
        expect(api.getPathType('/ASB2023')).toBe('dataset');
        expect(api.getDatasetContents('/ASB2023').loading).toBe(false);
        expect(api.getDatasetContents('/ASB2023').contents.length).toBe(2);
    });

    test("List subject contents", async () => {
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const api = new UserHomeDirectory(dir);
        // Incremental loading of folders
        await api.getPath("/ASB2023", false).promise;
        await api.getPath("/ASB2023/S01", false).promise;
        await api.getPath("/ASB2023/S01/trials", false).promise;
        expect(api.getPathType('/ASB2023/S01')).toBe('subject');

        expect(api.getSubjectContents('/ASB2023/S01').loading).toBe(false);
        expect(api.getSubjectContents('/ASB2023/S01').trials.length).toBe(2);
    });

    test("List trial contents", async () => {
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const api = new UserHomeDirectory(dir);
        // Incremental loading of folders
        await api.getPath("/ASB2023", false).promise;
        await api.getPath("/ASB2023/TestProsthetic", false).promise;
        await api.getPath("/ASB2023/TestProsthetic/trials", false).promise;
        await api.getPath("/ASB2023/TestProsthetic/trials/walking", false).promise;

        expect(api.getPathType('/ASB2023/TestProsthetic/trials/walking')).toBe('trial');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').loading).toBe(false);
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').segments.length).toBe(3);
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').segments.map(f => f.name)).toContain('segment_1');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').segments.map(f => f.path)).toContain('ASB2023/TestProsthetic/trials/walking/segment_1/');
    });

    test("List trial segment contents", async () => {
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3, pubsub);

        const api = new UserHomeDirectory(dir);
        // Incremental loading of folders
        await api.getPath("/ASB2023", false).promise;
        await api.getPath("/ASB2023/TestProsthetic", false).promise;
        await api.getPath("/ASB2023/TestProsthetic/trials", false).promise;
        await api.getPath("/ASB2023/TestProsthetic/trials/walking", false).promise;
        await api.getPath("/ASB2023/TestProsthetic/trials/walking/segment_1", false).promise;
        expect(api.getPathType('/ASB2023/TestProsthetic/trials/walking/segment_1')).toBe('trial_segment');
        expect(api.getTrialSegmentContents('/ASB2023/TestProsthetic/trials/walking/segment_1').dataPath).toBe("/ASB2023/TestProsthetic/trials/walking/segment_1/data.csv");
    });
});