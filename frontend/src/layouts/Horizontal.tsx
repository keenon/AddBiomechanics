// @flow
import React, { Suspense, useEffect, useState } from "react";
import { Container } from "react-bootstrap";
import Topbar from "./Topbar";
// import Navbar from "./Navbar";
import Footer from "./Footer";

// TODO:
// code splitting and lazy loading
// https://blog.logrocket.com/lazy-loading-components-in-react-16-6-6cea535c0b52
/*
const Topbar = React.lazy(() => import("../Topbar"));
const Navbar = React.lazy(() => import("./Navbar"));
const Footer = React.lazy(() => import("../Footer"));
*/

const loading = () => <div className="text-center"></div>;

type HorizontalLayoutProps = {
  children?: any;
};

const HorizontalLayout = ({ children }: HorizontalLayoutProps) => {
  return (
    <>
      <div className="wrapper">
        <div className="content-page">
          <div className="content">
            <Topbar navCssClasses="topnav-navbar" />

            {/*
            <Suspense fallback={loading()}>
              <Navbar isMenuOpened={isMenuOpened} />
            </Suspense>
            */}

            <Container fluid>{children}</Container>
          </div>

          <Suspense fallback={loading()}>
            <Footer />
          </Suspense>
        </div>
      </div>
    </>
  );
};

export default HorizontalLayout;
