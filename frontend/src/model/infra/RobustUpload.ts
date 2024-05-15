import { S3Client, PutObjectRequest, PutObjectCommand, PutObjectCommandOutput, CreateMultipartUploadCommand, UploadPartCommand, CompleteMultipartUploadCommandInput, CompleteMultipartUploadCommand, CompletedPart, AbortMultipartUploadCommand, ListPartsCommand } from '@aws-sdk/client-s3';
import { Credentials, getAmplifyUserAgent } from '@aws-amplify/core';
import * as events from 'events';
import { AxiosHttpHandler, SEND_UPLOAD_PROGRESS_EVENT, AxiosHttpHandlerOptions } from './RobustHandler'; // @aws-amplify/storage/src/providers/axios-http-handler

const MIN_PART_SIZE = 5 * 1024 * 1024; // in MB
const QUEUE_SIZE = 4;

export declare interface Part {
  bodyPart: any;
  length: number;
  partNumber: number;
  emitter: events.EventEmitter;
  etag?: string;
  _lastUploadedBytes: number;
}

class RobustUpload {
  region: string;
  bucket: string;
  key: string;
  body: any;
  contentType: string;
  params: PutObjectRequest;

  cancel: boolean = false;
  completedParts: CompletedPart[] = [];

  // Progress reporting
  bytesUploaded: number = 0;
  totalBytesToUpload: number = 0;

  client: S3Client;

  constructor(client: S3Client, region: string, bucket: string, key: string, body: string | Object | Blob | File, contentType: string, params?: PutObjectRequest) {
    this.region = region;
    this.bucket = bucket;
    this.key = key;
    this.body = body;

    if (this.isGenericObject(body)) {
      // Any javascript object
      this.body = JSON.stringify(body);
    } else {
      // Files, arrayBuffer etc
      this.body = body;
    }
    this.totalBytesToUpload = this.byteLength(this.body);

    this.contentType = contentType;

    this.params = {
      Key: this.key,
      Bucket: this.bucket,
      Body: this.body,
      ContentType: this.contentType
    };
    Object.assign(this.params, params);

    /*
    const INVALID_CRED = { accessKeyId: '', secretAccessKey: '' };
    const credentialsProvider = async () => {
      try {
        const credentials = await Credentials.get();
        if (!credentials) return INVALID_CRED;
        const cred = Credentials.shear(credentials);
        return cred;
      } catch (error) {
        console.warn('credentials provider error', error);
        return INVALID_CRED;
      }
    }

    this.client = new S3Client({
      region: this.region,
      // Using provider instead of a static credentials, so that if an upload task was in progress, but credentials gets
      // changed or invalidated (e.g user signed out), the subsequent requests will fail.
      credentials: credentialsProvider,
      customUserAgent: getAmplifyUserAgent(),
      requestHandler: new AxiosHttpHandler()
    });
    */
   this.client = client;
  }

  private isGenericObject(body: any): body is Object {
    if (body !== null && typeof body === 'object') {
      try {
        return !(this.byteLength(body) >= 0);
      } catch (error) {
        // If we cannot determine the length of the body, consider it
        // as a generic object and upload a stringified version of it
        return true;
      }
    }
    return false;
  }

  private byteLength(input: any) {
    if (input === null || input === undefined) return 0;
    if (typeof input.byteLength === 'number') {
      return input.byteLength;
    } else if (typeof input.length === 'number') {
      return input.length;
    } else if (typeof input.size === 'number') {
      return input.size;
    } else if (typeof input.path === 'string') {
      // return require('fs').lstatSync(input.path).size;
    } else {
      throw new Error('Cannot determine length of ' + input);
    }
  }

  private createParts(): Part[] {
    const parts: Part[] = [];
    for (let bodyStart = 0; bodyStart < this.totalBytesToUpload;) {
      const bodyEnd = Math.min(
        bodyStart + MIN_PART_SIZE,
        this.totalBytesToUpload
      );
      const sliceLength = bodyEnd - bodyStart;
      parts.push({
        bodyPart: this.body.slice(bodyStart, bodyEnd),
        length: sliceLength,
        partNumber: parts.length + 1,
        emitter: new events.EventEmitter(),
        _lastUploadedBytes: 0,
      });
      bodyStart += MIN_PART_SIZE;
    }
    return parts;
  }

