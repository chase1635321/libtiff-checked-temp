"""
"""
import re
import os
import sys
import json
import traceback
import subprocess
import logging

SLASH = os.sep
# file in which the individual commands will be stored
INDIVIDUAL_COMMANDS_FILE = os.path.realpath("convert_individual.sh")
# file in which the total commands will be stored.
TOTAL_COMMANDS_FILE = os.path.realpath("convert_all.sh")

# to separate multiple commands in a line
CMD_SEP = " &"
DEFAULT_ARGS = ["-dump-stats", "-output-postfix=checked", "-dump-intermediate"]
if os.name == "nt":
    DEFAULT_ARGS.append("-extra-arg-before=--driver-mode=cl")
    CMD_SEP = " ;"


def getCheckedCArgs(argument_list, work_dir):
    """
      Convert the compilation arguments (include folder and #defines)
      to checked C format.
    :param argument_list: list of compiler argument.
    :param work_dir: Path to the working directory from which
                     the compilation command was run.
    :return: checked c args
    """
    clang_x_args = []
    for curr_arg in argument_list:
        if curr_arg.startswith("-D") or curr_arg.startswith("-I"):
            if curr_arg.startswith("-I"):
                # if this is relative path,
                # convert into absolute path
                if not os.path.isabs(curr_arg[2:]):
                    curr_arg = "-I" + os.path.abspath(os.path.join(work_dir, curr_arg[2:]))
            clang_x_args.append('-extra-arg-before=' + curr_arg)
    # disable all warnings.
    clang_x_args.append('-extra-arg-before=-w')
    return clang_x_args


def tryFixUp(s):
    """
    Fix-up for a failure between cmake and nmake.
    """
    b = open(s, 'r').read()
    b = re.sub(r'@<<\n', "", b)
    b = re.sub(r'\n<<', "", b)
    f = open(s, 'w')
    f.write(b)
    f.close()
    return


def runCheckedCConvert(checkedc_bin, compile_commands_json, run_individual=False):
    global INDIVIDUAL_COMMANDS_FILE
    global TOTAL_COMMANDS_FILE
    runs = 0
    cmds = None
    while runs < 2:
        runs = runs + 1
        try:
            cmds = json.load(open(compile_commands_json, 'r'))
        except:
            traceback.print_exc()
            tryFixUp(compile_commands_json)

    if cmds == None:
        logging.error("failed to get commands from compile commands json:" + compile_commands_json)
        return

    s = set()
    total_x_args = []
    all_files = []
    for i in cmds:
        file_to_add = i['file']
        compiler_x_args = []
        target_directory = ""
        if file_to_add.endswith(".cpp"):
            continue  # Checked C extension doesn't support cpp files yet

        # BEAR uses relative paths for 'file' rather than absolute paths. It also
        # has a field called 'arguments' instead of 'command' in the cmake style.
        # Use that to detect BEAR and add the directory.
        if 'arguments' in i and not 'command' in i:
            # BEAR. Need to add directory.
            file_to_add = i['directory'] + SLASH + file_to_add
            # get the checked-c-convert and compiler arguments
            compiler_x_args = getCheckedCArgs(i["arguments"], i['directory'])
            total_x_args.extend(compiler_x_args)
            # get the directory used during compilation.
            target_directory = i['directory']
        file_to_add = os.path.realpath(file_to_add)
        all_files.append(file_to_add)
        s.add((frozenset(compiler_x_args), target_directory, file_to_add))

    # get the common path of the files as the base directory
    compilation_base_dir = os.path.commonprefix(all_files)
    prog_name = checkedc_bin
    f = open(INDIVIDUAL_COMMANDS_FILE, 'w')
    for compiler_args, target_directory, src_file in s:
        args = []
        # get the command to change the working directory
        change_dir_cmd = ""
        if len(target_directory) > 0:
            change_dir_cmd = "cd " + target_directory + CMD_SEP
        else:
            # default working directory
            target_directory = os.getcwd()
        args.append(prog_name)
        if len(compiler_args) > 0:
            args.extend(list(compiler_args))
        args.append('-base-dir="' + compilation_base_dir + '"')
        args.extend(DEFAULT_ARGS)
        args.append(src_file)
        # run individual commands.
        if run_individual:
            logging.debug("Running:" + ' '.join(args))
            subprocess.check_call(' '.join(args), cwd=target_directory, shell=True)
        # prepend the command to change the working directory.
        if len(change_dir_cmd) > 0:
            args = [change_dir_cmd] + args
        f.write(" \\\n".join(args))
        f.write("\n")
    f.close()
    logging.debug("Saved all the individual commands into the file:" + INDIVIDUAL_COMMANDS_FILE)

    args = []
    args.append(prog_name)
    args.extend(DEFAULT_ARGS)
    args.extend(list(set(total_x_args)))
    args.append('-base-dir="' + compilation_base_dir + '"')
    args.extend(list(set(all_files)))
    f = open(TOTAL_COMMANDS_FILE, 'w')
    f.write(" \\\n".join(args))
    f.close()
    # run whole command
    if not run_individual:
        logging.info("Running:" + str(' '.join(args)))
        subprocess.check_call(' '.join(args), shell=True)
    logging.debug("Saved the total command into the file:" + TOTAL_COMMANDS_FILE)
    return
