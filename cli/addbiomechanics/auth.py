import argparse
import os
import boto3
import requests
from typing import Dict
import json


class AuthContext:
    deployment: Dict[str, str]
    user_identity_id: str
    user_email: str
    aws_cred: Dict[str, str]
    aws_session: boto3.Session
    username: str = None
    password: str = None

    def __init__(self, deployment: Dict[str, str]):
        self.deployment = deployment

    def authenticate(self, username: str = None, password: str = None):
        username, password = self.ensure_login(username, password)
        self.username = username
        self.password = password
        id_token = self.get_id_token(
            self.deployment['POOL_CLIENT_ID'], username, password)
        self.user_identity_id = self.get_user_identity_id(
            id_token, self.deployment['REGION'], self.deployment['POOL_ID'], self.deployment['ID_POOL'])
        self.user_email = username
        print('Got user identity: '+self.user_identity_id)
        self.aws_cred = self.get_temp_aws_access_keys(
            id_token, self.user_identity_id, self.deployment['REGION'], self.deployment['POOL_ID'])
        self.aws_session = self.get_temp_aws_session(
            self.aws_cred, self.deployment['REGION'])

    def refresh(self):
        self.authenticate(self.username, self.password)

    def ensure_login(self, username: str = None, password: str = None, force_retype: bool = False):
        home_dir = os.path.expanduser("~")
        login_file_path = os.path.join(home_dir, ".addb_login.json")

        # 1. Check if there is a username and password passed in
        if username is not None and password is not None and not force_retype:
            login_info = {"username": username, "password": password}

            print('Saving login info to ' + login_file_path)
            with open(login_file_path, "w") as login_file:
                json.dump(login_info, login_file)

            return (username, password)
        elif os.path.exists(login_file_path) and not force_retype:
            with open(login_file_path, "r") as login_file:
                login_info = json.load(login_file)
                return (login_info["username"], login_info["password"])
        else:
            if username is None or force_retype:
                username = input("Please enter your username: ")
            if password is None or force_retype:
                password = input(
                    "Please enter your password for " + username + ": ")
            login_info = {"username": username, "password": password}

            with open(login_file_path, "w") as login_file:
                json.dump(login_info, login_file)
            return (username, password)

    def get_id_token(self, poolClientId: str, username: str, password: str) -> str:
        # Authenticate with AWS Cognito
        client = boto3.client('cognito-idp', region_name='us-west-2')
        while True:
            try:
                resp = client.initiate_auth(
                    # UserPoolId=deployment['POOL_ID'],
                    ClientId=poolClientId,
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters={
                        'USERNAME': username,
                        'PASSWORD': password
                    }
                )
                id_token = resp['AuthenticationResult']['IdToken']
                print('Successfully logged in as '+username+'!')
                return id_token
            except Exception as e:
                print('Login failed! Please try again.')
                print(e)
                username, password = self.ensure_login(force_retype=True)

    def get_user_identity_id(self, id_token: str, region: str, userPoolId: str, identityPool: str) -> str:
        # Use the temporary credentials to get the Cognito Identity ID
        cognito_client = boto3.client('cognito-identity', region_name=region)
        identity_id = cognito_client.get_id(
            IdentityPoolId=identityPool,
            AccountId='756193201945',
            Logins={
                'cognito-idp.'+region+'.amazonaws.com/'+userPoolId: id_token
            }
        )
        return identity_id['IdentityId']

    def get_temp_aws_access_keys(self, id_token: str, identity_id: str, region: str, userPoolId: str):
        cognito_client = boto3.client('cognito-identity', region_name=region)
        aws_cred = cognito_client.get_credentials_for_identity(
            IdentityId=identity_id,
            Logins={
                'cognito-idp.'+region+'.amazonaws.com/'+userPoolId: id_token
            }
        )
        return aws_cred['Credentials']

    def get_temp_aws_session(self, aws_cred: Dict[str, str], region: str, role_arn: str = None):
        aws_session = boto3.Session(
            aws_access_key_id=aws_cred['AccessKeyId'],
            aws_secret_access_key=aws_cred['SecretKey'],
            aws_session_token=aws_cred['SessionToken'],
            region_name=region
        )

        return aws_session
