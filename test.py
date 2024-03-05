import nimblephysics as nimble

subject = nimble.biomechanics.SubjectOnDisk("data/processed/standardized/rajagopal_no_arms/data/protected/us-west-2:5982a7a9-c183-485a-a8f1-f5f90723bb8a/data/s002_02/94ca2c408331332671c536ebf5d8750c6ecf27406830e2e62f90bc181801a1a8/94ca2c408331332671c536ebf5d8750c6ecf27406830e2e62f90bc181801a1a8.bin")
print("Loaded a subject with "+str(subject.getNumTrials())+" trials")

frames = subject.readFrames(trial = 0, startFrame = 0, numFramesToRead = subject.getTrialLength(0))

for frame in frames:
   # Print a vector of joint angles from this frame
   print(frame.pos)
