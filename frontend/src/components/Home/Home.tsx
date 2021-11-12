import React from "react";
import "./Home.scss";
import { Link } from "react-router-dom";
import UserHeader from "../UserHeader/UserHeader";

function Home() {
  return (
    <UserHeader>
      <>
        <div>Public Data Explorer:</div>
        <Link to="/my_uploads">Upload</Link>
      </>
    </UserHeader>
  );
}

export default Home;
