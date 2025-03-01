"""
plotting.py
-----------
Description: Plotting utilites for the AddBiomechanics processing engine.
Author(s): Nicholas Bianco
"""

import os
import numpy as np
from collections import defaultdict, OrderedDict
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.lines as mlines
import matplotlib; matplotlib.use('Agg')
import pandas as pd
import opensim as osim


# Convert a STO file to a pandas DataFrame.
def storage2pandas(storage_file, header_shift=0):
    f = open(storage_file, 'r')
    header = 0
    for i, line in enumerate(f):
        if line.count('endheader') != 0:
            header = i
    f.close()

    data = pd.read_csv(storage_file, delimiter="\t", header=header+header_shift)
    return data


# Create y-label plot labels based on the type of data (joint angles, joint
# forces and torques, or marker trajectories) and the type of motion
# (translational or rotational).
def get_label_from_motion_and_data_type(motion_type, data_type):
    label = ''
    if motion_type == 'rotational':
        if data_type == 'kinematic':
            label = 'angle (rad)'
        elif data_type == 'kinetic':
            label = 'torque (N-m)'
        elif data_type == 'marker':
            raise Exception('Marker data cannot be of motion type "rotational".')
        return label
    elif motion_type == 'translational':
        if data_type == 'kinematic':
            label = 'position (m)'
        elif data_type == 'kinetic':
            label = 'force (N)'
        elif data_type == 'marker':
            label = 'error (cm)'
        return label
    else:
        return label


# Truncate plot titles if the get too long.
def truncate(string, max_length):
    """https://www.xormedia.com/string-truncate-middle-with-ellipsis/"""
    if len(string) <= max_length:
        # string is already short-enough
        return string
    # half of the size, minus the 3 .'s
    n_2 = int(max_length / 2 - 3)
    # whatever's left
    n_1 = max_length - n_2 - 3
    return '{0}...{1}'.format(string[:n_1], string[-n_2:])


# Given a state or control name with substring identifying either the left or
# right limb, remove the substring and return the updated name. This function
# also takes the argument 'ls_dict', which is a dictionary of plot linestyles
# corresponding to the right leg (solid line) or left leg (dashed line); it is
# updated here for convenience.
def bilateralize(name, ls_dict, data_type):
    # Keep modifying the name until no side tags remain.
    isRightLeg = True
    isMarker = data_type == 'marker'
    while True:
        if '_r/' in name:
            name = name.replace('_r/', '/')
        elif '_l/' in name:
            name = name.replace('_l/', '/')
            isRightLeg = False
        elif '_r_' in name:
            name = name.replace('_r_', '_')
        elif '_l_' in name:
            name = name.replace('_l_', '_')
            isRightLeg = False
        elif name[-2:] == '_r':
            name = name[:-2]
        elif name[-2:] == '_l':
            name = name[:-2]
            isRightLeg = False
        elif name[0] == 'R' and isMarker:
            name = name[1:]
            ls_dict[name].append('-')
            break
        elif name[0] == 'L' and isMarker:
            name = name[1:]
            ls_dict[name].append('--')
            break
        else:
            if isRightLeg:
                ls_dict[name].append('-')
            else:
                ls_dict[name].append('--')

            break

    return name, ls_dict


