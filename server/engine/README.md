This code is a standalone utility to process a folder of data in the standard BiomechicsNet S3 format.

It can operate on a local folder, which it is someone else's responsibility (the `app/` code) to download, and then re-upload after processing.

It's designed to be called (as a new process) from the BiomechanicsNet `app/` code, or to be used manually if required.