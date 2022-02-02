import React from "react";
import { Outlet } from "react-router";
import MocapS3Cursor from '../state/MocapS3Cursor';
import { observer } from "mobx-react-lite";

type ErrorDisplayProps = {
  cursor: MocapS3Cursor;
};

const ErrorDisplay = observer(({ cursor }: ErrorDisplayProps) => {
  console.log("Rerendering ErrorDisplay");

  let errorBanner = null;
  if (cursor.hasNetworkErrors()) {
    let errors: string[] = cursor.getNetworkErrors();
    errorBanner = <>
      <div className="error-backdrop" />
      <div className="error-container">
        <div className="error-banner">
          {errors.join(" -- ")}
        </div>
      </div>
    </>;
  }

  return (<>
    {errorBanner}
    <Outlet />
  </>);
});

export default ErrorDisplay;
