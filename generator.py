import os
import argparse
import json
import glob
import re
import pathlib
import sys

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

# ------------------------------------------------------------------------------

def generate(templateFile, jsonData, outputDir):
    assert os.path.isfile(templateFile)
    languages = jsonData[LANGUAGES_KEY]
    filesMapping = jsonData[FILE_MAPPING_KEY]
    fileName = os.path.basename(templateFile)

    outputFiles = [os.path.join(outputDir, l, filesMapping[fileName][l] if (fileName in filesMapping and l in filesMapping[fileName]) else fileName) for l in languages]

    assert(len(outputFiles) == len(languages))
    print('template file {} will be generated to {}'.format(fileName, outputFiles))

    with open(templateFile, 'r') as fInput:
        content = fInput.read()
        for index, lang in enumerate(languages):
            assert lang in jsonData
            languageData = jsonData[lang]

            def replace(match):
                key = match.groups(0)[0]
                if key in languageData:
                    return languageData[key]

            pathlib.Path(os.path.dirname(outputFiles[index])).mkdir(parents=True, exist_ok=True)
            with open(outputFiles[index], 'w') as fOutput:
                expandedContent = re.sub(r'\{\{([a-zZ-Z-_]*)\}\}', replace, content)
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

    args = arg_parser.parse_args(args=argv)

    rootdir = os.path.abspath(args.input)
    assert os.path.exists(rootdir)

    outputDir = os.path.abspath(args.output)

    jsonFile = os.path.abspath(args.json)
    assert(os.path.isfile(jsonFile))

    jsonData = json.load(open(jsonFile, encoding='utf-8'))
    files = [f for f in glob.glob(rootdir + '/**/*.html', recursive=True)]
    for file in files:
        generate(file, jsonData, outputDir)
    #map(generate, files, jsonData, rootdir)

# ------------------------------------------------------------------------------
# Main entry point

if __name__ == '__main__':
    main(sys.argv[1:])
