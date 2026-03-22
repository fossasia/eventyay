from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, List, Protocol, TypeVar
from unittest import TestCase, skipIf

from .. import AlreadyBuiltError, NoTransition, TypeMachineBuilder, pep614

try:
    from zope.interface import Interface, implementer  # type:ignore[import-untyped]
except ImportError:
    hasInterface = False
else:
    hasInterface = True

    class ISomething(Interface):
        def something() -> int: ...  # type:ignore[misc,empty-body]


T = TypeVar("T")


class ProtocolForTesting(Protocol):

    def change(self) -> None:
        "Switch to the other state."

    def value(self) -> int:
        "Give a value specific to the given state."


class ArgTaker(Protocol):
    def takeSomeArgs(self, arg1: int = 0, arg2: str = "") -> None: ...
    def value(self) -> int: ...


class NoOpCore:
    "Just an object, you know?"


@dataclass
class Gen(Generic[T]):
    t: T


def buildTestBuilder() -> tuple[
    TypeMachineBuilder[ProtocolForTesting, NoOpCore],
    Callable[[NoOpCore], ProtocolForTesting],
]:
    builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)
    first = builder.state("first")
    second = builder.state("second")

    first.upon(ProtocolForTesting.change).to(second).returns(None)
    second.upon(ProtocolForTesting.change).to(first).returns(None)

    @pep614(first.upon(ProtocolForTesting.value).loop())
    def firstValue(machine: ProtocolForTesting, core: NoOpCore) -> int:
        return 3

    @pep614(second.upon(ProtocolForTesting.value).loop())
    def secondValue(machine: ProtocolForTesting, core: NoOpCore) -> int:
        return 4

    return builder, builder.build()


builder, machineFactory = buildTestBuilder()


def needsSomething(proto: ProtocolForTesting, core: NoOpCore, value: str) -> int:
    "we need data to build this state"
    return 3  # pragma: no cover


def needsNothing(proto: ArgTaker, core: NoOpCore) -> str:
    return "state-specific data"  # pragma: no cover


class SimpleProtocol(Protocol):
    def method(self) -> None:
        "A method"


class Counter(Protocol):
    def start(self) -> None:
        "enter the counting state"

    def increment(self) -> None:
        "increment the counter"

    def stop(self) -> int:
        "stop"


@dataclass
class Count:
    value: int = 0


