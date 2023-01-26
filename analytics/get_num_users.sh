#!/bin/bash
aws cognito-idp list-users --user-pool-id us-west-2_vRDVX9u35 > users.json
node parse_users.js