# Plot the DataFrame 'table' results into a PDF of figures at handle 'pdf'.
def plot_table(pdf, table, refs, colors, title_dict, ls_dict, label_dict,
               legend_handles, legend_labels, motion_type, data_type):

    # Set plot parameters.
    plots_per_page = 15.0
    num_cols = 3
    num_rows = (plots_per_page / num_cols) + 1

    # Get time column.
    time = table['time']

    # Loop through all keys in the dictionary and plot all variables.
    p = 1  # Counter to keep track of number of plots per page.
    for i, key in enumerate(title_dict.keys()):
        # If this is first key or if we filled up the previous page with
        # plots, create a new figure that will become the next page.
        if p % plots_per_page == 1:
            fig = plt.figure(figsize=(8.5, 11))

        plt.subplot(int(num_rows), int(num_cols),
                    int(p + num_cols))
        # Loop through all the state variable paths for this key.
        ymin = np.inf
        ymax = -np.inf
        handles = list()
        labels = list()
        # Is this a residual force?
        is_force = '_force' in key
        is_moment = '_moment' in key
        is_residual = ('pelvis' in key) and (is_force or is_moment)
        for path, ls in zip(title_dict[key], ls_dict[key]):
            var = table[path]
            ymin = np.minimum(ymin, np.min(var))
            ymax = np.maximum(ymax, np.max(var))

            # Plot the variable values from the MocoTrajectory.
            plt.plot(time, var, ls=ls,
                     color='k',
                     linewidth=1.5,
                     zorder=4)

            # Save legend handles to report marker or residual RMSE.
            if data_type == 'marker':
                h = mlines.Line2D([], [], ls=ls,
                                  color=colors[len(refs)], linewidth=1.0)
                handles.append(h)
                rmse = np.sqrt(np.mean(var ** 2))
                labels.append(f'RMSE = {rmse:1.2f} cm')

            elif data_type == 'kinetic' and is_residual:
                h = mlines.Line2D([], [], ls=ls,
                                  color=colors[len(refs)], linewidth=1.0)
                handles.append(h)
                rmse = np.sqrt(np.mean(var ** 2))
                if is_force:
                    labels.append(f'RMSE = {rmse:1.2f} N')
                elif is_moment:
                    labels.append(f'RMSE = {rmse:1.2f} N-m')

        # Plot labels and settings.
        plt.title(truncate(key, 38), fontsize=10)
        plt.xlabel('time (s)', fontsize=8)
        plt.ylabel(label_dict[key], fontsize=8)
        plt.xticks(fontsize=6)
        plt.yticks(fontsize=6)
        plt.xlim(time[0], time[time.size-1])
        plt.ticklabel_format(axis='y', style='sci', scilimits=(-3, 3))
        ax = plt.gca()
        ax.get_yaxis().get_offset_text().set_position((-0.15, 0))
        ax.get_yaxis().get_offset_text().set_fontsize(6)
        ax.tick_params(direction='in', gridOn=True, zorder=0)
        from matplotlib.ticker import FormatStrFormatter
        ax.xaxis.set_major_formatter(
            FormatStrFormatter('%.1f'))

        # Report marker or residual RMSE in axis legend.
        if data_type == 'marker':
            if ymax > 10:
                plt.ylim(0, 2.0 * np.ceil(ymax / 2.0))
            else:
                plt.ylim(0, 10)
                plt.yticks([0, 2, 4, 6, 8, 10])

            plt.axhline(y=2, color='g', linestyle='--', zorder=3, lw=1.0)
            plt.axhline(y=4, color='r', linestyle='--', zorder=3, lw=1.0)
            plt.legend(handles, labels, fontsize=7)

        elif is_residual:
            plt.legend(handles, labels, fontsize=7)

        # If we filled up the current figure or ran out of keys, add this
        # figure as a new page to the PDF. Otherwise, increment the plot
        # counter and keep going.
        if (p % plots_per_page == 0) or (i == len(title_dict.keys()) - 1):
            legfontsize = 64 / len(legend_handles)
            if legfontsize > 10:
                legfontsize = 10
            fig.tight_layout()
            plt.figlegend(legend_handles, legend_labels,
                          loc='lower center',
                          bbox_to_anchor=(0.5, 0.85),
                          fancybox=True, shadow=True,
                          prop={'size': legfontsize})
            pdf.savefig(fig)
            plt.close()
            p = 1
        else:
            p += 1


