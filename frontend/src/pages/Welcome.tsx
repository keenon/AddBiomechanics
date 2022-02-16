import React from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/images/logo-black.svg";
import plot from "../assets/images/relative-performance-plot.png";
import unifiedDataset from "../assets/images/public-unified-dataset.png";
import stanford from "../assets/images/stanford.png";

const Welcome = () => {
  const navigate = useNavigate();
  return (
    <>
      <div className="container col-xxl-8 px-4 py-5">
        <div className="row flex-lg-row-reverse align-items-center g-5 py-5">
          <div className="col-10 col-sm-8 col-lg-6">
            <img src={logo} className="d-block mx-lg-auto img-fluid" alt="Bootstrap Themes" width="700" height="500" loading="lazy" />
          </div>
          <div className="col-lg-6" style={{ position: "relative" }}>
            <div style={{
              color: "red",
              position: "absolute",
              top: -30,
              left: 10,
              fontSize: '20px',
              transform: 'rotate(-30deg)'
            }}>Early Beta!</div>
            <h1 className="display-5 fw-bold lh-1 mb-3">Automated OpenSim <span style={{ color: 'rgb(114 124 245)' }}>Scaling &amp; Marker Registration</span></h1>
            <p className="lead">Upload your <code>*.trc</code> or <code>*.c3d</code> marker files and <b>get an automatically scaled OpenSim model and IK done in minutes</b>. Share your data with the community with one click. Hosted by Stanford University.</p>
            <div className="d-grid gap-2 d-md-flex justify-content-md-start">
              <a type="button" className="btn btn-primary btn-lg px-4 me-md-2" href="/my_data" onClick={(e) => {
                e.preventDefault();
                navigate("/my_data");
              }}>Process and Share Data</a>
              <a type="button" className="btn btn-outline-secondary btn-lg px-4" href="/public_data"
                onClick={(e) => {
                  e.preventDefault();
                  navigate("/public_data");
                }}>Browse Public Data</a>
            </div>
          </div>
        </div>
        <hr />
        <div className="row">
          <div className="col-md-4">
            <div>
              <img src={plot} style={{ width: '100%' }} />
            </div>
          </div>
          <div className="col-md-8 align-self-center">
            <h2>Better, more consistent results</h2>
            <p className="lead">
              In our evaluations, our automated approach produces a <b>~40% lower RMSE than hand-scaling</b> OpenSim models.
              We compared against 4 different experts, across 35 hand-scaled trials. <b>But don't take our word for it!</b> The tool comes with easy built-in evaluations, if you upload a hand-scaled <code>*.osim</code> model and OpenSim <code>*.mot</code> IK results to compare against, it can produce comparison reports on your specific data.
            </p>
          </div>
        </div>
        <hr />
        <div className="row">
          <div className="col-md-6 align-self-center">
            <h2>Global data collaboration</h2>
            <p className="lead">
              Data processed with BiomechNet is automatically cleaned, anonymized, and converted into standard formats ready for publication. <b>Unless you explicitly opt-out, uploaded data will be automatically shared with the community 6 months after your upload</b>. You're allowed to opt-out of sharing for as long as you want, for free, but we hope you'll choose to share your data once your publication is published.
              Our aim in providing this tool as a free service to the biomechanics community is to increase the amount of publicly available biomechanics data for other researchers to use.
            </p>
          </div>
          <div className="col-md-6">
            <img src={unifiedDataset} style={{ width: '100%' }} />
          </div>
        </div>
        <hr />
        <div className="row">
          <div className="col-md-12">
            <h2>Our mission: an "ImageNet moment" in Biomechanics</h2>
            <p className="lead">
              In the last decade, research breakthroughs have often followed the creation of large, high-quality, public datasets.
              Machine learning researchers often speak in wistful tones about waiting for a research field's “ImageNet moment,” when a large new dataset allows the application of data-hungry modern machine learning methods, and previously impossible problems are toppled seemingly overnight. When <a href="https://www.image-net.org/">ImageNet</a>, a dataset containing 1.4 million labeled images, was originally published, it kicked off the deep learning revolution in computer vision. Within just a handful of years, as a direct result, we went from struggling to classify images of a car to deploying self-driving cars on city streets. We aim to bring about an ImageNet moment in the field of human movement biomechanics. In homage to ImageNet, we call our proposed project BiomechNet.
            </p>
          </div>
        </div>
        <hr />
        <div className="row">
          <div className="col-md-4 align-self-center text-center">
            <img src={stanford} style={{ width: '60%' }} />
          </div>
          <div className="col-md-8 align-self-center">
            <h2>About Us</h2>
            <p className="lead">
              We're a group of passionate biomechanists and computer scientists on a mission to bring "big data" methods to biomechanics.
              The first author on this project is Keenon Werling, a CS PhD student at Stanford University.
              The professors involved in this project are <a href="https://ckllab.stanford.edu/c-karen-liu">Karen Liu</a>, <a href="https://nmbl.stanford.edu/people/scott-delp/">Scott Delp</a>, and <a href="https://engineering.stanford.edu/person/steve-collins">Steve Collins</a>.
              If you'd like to get involved, feel free to reach out to any of us!
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default Welcome;
