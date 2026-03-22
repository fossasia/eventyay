

class Point:

    def __init__(self, x=0, y=0, z=0):
        self.x = x
        self.y = y
        self.z = z

    def __str__(self):
        return "({x}, {y}, {z})".format(x=self.x, y=self.y, z=self.z)

    def isAtInfinity(self):
        return self.y == 0
