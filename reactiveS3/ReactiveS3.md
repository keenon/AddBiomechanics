The whole application is built on an API that lets you create, delete, and listen for changes to files in S3 without a central server.

We support some simple operations:

- Check/Listen for the existence of certain patterns of file names (like ones that match ".*/READY_TO_PROCESS")
    - This is used to trigger server processing
- Check/listen for the existence of a file at a path
    - This is used by the frontend to figure out the status of processing
- List children of a path (empty if it doesn't exist)