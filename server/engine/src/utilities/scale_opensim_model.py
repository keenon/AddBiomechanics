import nimblephysics as nimble
from typing import Dict, List, Tuple
import tempfile
import shutil
import numpy as np
import subprocess


def scale_opensim_model(unscaled_generic_osim_text: str,
                        skel: nimble.dynamics.Skeleton,
                        mass_kg: float,
                        height_m: float,
                        markers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]],
                        overwrite_inertia: bool = False) -> str:
    marker_names: List[str] = []
    if skel is not None:
        print('Adjusting marker locations on scaled OpenSim file', flush=True)
        body_scales_map: Dict[str, np.ndarray] = {}
        for i in range(skel.getNumBodyNodes()):
            body_node: nimble.dynamics.BodyNode = skel.getBodyNode(i)
            # Now that we adjust the markers BEFORE we rescale the body, we don't want to rescale the marker locations
            # at all.
            body_scales_map[body_node.getName()] = np.ones(3)
        marker_offsets_map: Dict[str, Tuple[str, np.ndarray]] = {}
        for k in markers:
            v = markers[k]
            marker_offsets_map[k] = (v[0].getName(), v[1])
            marker_names.append(k)

    # Create a temporary directory
    with tempfile.TemporaryDirectory() as tmpdirname:
        if not tmpdirname.endswith('/'):
            tmpdirname += '/'

        # 9.1. Write the unscaled OpenSim file to disk
        unscaled_generic_osim_path = tmpdirname + 'unscaled_generic.osim'
        with open(unscaled_generic_osim_path, 'w') as f:
            f.write(unscaled_generic_osim_text)

        nimble.biomechanics.OpenSimParser.moveOsimMarkers(
            unscaled_generic_osim_path,
            body_scales_map,
            marker_offsets_map,
            tmpdirname + 'unscaled_but_with_optimized_markers.osim')

        # 9.3. Write the XML instructions for the OpenSim scaling tool
        nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
            'optimized_scale_and_markers',
            skel,
            mass_kg,
            height_m,
            'unscaled_but_with_optimized_markers.osim',
            'Unassigned',
            'optimized_scale_and_markers.osim',
            tmpdirname + 'rescaling_setup.xml')

        # 9.4. Call the OpenSim scaling tool
        command = f'cd {tmpdirname} && opensim-cmd run-tool {tmpdirname}rescaling_setup.xml'
        print('Scaling OpenSim files: ' + command, flush=True)
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE) as p:
            for line in iter(p.stdout.readline, b''):
                print(line.decode(), end='', flush=True)
            p.wait()

        # 9.5. Overwrite the inertia properties of the resulting OpenSim skeleton file
        if overwrite_inertia:
            nimble.biomechanics.OpenSimParser.replaceOsimInertia(
                tmpdirname + 'optimized_scale_and_markers.osim',
                skel,
                tmpdirname + 'output_scaled.osim')
        else:
            shutil.copyfile(tmpdirname + 'optimized_scale_and_markers.osim',
                            tmpdirname + 'output_scaled.osim')

        with open(tmpdirname + 'output_scaled.osim') as f:
            output_file_raw_text = '\n'.join(f.readlines())
    return output_file_raw_text
