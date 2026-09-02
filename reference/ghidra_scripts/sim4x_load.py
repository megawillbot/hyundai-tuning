#Load SIMK4x binaries
#@author Dante
#@category OpenGK.SIMK4x
#@keybinding 
#@menupath 
#@toolbar 
#@runtime PyGhidra

import jpype
from ghidra.program.model.mem import MemoryBlock
from ghidra.program.model.mem import MemoryBlockType
from ghidra.program.model.mem import MemoryConflictException
from ghidra.program.model.address import Address
from ghidra.program.database.mem import FileBytes

ECU_IDENTIFICATION_TABLE = [
	{
		'offset': 0x82014, # RSW zone
		'expected': [b'\x36\x36\x32\x31'], #6621
		'ecu': {
			'name': 'SIMK43 8mbit',
			'eeprom_size_bytes': 1048576,
			'bin_offset': 0,
			'bootloader2_section_address': 0x88000,
			'bootloader2_size_bytes': 0x7fff,
			'calibration_section_address': 0x90000,
			'calibration_size_bytes': 0x10000,
			'program_section_address': 0xA0000,
			'program_size_bytes': 0x5FFFF
		}
	},
	{
		'offset': 0x10040,
		'expected': [b'\x63\x61\x36\x36'], #CA66
		'ecu': {
			'name': 'SIMK43 2.0 4mbit',
			'eeprom_size_bytes': 524287,
			'bin_offset': -0x80000,
			'bootloader2_section_address': 0x88000,
			'bootloader2_size_bytes': 0x7fff,
			'calibration_section_address': 0x90000,
			'calibration_size_bytes': 0x10000,
			'program_section_address': 0xA0000,
			'program_size_bytes': 0x5FFFF
		},
	},
	{
		'offset': 0x8040,
		'expected': [b'\x63\x61\x36\x35\x34\x30\x31'],
		'ecu': {
			'name': 'SIMK43 V6 4mbit (5WY17)',
			'eeprom_size_bytes': 524287,
			'bin_offset': -0x80000,
			'bootloader2_section_address': None,
			'bootloader2_size_bytes': None,
			'calibration_section_address': 0x88000,
			'calibration_size_bytes': 0x8000,
			'program_section_address': 0x90000,
			'program_size_bytes': 0x6FFFF
		}
	},
	{
		'offset': 0x8040,
		'expected': [b'\x63\x61\x36\x36\x30', b'\x63\x61\x36\x35\x32', b'\x63\x61\x36\x35\x30'], #CA660, CA652, CA650
		'ecu': {
			'name': 'SIMK41 / V6 2mbit',
			'eeprom_size_bytes': 262143,
			'bin_offset': -0x40000,
			'bootloader2_section_address': None,
			'bootloader2_size_bytes': None,
			'calibration_section_address': 0x48000,
			'calibration_size_bytes': 0x8000,
			'program_section_address': 0x50000, 
			'program_size_bytes': 0x2FFFF
		}
	},
		{
		'offset': 0x12040,
		'expected': [b'\x63\x61\x36\x36'], # ca66
 		'ecu': {
			'name': 'SIMK2K (Elantra)',
			'eeprom_size_bytes': 524287,
			'bin_offset': -0x80000,
			'bootloader2_section_address': 0x88000,
			'bootloader2_size_bytes': 0x9fff,
			'calibration_section_address': 0x92000,
			'calibration_size_bytes': 0x12000, # 65536 bytes (64 KiB)
			'program_section_address': 0xA4000,
			'program_size_bytes': 0x5BFFF 
		}
	},
]

