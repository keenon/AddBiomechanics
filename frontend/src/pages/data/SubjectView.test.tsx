import { PathData } from "../../model/LiveDirectory";
import { S3APIMock } from "../../model/S3API";
import { PubSubSocketMock } from "../../model/PubSubSocket";
import Session from "../../model/Session";
import SubjectView from "./SubjectView";
import { autorun, spy, trace, observable, action } from "mobx";
import { observer } from "mobx-react-lite";
import { render, fireEvent, act, cleanup, waitFor } from '@testing-library/react';

function flushPromises() {
return new Promise(resolve => Promise.resolve().then(resolve));
}

afterEach(cleanup);

describe('AsyncMobX', () => {
    it('should not emit warnings', async () => {
        const obesravableObject = observable({
            foo: 'bar',
        });

        const TestComponent = observer(() => {
            return (
                <div>
                    {obesravableObject.foo}
                </div>
            );
        });

        const { getByText } = render(<TestComponent />);

        expect(getByText('bar')).toBeInTheDocument();

        await act(action(async () => {
            obesravableObject.foo = 'baz';
            await flushPromises();
        }));

        expect(getByText('baz')).toBeInTheDocument();
    });
});

/*
describe("SubjectView", () => {
    it('initial loading', () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        const session = new Session(s3, pubsub, "us-west-2");
        session.setLoggedIn('test', 'test@test.com');
        const url = session.parseDataURL("/data/test/subject1");
        const subjectView = render(<SubjectView home={url.homeDirectory} currentLocationUserId={url.userId} path={url.path} readonly={true} />);
        expect(subjectView.getByText("Loading...")).toBeInTheDocument();
    });

    it('should handle a single file drop event correctly', async () => {
        const s3 = new S3APIMock();
        const pubsub = new PubSubSocketMock("DEV");
        s3.setFilePathsExist([
            "protected/us-west-2:test/data/dataset1/subject1/_subject.json",
            "protected/us-west-2:test/data/dataset2/",
            "protected/us-west-2:test/data/root_subject/_subject.json",
            "protected/us-west-2:test/data/_subject.json",
        ]);
        s3.setFileContents("protected/us-west-2:test/data/dataset1/subject1/_subject.json", JSON.stringify({
            dataSource: 'study',
            subjectConsent: true,
            heightM: 1.7,
            massKg: 70,
            sex: 'male',
            ageYears: 30,
            skeletonPreset: 'vicon',
            disableDynamics: false,
            footBodyNames: ['calcn_r', 'calcn_l'],
            subjectTags: ['healthy'],
            runMoco: true,
            citation: 'Cite me!'
        }));

        const session = new Session(s3, pubsub, "us-west-2");
        session.setLoggedIn('test', 'test@test.com');

        const url = session.parseDataURL("/data/test/dataset1/subject1");
        const subjectContents = url.homeDirectory.getSubjectContents(url.path);
        expect(subjectContents.subjectJson.loading).not.toBeNull();
        await subjectContents.subjectJson.loading;

        const subjectView = render(<SubjectView home={url.homeDirectory} currentLocationUserId={url.userId} path={url.path} readonly={false} />);
        const dropZone = subjectView.getByText("Drop C3D or TRC files here to create trials.");
        expect(dropZone).toBeInTheDocument();

        // Create a mock file
        const file = new File(['running_trial'], 'running_trial.trc', {
            type: 'text/plain',
        });
    
        // Set dataTransfer object on a drop event
        const dropEvent = new Event('drop', { bubbles: true });
        Object.defineProperty(dropEvent, 'dataTransfer', {
            value: {
                files: [file],
                items: [
                {
                    kind: 'file',
                    type: 'text/plain',
                    getAsFile: () => file,
                },
                ],
                types: ['Files'],
            },
        });
    
        // Fire the drop event
        await act(async () => {
            fireEvent(dropZone, dropEvent);
            await flushPromises();
        });

        // Expect that "running_trial" will eventually show up
        expect((await subjectView.findAllByText("running_trial")).length).toBe(1);
    });
});
*/