import React from "react";
import UserHeader from "../UserHeader/UserHeader";
import "./LeftTabs.scss";

type LeftTabsProps = {
  tabs: React.ReactFragment[];
  active: number;
};

const LeftTabs = (props: React.PropsWithChildren<LeftTabsProps>) => {
  let tabs = [];
  for (let i = 0; i < props.tabs.length; i++) {
    tabs.push(
      <div
        key={i}
        className={
          "LeftTabs__tab" + (i == props.active ? " LeftTabs__tab-active" : "")
        }
      >
        {props.tabs[i]}
      </div>
    );
  }

  return (
    <div className="LeftTabs">
      <div className="LeftTabs__tabs">{tabs}</div>
      <div className="LeftTabs__body">{props.children}</div>
    </div>
  );
};

export default LeftTabs;
