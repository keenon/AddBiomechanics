import React from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/images/logo-alone.svg";

const ComingSoon = () => {
  const navigate = useNavigate();
  return (
    <>
      <div className="container col-xxl-8 px-4 py-5">
        <div className="row flex-lg-row-reverse align-items-center g-5 py-5">
          <div className="col-10 col-sm-8 col-lg-6">
            <img src={logo} className="d-block mx-lg-auto img-fluid" alt="Bootstrap Themes" width="700" height="500" loading="lazy" />
          </div>
          <div className="col-lg-6" style={{ position: "relative" }}>
            <h1 className="display-5 fw-bold lh-1 mb-3">Coming Soon!</h1>
            <p className="lead">This section is still under construction. Help us construct the world's best biomechanics dataset, and enable data-driven breakthroughs in human movement science.</p>
            <div className="d-grid gap-2 d-md-flex justify-content-md-start">
              <a type="button" className="btn btn-primary btn-lg px-4 me-md-2" href="/my_data" onClick={(e) => {
                e.preventDefault();
                navigate("/my_data");
              }}>Process and Share Data</a>
              <a type="button" className="btn btn-outline-secondary btn-lg px-4" href="/public_data"
                onClick={(e) => {
                  e.preventDefault();
                  navigate("/");
                }}>Back Home</a>
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default ComingSoon;
