// @flow
import React, { Suspense, useCallback, useEffect, useState } from "react";
import { Container } from "react-bootstrap";
import Topbar from "./Topbar";
import Footer from "./Footer";

const loading = () => <div className=""></div>;

type VerticalLayoutProps = {
  children?: any;
};

const VerticalLayout = ({ children }: VerticalLayoutProps) => {
  return (
    <>
      <div className="wrapper">
        <div className="content-page">
          <div className="content">
            <Suspense fallback={loading()}>
              <Topbar hideLogo={true} />
            </Suspense>
            <Container fluid>
              <Suspense fallback={loading()}>{children}</Suspense>
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
export default VerticalLayout;