# Generate a PDF report for the DataFrame 'table' at the location 'output_fpath'. Here,
# 'filename' is just used to create an appropriate legend label for the passed in table.
# The arguments 'data_type' and 'bilateral' are used to specify the appropriate axis labels
# for the plots generated by 'plotTable()' above.
def generate_report_for_table(table, filename, output_fpath, data_type, bilateral=True):

    # Set colors.
    colors = ['k']

    # Additional files to plot (TODO)
    refs = list()

    # Suffixes to detect if a pelvis coordinate is translational or rotational.
    translate_suffixes = ['_tx', '_ty', '_tz', '_force']
    rotate_suffixes = ['_tilt', '_list', '_rotation', '_moment']

    # Create legend handles and labels that can be used to create a figure
    # legend that is applicable all figures.
    legend_handles = list()
    legend_labels = list()
    all_files = list()
    # if ref_files != None: all_files += ref_files
    all_files.append(filename)
    lw = 8 / len(colors)
    if lw < 0.5:
        lw = 0.5
    if lw > 2:
        lw = 2
    for color, file in zip(colors, all_files):
        if bilateral:
            h_right = mlines.Line2D([], [], ls='-', color=color, linewidth=lw)
            legend_handles.append(h_right)
            legend_labels.append(file + ' (right leg)')
            h_left = mlines.Line2D([], [], ls='--', color=color, linewidth=lw)
            legend_handles.append(h_left)
            legend_labels.append(file + ' (left leg)')
        else:
            h = mlines.Line2D([], [], ls='-', color=color, linewidth=lw)
            legend_handles.append(h)
            legend_labels.append(file)

    # Fill the dictionaries needed by plotTable().
    title_dict = OrderedDict()
    ls_dict = defaultdict(list)
    label_dict = dict()
    motion_type = 'rotational'
    for col_label in table.columns:
        if col_label == 'time':
            continue

        title = col_label
        if bilateral:
            title, ls_dict = bilateralize(title, ls_dict, data_type)
        else:
            ls_dict[title].append('-')
        if title not in title_dict:
            title_dict[title] = list()

        # If 'bilateral' is True, the 'title' key will
        # correspond to a list containing paths for both sides
        # of the model.
        title_dict[title].append(col_label)

        # Create the appropriate labels.
        final_motion_type = str(motion_type)
        final_data_type = str(data_type)
        if data_type == 'marker':
            final_motion_type = 'translational'

        elif data_type == 'grf':
            # If we have GRF data, detect if force, moment, or COP.
            for cop_suffix in ['_px', '_py', '_pz']:
                if col_label.endswith(cop_suffix):
                    final_data_type = 'kinematic'
                    final_motion_type = 'translational'
                    break

            for force_suffix in ['_vx', '_vy', '_vz']:
                if col_label.endswith(force_suffix):
                    final_data_type = 'kinetic'
                    final_motion_type = 'translational'
                    break

            for moment_suffix in ['_mx', '_my', '_mz']:
                if col_label.endswith(moment_suffix):
                    final_data_type = 'kinetic'
                    final_motion_type = 'rotational'
                    break
        else:
            # If we have a pelvis coordinate, detect if translational or rotational.
            if 'pelvis' in col_label:
                for suffix in translate_suffixes:
                    if col_label.endswith(suffix):
                        final_motion_type = 'translational'

                for suffix in rotate_suffixes:
                    if col_label.endswith(suffix):
                        final_motion_type = 'rotational'
            else:
                # Otherwise, assume rotational.
                final_motion_type = 'rotational'

        label_dict[title] = get_label_from_motion_and_data_type(final_motion_type, final_data_type)

    # Create a PDF instance and plot the table.
    with PdfPages(output_fpath) as pdf:
        plot_table(pdf, table, refs, colors, title_dict, ls_dict, label_dict,
                   legend_handles, legend_labels, motion_type, data_type)


# Plot joint angle results located in MOT files under results/IK.
def plot_ik_results(data_fpath):
    table = storage2pandas(data_fpath, header_shift=-1)
    filename = os.path.basename(data_fpath)
    output_fpath = data_fpath.replace('.mot', '.pdf')
    data_type = 'kinematic'
    generate_report_for_table(table, filename, output_fpath, data_type)


# Plot residual loads and joint torques located in STO files under results/ID.
def plot_id_results(data_fpath):
    table = storage2pandas(data_fpath, header_shift=-1)
    filename = os.path.basename(data_fpath)
    output_fpath = data_fpath.replace('.sto', '.pdf')
    data_type = 'kinetic'
    generate_report_for_table(table, filename, output_fpath, data_type)


# Plot ground reaction force data located in MOT files under results/ID.
def plot_grf_data(data_fpath):
    table = storage2pandas(data_fpath, header_shift=1)
    filename = os.path.basename(data_fpath)
    output_fpath = data_fpath.replace('.mot', '.pdf')
    data_type = 'grf'
    generate_report_for_table(table, filename, output_fpath, data_type, bilateral=False)


# Plot marker errors located in CSV files under results/IK.
def plot_marker_errors(data_fpath, ik_fpath):
    # Load table.
    table = pd.read_csv(data_fpath)

    # Drop all timesteps RMSE row and timestep column.
    table.drop(columns='Timestep', inplace=True)
    table.drop(0, inplace=True)
    table.reset_index(drop=True, inplace=True)

    # Convert from m to cm.
    table *= 100.0

    # Insert time column from IK results.
    ik_table = storage2pandas(ik_fpath, header_shift=-1)
    table.insert(0, 'time', ik_table['time'])

    # Plot marker errors.
    filename = os.path.basename(data_fpath)
    output_fpath = data_fpath.replace('.csv', '.pdf')
    data_type = 'marker'
    generate_report_for_table(table, filename, output_fpath, data_type)


