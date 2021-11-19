/*
Copyright 2017 - 2017 Amazon.com, Inc. or its affiliates. All Rights Reserved.
Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with the License. A copy of the License is located at
    http://aws.amazon.com/apache2.0/
or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
*/




var express = require('express')
var bodyParser = require('body-parser')
var awsServerlessExpressMiddleware = require('aws-serverless-express/middleware')
const aws = require('aws-sdk');

// declare a new express app
var app = express()
app.use(bodyParser.json())
app.use(awsServerlessExpressMiddleware.eventContext())

// Enable CORS for all methods
app.use(function(req, res, next) {
  res.header("Access-Control-Allow-Origin", "*")
  res.header("Access-Control-Allow-Headers", "*")
  next()
});

/**********************
 * Example get method *
 **********************/

app.get('/', function(req, res) {
  // Add your code here
  res.json({success: 'get call succeed!', url: req.url});
});

app.put('/', function(req, res) {
  // Add your code here
  res.json({success: 'put call succeed!', url: req.url, body: req.body})
});

app.delete('/', function(req, res) {
  // Add your code here
  res.json({success: 'delete call succeed!', url: req.url});
});

app.post('/', function(req, res) {

  const iot = new aws.Iot({region: 'us-west-2', apiVersion: '2015-05-28', endpoint: 'https://iot.us-west-2.amazonaws.com'});

  const policyName = "WebRPC";
  const id = req.apiGateway.event.requestContext.identity.cognitoIdentityId;

  console.log("Create policy and attach with cognito identity id: " + id);
  var params = {policyName: policyName};
  iot.getPolicy(params , function(err, data) {
        if (err) {
             var policy = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Action": ["*"],"Resource": ["*"]}]};
             var policyDoc = JSON.stringify(policy);

             console.log("Creating policy: " + policyName + " with doc: " + policyDoc);

             var params = {
                     policyName: policyName,
                     policyDocument: policyDoc
                     };

             iot.createPolicy(params , function(err, data) {
                 if (err) {
                      //console.error(err);
                      if (err.code !== 'ResourceAlreadyExistsException') {
                         console.log(err);
                         res.json({error: err, url: req.url, body: req.body});
                      }
                 }
                 else {
                    console.log("CreatePolicy response=" + data);
                    var params = {policyName: policyName, target: id};

                    console.log("Attach IoT Policy: " + policyName + " with cognito identity id: " + id);
                    iot.attachPolicy(params, function(err, data) {
                         if (err) {
                               //console.error(err);
                               if (err.code !== 'ResourceAlreadyExistsException') {
                                  console.log(err);
                                  res.json({error: err, url: req.url, body: req.body});
                               }
                               else {
                                 console.log("IoT policy already attached");
                                 res.json({success: 'No-op, already attached'});
                               }
                          }
                         else  {
                            console.log(data);
                            res.json({success: 'Create and attach policy call succeed!', url: req.url, body: req.body});
                         }
                     });
                 }
             });
        }
        else {
           console.log("Policy " + policyName + " already exists..");

           var params = {policyName: policyName, target: id};

           console.log("Attach IoT Policy: " + policyName + " with cognito identity id: " + id);
           iot.attachPolicy(params, function(err, data) {
                if (err) {
                      //console.error(err);
                      if (err.code !== 'ResourceAlreadyExistsException') {
                         console.log(err);
                         res.json({error: err, url: req.url, body: req.body});
                      }
                      else {
                        console.log("IoT policy already attached");
                        res.json({success: 'No-op, already attached'});
                      }
                 }
                else  {
                   console.log(data);
                   res.json({success: 'Create and attach policy call succeed!', url: req.url, body: req.body});
                }
            });
        }
    });
});

app.listen(3000, function() {
    console.log("App started")
});

// Export the app object. When executing the application local this does nothing. However,
// to port it to AWS Lambda we will create a wrapper around that will load the app from
// this file
module.exports = app

