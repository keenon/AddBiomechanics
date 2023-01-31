// @flow
import React from "react";
import { Link } from "react-router-dom";
import classNames from "classnames";

// components
import ProfileDropdown from "../components/ProfileDropdown";

import logo from "../assets/images/logo-with-text.svg";
import logoSmall from "../assets/images/logo-alone.svg";

import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

type TopbarProps = {
  hideLogo?: boolean;
  isMenuOpened?: boolean;
  openLeftMenuCallBack?: () => void;
  navCssClasses?: string;
};

const Topbar = (props: TopbarProps) => {
  const navbarCssClasses = props.navCssClasses || "";
  const containerCssClasses = !props.hideLogo ? "container-fluid" : "";

  /*
  <span style={{color: "rgba(0,0,0,.9)" }}>add</span><span className="text-primary">biomechanics</span>
  */
  return (
    <>
      <div className={`navbar-custom ${navbarCssClasses}`}>
        <div className={containerCssClasses}>
          {!props.hideLogo && (
            <a href="https://addbiomechanics.org" className="topnav-logo">
              <span className="topnav-logo-lg">
                <img src={logo} alt="logo" height="60" />
              </span>
              <span className="topnav-logo-sm">
                <img src={logoSmall} alt="logo" height="60" />
              </span>
            </a>
          )}

          <ul className="list-unstyled topbar-menu float-end mb-0">
            {/*
            <li className="dropdown notification-list topbar-dropdown d-none d-lg-block">
              <LanguageDropdown />
            </li>
            */}
            <li className="dropdown notification-list topbar-dropdown d-lg-block">
              <ProfileDropdown />
            </li>
          </ul>

          <Link
            to="#"
            className={classNames("navbar-toggle", {
              open: props.isMenuOpened,
            })}
            onClick={(e) => {
              e.preventDefault();
              if (props.openLeftMenuCallBack) {
                props.openLeftMenuCallBack();
              }
            }}
          >
            <div className="lines">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </Link>
        </div>

        <div>
            <ToastContainer />
        </div>
      </div>
    </>
  );
};

export default Topbar;
