import React, { useRef, useState, useEffect } from "react";
import "./UserData.scss";
import { Navigate } from "react-router-dom";
import { Trans } from "react-i18next";
import Amplify, { Storage } from "aws-amplify";
import UserHeader from "../UserHeader/UserHeader";
import {
  S3ProviderListOutput,
  S3ProviderListOutputItem,
} from "@aws-amplify/storage";

function UserData() {
  const uploadInput = useRef(null);

  const [files, setFiles] = useState([] as S3ProviderListOutput);

  // Put a file into Storage
  // const result = Storage.put("test.txt", "Hello");

  // Delete a file
  // Storage.remove("test.txt", { level: "protected" });

  // Download a file
  /*
  Storage.get('filename.txt', {
      download: true,
      progressCallback(progress) {
          console.log(`Downloaded: ${progress.loaded}/${progress.total}`);
      }
  }).then((result) => {
    // data.Body is a Blob
    result.Body.text().then(string => { 
      // handle the String data return String 
    });
  });
  */

  const refreshFileList = () => {
    Storage.list("", { level: "protected" })
      .then((result: S3ProviderListOutput) => {
        console.log(result);
        setFiles(result);
      })
      .catch((err: Error) => console.log(err));
  };

  // List the existing files
  useEffect(() => {
    refreshFileList();
  }, []);

  const uploadFiles = () => {
    if (uploadInput.current != null) {
      const uploadElem: HTMLInputElement = uploadInput.current;
      const fileList: FileList | null = uploadElem.files;
      if (fileList != null) {
        for (let i = 0; i < fileList.length; i++) {
          const file = fileList[i];
          try {
            Storage.put(file.name, file, {
              level: "protected",
              completeCallback: (event) => {
                console.log(`Successfully uploaded ${event.key}`);
              },
              progressCallback: (progress) => {
                console.log(`Uploaded: ${progress.loaded}/${progress.total}`);
                if (progress.loaded == progress.total) {
                  refreshFileList();
                }
              },
              errorCallback: (err) => {
                console.error("Unexpected error while uploading", err);
              },
            });
          } catch (error) {
            console.log("Error uploading file: ", error);
          }
        }
      }
    }
  };

  const deleteFile = (key?: string) => {
    if (key != null) {
      console.log('Removing key "' + key + '"');
      Storage.remove(key, { level: "protected" })
        .then((result) => {
          console.log(result);
          refreshFileList();
        })
        .catch((e: Error) => {
          console.log(e);
        });
    }
  };

  const downloadJson = (key?: string) => {
    if (key != null) {
      Storage.get(key, { download: true, cacheControl: "no-cache" }).then(
        (result) => {
          if (result != null && result.Body != null) {
            // data.Body is a Blob
            (result.Body as Blob).text().then((text: string) => {
              console.log(text);
            });
          }
        }
      );
    }
  };

  const downloadFile = (key?: string) => {
    if (key != null) {
      Storage.get(key, {
        level: "protected",
      }).then((signedURL) => {
        const link = document.createElement("a");
        link.href = signedURL;
        link.target = "#";
        link.click();
      });
    }
  };

  let fileElems: React.ReactFragment[] = [];
  for (let i = 0; i < files.length; i++) {
    const file: S3ProviderListOutputItem = files[i];
    fileElems.push(
      <tr key={file.key}>
        <td>{file.key}</td>
        <td>
          <button onClick={() => deleteFile(file.key)}>Delete</button>
        </td>
        <td>
          <button onClick={() => downloadFile(file.key)}>Download</button>
        </td>
      </tr>
    );
  }

  return (
    <UserHeader>
      <>
        <div>My Data Folder:</div>
        <input type="file" multiple ref={uploadInput} />
        <button onClick={uploadFiles}>Upload</button>
        <div>Files:</div>
        <table>
          <thead>
            <tr>
              <td>Name</td>
              <td>Delete</td>
              <td>Download</td>
            </tr>
          </thead>
          <tbody>{fileElems}</tbody>
        </table>
      </>
    </UserHeader>
  );
}

export default UserData;