class TypeMachineTests(TestCase):

    def test_oneTransition(self) -> None:

        machine = machineFactory(NoOpCore())

        self.assertEqual(machine.value(), 3)
        machine.change()
        self.assertEqual(machine.value(), 4)
        self.assertEqual(machine.value(), 4)
        machine.change()
        self.assertEqual(machine.value(), 3)

    def test_stateSpecificData(self) -> None:

        builder = TypeMachineBuilder(Counter, NoOpCore)
        initial = builder.state("initial")
        counting = builder.state("counting", lambda machine, core: Count())
        initial.upon(Counter.start).to(counting).returns(None)

        @pep614(counting.upon(Counter.increment).loop())
        def incf(counter: Counter, core: NoOpCore, count: Count) -> None:
            count.value += 1

        @pep614(counting.upon(Counter.stop).to(initial))
        def finish(counter: Counter, core: NoOpCore, count: Count) -> int:
            return count.value

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.start()
        machine.increment()
        machine.increment()
        self.assertEqual(machine.stop(), 2)
        machine.start()
        machine.increment()
        self.assertEqual(machine.stop(), 1)

    def test_stateSpecificDataWithoutData(self) -> None:
        """
        To facilitate common implementations of transition behavior methods,
        sometimes you want to implement a transition within a data state
        without taking a data parameter.  To do this, pass the 'nodata=True'
        parameter to 'upon'.
        """
        builder = TypeMachineBuilder(Counter, NoOpCore)
        initial = builder.state("initial")
        counting = builder.state("counting", lambda machine, core: Count())
        startCalls = []

        @pep614(initial.upon(Counter.start).to(counting))
        @pep614(counting.upon(Counter.start, nodata=True).loop())
        def start(counter: Counter, core: NoOpCore) -> None:
            startCalls.append("started!")

        @pep614(counting.upon(Counter.increment).loop())
        def incf(counter: Counter, core: NoOpCore, count: Count) -> None:
            count.value += 1

        @pep614(counting.upon(Counter.stop).to(initial))
        def finish(counter: Counter, core: NoOpCore, count: Count) -> int:
            return count.value

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.start()
        self.assertEqual(len(startCalls), 1)
        machine.start()
        self.assertEqual(len(startCalls), 2)
        machine.increment()
        self.assertEqual(machine.stop(), 1)

    def test_incompleteTransitionDefinition(self) -> None:
        builder = TypeMachineBuilder(SimpleProtocol, NoOpCore)
        sample = builder.state("sample")
        sample.upon(SimpleProtocol.method).loop()  # oops, no '.returns(None)'
        with self.assertRaises(ValueError) as raised:
            builder.build()
        self.assertIn(
            "incomplete transition from sample to sample upon SimpleProtocol.method",
            str(raised.exception),
        )

    def test_dataToData(self) -> None:
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)

        @dataclass
        class Data1:
            value: int

        @dataclass
        class Data2:
            stuff: List[str]

        initial = builder.state("initial")
        counting = builder.state("counting", lambda proto, core: Data1(1))
        appending = builder.state("appending", lambda proto, core: Data2([]))

        initial.upon(ProtocolForTesting.change).to(counting).returns(None)

        @pep614(counting.upon(ProtocolForTesting.value).loop())
        def countup(p: ProtocolForTesting, c: NoOpCore, d: Data1) -> int:
            d.value *= 2
            return d.value

        counting.upon(ProtocolForTesting.change).to(appending).returns(None)

        @pep614(appending.upon(ProtocolForTesting.value).loop())
        def appendup(p: ProtocolForTesting, c: NoOpCore, d: Data2) -> int:
            d.stuff.extend("abc")
            return len(d.stuff)

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.change()
        self.assertEqual(machine.value(), 2)
        self.assertEqual(machine.value(), 4)
        machine.change()
        self.assertEqual(machine.value(), 3)
        self.assertEqual(machine.value(), 6)

    def test_dataFactoryArgs(self) -> None:
        """
        Any data factory that takes arguments will constrain the allowed
        signature of all protocol methods that transition into that state.
        """
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)
        initial = builder.state("initial")
        data = builder.state("data", needsSomething)
        data2 = builder.state("data2", needsSomething)
        # toState = initial.to(data)

        # 'assertions' in the form of expected type errors:
        # (no data -> data)
        uponNoData = initial.upon(ProtocolForTesting.change)
        uponNoData.to(data)  # type:ignore[arg-type]

        # (data -> data)
        uponData = data.upon(ProtocolForTesting.change)
        uponData.to(data2)  # type:ignore[arg-type]

    def test_dataFactoryNoArgs(self) -> None:
        """
        Inverse of C{test_dataFactoryArgs} where the data factory specifically
        does I{not} take arguments, but the input specified does.
        """
        builder = TypeMachineBuilder(ArgTaker, NoOpCore)
        initial = builder.state("initial")
        data = builder.state("data", needsNothing)
        (
            initial.upon(ArgTaker.takeSomeArgs)
            .to(data)  # type:ignore[arg-type]
            .returns(None)
        )

    def test_invalidTransition(self) -> None:
        """
        Invalid transitions raise a NoTransition exception.
        """
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)
        builder.state("initial")
        factory = builder.build()
        machine = factory(NoOpCore())
        with self.assertRaises(NoTransition):
            machine.change()

    def test_reentrancy(self) -> None:
        """
        During the execution of a transition behavior implementation function,
        you may invoke other methods on your state machine.  However, the
        execution of the behavior of those methods will be deferred until the
        current behavior method is done executing.  In order to implement that
        deferral, we restrict the set of methods that can be invoked to those
        that return None.

        @note: it may be possible to implement deferral via Awaitables or
            Deferreds later, but we are starting simple.
        """

        class SomeMethods(Protocol):
            def start(self) -> None:
                "Start the machine."

            def later(self) -> None:
                "Do some deferrable work."

        builder = TypeMachineBuilder(SomeMethods, NoOpCore)

        initial = builder.state("initial")
        second = builder.state("second")

        order = []

        @pep614(initial.upon(SomeMethods.start).to(second))
        def startup(methods: SomeMethods, core: NoOpCore) -> None:
            order.append("startup")
            methods.later()
            order.append("startup done")

        @pep614(second.upon(SomeMethods.later).loop())
        def later(methods: SomeMethods, core: NoOpCore) -> None:
            order.append("later")

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        machine.start()
        self.assertEqual(order, ["startup", "startup done", "later"])

    def test_reentrancyNotNoneError(self) -> None:
        class SomeMethods(Protocol):
            def start(self) -> None:
                "Start the machine."

            def later(self) -> int:
                "Do some deferrable work."

        builder = TypeMachineBuilder(SomeMethods, NoOpCore)

        initial = builder.state("initial")
        second = builder.state("second")

        order = []

        @pep614(initial.upon(SomeMethods.start).to(second))
        def startup(methods: SomeMethods, core: NoOpCore) -> None:
            order.append("startup")
            methods.later()
            order.append("startup done")  # pragma: no cover

        @pep614(second.upon(SomeMethods.later).loop())
        def later(methods: SomeMethods, core: NoOpCore) -> int:
            order.append("later")
            return 3

        machineFactory = builder.build()
        machine = machineFactory(NoOpCore())
        with self.assertRaises(RuntimeError):
            machine.start()
        self.assertEqual(order, ["startup"])
        # We do actually do the state transition, which happens *before* the
        # output is generated; TODO: maybe we should have exception handling
        # that transitions into an error state that requires explicit recovery?
        self.assertEqual(machine.later(), 3)
        self.assertEqual(order, ["startup", "later"])

    def test_buildLock(self) -> None:
        """
        ``.build()`` locks the builder so it can no longer be modified.
        """
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)
        state = builder.state("test-state")
        state2 = builder.state("state2")
        state3 = builder.state("state3")
        upon = state.upon(ProtocolForTesting.change)
        to = upon.to(state2)
        to2 = upon.to(state3)
        to.returns(None)
        with self.assertRaises(ValueError) as ve:
            to2.returns(None)
        with self.assertRaises(AlreadyBuiltError):
            to.returns(None)
        builder.build()
        with self.assertRaises(AlreadyBuiltError):
            builder.state("hello")
        with self.assertRaises(AlreadyBuiltError):
            builder.build()

    def test_methodMembership(self) -> None:
        """
        Input methods must be members of their protocol.
        """
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)
        state = builder.state("test-state")

        def stateful(proto: ProtocolForTesting, core: NoOpCore) -> int:
            return 4  # pragma: no cover

        state2 = builder.state("state2", stateful)

        def change(self: ProtocolForTesting) -> None: ...

        def rogue(self: ProtocolForTesting) -> int:
            return 3  # pragma: no cover

        with self.assertRaises(ValueError):
            state.upon(change)
        with self.assertRaises(ValueError) as ve:
            state2.upon(change)
        with self.assertRaises(ValueError):
            state.upon(rogue)

    def test_startInAlternateState(self) -> None:
        """
        The state machine can be started in an alternate state.
        """
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)
        one = builder.state("one")
        two = builder.state("two")

        @dataclass
        class Three:
            proto: ProtocolForTesting
            core: NoOpCore
            value: int = 0

        three = builder.state("three", Three)
        one.upon(ProtocolForTesting.change).to(two).returns(None)
        one.upon(ProtocolForTesting.value).loop().returns(1)
        two.upon(ProtocolForTesting.change).to(three).returns(None)
        two.upon(ProtocolForTesting.value).loop().returns(2)

        @pep614(three.upon(ProtocolForTesting.value).loop())
        def threevalue(proto: ProtocolForTesting, core: NoOpCore, three: Three) -> int:
            return 3 + three.value

        onetwothree = builder.build()

        # confirm positive behavior first, particularly the value of the three
        # state's change
        normal = onetwothree(NoOpCore())
        self.assertEqual(normal.value(), 1)
        normal.change()
        self.assertEqual(normal.value(), 2)
        normal.change()
        self.assertEqual(normal.value(), 3)

        # now try deserializing it in each state
        self.assertEqual(onetwothree(NoOpCore()).value(), 1)
        self.assertEqual(onetwothree(NoOpCore(), two).value(), 2)
        self.assertEqual(
            onetwothree(
                NoOpCore(), three, lambda proto, core: Three(proto, core, 4)
            ).value(),
            7,
        )

    def test_genericData(self) -> None:
        """
        Test to cover get_origin in generic assertion.
        """
        builder = TypeMachineBuilder(ArgTaker, NoOpCore)
        one = builder.state("one")

        def dat(
            proto: ArgTaker, core: NoOpCore, arg1: int = 0, arg2: str = ""
        ) -> Gen[int]:
            return Gen(arg1)

        two = builder.state("two", dat)
        one.upon(ArgTaker.takeSomeArgs).to(two).returns(None)

        @pep614(two.upon(ArgTaker.value).loop())
        def val(proto: ArgTaker, core: NoOpCore, data: Gen[int]) -> int:
            return data.t

        b = builder.build()
        m = b(NoOpCore())
        m.takeSomeArgs(3)
        self.assertEqual(m.value(), 3)

    @skipIf(not hasInterface, "zope.interface not installed")
    def test_interfaceData(self) -> None:
        """
        Test to cover providedBy assertion.
        """
        builder = TypeMachineBuilder(ArgTaker, NoOpCore)
        one = builder.state("one")

        @implementer(ISomething)
        @dataclass
        class Something:
            val: int

            def something(self) -> int:
                return self.val

        def dat(
            proto: ArgTaker, core: NoOpCore, arg1: int = 0, arg2: str = ""
        ) -> ISomething:
            return Something(arg1)  # type:ignore[return-value]

        two = builder.state("two", dat)
        one.upon(ArgTaker.takeSomeArgs).to(two).returns(None)

        @pep614(two.upon(ArgTaker.value).loop())
        def val(proto: ArgTaker, core: NoOpCore, data: ISomething) -> int:
            return data.something()  # type:ignore[misc]

        b = builder.build()
        m = b(NoOpCore())
        m.takeSomeArgs(3)
        self.assertEqual(m.value(), 3)

    def test_noMethodsInAltStateDataFactory(self) -> None:
        """
        When the state machine is received by a data factory during
        construction, it is in an invalid state.  It may be invoked after
        construction is complete.
        """
        builder = TypeMachineBuilder(ProtocolForTesting, NoOpCore)

        @dataclass
        class Data:
            value: int
            proto: ProtocolForTesting

        start = builder.state("start")
        data = builder.state("data", lambda proto, core: Data(3, proto))

        @pep614(data.upon(ProtocolForTesting.value).loop())
        def getval(proto: ProtocolForTesting, core: NoOpCore, data: Data) -> int:
            return data.value

        @pep614(start.upon(ProtocolForTesting.value).loop())
        def minusone(proto: ProtocolForTesting, core: NoOpCore) -> int:
            return -1

        factory = builder.build()
        self.assertEqual(factory(NoOpCore()).value(), -1)

        def touchproto(proto: ProtocolForTesting, core: NoOpCore) -> Data:
            return Data(proto.value(), proto)

        catchdata = []

        def notouchproto(proto: ProtocolForTesting, core: NoOpCore) -> Data:
            catchdata.append(new := Data(4, proto))
            return new

        with self.assertRaises(NoTransition):
            factory(NoOpCore(), data, touchproto)
        machine = factory(NoOpCore(), data, notouchproto)
        self.assertIs(machine, catchdata[0].proto)
        self.assertEqual(machine.value(), 4)
