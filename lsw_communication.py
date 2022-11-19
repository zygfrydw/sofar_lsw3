import binascii
import struct
import json

from dataclasses import dataclass
import libscrc
import socket

@dataclass
class LSWQuery:
    inverter_sn: int
    register_start: int
    register_end: int


def calculate_check_sum(data: bytearray) -> int:
    checksum = 0
    for d in data:
        checksum += d & 255
    return int((checksum & 255))


def generate_frame(query: LSWQuery) -> bytearray:
    start = 0xA5
    length = 0x0017
    control_code = 0x4510
    serial = 0x0
    serial_number = query.inverter_sn
    registert_cmd = 0x0103
    reg_start = query.register_start
    reg_len = query.register_end - query.register_start +1

    header = struct.pack('<BHHHI', start, length, control_code, serial, serial_number)
    data_field = struct.pack('<BIQH', 0x02, 0, 0, 0)
    business_field = struct.pack('>HHH', registert_cmd, reg_start, reg_len)
    crc = struct.pack('<H', libscrc.modbus(business_field))
    frame = header + data_field + business_field + crc
    checksum = calculate_check_sum(bytearray(frame)[1:])
    footer = struct.pack('<BB', checksum, 0x15)
    return bytearray(frame + footer)

def read_status(ip, port, inverter_sn, reg_start, reg_stop):
    query = LSWQuery(inverter_sn=inverter_sn, register_start=reg_start, register_end=reg_stop)
    data_frame = generate_frame(query)

    add_info = socket.getaddrinfo(ip, port, socket.AF_INET, socket.SOCK_STREAM)
    family, socktype, proto, canonname, sockadress = add_info[0]
    try:
        client_socket = socket.socket(family, socktype, proto)
        client_socket.settimeout(10)
        client_socket.connect(sockadress)

        client_socket.sendall(data_frame)
        response = client_socket.recv(1024)
        return response
    except Exception as msg:
        print(msg)

    return None


@dataclass
class Register:
    address : int
    name: str
    ratio: float

def find_register(json_data, reg_addr: int):
    for dir in json_data:
        for reg in dir['items']:
            for adr in reg['registers']:
                int_adr = int(adr, 16)
                if int_adr == reg_addr:
                    return Register(address=int_adr, name=reg['titleEN'], ratio=reg['ratio'])
    return None


if __name__ == '__main__':
    inverter_ip = '192.168.1.45'
    inverter_port = 8899
    inverter_sn = 1742340000
    register_start1 = 0x0000
    register_end1 = 0x0027

    response = read_status(inverter_ip, inverter_port, inverter_sn, register_start1, register_end1)

    with open('SOFARMap.json', 'r', encoding='utf-8') as j:
        json_data = json.load(j)

    for reg_add in range(register_start1, register_end1+1):
        reg_def = find_register(json_data, reg_add)
        if reg_def is not None:
            offset_to_data = 28
            data_index = offset_to_data + (reg_add - register_start1) * 2
            register_data = response[data_index:data_index + 2]
            print(f"{reg_def.name}: {struct.unpack('>h', register_data)[0] * reg_def.ratio}")
