# OpenGK Ghidra scripts 

This is a collection of scripts used to aid with reverse engineering SIMK4x binaries

## Installation

1. Clone or download the repository

1. Open PyGhidra

2. Go to Tools -> Script Manager 

3. Right click anywhere, open "Script directories"

4. Add the repository as a folder

5. Done. You'll find the scripts under the "OpenGK" category

## Scripts

### simk4x_load

Detects the variant and splits SIMK4x binaries into appropriate segments. 
This script deletes the default memory block and creates new blocks from scratch,
meaning **you WILL lose any progress so far!**. Only run this script when starting a new project

### c167_apply_symbol_descriptions

Adds symbol descriptions (such as `EXISEL` -> `External Interrupt Select register`) in the form of EOL comments.
Comments are appended, not set, so existing comments won't get overwritten