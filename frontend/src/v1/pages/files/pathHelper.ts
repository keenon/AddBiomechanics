type Path = {
  parts: string[];
  type: 'mine' | 'private' | 'readonly';
  dataPath: string;
};

export function parsePath(pathname: string, myIdentityId: string): Path {
  const pathParts = pathname.split('/');
  while (pathParts.length > 0 && ((pathParts[0] === 'data') || (pathParts[0] === '') || (pathParts[0] === 'profile'))) {
    pathParts.splice(0, 1);
  }
  for (let i = 0; i < pathParts.length; i++) {
    pathParts[i] = decodeURIComponent(pathParts[i]);
  }

  if (pathParts[0] === 'private') {
    const dataPath = 'private/us-west-2:' + myIdentityId + '/data/' + (pathParts.slice(1).join('/'));
    return {
      parts: pathParts,
      type: 'private',
      dataPath
    };
  }

  const dataIdentity = decodeURIComponent(pathParts[0]).replace("us-west-2:", "");
  const dataPath = 'protected/us-west-2:' + dataIdentity + '/data/' + (pathParts.slice(1).join('/'));
  return {
    parts: pathParts,
    type: dataIdentity === myIdentityId ? 'mine' : 'readonly',
    dataPath
  };
};
