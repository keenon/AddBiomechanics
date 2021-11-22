import React from "react";
import { NavLink, Link } from "react-router-dom";
import { Collapse } from "react-bootstrap";
import classNames from "classnames";

type NavbarProps = {
  isMenuOpened?: boolean;
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
                  <li className="nav-item">
                    <NavLink
                      to={"/public_data"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-brain me-1 vertical-middle"></i>
                      <span>Browse Public Data</span>
                    </NavLink>
                  </li>
                  <li className="nav-item">
                    <NavLink
                      to={"/my_data"}
                      className={({ isActive }) =>
                        "nav-item nav-link" + (isActive ? " active" : "")
                      }
                    >
                      <i className="mdi mdi-run me-1 vertical-middle"></i>
                      <span>Process and Share Data</span>
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
