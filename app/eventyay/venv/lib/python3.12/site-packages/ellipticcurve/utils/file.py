

class File:

    @classmethod
    def read(cls, path, mode="r"):
        with open(path, mode) as blob:
            content = blob.read()
        return content
