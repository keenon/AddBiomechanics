import React from "react";
import { NavLink } from "react-router-dom";
import { Collapse } from "react-bootstrap";
import classNames from "classnames";
import MocapS3Cursor from '../state/MocapS3Cursor';

type NavbarProps = {
  isMenuOpened?: boolean;
  cursor: MocapS3Cursor;
};

const Navbar = (props: NavbarProps) => {
  // change the inputTheme value to light for creative theme
  const inputTheme = "dark";

  return (
    <>
      <div className="topnav">
        <div className="container-fluid">
          <nav
            className={classNames(
              "navbar",
              "navbar-expand-lg",
              "topnav-menu",
              "navbar-" + inputTheme
            )}
          >
            <Collapse in={props.isMenuOpened} className="navbar-collapse">
              <div>
                <ul className="navbar-nav" id="main-side-menu">

                  {/*Element shown only in small and medium devices*/}
                  <li className="nav-item d-lg-none">
                    <NavLink
                      to={"/profile"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-account me-1 vertical-middle"></i>
                      <span>Your Profile</span>
                    </NavLink>
                  </li>

                  {/*Elements shown in all devices*/}
                  <li className="nav-item">
                    <NavLink
                      to={"/search"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-magnify me-1 vertical-middle"></i>
                      <span>Search Public Data</span>
                    </NavLink>
                  </li>
                  <li className="nav-item">
                    <NavLink
                      to={"/data"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-run me-1 vertical-middle"></i>
                      <span>Process, Share and Analyze Data</span>
                    </NavLink>
                  </li>
                  <li className="nav-item">
                    <NavLink
                      to={"/server_status"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-server me-1 vertical-middle"></i>
                      <span>Processing Server Status</span>
                    </NavLink>
                  </li>

                  {/*Element shown only in small and medium devices*/}
                  <li className="nav-item d-lg-none">
                    <NavLink
                      to={"/logout"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-logout me-1 vertical-middle"></i>
                      <span>Logout</span>
                    </NavLink>
                  </li>

                </ul>
              </div>
            </Collapse>
          </nav>
        </div>
      </div>
    </>
  );
};

export default Navbar;
