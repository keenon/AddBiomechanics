-- @block Create data sources table
-- @conn DatasetDB - Test
CREATE TABLE IF NOT EXISTS source (
  id INTEGER PRIMARY KEY,
  latex_citation TEXT,
  bibtex_citation TEXT,
  license_type VARCHAR(10),
  license TEXT
);
-- @block Create clips table
-- @conn DatasetDB - Test
CREATE TABLE IF NOT EXISTS clip (
  id INTEGER PRIMARY KEY,
  source_id INTEGER REFERENCES(source.id),
  num_frames INTEGER,
  -- the scale of each body node in the Rajagopal model for this clip
  body_scales_np BLOB,
  -- the number of frames per second in this recording (1 / dt)
  fps INTEGER
);
-- @block Create frames table
-- @conn DatasetDB - Test
CREATE TABLE IF NOT EXISTS frames (
  id INTEGER PRIMARY KEY,
  clip_id INTEGER REFERENCES(clip.id),
  source_id INTEGER REFERENCES(source.id),
  -- the time within the clip that this frame belongs to
  t INTEGER,
  -- the kinematics information
  poses_np BLOB,
  vels_np BLOB,
  accels_np BLOB,
  -- the number of frames per second in this recording (1 / dt)
  fps INTEGER,
  -- the other modalities, if they exist
  left_grf_np BLOB,
  right_grf_np BLOB,
  imu_np BLOB,
  emg_np BLOB,
  -- these are enums: 0 == false, 1 == true, 2 == unknown
  left_foot_down INTEGER,
  right_foot_down INTEGER,
  has_grf INTEGER,
  has_imu INTEGER,
  has_emg INTEGER
);