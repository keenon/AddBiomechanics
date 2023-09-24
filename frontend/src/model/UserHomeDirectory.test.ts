import UserHomeDirectory from "./UserHomeDirectory";
import { LiveDirectoryImpl } from "./LiveDirectory";
import { S3APIMock } from "./S3API";
import { PubSubSocketMock } from "./PubSubSocket";
import { autorun } from "mobx";

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
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/preview.bin",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/data.csv",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_1/_results.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_2/preview.bin",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_2/data.csv",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_2/_results.json",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_3/preview.bin",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_3/data.csv",
        "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/TestProsthetic/trials/walking/segment_3/_results.json",
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
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').name).toBe('walking');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').c3dFilePath).toBe('ASB2023/TestProsthetic/trials/walking/markers.c3d');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').c3dFileExists).toBe(false);
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').trcFilePath).toBe('ASB2023/TestProsthetic/trials/walking/markers.trc');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').trcFileExists).toBe(true);
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').grfMotFilePath).toBe('ASB2023/TestProsthetic/trials/walking/grf.mot');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').grfMotFileExists).toBe(true);
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').segments.length).toBe(3);
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').segments.map(f => f.name)).toContain('segment_1');
        expect(api.getTrialContents('/ASB2023/TestProsthetic/trials/walking').segments.map(f => f.path)).toContain('ASB2023/TestProsthetic/trials/walking/segment_1/');
    });

    test("Delete trial still lists remaining trials correctly", async () => {
        // Use an isolated S3 mock, because this test has side effects
        const s3_isolated = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3_isolated.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running/markers.trc",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/running/grf.mot",
        ]);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", s3_isolated, pubsub);

        const api = new UserHomeDirectory(dir);
        await api.getPath("/ASB2023/S01", true).promise;
        expect(api.getPath("/ASB2023/S01/trials/", true).folders.length).toBe(2);


        expect(api.getPathType('/ASB2023/S01/')).toBe('subject');
        expect(api.getSubjectContents('/ASB2023/S01').loading).toBe(false);
        expect(api.getSubjectContents('/ASB2023/S01').trials.length).toBe(2);
        expect(api.getSubjectContents('/ASB2023/S01').trials.map(trial => trial.name)).toContain('walking');

        await api.deleteFolder("/ASB2023/S01/trials/walking");

        expect(api.getSubjectContents('/ASB2023/S01').loading).toBe(false);
        expect(api.getSubjectContents('/ASB2023/S01').trials.length).toBe(1);
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
        expect(api.getTrialSegmentContents('/ASB2023/TestProsthetic/trials/walking/segment_1').name).toBe("segment_1");
        expect(api.getTrialSegmentContents('/ASB2023/TestProsthetic/trials/walking/segment_1').dataPath).toBe("ASB2023/TestProsthetic/trials/walking/segment_1/data.csv");
    });

    test("Upload folder creates a folder", async () => {
        // This test has side effects, so we isolate it
        const isolated_s3 = new S3APIMock();
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", isolated_s3, pubsub);
        const api = new UserHomeDirectory(dir);
        await api.getPath("ASB2023/", false);
        expect(api.getPath("ASB2023/", false).folders.length).toBe(0);
        await api.createDataset("ASB2023/", "TestFolder");
        expect(api.getPath("ASB2023/", false).loading).toBe(false);
        expect(api.getPath("ASB2023/", false).folders.length).toBe(1);
        expect(api.getPath("ASB2023/", false).folders).toContain("ASB2023/TestFolder/");
        await api.getPath("ASB2023/TestFolder/", false);
        expect(api.getPathType('ASB2023/TestFolder/')).toBe('dataset');
    });

    test("Upload folder triggers an autorun in subfolder", async () => {
        // This test has side effects, so we isolate it
        const isolated_s3 = new S3APIMock();
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", isolated_s3, pubsub);
        const api = new UserHomeDirectory(dir);
        await api.getPath("ASB2023/", false);

        const counter = { count: 0 };
        autorun(() => {
            api.getDatasetContents('ASB2023/');
            counter.count++;
        });
        expect(counter.count).toBe(1);

        await api.createDataset("ASB2023/", "TestFolder");
        expect(counter.count).toBe(2);
    });

    test("Upload folder triggers an autorun in root", async () => {
        // This test has side effects, so we isolate it
        const isolated_s3 = new S3APIMock();
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", isolated_s3, pubsub);
        const api = new UserHomeDirectory(dir);
        await api.getPath("", false);

        const counter = { count: 0 };
        autorun(() => {
            api.getDatasetContents('');
            counter.count++;
        });
        expect(counter.count).toBe(1);

        await api.createDataset("", "TestFolder");
        expect(counter.count).toBe(2);
    });

    test("Delete folder triggers an autorun in subfolder", async () => {
        // This test has side effects, so we isolate it
        const isolated_s3 = new S3APIMock();
        isolated_s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S02",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S02/trials",
        ]);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", isolated_s3, pubsub);
        const api = new UserHomeDirectory(dir);
        await api.getPath("ASB2023/", false);

        const counter = { count: 0 };
        autorun(() => {
            api.getDatasetContents('ASB2023/');
            counter.count++;
        });
        expect(counter.count).toBe(1);

        await api.deleteFolder("ASB2023/S01");
        expect(counter.count).toBeGreaterThan(1);
    });

    test("Delete folder triggers an autorun in root", async () => {
        // This test has side effects, so we isolate it
        const isolated_s3 = new S3APIMock();
        isolated_s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/CVPR/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/CVPR/S02/trials",
        ]);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", isolated_s3, pubsub);
        const api = new UserHomeDirectory(dir);
        await api.getPath("", true);

        const counter = { count: 0 };
        autorun(() => {
            api.getDatasetContents('');
            counter.count++;
        });
        expect(counter.count).toBe(1);

        await api.deleteFolder("ASB2023");
        expect(counter.count).toBeGreaterThan(1);

        let result = api.getPath("", true);
        expect(result.loading).toBe(false);
        expect(result.folders.length).toBe(1);
    });

    test("Upload trial triggers an autorun in subfolder", async () => {
        // This test has side effects, so we isolate it
        const isolated_s3 = new S3APIMock();
        isolated_s3.setFilePathsExist([
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/_subject.json",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking",
            "protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/ASB2023/S01/trials/walking/markers.c3d",
        ]);
        const dir = new LiveDirectoryImpl("protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/", isolated_s3, pubsub);
        const api = new UserHomeDirectory(dir);
        await api.getPath("ASB2023/", false);

        const counter = { count: 0 };
        autorun(() => {
            api.getSubjectContents('ASB2023/S01');
            counter.count++;
        });
        expect(counter.count).toBe(1);

        await api.createTrial("ASB2023/S01/", "running");
        expect(counter.count).toBeGreaterThan(1);

        expect(api.getSubjectContents('ASB2023/S01').trials.length).toBe(2);
    });
});