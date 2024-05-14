# Welcome to the AddBiomechanics Command Line Interface

This tool allows you to conveniently upload large datasets to be bulk processed on SLURM by AddBiomechanics, as well as do bulk downloads and collect statistics about datasets.

To install, just run (from the root of this repository):

`pip3 install ./cli`

## Bulk Uploading

Then you can use the new `addb` tool on the command line, like so:

`addb upload <path_to_your_folder>`

## Creating Datasets

You can bulk download processed datasets from AddBiomechanics using the `download` command:

`addb download <regex_to_match>`

AddBiomechanics maintains a list of standard models, and will reprocess all data into the standard models automatically.
To download all the binary data from the `rajagopal_no_arms` standard model, you can run:

`addb -d dev download "standardized/rajagopal_no_arms/.*\.bin$"`

to get the data off the DEV servers, and

`addb -d prod download "standardized/rajagopal_no_arms/.*\.bin$"`

to get the data off the PROD servers.

Then, you'll likely want to downsample and/or lowpass filter the newly downloaded data (AddBiomechanics doesn't do any 
filtering on the server side, so we don't accidentally destroy useful high-frequency content).

To resample a downloaded folder at 50Hz sample rate, with a 20Hz lowpass filter, run:

`addb post-process <source_data_folder> <destination_data_folder> --sample-rate 50 --lowpass-hz 20`

## Exporting Data to CSV

To export a subject to a CSV, run:

`addb export-csv <source_bin_file> <destination_csv_file> --column pos_<dof> vel_<dof> wrk_<dof>`

You can specify as many columns as you like, and the CSV will be created with the specified columns. The naming 
convention for the columns is they are the prefix, followed by an underscore, followed by the degree of freedom. The 
currently available prefixes are:
- `pos`: position
- `vel`: velocity
- `acc`: acceleration
- `tau`: torque
- `pwr`: power = torque * velocity
- `wrk`: work = time integral of `pwr`

## Misc Utilities

There are built in commands to translate markersets between OpenSim models, run analytics on AddBiomechanics uploads, 
list files, etc. For more info and other commands:

`addb --help`