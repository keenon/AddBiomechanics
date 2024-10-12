import json
import nimblephysics as nimble
import os
from pprint import pprint

dof_lookup = [
    "pelvis_tilt", "pelvis_list", "pelvis_rotation", "pelvis_tx", "pelvis_ty", 
    "pelvis_tz", "hip_flexion_r", "hip_adduction_r", "hip_rotation_r", "knee_angle_r", 
    "ankle_angle_r", "subtalar_angle_r", "mtp_angle_r", "hip_flexion_l", "hip_adduction_l", 
    "hip_rotation_l", "knee_angle_l", "ankle_angle_l", "subtalar_angle_l", "mtp_angle_l", 
    "lumbar_extension", "lumbar_bending", "lumbar_rotation"
]

class data_attr:
    def __init__(self, data_path:str) -> None:
        self.data_path = data_path
        filename = os.path.basename(self.data_path)
        self.json_path = "data/custom/" + filename
        self.subject = nimble.biomechanics.SubjectOnDisk(self.data_path)
        self.frames = self.subject.readFrames(trial = 0, startFrame = 0, numFramesToRead = self.subject.getTrialLength(0))
       
        self.master_dict = {}
        self.master_dict["status"] = {}
        self.load()
        self.calculate()

    def load(self):
        try:
            with open(self.json_path, 'r') as json_file:
                data_dict = json.load(json_file)
                self.master_dict = data_dict
        except FileNotFoundError:
            pass

    def save(self):
        with open(self.json_path, 'w') as json_file:
            json.dump(self.master_dict, json_file, indent=4)

    def calculate(self):
        if not self.inAndTrue("calc",self.master_dict["status"]):
            self.calc()
        
        self.save()

    def inAndTrue(self, key, dict):
        if key in dict.keys() and dict[key] == 1:
            return 1
        return 0

    def fillMasterDict(self):
        self.master_dict = self.subject

    def calc(self):
        def print_attributes(obj):
            for attr in dir(obj):
                if not attr.startswith("__"):
                    print(attr, ":", getattr(obj, attr))

        for i in range(0, len(dof_lookup)):
            self.master_dict[dof_lookup[i]] = {
                "pos":[],
                "vel":[],
                "acc":[],

                
            }

        for i in range(0, len(dof_lookup)):
            t = 0
            for frame in self.frames:
                print_attributes(frame)
                return
                self.master_dict[dof_lookup[i]]["pos"].append(frame.pos)
                self.master_dict[dof_lookup[i]]["vel"].append(frame.vel)
                self.master_dict[dof_lookup[i]]["acc"].append(frame.acc)
                
        
        self.master_dict["status"]["calc"] = 1

if __name__ == "__main__":
    fileid = "0"

    with open("data/filename_lookup.json", 'r') as json_file:
        data_dict = json.load(json_file)

    filename = data_dict[fileid]
    data = data_attr(filename)