# A base helper function for plotting results from fitting function-based muscle paths.
def plot_path_fitting_results(pdf_filename, original, fitted=None, sampled=None, 
                              sampled_fitted=None, nrow=4, ncol=4, ylabel='value', 
                              scale: float = 1):
    labels = original.getColumnLabels()
    original_color = 'blue'
    fitted_color = 'orange'

    nplots = nrow * ncol
    nfig = int(np.ceil(len(labels) / nplots))
    
    # Create a PDF file to save the figures
    with PdfPages(pdf_filename) as pdf:
        for ifig in range(nfig):
            fig, axs = plt.subplots(nrow, ncol, figsize=(10, 8))
            for irow in range(nrow):
                for icol in range(ncol):
                    iplot = irow * ncol + icol
                    ilabel = iplot + ifig * nplots
                    if ilabel < len(labels):

                        if sampled is not None:
                            axs[irow, icol].scatter(
                                sampled.getIndependentColumn(),
                                scale * sampled.getDependentColumn(labels[ilabel]).to_numpy(),
                                alpha=0.15, color=original_color, s=0.5)

                        if sampled_fitted is not None:
                            axs[irow, icol].scatter(
                                sampled_fitted.getIndependentColumn(),
                                scale * sampled_fitted.getDependentColumn(labels[ilabel]).to_numpy(),
                                alpha=0.15, color=fitted_color, s=0.5)

                        times = original.getIndependentColumn()
                        axs[irow, icol].plot(
                            times,
                            scale * original.getDependentColumn(labels[ilabel]).to_numpy(),
                            lw=3, color=original_color)
                        axs[irow, icol].set_xlim(times[0], times[-1])
                        axs[irow, icol].set_title(labels[ilabel], fontsize=6)

                        if fitted is not None:
                            axs[irow, icol].plot(
                                fitted.getIndependentColumn(),
                                scale * fitted.getDependentColumn(labels[ilabel]).to_numpy(),
                                lw=3, color=fitted_color)

                        if irow == nrow - 1:
                            axs[irow, icol].set_xlabel('time (s)')
                        else:
                            axs[irow, icol].set_xlabel('')
                            axs[irow, icol].set_xticklabels([])

                        if icol == 0:
                            axs[irow, icol].set_ylabel(ylabel)

            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)


def plot_coordinate_samples(results_dir, model_name):
    coordinates = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_coordinate_values.sto'))
    coordinates_sampled = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_coordinate_values_sampled.sto'))
    pdf_filename = os.path.join(results_dir, f'{model_name}_coordinate_samples.pdf')
    plot_path_fitting_results(pdf_filename, coordinates,
                              sampled=coordinates_sampled,
                              nrow=3, ncol=3, ylabel='value (deg)', 
                              scale=(180.0 / np.pi))


def plot_path_lengths(results_dir, model_name):
    path_lengths = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_path_lengths.sto'))
    path_lengths_fitted = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_path_lengths_fitted.sto'))
    path_lengths_sampled = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_path_lengths_sampled.sto'))
    path_lengths_sampled_fitted = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_path_lengths_sampled_fitted.sto'))
    pdf_filename = os.path.join(results_dir, f'{model_name}_path_lengths.pdf')
    plot_path_fitting_results(pdf_filename, path_lengths,
                              fitted=path_lengths_fitted,
                              sampled=path_lengths_sampled,
                              sampled_fitted=path_lengths_sampled_fitted,
                              nrow=4, ncol=4, ylabel='length (cm)', scale=100.0)


def plot_moment_arms(results_dir, model_name):
    moment_arms = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_moment_arms.sto'))
    moment_arms_fitted = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_moment_arms_fitted.sto'))
    moment_arms_sampled = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_moment_arms_sampled.sto'))
    moment_arms_sampled_fitted = osim.TimeSeriesTable(
        os.path.join(results_dir, f'{model_name}_moment_arms_sampled_fitted.sto'))
    pdf_filename = os.path.join(results_dir, f'{model_name}_moment_arms.pdf')
    plot_path_fitting_results(pdf_filename, moment_arms,
                              fitted=moment_arms_fitted,
                              sampled=moment_arms_sampled,
                              sampled_fitted=moment_arms_sampled_fitted,
                              nrow=4, ncol=4, ylabel='moment arm (cm)', scale=100.0)
    

