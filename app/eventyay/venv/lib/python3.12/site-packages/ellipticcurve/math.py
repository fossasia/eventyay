from .point import Point


class Math:

    @classmethod
    def modularSquareRoot(cls, value, prime):
        return pow(value, (prime + 1) // 4, prime)

    @classmethod
    def multiply(cls, p, n, N, A, P):
        """
        Fast way to multily point and scalar in elliptic curves

        :param p: First Point to mutiply
        :param n: Scalar to mutiply
        :param N: Order of the elliptic curve
        :param P: Prime number in the module of the equation Y^2 = X^3 + A*X + B (mod p)
        :param A: Coefficient of the first-order term of the equation Y^2 = X^3 + A*X + B (mod p)
        :return: Point that represents the sum of First and Second Point
        """
        return cls._fromJacobian(
            cls._jacobianMultiply(cls._toJacobian(p), n, N, A, P), P
        )

    @classmethod
    def add(cls, p, q, A, P):
        """
        Fast way to add two points in elliptic curves

        :param p: First Point you want to add
        :param q: Second Point you want to add
        :param P: Prime number in the module of the equation Y^2 = X^3 + A*X + B (mod p)
        :param A: Coefficient of the first-order term of the equation Y^2 = X^3 + A*X + B (mod p)
        :return: Point that represents the sum of First and Second Point
        """
        return cls._fromJacobian(
            cls._jacobianAdd(cls._toJacobian(p), cls._toJacobian(q), A, P), P,
        )

    @classmethod
    def inv(cls, x, n):
        """
        Extended Euclidean Algorithm. It's the 'division' in elliptic curves

        :param x: Divisor
        :param n: Mod for division
        :return: Value representing the division
        """
        if x == 0:
            return 0

        lm = 1
        hm = 0
        low = x % n
        high = n

        while low > 1:
            r = high // low
            nm = hm - lm * r
            nw = high - low * r
            high = low
            hm = lm
            low = nw
            lm = nm

        return lm % n

    @classmethod
    def _toJacobian(cls, p):
        """
        Convert point to Jacobian coordinates

        :param p: First Point you want to add
        :return: Point in Jacobian coordinates
        """
        return Point(p.x, p.y, 1)

    @classmethod
    def _fromJacobian(cls, p, P):
        """
        Convert point back from Jacobian coordinates

        :param p: First Point you want to add
        :param P: Prime number in the module of the equation Y^2 = X^3 + A*X + B (mod p)
        :return: Point in default coordinates
        """
        z = cls.inv(p.z, P)
        x = (p.x * z ** 2) % P
        y = (p.y * z ** 3) % P

        return Point(x, y, 0)

    @classmethod
    def _jacobianDouble(cls, p, A, P):
        """
        Double a point in elliptic curves

        :param p: Point you want to double
        :param P: Prime number in the module of the equation Y^2 = X^3 + A*X + B (mod p)
        :param A: Coefficient of the first-order term of the equation Y^2 = X^3 + A*X + B (mod p)
        :return: Point that represents the sum of First and Second Point
        """
        if p.y == 0:
            return Point(0, 0, 0)

        ysq = (p.y ** 2) % P
        S = (4 * p.x * ysq) % P
        M = (3 * p.x ** 2 + A * p.z ** 4) % P
        nx = (M**2 - 2 * S) % P
        ny = (M * (S - nx) - 8 * ysq ** 2) % P
        nz = (2 * p.y * p.z) % P

        return Point(nx, ny, nz)

    @classmethod
    def _jacobianAdd(cls, p, q, A, P):
        """
        Add two points in elliptic curves

        :param p: First Point you want to add
        :param q: Second Point you want to add
        :param P: Prime number in the module of the equation Y^2 = X^3 + A*X + B (mod p)
        :param A: Coefficient of the first-order term of the equation Y^2 = X^3 + A*X + B (mod p)
        :return: Point that represents the sum of First and Second Point
        """
        if p.y == 0:
            return q
        if q.y == 0:
            return p

        U1 = (p.x * q.z ** 2) % P
        U2 = (q.x * p.z ** 2) % P
        S1 = (p.y * q.z ** 3) % P
        S2 = (q.y * p.z ** 3) % P

        if U1 == U2:
            if S1 != S2:
                return Point(0, 0, 1)
            return cls._jacobianDouble(p, A, P)

        H = U2 - U1
        R = S2 - S1
        H2 = (H * H) % P
        H3 = (H * H2) % P
        U1H2 = (U1 * H2) % P
        nx = (R ** 2 - H3 - 2 * U1H2) % P
        ny = (R * (U1H2 - nx) - S1 * H3) % P
        nz = (H * p.z * q.z) % P

        return Point(nx, ny, nz)

    @classmethod
    def _jacobianMultiply(cls, p, n, N, A, P):
        """
        Multily point and scalar in elliptic curves

        :param p: First Point to mutiply
        :param n: Scalar to mutiply
        :param N: Order of the elliptic curve
        :param P: Prime number in the module of the equation Y^2 = X^3 + A*X + B (mod p)
        :param A: Coefficient of the first-order term of the equation Y^2 = X^3 + A*X + B (mod p)
        :return: Point that represents the sum of First and Second Point
        """
        if p.y == 0 or n == 0:
            return Point(0, 0, 1)

        if n == 1:
            return p

        if n < 0 or n >= N:
            return cls._jacobianMultiply(p, n % N, N, A, P)

        if (n % 2) == 0:
            return cls._jacobianDouble(
                cls._jacobianMultiply(p, n // 2, N, A, P), A, P
            )

        return cls._jacobianAdd(
            cls._jacobianDouble(cls._jacobianMultiply(p, n // 2, N, A, P), A, P), p, A, P
        )
