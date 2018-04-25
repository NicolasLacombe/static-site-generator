import os
import argparse
import json
import glob
import re
import pathlib
import sys
import warnings
import http.server
import socketserver
import time
import threading

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path

# Json file format:
# {
#    'languages': ['fr', 'ru']
#    'files_mapping':
#       {
#           'foo.html' :
#               {
#                   'fr': 'foo_fr',
#                   ....
#               },
#              .....
#       }
#   'fr':
#       {
#           'key' : 'value',
#           .....
#       }
#   'ru':
#       {
#           'key' : 'value',
#           .....
#       }
# }

LANGUAGES_KEY    = 'languages'
FILE_MAPPING_KEY = 'files_mapping'

error_tmpl = """
<p style="background-color: #660000; color: white; padding: 20px">
  %s
</p>
"""

# ------------------------------------------------------------------------------

class EventHandler(FileSystemEventHandler,):
    def __init__(self, callback):
        self._callback = callback

    def on_moved(self, event):
        super(EventHandler, self).on_moved(event)
        self._callback()

    def on_created(self, event):
        super(EventHandler, self).on_created(event)
        self._callback()

    def on_deleted(self, event):
        super(EventHandler, self).on_deleted(event)
        self._callback()

    def on_modified(self, event):
        super(EventHandler, self).on_modified(event)
        self._callback()

def findAndReplaceKey(input, data):
    def replace(match):
        key = match.groups(0)[0]
        if key in data:
            return data[key]
        return ''

    output = re.sub(r'\{\{([a-zZ-Z-_]*)\}\}', replace, input)
    return output


def generate(templateFile, jsonData, outputDir):
    assert os.path.isfile(templateFile)
    filesMapping     = jsonData[FILE_MAPPING_KEY]
    fileName         = os.path.basename(templateFile)
    if not fileName in filesMapping:
        print('File {} is not configured to be expanded. Mapping: {}'.format(fileName, filesMapping))
        return

    templateFilePath = os.path.dirname(os.path.realpath(templateFile))
    languages        = jsonData[LANGUAGES_KEY]


    outputFiles      = [os.path.join(outputDir, l, filesMapping[fileName][l] if (fileName in filesMapping and l in filesMapping[fileName]) else fileName) for l in languages]

    assert(len(outputFiles) == len(languages))
    print('template file {} will be expaned to {}'.format(fileName, outputFiles))

    def getIncludeFileContent(match):
        """Read a file, expanding <!-- #include --> statements."""
        fileToRead = os.path.join(templateFilePath, match.group(2))
        if os.path.exists(fileToRead):
            return open(fileToRead, encoding='utf-8').read()

        error = "File not found: %s" % fileToRead
        warnings.warn(error)
        return error_tmpl % error

    with open(templateFile, 'r') as fInput:
        content = fInput.read()
        # Expand file include
        content = re.sub(r'<!-- *#include *(virtual|file)=[\'"]([^\'"]+)[\'"] *-->',
                         getIncludeFileContent,
                         content)

        # Expand Key per language
        for index, lang in enumerate(languages):
            assert lang in jsonData
            languageData = jsonData[lang]
            expandedContent = findAndReplaceKey(content, languageData)

            pathlib.Path(os.path.dirname(outputFiles[index])).mkdir(parents=True, exist_ok=True)
            with open(outputFiles[index], 'w') as fOutput:
                fOutput.write(expandedContent)

# ------------------------------------------------------------------------------

def main(argv):
    usage_description = 'Generate html files based on template & json content'

    arg_parser = argparse.ArgumentParser(description= usage_description)
    arg_parser.add_argument('--in',
                            action='store',
                            dest='input',
                            help= '[REQUIRED] Root path')
    arg_parser.add_argument('--out',
                            action='store',
                            dest='output',
                            help= '[REQUIRED] Output Path')
    arg_parser.add_argument('--json',
                            action='store',
                            dest='json',
                            help= '[REQUIRED] Json file containing config & variables to expand')
    arg_parser.add_argument('--serve',
                            action="store_true",
                            help= '[Optional] Start a server at output past')
    arg_parser.add_argument('--scan',
                            action="store_true",
                            help= '[Optional] Continually scan input folder & generate output at every updated')

    args = arg_parser.parse_args(args=argv)

    rootdir = os.path.abspath(args.input)
    assert os.path.exists(rootdir)

    outputDir = os.path.abspath(args.output)

    jsonFile = os.path.abspath(args.json)
    assert(os.path.isfile(jsonFile))

    jsonData = json.load(open(jsonFile, encoding='utf-8'))

    def findFilesAndGenerate():
        print("Generating...")
        files = [f for f in glob.glob(rootdir + '/**/*.html', recursive=True)]
        for file in files:
            generate(file, jsonData, outputDir)

    findFilesAndGenerate()

    # Spawn server!
    def serve():
        os.chdir(outputDir)
        port = 8000
        with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
            print("serving local path {} at port {}".format(outputDir, port))
            try:
                httpd.serve_forever()
            except:
                print("Catched!")
                raise


    # Continually scan & regenerate
    def scan():
        event_handler = EventHandler(callback=findFilesAndGenerate)
        observer = Observer()
        observer.schedule(event_handler, rootdir, recursive=True)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
            raise
        observer.join()

    assert os.path.exists(outputDir)
    if args.serve:
        t1 = threading.Thread(target=serve)
        t1.daemon = True
        t1.start()

    if args.scan:
       scan()
    elif args.serve:
        try:
            while True:
                time.sleep(1)
        except:
            raise

# ------------------------------------------------------------------------------
# Main entry point

if __name__ == '__main__':
    main(sys.argv[1:])
