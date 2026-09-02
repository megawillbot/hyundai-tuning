#Apply C167 symbol descriptions. Resolves https://github.com/NationalSecurityAgency/ghidra/issues/8339
#@author Dante
#@category OpenGK.C167
#@keybinding 
#@menupath 
#@toolbar 
#@runtime PyGhidra

from ghidra.app.cmd.comments import AppendCommentCmd
from ghidra.program.model.listing import CodeUnit
from assets.c167_symbol_descriptions import SYMBOL_DESCRIPTIONS

def run_script():
	for symbol in SYMBOL_DESCRIPTIONS:
		c = AppendCommentCmd(toAddr(symbol.offset), CodeUnit.EOL_COMMENT, symbol.description, ',')
		c.applyTo(getState().getCurrentProgram())

	print("EOL comments appended to C167 symbols")

run_script()