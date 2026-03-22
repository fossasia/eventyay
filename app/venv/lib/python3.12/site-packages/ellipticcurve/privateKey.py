from .math import Math
from .utils.integer import RandomInteger
from .utils.pem import getPemContent, createPem
from .utils.binary import hexFromByteString, byteStringFromHex, intFromHex, base64FromByteString, byteStringFromBase64
from .utils.der import hexFromInt, parse, encodeConstructed, DerFieldType, encodePrimitive
from .curve import secp256k1, getByOid
from .publicKey import PublicKey


class PrivateKey:

    def __init__(self, curve=secp256k1, secret=None):
        self.curve = curve
        self.secret = secret or RandomInteger.between(1, curve.N - 1)

    def publicKey(self):
        curve = self.curve
        publicPoint = Math.multiply(
            p=curve.G,
            n=self.secret,
            N=curve.N,
            A=curve.A,
            P=curve.P,
        )
        return PublicKey(point=publicPoint, curve=curve)

    def toString(self):
        return hexFromInt(self.secret)

    def toDer(self):
        publicKeyString = self.publicKey().toString(encoded=True)
        hexadecimal = encodeConstructed(
            encodePrimitive(DerFieldType.integer, 1),
            encodePrimitive(DerFieldType.octetString, hexFromInt(self.secret)),
            encodePrimitive(DerFieldType.oidContainer, encodePrimitive(DerFieldType.object, self.curve.oid)),
            encodePrimitive(DerFieldType.publicKeyPointContainer, encodePrimitive(DerFieldType.bitString, publicKeyString))
        )
        return byteStringFromHex(hexadecimal)

    def toPem(self):
        der = self.toDer()
        return createPem(content=base64FromByteString(der), template=_pemTemplate)

    @classmethod
    def fromPem(cls, string):
        privateKeyPem = getPemContent(pem=string, template=_pemTemplate)
        return cls.fromDer(byteStringFromBase64(privateKeyPem))

    @classmethod
    def fromDer(cls, string):
        hexadecimal = hexFromByteString(string)
        privateKeyFlag, secretHex, curveData, publicKeyString = parse(hexadecimal)[0]
        if privateKeyFlag != 1:
            raise Exception("Private keys should start with a '1' flag, but a '{flag}' was found instead".format(
                flag=privateKeyFlag
            ))
        curve = getByOid(curveData[0])
        privateKey = cls.fromString(string=secretHex, curve=curve)
        if privateKey.publicKey().toString(encoded=True) != publicKeyString[0]:
            raise Exception("The public key described inside the private key file doesn't match the actual public key of the pair")
        return privateKey

    @classmethod
    def fromString(cls, string, curve=secp256k1):
        return PrivateKey(secret=intFromHex(string), curve=curve)


_pemTemplate = """
-----BEGIN EC PRIVATE KEY-----
{content}
-----END EC PRIVATE KEY-----
"""
