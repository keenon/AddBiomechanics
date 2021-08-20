import unittest
import data


class DatasetTest(unittest.TestCase):

  def test_create(self):
    with data.Dataset('file') as db:
      pass


if __name__ == '__main__':
  unittest.main()
