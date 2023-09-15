import Session, { DataURL } from "./Session";
import { S3APIMock } from "./S3API";
import { PubSubSocketMock } from "./PubSubSocket";
import { PathData } from "./LiveDirectory";
import { autorun, spy, trace, observable, action } from "mobx";

describe("Session", () => {
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
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/_subject.json",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/trials",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/trials/S05DN408",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/trials/S05DN408/_results.json",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/trials/S05DN408/markers.c3d",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/trials/S05DN408/plot.csv",
        "protected/us-west-2:12773914-1588-4180-95d5-ee486c714c48/data/Perturb_Subject_5/trials/S05DN408/preview.bin.zip",
    ]);

    test('Constructor', () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        expect(session).toBeInstanceOf(Session);
    });

    test('Parse existing URL', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const parsed: DataURL = session.parseDataURL('/data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023');

        // The path should be right
        expect(parsed.path).toBe('ASB2023');
        expect(parsed.userId).toBe('35e1c7ca-cc58-457e-bfc5-f6161cc7278b');
        // We're not logged in in this test, so everything should be readonly
        expect(parsed.readonly).toBe(true);

        // The directory prefix should be right
        expect(parsed.homeDirectory.dir.prefix).toBe('protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/');

        // There should be real data when we try to load it
        let pathData: PathData = parsed.homeDirectory.getPath(parsed.path, false);
        if (pathData.loading && pathData.promise != null) {
            pathData = await pathData.promise;
        }
        expect(pathData.folders.length).toBe(2);
    });

    test('Create link to URL', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const parsed: DataURL = session.parseDataURL('/data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023');

        // The path should be right
        expect(parsed.path).toBe('ASB2023');
        expect(parsed.userId).toBe('35e1c7ca-cc58-457e-bfc5-f6161cc7278b');
        // We're not logged in in this test, so everything should be readonly
        expect(parsed.readonly).toBe(true);

        const link: string = session.getDataURL(parsed, 'ASB2023/S01/trials/walking/segment_1/markers.c3d');
        expect(link).toBe('/data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023/S01/trials/walking/segment_1/markers.c3d');
    });

    test('Parse not found URL', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const parsed: DataURL = session.parseDataURL('/data/not-exists/test');

        // The path should be right
        expect(parsed.path).toBe('test');
        expect(parsed.userId).toBe('not-exists');

        // The directory prefix should be right
        expect(parsed.homeDirectory.dir.prefix).toBe('protected/us-west-2:not-exists/data/');

        // There should be no data when we try to load it
        let pathData: PathData = parsed.homeDirectory.getPath(parsed.path, false);
        if (pathData.loading && pathData.promise != null) {
            pathData = await pathData.promise;
        }
        expect(pathData.folders.length).toBe(0);
        expect(pathData.files.length).toBe(0);
    });

    test('Parse URL twice with cacheing home directory', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const parsed1: DataURL = session.parseDataURL('/data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023');
        const parsed2: DataURL = session.parseDataURL('/data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023');

        expect(parsed1.homeDirectory === parsed2.homeDirectory).toBe(true);
    });

    test('Login triggers mobx listeners', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const counter = { count: 0 }
        // Sets up the autorun and prints 0.
        const disposer = autorun(() => {
            session.loggedIn;
            counter.count++
        })
        expect(counter.count).toBe(1);

        // This should trigger the autorun again
        session.setLoggedIn('35e1c7ca-cc58-457e-bfc5-f6161cc7278b', 'test@gmail.com');
        expect(counter.count).toBe(2);

        disposer();
    });

    test('Logout triggers mobx listeners', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const counter = { count: 0 }
        // Sets up the autorun and prints 0.
        const disposer = autorun(() => {
            session.loadingLoginState;
            counter.count++
        })
        expect(counter.count).toBe(1);

        // This should trigger the autorun again
        session.setNotLoggedIn();
        expect(counter.count).toBe(2);

        disposer();
    });

    test('Login updates home directory path', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const counter = { count: 0 }
        // Sets up the autorun and prints 0.
        const disposer = autorun(() => {
            session.getHomeDirectoryURL();
            counter.count++
        })
        expect(counter.count).toBe(1);

        // This should trigger the autorun again
        session.setLoggedIn('35e1c7ca-cc58-457e-bfc5-f6161cc7278b', 'test@gmail.com');
        expect(counter.count).toBe(2);

        disposer();
    });

    test('Login updates readonly status', async () => {
        const session = new Session(s3, pubsub, 'us-west-2');

        const counter = { count: 0 }
        // Sets up the autorun and prints 0.
        const disposer = autorun(() => {
            session.parseDataURL('/data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023');
            counter.count++
        })
        expect(counter.count).toBe(1);

        // This should trigger the autorun again
        session.setLoggedIn('35e1c7ca-cc58-457e-bfc5-f6161cc7278b', 'test@gmail.com');
        expect(counter.count).toBe(2);

        disposer();
    });

});