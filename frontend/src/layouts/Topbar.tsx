// @flow
import React, { useState } from "react";
import { Link } from "react-router-dom";
import classNames from "classnames";

// components
import LanguageDropdown from "../components/LanguageDropdown";
import ProfileDropdown from "../components/ProfileDropdown";

import logo from "../assets/images/logo-black-sm.svg";
import logoSmall from "../assets/images/logo-black-xs.svg";

type TopbarProps = {
  hideLogo?: boolean;
  navCssClasses?: string;
};

const Topbar = ({ hideLogo, navCssClasses }: TopbarProps) => {
  const navbarCssClasses = navCssClasses || "";
  const containerCssClasses = !hideLogo ? "container-fluid" : "";

  return (
    <>
      <div className={`navbar-custom ${navbarCssClasses}`}>
        <div className={containerCssClasses}>
          {!hideLogo && (
            <Link to="/" className="topnav-logo">
              <span className="topnav-logo-lg">
                <img src={logo} alt="logo" height="60" />
              </span>
              <span className="topnav-logo-sm">
                <img src={logoSmall} alt="logo" height="60" />
              </span>
            </Link>
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
        </div>
      </div>
    </>
  );
};

export default Topbar;