C167_REGIONS = [
	{
		'name': 'Internal_ROM',
		'start': toAddr(0x0000), # 0x0000 - 0x1fff
		'offset': 0,
		'size': 0x1fff,
		'read': True,
		'write': False,
		'execute': True,
	},
	{
		'name': 'External_Memory',
		'start': toAddr(0x2000), # 0x2000 - 0xD9FF
		'offset': 0x2000,
		'size': 0xB9FF,
		'read': True,
		'write': True,
		'execute': False,
	},
	{
		'name': 'XRAM',
		'start': toAddr(0xE000), # 0xE000 - 0xEEFF. should have been 0xE000 - 0xE7FF, but a reserved region is used
		'offset': 0xE000,
		'size': 0xF00,
		'read': True,
		'write': True,
		'execute': False,
	},
	{
		'name': 'CAN1',
		'start': toAddr(0xEF00),
		'offset': 0xEF00,
		'size': 0x100,
		'read': True,
		'write': True,
		'execute': False,
	},
	{
		'name': 'ESFR',
		'start': toAddr(0xF000),
		'offset': 0xF000,
		'size': 0x200,
		'read': True,
		'write': True,
		'execute': False,
	},
	{
		'name': 'Internal_RAM',
		'start': toAddr(0xF200), # according to datasheet this starts at 0xf600, and 0xf200-0xf600 is reserved but this proves to not be the case
		'offset': 0xF200,
		'size': 0x9FF, # used to be 0x5ff, see above
		'read': True,
		'write': True,
		'execute': False,
	},
	{
		'name': 'Internal_SFRs',
		'start': toAddr(0xFC00),
		'offset': 0xFC00,
		'size': 0x400,
		'read': True,
		'write': True,
		'execute': False,
	}
]

ECU_SPECIFIC_REGIONS = {
	'bootloader2': {
		'name': 'Bootloader_2',
		'read': True,
		'write': False,
		'execute': True,
	},
	'calibration': {
		'name': 'Calibration',
		'read': True,
		'write': True,
		'execute': False,
	},
	'program': {
		'name': 'Program',
		'read': True,
		'write': False,
		'execute': True,
	},
}

def create_memory_region (memory, name: str, start: Address, fileBytes: FileBytes, offset: int, size: int, read: bool, write: bool, execute: bool) -> MemoryBlock:
	block = memory.createInitializedBlock(name, start, fileBytes, offset, size, False)
	block.setRead(read)
	block.setWrite(write)
	block.setExecute(execute)

def compare_with_tolerance (value: int, desired: int, tolerance: int = 10) -> bool:
	return (abs(value-desired)<tolerance)

def identify_ecu (fileBytes: FileBytes):
	for ecu_identifier in ECU_IDENTIFICATION_TABLE:
		flag_size = len(ecu_identifier['expected'][0])
		result = jpype.JByte[flag_size]
		fileBytes[0].getOriginalBytes(ecu_identifier['offset'], result)
		result = bytes(result)

		if result in ecu_identifier['expected']:
			print('Bin identified: {}'.format(ecu_identifier['ecu']['name']))
			return ecu_identifier['ecu']

	print('Failed to identify the ECU. Fallback to SIMK43 2.0')
	return ECU_IDENTIFICATION_TABLE[1]['ecu']

def generate_ecu_regions (ecu: dict) -> list:
	regions = []

	for section_name in ['bootloader2', 'calibration', 'program']:
		if not ecu.get(f'{section_name}_section_address'):
			continue

		region = ECU_SPECIFIC_REGIONS[section_name]
		region['start'] = toAddr(ecu.get(f'{section_name}_section_address'))
		region['offset'] = ecu.get(f'{section_name}_section_address') + ecu['bin_offset']
		region['size'] = ecu.get(f'{section_name}_size_bytes')
		regions.append(region)

	return regions

def run_script():
	state = getState()
	currentProgram = state.getCurrentProgram()
	memory = currentProgram.getMemory()

	fileBytes = memory.getAllFileBytes()
	ecu = identify_ecu(fileBytes)

	MEMORY_REGIONS = C167_REGIONS + generate_ecu_regions(ecu)

	for block in memory.getBlocks():
		memory.removeBlock(block, monitor)

	for region in MEMORY_REGIONS:
		print('Creating region {}'.format(region['name']))
		create_memory_region(memory, fileBytes=fileBytes[0], **region)

	print("Memory blocks have been re-created for the C166 firmware!")

run_script()