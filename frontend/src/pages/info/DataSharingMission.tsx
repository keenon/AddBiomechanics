import React from 'react';

const DataSharingMission = () => {
  return (
    <div className="my-4">
        <h2>Mission</h2>
        <p>The mission of AddBiomechanics is two-fold:</p>
        <ol>
            <li>To make it easier and faster to generate high-quality, quantitative biomechanics data.</li>
            <li>To create a large-scale repository of biomechanics data that is open to the research community, so we can together
              improve movement and mobility for all people.</li>
        </ol>
        
        <h2>License for the Software and Data</h2>
        <p>To achieve this mission, we are sharing AddBiomechanics freely with anyone who would like to use it, under the <a href="https://opensource.org/license/gpl-3-0/" target="_blank">GPL v3.0 License</a>.
        By uploading data to AddBiomechanics you agree to share it with a <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank"> Creative Commons BY 4.0 License</a>,
        with the exception of the private data we allow users to upload for limited testing purposes (more details are below).</p>
        <p>We share the AddBiomechanics source code so that researchers can fully understand the methods. We highly encourage you to
          use the web application rather than building the code from source. Note that we are a small team and are not able to support
          individuals wishing to build from source.</p>
        
        <h2>Will I Be Acknowledged for Sharing My Data?</h2>
        <p>The <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank">Creative Commons BY 4.0 License</a> requires that users
        acknowledge you when they use the data. We also provide a list of citations in a <code>DATA_CITATIONS.txt</code> file with each downloaded
        dataset so users know how to acknowledge you for the data you share.</p>
        <p>Make sure you: (1) update your user profile to include your name and institution, and (2) annotate each of your data
          folders with any publications or other references that users of your data should cite.</p>
        
        <h2>What If I Want to Test AddBiomechanics Before Sharing Data?</h2>
        <p>We know that data may not be ready right away for others to view, download, and use, so we provide the following data
          sharing options:</p>
        <ul>
            <li>When you upload your data, it will by default be tagged as an “Unfinalized Draft”. You can share this data by
              providing colleagues with a link, but it won’t appear in the public search results view unless users explicitly
              check the box to show draft data. “Unfinalized Draft” data may still be included in the large aggregate human motion
              datasets that we publish from time-to-time, if it is not a duplicate and passes our automated quality checks, though
              it will be marked as a draft in the <code>DATA_CITATIONS.txt</code> file, so that end users know you have not certified this data
              as complete.</li>
            <li>Once you click “Publish” your data will be automatically searchable. </li>
            <li>Every user also has a private folder where you can try out the AddBiomechanics service. It is important to note,
              however, that while AddBiomechanics makes a best effort at security, it <em><strong>is not cleared to store PHI or HIPAA
              data</strong></em>, so the private folder should be used only to process data that is not subject to these constraints.
              Users may only upload up to 10 test trials to this private folder. </li>
        </ul>
        
        <h2>Can I Delete My Data?</h2>
        <p>Please be aware that we retain copies of all processed data that is not in the “private” folder, even if it is subsequently
          deleted from your personal account. We make this data available in large aggregate datasets of all the data that has been
          processed by AddBiomechanics. These datasets include screens to check for data quality and provide users the option to convert
          all data to standardized OpenSim skeleton types to make aggregate analysis easier.</p>

        <h2>How Do I Inform Participants of How Their Data Will Be Used?</h2>
        <p>As with all human subjects research, you must ensure your work has been approved by your institution's ethics committee and
          you have informed participants of how their data will be used.</p>
        <p>You could use language like the following in your consent (IRB) forms to inform participants about how you will share their
          data, and give them the option to opt out.</p>
        <ul>
            <li>“I understand that my motion capture data (i.e., the time-history of how my body segments are moving when I walk or
              perform other movements) will be shared in a public repository. Sharing my data will enable others to replicate the
              results of this study, and enable future progress in human motion science. This motion data will not be linked with any
              other identifiable information about me.”</li>
            <li>“Biomechanics data are processed using the AddBiomechanics web application and stored in Amazon Web Services (AWS) S3
              instances. All drafted and published data stored in these instances are publicly accessible to AddBiomechanics users. Data
              stored in private user folders are not accessible. Public data will be accessible through the web interface and through
              aggregated data distributions hosted on SimTK.org.”</li>
        </ul>

        <h2>What Do I Say to IT to Get Them to Let Me Use AddBiomechanics?</h2>
        <p>“Study participants consented to public data sharing, and no sensitive or private data is ever passed to or stored in
          AddBiomechanics.org. All data uploaded to the AddBiomechanics.org service is intended to be immediately publicly accessible.”</p>
        <p>Most IT departments will then stop asking questions, because AddBiomechanics falls into the “extremely low risk” and/or
          “publicly accessible” category of data sensitivity.</p>

    </div>
  );
};

export default DataSharingMission;
