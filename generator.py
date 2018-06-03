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
import codecs

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

# ------------------------------------------------------------------------------

def findAndReplaceKey(input, data):
    def replace(match):
        key = match.group(1)
        if key in data:
            return data[key]
        return key

    output = re.sub(r'\{\{([a-zZ-Z-_1-9]*)\}\}', replace, input)
    return output

def generate(templateFile, jsonData, outputDir):
    assert os.path.isfile(templateFile)
    filesMapping      = jsonData[FILE_MAPPING_KEY]
    fileName          = os.path.basename(templateFile)
    generatedFilesPath = []
    if not fileName in filesMapping:
        print('File "{}" will be skipped'.format(fileName))
        return []

    templateFilePath = os.path.dirname(os.path.realpath(templateFile))
    languages        = jsonData[LANGUAGES_KEY]

    def getIncludeFileContent(match):
        """Read a file, expanding <!-- #include --> statements."""
        fileToRead = os.path.join(templateFilePath, match.group(2))
        if os.path.exists(fileToRead):
            return open(fileToRead, encoding='utf-8').read()

        error = "File not found: %s" % fileToRead
        warnings.warn(error)
        return error_tmpl % error

    def getSpecialVariable(match):
        if match.group('variable') == 'FILENAME':
            langId = match.group('lang').lower()
            return filesMapping[fileName][langId] if fileName in filesMapping and langId in filesMapping[fileName] else filesMapping[fileName][langId + '-link']
        else:
            print('Special Variable {} Unknown!'.format(match.group(1)))


    with open(templateFile, 'r') as fInput:
        content = fInput.read()
        # Expand file include
        content = re.sub(r'<!-- *#include *(virtual|file)=[\'"]([^\'"]+)[\'"] *-->',
                         getIncludeFileContent,
                         content)

        # Expand "special" variable
        content = re.sub(r'\$\$(?P<variable>[a-zA-Z-.]+)_*(?P<lang>[A-Z]*)\$\$',
                         getSpecialVariable,
                         content)

        # Expand Key per language
        for lang in languages:
            assert lang in jsonData

            if not fileName in filesMapping or not lang in filesMapping[fileName]:
                print("Mapping for file {} does not exists for language {}".format(fileName, lang))
                continue

            languageData = jsonData[lang]
            expandedContent = findAndReplaceKey(content, languageData)

            def replaceLink(match):
                path = match.group('path')
                fileName = match.group('file')
                options = match.group('options')
                print("Replacing {}{}{}".format(path, fileName, options))
                print('href="{}{}{}"'.format(
                    path,
                    filesMapping[fileName][lang] if fileName in filesMapping and lang in filesMapping[fileName] else fileName,
                    options if options else ''))
                return 'href="{}{}{}"'.format(
                    path,
                    filesMapping[fileName][lang] if fileName in filesMapping and lang in filesMapping[fileName] else fileName,
                    options if options else '')

            # Expand Link

            print("EXPANDING!!!!!!!!!!!")
            expandedContent = re.sub(r'href=\"(?P<path>([a-zA-Z\.]*\/)*)(?P<file>[a-zA-Z-_]+\.html|htm)(?P<options>[?#a-zA-Z-_]+)*\"',
                                     #expandedContent = re.sub(r'href =\"(?P<path>([a-zA-Z\.]*\/)*)(?P<file>[a-zA-Z-_]+\.(html|htm))(?P<options>[?#a-zA-Z-_]*)\"',
                                     replaceLink,
                                     expandedContent)
            outputFile = os.path.join(outputDir, lang, filesMapping[fileName][lang])

            pathlib.Path(os.path.dirname(outputFile)).mkdir(parents=True, exist_ok=True)
            with codecs.open(outputFile, 'w', 'utf-8') as fOutput:
                fOutput.write(expandedContent)

            generatedFilesPath.append(outputFile)
            print('"{}" => {}'.format(fileName, outputFile))

    return generatedFilesPath

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
    arg_parser.add_argument('--serv',
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


    def findFilesAndGenerate():
        try:
            jsonData = json.load(open(jsonFile, encoding='utf-8'))
        except Exception as e:
            print('Error reading json file {}'.format(jsonFile))
            print(e)
            return

        print('Generating from {} to {}'.format(rootdir, outputDir))
        files = [f for f in glob.glob(rootdir + '/**/*.html', recursive=True)]
        generatedFiles = []
        for file in files:
            generatedFiles.append(generate(file, jsonData, outputDir))
        print('Generated {} files'.format(len(generatedFiles)))

    findFilesAndGenerate()

    # Spawn server!
    def serv():
        os.chdir(outputDir)
        port = 8000
        with socketserver.TCPServer(("", port), http.server.SimpleHTTPRequestHandler) as httpd:
            print("serving local path {} at port {}".format(outputDir, port))
            try:
                httpd.serve_forever()
            except:
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
    if args.serv:
        t1 = threading.Thread(target=serv)
        t1.daemon = True
        t1.start()

    if args.scan:
       scan()
    elif args.serv:
        try:
            while True:
                time.sleep(1)
        except:
            raise

# ------------------------------------------------------------------------------
# Main entry point

if __name__ == '__main__':
    main(sys.argv[1:])
