from .utils.compatibility import *
from .utils.der import parse, encodeConstructed, encodePrimitive, DerFieldType
from .utils.binary import hexFromByteString, byteStringFromHex, base64FromByteString, byteStringFromBase64


class Signature:

    def __init__(self, r, s, recoveryId=None):
        self.r = r
        self.s = s
        self.recoveryId = recoveryId

    def toDer(self, withRecoveryId=False):
        hexadecimal = self._toString()
        encodedSequence = byteStringFromHex(hexadecimal)
        if not withRecoveryId:
            return encodedSequence
        return toBytes(chr(27 + self.recoveryId)) + encodedSequence

    def toBase64(self, withRecoveryId=False):
        return base64FromByteString(self.toDer(withRecoveryId))

    @classmethod
    def fromDer(cls, string, recoveryByte=False):
        recoveryId = None
        if recoveryByte:
            recoveryId = string[0] if isinstance(string[0], intTypes) else ord(string[0])
            recoveryId -= 27
            string = string[1:]

        hexadecimal = hexFromByteString(string)
        return cls._fromString(string=hexadecimal, recoveryId=recoveryId)

    @classmethod
    def fromBase64(cls, string, recoveryByte=False):
        der = byteStringFromBase64(string)
        return cls.fromDer(der, recoveryByte)

    def _toString(self):
        return encodeConstructed(
            encodePrimitive(DerFieldType.integer, self.r),
            encodePrimitive(DerFieldType.integer, self.s),
        )

    @classmethod
    def _fromString(cls, string, recoveryId=None):
        r, s = parse(string)[0]
        return Signature(r=r, s=s, recoveryId=recoveryId)
