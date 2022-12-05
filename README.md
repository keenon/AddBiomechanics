### AddBiomechanics

[![DOI](https://zenodo.org/badge/398424759.svg)](https://zenodo.org/badge/latestdoi/398424759)

This is an open effort to assemble a large dataset of human motion. We're hoping to faccilitate this by providing easy-to-use tools that can automatically process motion capture data, and prepare it for biomechanical analysis. We're also working to provide large aggregate datasets in standard formats, along with tools to easily handle the data, at some point in the near future.

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
## Getting Set Up For Development (server)

1. Download [credentials](https://drive.google.com/file/d/1okCCdvqaZh20gc4TG152o7yJV9_vnBtf/view?usp=sharing) into `.devcontainer/.aws/credentials` and `server/.aws/credentials`.
2. Download [server_credentials.csv](https://drive.google.com/file/d/1e1GrwpOm0viZhNGkw_lDNPa_cfYhJ3r3/view?usp=sharing) into `.devcontainer/server_credentials.csv` and `server/server_credentials.csv`.
3. Open this project in VSCode, and then use Ctrl+Shift+P and get to the command "Remote-Containers: Open Folder in Container...". Re-open this folder in a Docker container.
4. Using a VSCode Terminal, navigate to `frontend` and execute `yarn start` to begin serving a live frontend

## Hosting a Processing Server

1. Got into the `server` folder
2. Run `docker build -f Dockerfile.dev .` (to run a dev server) or `docker build -f Dockerfile.prod .` (to run a prod server) to build the Docker container to run the server. It's important that you rebuild the Docker container each time you boot a new server, since that sets it up with its own PubSub connection.
3. Run the docker container you just built! That's your server. Leave it running as a process.

## Switching between Dev and Prod
By default, the main branch is pointed at the dev servers. We keep the current prod version on the `prod` branch.

To switch between environments, run `amplify env checkout dev` or `amplify env checkout prod`

## Apple M1(X) Macs

For the time being, need to specify an `x86_64` emulator for the Docker that you may want to launch your editor in.
You can do that by running `docker build  --platform linux/x86_64 .` from inside `.devcontainer`