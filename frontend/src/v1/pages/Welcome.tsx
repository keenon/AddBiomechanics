import React from "react";
import { Navigate } from "react-router-dom";

const Welcome = () => {
  return (
    <Navigate replace to="/search" />
  );
};

export default Welcome;
