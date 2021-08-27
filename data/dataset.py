import sqlite3
import numpy as np
import io
from os import path


class Dataset:
  def __init__(self, dbpath: str) -> None:
    # Converts np.array to BLOB when inserting
    sqlite3.register_adapter(np.ndarray, self.__adapt_nparray)

    # Converts BLOB to np.array when selecting
    sqlite3.register_converter("array", self.__convert_nparray)

    # Connect to SQLite
    con = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    cur = con.cursor()
    cur.execute("create table test (arr array)")
    self.con = con

    basepath = path.dirname(__file__)
    filepath = path.abspath(path.join(basepath, "schema.sql"))
    with open(filepath, "r") as f:
      pass  # TODO

  def __enter__(self):
    return self

  def __exit__(self, ctx_type, ctx_value, ctx_traceback):
    self.con.close()

  def __adapt_nparray(self, arr):
    """
    http://stackoverflow.com/a/31312102/190597 (SoulNibbler)
    """
    out = io.BytesIO()
    np.save(out, arr)
    out.seek(0)
    return sqlite3.Binary(out.read())

  def __convert_nparray(self, text):
    out = io.BytesIO(text)
    out.seek(0)
    return np.load(out)
