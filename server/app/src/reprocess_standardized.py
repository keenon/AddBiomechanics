import argparse
from reactive_s3 import ReactiveS3Index, FileMetadata
import json
from typing import Dict, List, Tuple

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This is a skeleton of a script to patch the standardized data in various ways.')
    # "biomechanics-uploads161949-dev"
    # "biomechanics-uploads83039-prod"
    parser.add_argument('--bucket', type=str, default="biomechanics-uploads161949-dev",
                        help='The S3 bucket to access user data in')
    parser.add_argument('--deployment', type=str,
                        default='DEV',
                        help='The deployment to target (must be DEV or PROD)')
    args = parser.parse_args()

    print('Connecting to S3...')
    index = ReactiveS3Index(args.bucket, args.deployment, disable_pubsub=True)

    # for object in index.bucket.objects.all():
    #     key: str = object.key
    #     lastModified: int = int(object.last_modified.timestamp() * 1000)
    #     eTag = object.e_tag[1:-1]  # Remove the double quotes around the ETag value
    #     size: int = object.size
    #     print(key)

    subject_hashes: Dict[str, List[Tuple[str, int]]] = {}

    subjects_with_dynamics = 0
    subjects_without_dynamics = 0
    subjects_not_yet_updated = 0

    index.refreshIndex()
    for folder in index.listAllFolders():
        # We want to collect all the dataset targets that we're supposed to be copying data to, in case
        # those have been updated
        if folder.startswith('standardized'):
            if folder.endswith('/'):
                folder = folder[:-1]
            children = index.getImmediateChildren(folder + '/')
            is_subject = any([x.endswith('_subject.json') for x in children])

            if not is_subject:
                continue

            has_dynamics_b3d = any([x.endswith('_dynamics_trials_only.b3d') for x in children])
            has_no_dynamics_flag = any([x.endswith('NO_DYNAMICS_TRIALS') for x in children])
            if has_dynamics_b3d:
                subjects_with_dynamics += 1
            elif has_no_dynamics_flag:
                subjects_without_dynamics += 1
            else:
                subjects_not_yet_updated += 1

            path_parts = folder.split('/')
            hash_id = path_parts[-1]
            original_subject = '/'.join(path_parts[:-1])
            try:
                subject_json_last_modified = index.getMetadata(folder + '/_subject.json').lastModified

                if original_subject not in subject_hashes:
                    subject_hashes[original_subject] = []
                subject_hashes[original_subject].append((hash_id, subject_json_last_modified))
            except:
                print(f'Error processing {folder}')

    average_num_hashes = sum([len(x) for x in subject_hashes.values()]) / len(subject_hashes)

    num_reprocessed = 0
    for original_subject, hashes in subject_hashes.items():
        # sort hashes by last modified date
        hashes.sort(key=lambda x: x[1])
        assert(len(hashes) > 0)
        # Get the last hash
        hash_id = hashes[-1][0]
        folder = f'{original_subject}/{hash_id}'
        children = index.getImmediateChildren(folder + '/')
        dynamics_b3d = [x for x in children if x.endswith('_dynamics_trials_only.b3d')]
        no_dynamics_flag = [x for x in children if x.endswith('NO_DYNAMICS_TRIALS')]
        missing_dynamics = ((len(dynamics_b3d) + len(no_dynamics_flag)) == 0)
        has_slurm = any([x.endswith('SLURM') for x in children])
        has_processing = any([x.endswith('PROCESSING') for x in children])
        b3d_files = [x for x in children if x.endswith('.b3d')]
        results_files = [x for x in children if x.endswith('_results.json')]

        # Reprocess the subjects we've already processed
        # if (not missing_dynamics) and (has_processing or has_slurm):
        #     print(f'Reprocessing {folder}...')
        #     index.delete(folder + '/SLURM')
        #     index.delete(folder + '/PROCESSING')
        #     index.delete(folder + '/NO_DYNAMICS_TRIALS')
        #     index.delete(folder + '/_results.json')
        #     b3d_files = [x for x in children if x.endswith('.b3d')]
        #     for b3d_file in b3d_files:
        #         index.delete(folder + '/' + b3d_file)

        # Reprocess all the subjects that have not been updated yet
        if len(dynamics_b3d) + len(no_dynamics_flag) == 0:
            if len(b3d_files) > 0 and len(results_files) > 0:
                print(f'Reprocessing {folder}...')
                print('Deleting ' + folder + '/SLURM')
                index.delete(folder + '/SLURM')
                index.delete(folder + '/PROCESSING')
                index.delete(folder + '/_results.json')
                b3d_files = [x for x in children if x.endswith('.b3d')]
                for b3d_file in b3d_files:
                    index.delete(folder + '/' + b3d_file)
                num_reprocessed += 1
                # if num_reprocessed >= 150:
                #     break

    print('Done!')
    print('Average number of hashes per subject: ' + str(average_num_hashes))
    print('Number of subjects: ' + str(len(subject_hashes)))
    print('Number of hashes: ' + str(sum([len(x) for x in subject_hashes.values()])))
    print('Number of subjects with dynamics: ' + str(subjects_with_dynamics))
    print('Number of subjects without dynamics: ' + str(subjects_without_dynamics))
    print('Number of subjects not yet updated: ' + str(subjects_not_yet_updated))

