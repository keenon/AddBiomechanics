import React, { Suspense, useState } from "react";
import { Container } from "react-bootstrap";
import Topbar from "./Topbar";
import Navbar from "./Navbar";
import Footer from "./Footer";
import Session from "../../model/Session";

const loading = () => <div className="text-center"></div>;

type HorizontalLayoutProps = {
  children?: any;
  session: Session;
};

const HorizontalLayout = ({ children, session }: HorizontalLayoutProps) => {
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
              session={session}
            />

            <Navbar isMenuOpened={isMenuOpened} />

            <Container fluid>
              {children}
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
