from .binary import intFromHex, hexFromInt


def oidFromHex(hexadecimal):
    firstByte, remainingBytes = hexadecimal[:2], hexadecimal[2:]
    firstByteInt = intFromHex(firstByte)
    oid = [firstByteInt // 40, firstByteInt % 40]
    oidInt = 0
    while len(remainingBytes) > 0:
        byte, remainingBytes = remainingBytes[0:2], remainingBytes[2:]
        byteInt = intFromHex(byte)
        if byteInt >= 128:
            oidInt = (128 * oidInt) + (byteInt - 128)
            continue
        oidInt = (128 * oidInt) + byteInt
        oid.append(oidInt)
        oidInt = 0
    return oid


def oidToHex(oid):
    hexadecimal = hexFromInt(40 * oid[0] + oid[1])
    for number in oid[2:]:
        hexadecimal += _oidNumberToHex(number)
    return hexadecimal


def _oidNumberToHex(number):
    hexadecimal = ""
    endDelta = 0
    while number > 0:
        hexadecimal = hexFromInt((number % 128) + endDelta) + hexadecimal
        number //= 128
        endDelta = 128
    return hexadecimal or "00"
