from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
import os
from typing import List, Dict

class ExportCSVCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'export-csv', help='This command will read a SubjectOnDisk binary file, and will spit out a CSV '
                               'with the requested columns.')
        parser.add_argument('input_path', type=str)
        parser.add_argument('output_path', type=str)
        parser.add_argument(
            '-c',
            '--column',
            help='This adds a column to the export list. Columns follow the pattern of [pos/vel/acc/tau/pwr/wrk]_[dof]',
            nargs='+',
            type=str)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'export-csv':
            return False
        input_path: str = os.path.abspath(args.input_path)
        output_path: str = os.path.abspath(args.output_path)
        if args.column is None or len(args.column) == 0:
            print('ERROR: At least one column must be specified with the --column option')
            return True
        columns: List[str] = args.column

        try:
            import nimblephysics as nimble
            from nimblephysics import NimbleGUI
        except ImportError:
            print("The required library 'nimblephysics' is not installed. Please install it and try this command again.")
            return True
        try:
            import numpy as np
        except ImportError:
            print("The required library 'numpy' is not installed. Please install it and try this command again.")
            return True

        print('Reading SubjectOnDisk at '+input_path+'...')
        subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(input_path)

        skel = subject.readSkel()
        dofs: List[str] = []
        for i in range(skel.getNumDofs()):
            dof = skel.getDofByIndex(i)
            dofs.append(dof.getName())

        print('Exporting to CSV...')
        col_dof_index: List[int] = []
        with open(output_path, 'w') as f:
            # Write the header
            header: str = 'trial,frame,time'
            for column in columns:
                if column.startswith('pos_') or column.startswith('vel_') or column.startswith('acc_') or column.startswith('tau_') or column.startswith('pwr_') or column.startswith('wrk_'):
                    dof = column[4:]
                    if dof not in dofs:
                        print('ERROR: ' + dof + ' is not a valid degree of freedom for col '+column)
                        return True
                    col_dof_index.append(dofs.index(dof))
                else:
                    print('ERROR: ' + column + ' is not a valid column name')
                    return True
                header += ',' + column
            header += '\n'
            f.write(header)

            # Write the data
            work_sums: Dict[str, float] = {key: 0 for key in columns}
            for trial in range(subject.getNumTrials()):
                for i in range(subject.getTrialLength(trial)):
                    frame: nimble.biomechanics.Frame = subject.readFrames(trial, i, 1)[0]
                    row: str = str(trial)+','+str(i)+','+str(i * subject.getTrialTimestep(trial))
                    for i, column in enumerate(columns):
                        if column.startswith('pos_'):
                            row += ','+str(frame.pos[col_dof_index[i]])
                        elif column.startswith('vel_'):
                            row += ','+str(frame.vel[col_dof_index[i]])
                        elif column.startswith('acc_'):
                            row += ','+str(frame.acc[col_dof_index[i]])
                        elif column.startswith('tau_'):
                            row += ','+str(frame.tau[col_dof_index[i]])
                        elif column.startswith('pwr_'):
                            row += ',' + str(frame.vel[col_dof_index[i]] * frame.tau[col_dof_index[i]])
                        elif column.startswith('wrk_'):
                            pwr = frame.vel[col_dof_index[i]] * frame.tau[col_dof_index[i]]
                            work_sums[column] += pwr * subject.getTrialTimestep(trial)
                            row += ',' + str(work_sums[column])
                    row += '\n'
                    f.write(row)

        return True
