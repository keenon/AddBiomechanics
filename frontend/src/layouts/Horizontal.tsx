import React, { Suspense, useState } from "react";
import { Container } from "react-bootstrap";
import { Outlet } from "react-router";
import Topbar from "./Topbar";
import Navbar from "./Navbar";
import Footer from "./Footer";
import MocapS3Cursor from '../state/MocapS3Cursor';

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
  cursor: MocapS3Cursor;
};

const HorizontalLayout = ({ cursor, children }: HorizontalLayoutProps) => {
  const [isMenuOpened, setIsMenuOpened] = useState(false);

  /**
   * Open the menu when having mobile screen
   */
  const openMenu = () => {
    setIsMenuOpened(!isMenuOpened);
    if (document.body) {
      if (isMenuOpened) {
        document.body.classList.remove("sidebar-enable");
      } else {
        document.body.classList.add("sidebar-enable");
      }
    }
  };

  return (
    <>
      <div className="wrapper">
        <div className="content-page">
          <div className="content">
            <Topbar
              isMenuOpened={isMenuOpened}
              openLeftMenuCallBack={openMenu}
              navCssClasses="topnav-navbar"
            />

            <Navbar cursor={cursor} isMenuOpened={isMenuOpened} />

            <Container fluid>
              <Outlet />
            </Container>
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
