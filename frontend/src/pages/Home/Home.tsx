import React from "react";
import "./Home.scss";
import { Link } from "react-router-dom";
import UserHeader from "../UserHeader/UserHeader";
import PubSubTest from "../../dead_components/PubSubTest/PubSubTest";

function Home() {
  return (
    <UserHeader>
      <>
        <div>Public Data Explorer:</div>
        <Link to="/my_uploads">Upload</Link>
        <PubSubTest />
      </>
    </UserHeader>
  );
}

export default Home;