  private async createMultiPartUpload(): Promise<string> {
    const createMultiPartUploadCommand = new CreateMultipartUploadCommand(
      this.params
    );
    const response = await this.client.send(createMultiPartUploadCommand);
    return response.UploadId || '';
  }

  /**
   * @private Not to be extended outside of tests
   * @VisibleFotTesting
   */
  protected async uploadParts(uploadId: string, parts: Part[], progressCallback: (progress: {
    loaded: number,
    total: number
  }) => void) {
    console.log("Uploading parts", parts);

    let totalSize = 0;
    let loadedPerResult: number[] = [];
    for (let i = 0; i < parts.length; i++) {
      totalSize += parts[i].length;
      loadedPerResult.push(0);
    }
    const recomputeTotal = () => {
      let totalLoaded = 0;
      for (let i = 0; i < loadedPerResult.length; i++) {
        totalLoaded += loadedPerResult[i];
      }
      progressCallback({
        loaded: totalLoaded,
        total: totalSize
      });
    };

    try {
      const allResults = await Promise.all(
        parts.map(async (part, index) => {
          this.setupEventListener(part);
          const {
            Key,
            Bucket,
            SSECustomerAlgorithm,
            SSECustomerKey,
            SSECustomerKeyMD5,
          } = this.params;
          const options: AxiosHttpHandlerOptions = {
            progressCallback: (partProgress) => {
              loadedPerResult[index] = partProgress.loaded;
              recomputeTotal();
            }
          };
          const res = await this.client.send(
            new UploadPartCommand({
              PartNumber: part.partNumber,
              Body: part.bodyPart,
              UploadId: uploadId,
              Key,
              Bucket,
              ...(SSECustomerAlgorithm && { SSECustomerAlgorithm }),
              ...(SSECustomerKey && { SSECustomerKey }),
              ...(SSECustomerKeyMD5 && { SSECustomerKeyMD5 }),
            }),
            options
          );
          return res;
        })
      );
      // The order of resolved promises is the same as input promise order.
      for (let i = 0; i < allResults.length; i++) {
        this.completedParts.push({
          PartNumber: parts[i].partNumber,
          ETag: allResults[i].ETag,
        });
      }
    } catch (error) {
      console.error(
        'error happened while uploading a part. Cancelling the multipart upload',
        error
      );
      this.cancelUpload();
      return;
    }
  }

  private async finishMultiPartUpload(uploadId: string) {
    console.log(this.completedParts);
    const input: CompleteMultipartUploadCommandInput = {
      Bucket: this.params.Bucket,
      Key: this.params.Key,
      UploadId: uploadId,
      MultipartUpload: { Parts: this.completedParts },
    };
    const completeUploadCommand = new CompleteMultipartUploadCommand(input);
    try {
      const data = await this.client.send(completeUploadCommand);
      return data.Key;
    } catch (error) {
      console.error(
        'error happened while finishing the upload. Cancelling the multipart upload',
        error
      );
      this.cancelUpload();
      // Rethrow this error so that upstream code can respond correctly
      throw error;
    }
  }

  private async checkIfUploadCancelled(uploadId: string) {
    if (this.cancel) {
      let errorMessage = 'Upload was cancelled.';
      try {
        await this.cleanup(uploadId);
      } catch (error: any) {
        errorMessage += ` ${error.message}`;
      }
      throw new Error(errorMessage);
    }
  }

  public cancelUpload() {
    this.cancel = true;
  }

