import React, { Suspense, useState } from "react";
import { Container } from "react-bootstrap";
import { Outlet } from "react-router";
import Topbar from "./Topbar";
import Navbar from "./Navbar";
import Footer from "./Footer";

const loading = () => <div className="text-center"></div>;

type HorizontalLayoutProps = {
  children?: any;
};

const HorizontalLayout = ({ children }: HorizontalLayoutProps) => {
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
          <div className="content mb-5">
            <Topbar
              isMenuOpened={isMenuOpened}
              openLeftMenuCallBack={openMenu}
              navCssClasses="topnav-navbar"
            />

            <Navbar isMenuOpened={isMenuOpened} />

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
