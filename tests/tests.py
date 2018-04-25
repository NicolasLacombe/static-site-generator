import unittest
import os
import shutil

from generator import main as generate

class testGenerator(unittest.TestCase):

    _htmlFileName = 'foo.html'
    _jsonFileName = 'data.json'

    def setUp(self):
        pass
    def tearDown(self):
        shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output'), ignore_errors=True)
        pass

    # --

    def test_generator(self):
        currentDirPath = os.path.dirname(os.path.abspath(__file__))
        argv = [
            '--in', currentDirPath,
            '--out', os.path.join(currentDirPath, 'output'),
            '--json', os.path.join(currentDirPath, self._jsonFileName),
        ]
        generate(argv)

if __name__ == '__main__':
    unittest.main()
