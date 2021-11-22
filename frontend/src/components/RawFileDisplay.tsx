import React, { useState, useEffect } from "react";
import { Spinner } from "react-bootstrap";
import { LiveS3File } from "../state/LiveS3";

type RawFileDisplayProps = {
  file: LiveS3File | null;
};

const RawFileDisplay = (props: RawFileDisplayProps) => {
  let [loading, setLoading] = useState(true);
  let [contents, setContents] = useState("");

  useEffect(() => {
    if (props.file) {
      setLoading(true);
      props.file.downloadText().then((text: string) => {
        setContents(text);
        setLoading(false);
      });
    } else {
      setContents("[ no file ]");
      setLoading(false);
    }
  }, [props.file]);

  if (loading) {
    return <Spinner animation="border" />;
  } else {
    return <pre>{contents}</pre>;
  }
};

export default RawFileDisplay;