def plot_joint_moment_breakdown(model, solution_fpath, tendon_forces_fpath, id_fpath, 
                                coordinate_names, reserve_strength, output_fpath):
    
    # Load the Moco solution and computed tendon forces.
    solution = osim.TimeSeriesTable(solution_fpath)
    tendon_forces = osim.TimeSeriesTable(tendon_forces_fpath)
    times = tendon_forces.getIndependentColumn()

    # Load the inverse dynamics results.
    id = osim.TimeSeriesTable(id_fpath)
    id_splines = osim.GCVSplineSet(id)

    # Resample the ID results to the tendon force times.
    id_sampled = osim.TimeSeriesTable()
    id_sampled.setColumnLabels(id.getColumnLabels())
    for time in times:
        timeVec = osim.Vector(1, time)
        id_row = osim.RowVector(id.getNumColumns())
        for ilabel, label in enumerate(id.getColumnLabels()):
            id_row[ilabel] = id_splines.get(label).calcValue(timeVec)
        id_sampled.appendRow(time, id_row)

    # Compute the moment arms.
    #  N times x N muscles x N coordinates
    trajectory = osim.MocoTrajectory(solution_fpath)
    statesTraj = trajectory.exportToStatesTrajectory(model)
    coordSet = model.getCoordinateSet()
    muscles = model.getMuscles()
    moment_arm_matrix = np.zeros((len(times), muscles.getSize(), 
                                  len(coordinate_names)))
    muscle_path_to_index = defaultdict(int)
    for istate in range(statesTraj.getSize()):
        state = statesTraj.get(istate)
        model.realizePosition(state)
        for imusc, muscle in enumerate(muscles):
            muscle_path = muscle.getAbsolutePathString()
            muscle_path_to_index[muscle_path] = imusc
            for icoord, cname in enumerate(coordinate_names):
                moment_arm = muscle.getPath().computeMomentArm(state, coordSet.get(cname))
                moment_arm_matrix[istate, imusc, icoord] = moment_arm

    # Create a mapping between coordinate names and muscle moment arms.
    moment_arm_map = defaultdict(list)
    for icoord, cname in enumerate(coordinate_names):
        for imusc, muscle in enumerate(muscles):
            muscle_path = muscle.getAbsolutePathString()
            if moment_arm_matrix[:, imusc, icoord].any():
                moment_arm_map[cname].append(muscle_path)
    muscle_coordinate_names = list(moment_arm_map.keys())

    # Detect reserve actuator names from the Moco solution.
    reserve_actuator_map = dict()
    for label in solution.getColumnLabels():
        for mcname in muscle_coordinate_names:
            if 'reserve' in label and mcname in label:
                reserve_actuator_map[mcname] = label
    
    # Plot the joint moment breakdown.
    nplots = 2
    nfig = int(np.ceil(len(muscle_coordinate_names) / nplots))    
    icoord = 0
    with PdfPages(output_fpath) as pdf:
        for ifig in range(nfig):
            fig = plt.figure(figsize=(10, 8)) 
            gs = gridspec.GridSpec(3, 2, width_ratios=[3, 1])
            for irow in range(3):
                if icoord >= len(muscle_coordinate_names): break
                musc_coord_name = muscle_coordinate_names[icoord]
                ax = fig.add_subplot(gs[irow, 0])

                # Net joint moment.
                id_moment = id_sampled.getDependentColumn(
                        f'{musc_coord_name}_moment').to_numpy()
                ax.plot(times, id_moment, label='net joint moment', color='black', lw=4)
                ax.set_title(musc_coord_name, fontsize=14)
                ax.set_xlim(times[0], times[-1])

                # Muscle generated moments.
                sum_muscle_moments = np.zeros_like(id_moment)
                for muscle_path in moment_arm_map[musc_coord_name]:
                    imusc = muscle_path_to_index[muscle_path]
                    moment_arm = moment_arm_matrix[:, imusc, icoord]
                    tendon_force = tendon_forces.getDependentColumn(
                            f'{muscle_path}|tendon_force').to_numpy()
                    muscle_moment = np.multiply(moment_arm, tendon_force)
                    ax.plot(times, muscle_moment, 
                            label=muscle_path.lstrip('/forceset/'), lw=1.5)
                    sum_muscle_moments += muscle_moment
                ax.plot(times, sum_muscle_moments, label='sum of muscle moments', 
                        color='gray', lw=2.5, ls='--')
                
                # Reserve moment.
                reserve_moment = reserve_strength * solution.getDependentColumn(
                        reserve_actuator_map[musc_coord_name]).to_numpy()
                ax.plot(times, reserve_moment, label='reserve moment', 
                        color='gray', lw=2.5)

                # Legend
                legend_ax = fig.add_subplot(gs[irow, 1])
                legend_ax.axis("off")
                legend_ax.legend(*ax.get_legend_handles_labels(), loc="center", 
                                 ncol=2, fontsize=6)
                icoord += 1

            plt.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
