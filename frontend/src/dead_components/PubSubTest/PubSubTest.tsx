import React, { useState, useEffect } from "react";
import { PubSub } from "aws-amplify";

const PubSubTest = () => {
  let [msgs, setMsgs] = useState([] as string[]);
  useEffect(() => {
    // Subscribe to PubSub
    PubSub.subscribe("/").subscribe({
      next: (data) => console.log("Message received", data),
      error: (error) => {
        console.error("Error on PubSub.subscribe()");
        console.error(error);
      },
      complete: () => console.log("Done"),
    });
  }, []);

  return (
    <div>
      {msgs.map((m) => (
        <div key="m">{m}</div>
      ))}
      <div>
        <button
          onClick={() => {
            console.log("Attempting to publish");
            PubSub.publish("/", { msg: "Hello to all subscribers!" });
          }}
        >
          Send!
        </button>
      </div>
    </div>
  );
};

export default PubSubTest;
