import React from "react";
import "./MyUploads.scss";
import MyMocapUploads, {
  MocapFolder,
  MocapClip,
} from "../../state/MyMocapUploads";
import { action } from "mobx";
import { observer } from "mobx-react-lite"; // Or "mobx-react".
import UserHeader from "../UserHeader/UserHeader";

type MocapClipDisplayProps = {
  state: MocapClip;
};

const MocapClipDisplay = observer((props: MocapClipDisplayProps) => {
  return <div>{props.state.statusFile.fullPath}</div>;
});

type MyUploadsProps = {
  state: MyMocapUploads;
};

const MyUploadFolderNavigator = observer((props: MyUploadsProps) => {
  if (props.state.loading) {
    return <div>Loading...</div>;
  } else {
    let data = [];
    for (let i = 0; i < props.state.currentFolder.mocapClips.length; i++) {
      const clip = props.state.currentFolder.mocapClips[i];
      data.push(
        <MocapClipDisplay key={clip.statusFile.fullPath} state={clip} />
      );
    }
    return (
      <div>
        Current: {props.state.currentFolder.backingFolder.bucketPath} -{" "}
        {props.state.currentFolder.mocapClips.length} Clips
        {data}
        <button
          onClick={action(() => {
            props.state.currentFolder.addMocapClip();
          })}
        >
          Upload new clip
        </button>
      </div>
    );
  }
});

const MyUploads = (props: MyUploadsProps) => {
  return (
    <UserHeader>
      <div className="container-fluid">
        <div className="row">
          <div className="col">
            <div className="card">
              <MyUploadFolderNavigator {...props} />
            </div>
          </div>
        </div>
      </div>
    </UserHeader>
  );
};

export default MyUploads;
