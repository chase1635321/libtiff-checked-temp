#!/bin/bash

echo Converting:
for file in checked/libtiff/*aux.c; do echo "   " $file; done

for file in checked/libtiff/*aux.c; do (~/github/checkedc-clang/build/bin/CConvertStandalone -p checked/compile_commands.json $file > temp) && mv temp $file; done

#rm -r __pycache__
#rm temp.temp
