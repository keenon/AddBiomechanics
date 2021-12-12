The code in the `frontend/` uploads files to S3 in specific structure, and waits for PubSub notifications to refresh and re-download.

The code in `server/` downloads, processes, and reuploads files to S3 in specific structure, and notifies PubSub.

The file structure on S3 follows:

#### Folders:
Folders are implicit in S3 path names. A folder can be an empty file indicating a folder. Any S3 folder that doesn't meet a more specific criteria below is "just a folder", and will be displayed as such on the frontend.

#### Subjects:
A single subject gets its own special folder.

A subject is a folder with the following structure

- `{SUBJECT_NAME}/unscaled_generic.osim`
- `{SUBJECT_NAME}/trials/*`

It may also contain:

- `{TRIAL_NAME}/manually_scaled.osim`, if we'd like to compare automatic scaling to a manual version

#### Trials:

A trial is a folder within a `{SUBJECT_NAME}/trials/*` folder, which must contain:

- `{TRIAL_NAME}/markers.{trc,c3d}`

It may also contain:

- `{TRIAL_NAME}/manual_ik.mot`, if we'd like to compare automatic scaling to a manual version

We can have a number of flags attached to the folder, as empty S3 files:

- `{SUBJECT_NAME}/READY_TO_PROCESS`, which is a flag saying that the frontend is ready for this trial to be processed
- `{SUBJECT_NAME}/PROCESSING`, which is a flag saying that a backend started processing this trial. The backend is allowed to crash without cleaning this up, so we ask that the backend re-upload this file once every few minutes, and if the frontend (or other servers) detect this file is getting old, they'll assume the processing server died.

If the server has run autoscaling, it may also contain:

- `{SUBJECT_NAME}/auto_scaled.osim`, the downloadable output of automatically scaling for just this trial
- `{SUBJECT_NAME}/auto_ik.mot`, the downloadable output of automatically running IK with automatic scaling
- `{SUBJECT_NAME}/preview.json`, the JSON encoded Web GUI preview for autoscaling
- `{SUBJECT_NAME}/summary.json`, the JSON encoded summary of performance of autoscaling
- `{SUBJECT_NAME}/log.txt`, the raw log of the auto-scaling process