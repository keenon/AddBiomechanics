import sqlite3
import numpy as np
import io


class Dataset:
  def __init__(self, path: str) -> None:
    # Converts np.array to TEXT when inserting
    sqlite3.register_adapter(np.ndarray, self.__adapt_nparray)

    # Converts TEXT to np.array when selecting
    sqlite3.register_converter("array", self.__convert_nparray)

    x = np.arange(12).reshape(2, 6)

    con = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES)
    cur = con.cursor()
    cur.execute("create table test (arr array)")
    self.con = con

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
