import argparse
from addbiomechanics.auth import AuthContext
from addbiomechanics.commands.download import DownloadCommand
from addbiomechanics.commands.download_files import DownloadFilesCommand
from addbiomechanics.commands.ls import LsCommand
from addbiomechanics.commands.upload import UploadCommand
from addbiomechanics.commands.analytics import AnalyticsCommand
from addbiomechanics.commands.transfer_markerset import TransferMarkersetCommand
from addbiomechanics.commands.plot import PlotCommand
from addbiomechanics.commands.debug import DebugCommand
from addbiomechanics.commands.view import ViewCommand
from addbiomechanics.commands.compare import CompareCommand
from addbiomechanics.commands.post_process import PostProcessCommand
from addbiomechanics.commands.export_csv import ExportCSVCommand
from addbiomechanics.commands.describe_dataset import DescribeDatasetCommand
from addbiomechanics.commands.transfer_reviews import TransferReviewsCommand
from addbiomechanics.commands.create_b3d import CreateB3DCommand
from addbiomechanics.commands.generate_credits import GenerateCreditsCommand
from addbiomechanics.commands.clean_up import CleanUpCommand
from addbiomechanics.commands.stats import StatsCommand


PROD_DEPLOYMENT = {
    'POOL_NAME': "biomechanicsfrontendf7e99b66_userpool_f7e99b66-prod",
    'POOL_ID': "us-west-2_vRDVX9u35",
    'POOL_ARN': "arn:aws:cognito-idp:us-west-2:756193201945:userpool/us-west-2_vRDVX9u35",
    'POOL_CLIENT_ID': '2sf0gfv660a0q6abr8d3hi99ck',
    'ID_POOL': 'us-west-2:8817f48e-9e7b-46a4-91ea-42f4b35a55b3',
    'BUCKET': "biomechanics-uploads83039-prod",
    'REGION': "us-west-2",
    'ROLE_ARN': "arn:aws:iam::756193201945:role/amplify-biomechanicsfrontend-prod-83039-authRole",
    'MQTT_PREFIX': "PROD",
    'NAME': 'PROD'
}

DEV_DEPLOYMENT = {
    'POOL_NAME': "biomechanicsfrontendf7e99b66_userpool_f7e99b66-dev",
    'POOL_ID': "us-west-2_2axuLRtXr",
    'POOL_ARN': "arn:aws:cognito-idp:us-west-2:756193201945:userpool/us-west-2_2axuLRtXr",
    'POOL_CLIENT_ID': '9edncgra4lj0dlt245sio7qpn',
    'ID_POOL': 'us-west-2:3c433c8f-9b94-44b5-83c0-bae84529e0f7',
    'BUCKET': "biomechanics-uploads161949-dev",
    'REGION': "us-west-2",
    'ROLE_ARN': "arn:aws:iam::756193201945:role/amplify-biomechanicsfrontend-dev-161949-authRole",
    'MQTT_PREFIX': "DEV",
    'NAME': 'DEV'
}


def main():
    local_commands = [PlotCommand(),
                      DebugCommand(),
                      ViewCommand(),
                      CompareCommand(),
                      TransferMarkersetCommand(),
                      PostProcessCommand(),
                      ExportCSVCommand(),
                      DescribeDatasetCommand(),
                      TransferReviewsCommand(),
                      CreateB3DCommand(),
                      CleanUpCommand(),
                      StatsCommand()]

    commands = [LsCommand(),
                DownloadCommand(),
                DownloadFilesCommand(),
                GenerateCreditsCommand(),
                UploadCommand(),
                AnalyticsCommand()]

    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(
        description='AddBiomechanics Command Line Interface')
    parser.add_argument('-u', '--username', type=str, default=None,
                        help='The username to use to log in to AddBiomechanics (if not provided, will attempt to load from ~/.addb_login.json, and then fallback to prompting for username and password)')
    parser.add_argument('-p', '--password', type=str, default=None,
                        help='The password to use to log in to AddBiomechanics (if not provided, will attempt to load from ~/.addb_login.json, and then fallback to prompting for username and password)')
    parser.add_argument('-d', '--deployment', type=str, default='dev', choices=['dev', 'prod'],
                        help='The deployment to interact with (default: dev)')

    # Split up by command
    subparsers = parser.add_subparsers(dest="command")

    # Add a parser for each command
    for command in commands:
        command.register_subcommand(subparsers)
    for command in local_commands:
        command.register_subcommand(subparsers)

    # Parse the arguments
    args = parser.parse_args()

    for command in local_commands:
        if command.run_local(args):
            return

    # Get deployment info
    deployment = DEV_DEPLOYMENT if args.deployment == 'dev' else PROD_DEPLOYMENT

    # Authenticate the user
    context = AuthContext(deployment)
    context.authenticate(args.username, args.password)

    # Call the main function with the parsed arguments
    for command in commands:
        # Each command is responsible for ignoring commands that aren't theirs
        command.run(context, args)


if __name__ == '__main__':
    main()
