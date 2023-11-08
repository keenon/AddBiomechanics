import React, { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { observer } from "mobx-react-lite";
import Session from "../../model/Session";
import ProfileView from "../../pages/profile/ProfileView"
import { isUUID } from "../../utils"

type ProfileRouterProps = {
  session: Session;
};

const ProfileRouter = observer((props: ProfileRouterProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const profilePath = props.session.parseProfileURL(location.pathname);

  useEffect(() => {
    if ((profilePath.userId === "" || profilePath.userId === "profile") && props.session.userId !== "") {
      navigate(`/profile/${props.session.userId}/`);
    }
  }, [profilePath.userId, props.session.userId, navigate, profilePath.userProfile.getPathType('')]);

  let body = <div>Loading...</div>;

  const pathType = profilePath.userProfile.getPathType('');
  if (pathType === 'profile') {
    body = <ProfileView userProfile={profilePath.userProfile} session={props.session} userId={profilePath.userId}/>;
  } else {
    body = <div>Not yet implemented type: {pathType}</div>;
  }

  return (
    <div className='container'>
      {body}
    </div>
  );
});

export default ProfileRouter;