  private async cleanup(uploadId: string) {
    // Reset this's state
    this.body = null;
    this.completedParts = [];
    this.bytesUploaded = 0;
    this.totalBytesToUpload = 0;

    const input = {
      Bucket: this.params.Bucket,
      Key: this.params.Key,
      UploadId: uploadId,
    };

    await this.client.send(new AbortMultipartUploadCommand(input));

    // verify that all parts are removed.
    const data = await this.client.send(new ListPartsCommand(input));

    if (data && data.Parts && data.Parts.length > 0) {
      throw new Error('Multi Part upload clean up failed');
    }
  }

  private removeEventListener(part: Part) {
    part.emitter.removeAllListeners(SEND_UPLOAD_PROGRESS_EVENT);
  }

  private setupEventListener(part: Part) {
    part.emitter.on(SEND_UPLOAD_PROGRESS_EVENT, progress => {
      this.progressChanged(
        part.partNumber,
        progress.loaded - part._lastUploadedBytes
      );
      part._lastUploadedBytes = progress.loaded;
    });
  }

  private progressChanged(partNumber: number, incrementalUpdate: number) {
    this.bytesUploaded += incrementalUpdate;
    /*
    this.emitter.emit(SEND_UPLOAD_PROGRESS_EVENT, {
      loaded: this.bytesUploaded,
      total: this.totalBytesToUpload,
      part: partNumber,
      key: this.params.Key,
    });
    */
  }

  public async upload(progressCallback: (progress: {
    loaded: number,
    total: number
  }) => void): Promise<any> {
    /*
    this.emitter.on(SEND_UPLOAD_PROGRESS_EVENT, progress => {
      progressCallback(progress);
    });
    */
    // if (this.totalBytesToUpload == 0) {
    if (this.totalBytesToUpload <= MIN_PART_SIZE) {
      // Multipart upload is not required. Upload the sanitized body as is
      const putObjectCommand = new PutObjectCommand(this.params);
      console.log("Sending PutObjectCommand command (single part upload)");

      // We wrap this in a promise to ensure that we resolve when the progress indicator reaches 100%, 
      // since the axios handler will sometimes fail to resolve if internet cuts out just as the upload is finishing.

      return new Promise<PutObjectCommandOutput>((resolve, reject) => {
        const options: AxiosHttpHandlerOptions = {
          progressCallback: (progress) => {
            progressCallback(progress);
            if (progress.loaded >= progress.total) {
              // This is a bad use of types, but hopefully is fine
              resolve(null as any);
            }
          }
        };
        this.client.send(putObjectCommand, options).then(resolve).catch(reject);
      });
    } else {
      console.log("Creating multi-part upload");
      // Step 1: Initiate the multi part upload
      const uploadId = await this.createMultiPartUpload();

      // Step 2: Upload chunks in parallel as requested
      const numberOfPartsToUpload = Math.ceil(
        this.totalBytesToUpload / MIN_PART_SIZE
      );

      const parts: Part[] = this.createParts();
      let totalUploaded = 0;
      for (
        let start = 0;
        start < numberOfPartsToUpload;
        start += QUEUE_SIZE
      ) {
        /** This first block will try to cancel the upload if the cancel
         *	request came before any parts uploads have started.
        **/
        await this.checkIfUploadCancelled(uploadId);

        const totalUploadedSoFar = totalUploaded;
        // Upload as many as `queueSize` parts simultaneously
        await this.uploadParts(
          uploadId,
          parts.slice(start, start + QUEUE_SIZE),
          (progress: {loaded: number, total: number}) => {
            progressCallback({
              loaded: totalUploadedSoFar + progress.loaded,
              total: this.totalBytesToUpload
            });
          }
        );
        totalUploaded = totalUploadedSoFar + parts.slice(start, start + QUEUE_SIZE).reduce((acc, part) => acc + part.length, 0);

        /** Call cleanup a second time in case there were part upload requests
         *  in flight. This is to ensure that all parts are cleaned up.
         */
        await this.checkIfUploadCancelled(uploadId);
      }

      parts.map(part => {
        this.removeEventListener(part);
      });

      // Step 3: Finalize the upload such that S3 can recreate the file
      return await this.finishMultiPartUpload(uploadId);
    }
  }
};

export default RobustUpload;