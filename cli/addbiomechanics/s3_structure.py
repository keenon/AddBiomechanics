from typing import List, Dict, Tuple
import datetime
from addbiomechanics.auth import AuthContext

def sizeof_fmt(num: int, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"


class S3Node:
    name: str
    parent: 'S3Node' = None
    children: List['S3Node']
    is_file: bool
    size: int
    last_modified: datetime
    etag: str

    def __init__(self, name: str, parent: 'S3Node' = None):
        self.name = name
        self.parent = parent
        self.is_file = False
        self.children = []

    def get_child(self, path: str) -> 'S3Node':
        if path.startswith('/'):
            path = path[1:]
        if path.endswith('/'):
            path = path[:-1]
        parts = path.split('/')
        if len(path) == 0 or len(parts) == 0:
            return self
        for child in self.children:
            if child.name == parts[0]:
                return child.get_child('/'.join(parts[1:]))
        # Create a child
        child = S3Node(parts[0], self)
        self.children.append(child)
        return child.get_child('/'.join(parts[1:]))

    def set_is_file(self, size: int, last_modified: datetime, etag: str):
        self.is_file = True
        self.size = size
        self.last_modified = last_modified
        self.etag = etag

    def has_children(self, list: List[str]):
        if len(list) == 0:
            return True
        for child in self.children:
            if child.name == list[0]:
                return self.has_children(list[1:])
        return False

    def get_path(self) -> str:
        if self.parent is None:
            return ''
        parent_path = self.parent.get_path()
        if len(parent_path) == 0:
            return self.name
        else:
            return parent_path + '/' + self.name

    def get_total_children_size(self, grf_only: bool = False) -> int:
        total: int = 0
        if self.is_file:
            total += self.size
        # Don't recurse if we don't contain GRF data
        if (not self.has_grf()) and grf_only:
            return total
        for child in self.children:
            total += child.get_total_children_size(grf_only)
        return total

    def get_num_subjects(self, grf_only: bool = False) -> int:
        if self.is_subject():
            if self.has_grf() or not grf_only:
                return 1
            else:
                return 0
        total: int = 0
        for child in self.children:
            total += child.get_num_subjects(grf_only)
        return total

    def get_num_trials(self, grf_only: bool = False) -> int:
        if self.is_trial():
            if self.has_grf() or not grf_only:
                return 1
            else:
                return 0
        total: int = 0
        for child in self.children:
            total += child.get_num_trials(grf_only)
        return total

    def get_all_subjects(self, grf_only: bool = False) -> List['S3Node']:
        if self.is_subject():
            if self.has_grf() or not grf_only:
                return [self]
            else:
                return []
        total: List['S3Node'] = []
        for child in self.children:
            total += child.get_all_subjects(grf_only)
        return total

    def is_subject(self):
        return self.has_children(['trials', '_subject.json'])

    def is_user(self):
        return self.has_children(['account.json', 'data'])

    def is_trial(self):
        return self.has_children(['markers.c3d']) or self.has_children(['markers.trc'])

    def is_trial_with_grf(self):
        return self.has_children(['markers.c3d']) or (self.has_children(['markers.trc']) and self.has_children(['grf.mot']))

    def has_grf(self):
        if self.is_trial_with_grf():
            return True
        for child in self.children:
            if child.has_grf():
                return True
        return False

    def get_download_list(self, path_substring: str, grf_only: bool = False) -> List['S3Node']:
        if self.is_file:
            if (path_substring is None or path_substring in self.get_path()) and \
                    (self.name.endswith('.trc') or
                     self.name.endswith('.c3d') or
                     self.name.endswith('.mot') or
                     self.name.endswith('.json') or
                     self.name.endswith('.osim')) and (
                self.name != '_results.json' and
                self.name != '_trial.json' and
                self.name != 'account.json' and
                self.name != 'profile.json' and
                self.name != '_errors.json'
            ):
                return [self]
            else:
                return []
        total: List[str] = []
        if not grf_only or self.has_grf():
            for child in self.children:
                total += child.get_download_list(path_substring, grf_only)
        return total

    def debug(self,
              tab_level: int = 0,
              include_trials: bool = False,
              include_subjects: bool = True,
              grf_only: bool = False):
        if self.is_trial():
            if include_trials:
                size = sizeof_fmt(self.get_total_children_size(grf_only=grf_only))
                has_grf = ' [Has GRF] ' if self.has_grf() else ''
                print('\t' * tab_level + '> trial \"' + self.name + '\", ' + size + has_grf)
        elif self.is_subject():
            if include_subjects:
                num_trials = self.get_num_trials(grf_only=grf_only)
                if num_trials == 0:
                    return
                size = sizeof_fmt(self.get_total_children_size(grf_only=grf_only))
                has_grf = ' [Has GRF] ' if self.has_grf() else ''
                print('\t' * tab_level + '> subject \"' + self.name + '\", ' + str(num_trials) + ' trials, ' + size + has_grf)
                trials = self.get_child('trials')
                for child in trials.children:
                    child.debug(tab_level + 1, include_trials=include_trials, include_subjects=include_subjects, grf_only=grf_only)
        elif self.is_user():
            num_subjects = self.get_num_subjects(grf_only=grf_only)
            num_trials = self.get_num_trials(grf_only=grf_only)
            size = sizeof_fmt(self.get_total_children_size(grf_only=grf_only))
            if size == 0:
                return
            if num_subjects == 0 and num_trials == 0:
                return
            has_grf = ' [Has GRF] ' if self.has_grf() else ''
            print('\t' * tab_level + '> user \"' + self.name + '\", ' + str(num_subjects) + ' subjects, ' + str(num_trials) + ' trials, ' + size + has_grf)
            data = self.get_child('data')
            for child in data.children:
                child.debug(tab_level + 1, include_trials=include_trials, include_subjects=include_subjects,
                            grf_only=grf_only)
        else:
            # This is an intermediate folder
            num_subjects = self.get_num_subjects(grf_only=grf_only)
            num_trials = self.get_num_trials(grf_only=grf_only)
            size = sizeof_fmt(self.get_total_children_size(grf_only=grf_only))
            if size == 0:
                return
            if num_subjects == 0 and num_trials == 0:
                return
            has_grf = ' [Has GRF] ' if self.has_grf() else ''
            print('\t' * tab_level + '> folder \"' + self.name + '\", ' + str(num_subjects) + ' subjects, ' + str(num_trials) + ' trials, ' + size + has_grf)
            for child in self.children:
                child.debug(tab_level + 1, include_trials=include_trials, include_subjects=include_subjects,
                            grf_only=grf_only)

def retrieve_s3_structure(ctx: AuthContext, s3_prefix: str = 'protected/') -> 'S3Node':
    s3 = ctx.aws_session.client('s3')
    # Call list_objects_v2() with the continuation token
    response = s3.list_objects_v2(
        Bucket=ctx.deployment['BUCKET'], Prefix=s3_prefix)

    root = S3Node('')
    # Retrieve the first set of objects
    while True:
        # Process the objects in the response
        if 'Contents' in response:
            for obj in response['Contents']:
                path = obj['Key']
                last_modified = obj['LastModified']
                size = obj['Size']
                etag = obj['ETag']
                root.get_child(path).set_is_file(size, last_modified, etag)

        # Check if there are more objects to retrieve
        if response['IsTruncated']:
            continuation_token = response['NextContinuationToken']
            response = s3.list_objects_v2(
                Bucket=ctx.deployment['BUCKET'], Prefix=s3_prefix, ContinuationToken=continuation_token)
        else:
            break

    return root

