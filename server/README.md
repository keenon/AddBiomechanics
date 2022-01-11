This contains the code that pulls from S3, and does the actual work of processing data and writing results back.

To run the server on a new computer, build the Dockerfile that's in this folder, and run it.

It's important to rebuild the Dockerfile each time we want to launch a new server, since that takes care of setting up a unique PubSub address for the server.