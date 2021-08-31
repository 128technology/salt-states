#!/usr/bin/env python3

import os
from zipapp import create_archive

project_dir = os.getcwd()
project_name = project_dir.split('/')[-1]
archive_name = 't128-' + project_name + '.pyz'

def filter_archive(file):
    if file.suffix == '.py' or file.name == 'lib':
        return True
    else:
        return False

create_archive(
    project_dir,
    target=os.path.join('..', archive_name),
    interpreter='/usr/bin/env python3',
    filter=filter_archive,
    compressed=True)
