/*
 * Copyright 2017-2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"). You may not use this file except in compliance with
 * the License. A copy of the License is located at
 *
 *     http://aws.amazon.com/apache2.0/
 *
 * or in the "license" file accompanying this file. This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
 * CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions
 * and limitations under the License.
 */

import { HttpHandlerOptions } from '@aws-sdk/types';
import { HttpHandler, HttpRequest, HttpResponse } from '@aws-sdk/protocol-http';
import { buildQueryString } from '@aws-sdk/querystring-builder';
import axios, {
  AxiosRequestConfig,
  Method,
} from 'axios';

enum AWSS3ProviderUploadErrorStrings {
  UPLOAD_PAUSED_MESSAGE = 'paused',
}

export const SEND_UPLOAD_PROGRESS_EVENT = 'sendUploadProgress';
export const SEND_DOWNLOAD_PROGRESS_EVENT = 'sendDownloadProgress';

export type AxiosHttpHandlerOptions = HttpHandlerOptions & {
  progressCallback?: (progress: {
    loaded: number,
    total: number
  }) => void;
};

export class AxiosHttpHandler implements HttpHandler {
  destroy(): void {
    // Do nothing. TLS and HTTP/2 connection pooling is handled by the
    // browser.
  }

  handle(
    request: HttpRequest,
    options?: AxiosHttpHandlerOptions
  ): Promise<{ response: HttpResponse }> {
    console.log("Starting upload request");

    let path = request.path;
    if (request.query) {
      const queryString = buildQueryString(request.query);
      if (queryString) {
        path += `?${queryString}`;
      }
    }

    const port = request.port;
    const url = `${request.protocol}//${request.hostname}${port ? `:${port}` : ''
      }${path}`;

    const axiosRequest: AxiosRequestConfig = {};
    axiosRequest.url = url;
    axiosRequest.method = request.method as Method;
    axiosRequest.headers = request.headers;

    // The host header is automatically added by the browser and adding it explicitly in the
    // axios request throws an error https://github.com/aws-amplify/amplify-js/issues/5376
    // This is because the host header is a forbidden header for the http client to set
    // see https://developer.mozilla.org/en-US/docs/Glossary/Forbidden_header_name and
    // https://fetch.spec.whatwg.org/#forbidden-header-name
    // The reason we are removing this header here instead of in the aws-sdk's client
    // middleware is that the host header is required to be in the request signature and if
    // we remove it from the middlewares, then the request fails because the header is added
    // by the browser but is absent from the signature.
    delete axiosRequest.headers['host'];

    axiosRequest.data = request.body;

    axiosRequest.onUploadProgress = function (event) {
      console.log("SEND_UPLOAD_PROGRESS_EVENT: ", event);
      console.log("Options: ", options);
      if (options?.progressCallback) {
        options.progressCallback({
          loaded: event.loaded,
          total: event.total
        });
      }
    };
    axiosRequest.onDownloadProgress = function (event) {
      console.log("SEND_DOWNLOAD_PROGRESS_EVENT: ", event);
    };

    // From gamma release, aws-sdk now expects all response type to be of blob or streams
    axiosRequest.responseType = 'blob';

    // Timeout after 5 minutes -- want to make this as generous as possible, in case uploads have to wait for other uploads in a bulk upload scenario
    const requestTimeoutInMs = 5 * 60000;
    axiosRequest.timeout = requestTimeoutInMs;

    const raceOfPromises = [
      axios
        .request(axiosRequest)
        .then(response => {
          console.log("RobustHandler finished network call");
          return {
            response: new HttpResponse({
              headers: response.headers,
              statusCode: response.status,
              body: response.data,
            }),
          };
        })
        .catch(error => {
          // Error
          if (
            error.message !==
            AWSS3ProviderUploadErrorStrings.UPLOAD_PAUSED_MESSAGE
          ) {
            console.error(error);
            // logger.error(error.message);
          }
          // for axios' cancel error, we should re-throw it back so it's not considered an s3client error
          // if we return empty, or an abitrary error HttpResponse, it will be hard to debug down the line
          if (axios.isCancel(error) || error.response == null) {
            throw error;
          }
          // otherwise, we should re-construct an HttpResponse from the error, so that it can be passed down to other
          // aws sdk middleware (e.g retry, clock skew correction, error message serializing)
          const responseData = {
            statusCode: error.response?.status,
            body: error.response?.data,
            headers: error.response?.headers,
          };
          return {
            response: new HttpResponse(responseData),
          };
        }),
      requestTimeout(requestTimeoutInMs),
    ];
    return Promise.race(raceOfPromises);
  }
}

function requestTimeout(timeoutInMs: number = 0): Promise<never> {
  return new Promise((resolve, reject) => {
    if (timeoutInMs) {
      setTimeout(() => {
        console.log("Timed out request!");

        const timeoutError = new Error(
          `Request did not complete within ${timeoutInMs} ms`
        );
        timeoutError.name = 'TimeoutError';
        reject(timeoutError);
      }, timeoutInMs);
    }
  });
}
