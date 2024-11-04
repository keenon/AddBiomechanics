import subprocess
import sys
import os
import time
from typing import Dict, List


# 4. Launch a processing process
engine_module = "src.engine"
python_executable = sys.executable  # Gets the Python executable (e.g., `python3`)

path = '/home/nbianco/repos/AddBiomechanics/server/engine/tests/data/rajagopal2015'
subjectName = 'osim_results'
href = '<href>'

# print('Calling Command:\n' + python_executable + ' -m ' + engine_module + ' ' +
#       path + ' ' + subjectName + ' ' + href, flush=True)

# with open(path + 'log.txt', 'wb+') as logFile:
#     # Run the engine module as a subprocess with arguments
#     with subprocess.Popen(
#         [python_executable, "-m", engine_module, path, subjectName, href],
#         stdout=subprocess.PIPE, 
#         stderr=subprocess.STDOUT
#     ) as proc:
#         print('Process created: ' + str(proc.pid), flush=True)

#         unflushedLines: List[str] = []
#         lastFlushed = time.time()
#         for lineBytes in iter(proc.stdout.readline, b''):
#             if lineBytes is None and proc.poll() is not None:
#                 break
#             line = lineBytes.decode("utf-8")
#             print('>>> '+str(line).strip(), flush=True)
#             # Send to the log
#             logFile.write(lineBytes)
#             # Add it to the queue
#             unflushedLines.append(line)

#             now = time.time()
#             elapsedSeconds = now - lastFlushed

def absPath(path: str):
    root_file_path = os.path.join(os.getcwd(), sys.argv[0])
    absolute_path = os.path.join(os.path.dirname(root_file_path), path)
    return absolute_path

enginePath = absPath('../../engine/src/engine.py')
print('Calling Command:\n'+enginePath+' ' +
        path+' '+subjectName+' '+href, flush=True)
with open(path + 'log.txt', 'wb+') as logFile:
    with subprocess.Popen([enginePath, path, subjectName, href], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as proc:
        print('Process created: '+str(proc.pid), flush=True)

        unflushedLines: List[str] = []
        lastFlushed = time.time()
        for lineBytes in iter(proc.stdout.readline, b''):
            if lineBytes is None and proc.poll() is not None:
                break
            line = lineBytes.decode("utf-8")
            print('>>> '+str(line).strip(), flush=True)
            # Send to the log
            logFile.write(lineBytes)
            # Add it to the queue
            unflushedLines.append(line)

            now = time.time()
            elapsedSeconds = now - lastFlushed

