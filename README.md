### AddBiomechanics

[![DOI](https://zenodo.org/badge/398424759.svg)](https://zenodo.org/badge/latestdoi/398424759)

This is an open effort to assemble a large dataset of human motion. We're hoping to facilitate this by providing easy-to-use tools that can automatically process motion capture data, and prepare it for biomechanical analysis. We're also working to provide large aggregate datasets in standard formats, along with tools to easily handle the data, at some point in the near future.

### Getting Set Up (for Stanford Developers)

*A note for non-Stanford devs: these instructions probably won't help you!* We share the AddBiomechanics source code so that researchers can fully understand the methods. We highly encourage you to use the web application rather than building the code from source. Note that we are a small team and are not able to support individuals wishing to build from source. You're welcome to try, but it's probably going to be harder than you hope, and we're sorry about that. Part of the complexity here is that the cloud application is built to interface directly with a web of different AWS resources, each of which has its own (currently undocumented) IAM setup, which are provisioned and continually maintained by our team for the public instance of AddBiomechanics. If you are trying to run your own independent instance to avoid sharing data, even if we gave you the permissions files referenced in these instructions, your code would by default talk to our AWS resources, and effectively just join our cluster. If you want it to talk to your own resources, we cannot offer support debugging your setup to get everything to work.

## Getting Set Up for Development (frontend)

1. Download the [aws-exports-dev.js](https://drive.google.com/file/d/1IBr3Fm-8rYeGudyWLvIEGPkdzdpR0I90/view?usp=sharing) file, rename it `aws-exports.js` and put it into the `frontend/src` folder.
2. Run `yarn start` to launch the app!

## Notes (frontend)

Note: the above instructions will cause your local frontend to target the dev servers, if you would rather interact with production servers, download the [aws-exports-prod.js](https://drive.google.com/file/d/1VZVgHHwSP-xmJW-qZeQ6U92FYWoU36aP/view?usp=sharing) file, rename it `aws-exports.js` and put it into the `frontend/src` folder.

Because the app is designed to be served as a static single page application (see the wiki for details) running it locally with the appropriate `aws-exports.js` will behave exactly the same as viewing it from [dev.addbiomechanics.org](https://dev.addbiomechanics.org) (dev servers) or [app.addbiomechanics.org](https://app.addbiomechanics.org) (prod servers)

## Getting Set Up For Deployment (frontend)

1. Log in with the AddBiomechanics AWS root account on your local `aws` CLI.
2. Install the Amplify CLI `npm install -g @aws-amplify/cli` (may require `sudo`, depending on your setup)
3. From inside the `frontend` folder, run `amplify configure`, and follow the instructions to create a new IAM user for your computer (in the 'us-west-2' region)
4. From inside the `frontend` folder, run `amplify init`
    a. When asked "Do you want to use an existing environment?" say YES
    b. Choose the environment "dev"
    c. Choose anything you like for your default editor
    d. Select the authentication method "AWS profile", and select the profile you created in step 2
5. Run `yarn start` to launch the app!
## Getting Set Up For Development (server processing algorithm)

The core algorithm for processing data exists in `server/engine/engine.py`. To test changes `engine.py`:

1. Run `pip3 install -r /engine/requirements.txt`
2. Download the [`test_engine.sh` script](https://drive.google.com/file/d/1n-9KSv-wZevuVNwShb1Ur36MRAZlnNhv/view?usp=share_link), place it in this directory
3. Download the [test_data/ folder](https://drive.google.com/drive/folders/1jGfgM1m13ksqLZByKUEoUwsy22OVtEza?usp=share_link) (ask Keenon for access to this), place it in this directory
4. Run `./test_engine.sh` to test out your changes to `engine.py` on existing data. Change the line `TEST_NAME="opencap_test"` to different run against other folder names you find in `test_data/` (careful, don't include the `_original` part or you'll overwrite your input data by accident)

## Hosting a Processing Server

1. Got into the `server` folder
2. Download the `server_credentials.csv` file, which Keenon can give you a link to
3. Run `docker build -f Dockerfile.dev .` (to run a dev server) or `docker build -f Dockerfile.prod .` (to run a prod server) to build the Docker container to run the server. It's important that you rebuild the Docker container each time you boot a new server, since that sets it up with its own PubSub connection.
4. Run the docker container you just built! That's your server. Leave it running as a process.

## Switching between Dev and Prod
By default, the main branch is pointed at the dev servers. We keep the current prod version on the `prod` branch.

To switch between environments, run `amplify env checkout dev` or `amplify env checkout prod`

## Apple M1(X) Macs

For the time being, need to specify an `x86_64` emulator for the Docker that you may want to launch your editor in.
You can do that by running `docker build  --platform linux/x86_64 .` from inside `.devcontainer`
