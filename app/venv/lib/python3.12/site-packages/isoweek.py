from datetime import date, datetime, timedelta
from collections import namedtuple

__version__ = (1, 3, 3)


import sys
if sys.version >= '3':
    # compatiblity tweaks
    basestring = str
    long = int

class Week(namedtuple('Week', ('year', 'week'))):
    """A Week represents a period of 7 days starting with a Monday.
    Weeks are identified by a year and week number within the year.
    This corresponds to the read-only attributes 'year' and 'week'.

    Week 1 of a year is defined to be the first week with 4 or more days in
    January.  The preceeding week is either week 52 or 53 of the
    preceeding year.

    Week objects are tuples, and thus immutable, with an interface
    similar to the standard datetime.date class.
    """
    __slots__ = ()

    def __new__(cls, year, week):
        """Initialize a Week tuple with the given year and week number.

        The week number does not have to be within range.  The numbers
        will be normalized if not.  The year must be within the range
        1 to 9999.
        """
        if week < 1 or week > 52:
            return cls(year, 1) + (week - 1)
        if year < 1 or year > 9999:
            raise ValueError("year is out of range")
        return super(Week, cls).__new__(cls, year, week)

    @classmethod
    def thisweek(cls):
        """Return the current week (local time)."""
        return cls(*(date.today().isocalendar()[:2]))

    @classmethod
    def fromordinal(cls, ordinal):
        """Return the week corresponding to the proleptic Gregorian ordinal,
        where January 1 of year 1 starts the week with ordinal 1.
        """
        if ordinal < 1:
            raise ValueError("ordinal must be >= 1")
        return super(Week, cls).__new__(cls, *(date.fromordinal((ordinal-1) * 7 + 1).isocalendar()[:2]))

    @classmethod
    def fromstring(cls, isostring):
        """Return a week initialized from an ISO formatted string like "2011W08" or "2011-W08"."""
        if isinstance(isostring, basestring) and len(isostring) == 7 and isostring[4] == 'W':
           return cls(int(isostring[0:4]), int(isostring[5:7]))
        elif isinstance(isostring, basestring) and len(isostring) == 8 and isostring[4:6] == '-W':
           return cls(int(isostring[0:4]), int(isostring[6:8]))
        else:
            raise ValueError("Week.tostring argument must be on the form <yyyy>W<ww>; got %r" % (isostring,))

    @classmethod
    def withdate(cls, date):
        """Return the week that contains the given datetime.date"""
        return cls(*(date.isocalendar()[:2]))

    @classmethod
    def weeks_of_year(cls, year):
        """Return an iterator over the weeks of the given year.
        Years have either 52 or 53 weeks."""
        w = cls(year, 1)
        while w.year == year:
            yield w
            w += 1

    @classmethod
    def last_week_of_year(cls, year):
        """Return the last week of the given year.
        This week with either have week-number 52 or 53.

        This will be the same as Week(year+1, 0), but will even work for
        year 9999 where this expression would overflow.

        The first week of a given year is simply Week(year, 1), so there
        is no dedicated classmethod for that.
        """
        if year == cls.max.year:
            return cls.max
        return cls(year+1, 0)

    def day(self, num):
        """Return the given day of week as a date object.  Day 0 is the Monday."""
        d = date(self.year, 1, 4)  # The Jan 4th must be in week 1 according to ISO
        return d + timedelta(weeks=self.week-1, days=-d.weekday() + num)

    def monday(self):
        """Return the first day of the week as a date object"""
        return self.day(0)

    def tuesday(self):
        """Return the second day the week as a date object"""
        return self.day(1)

    def wednesday(self):
        """Return the third day the week as a date object"""
        return self.day(2)

    def thursday(self):
        """Return the fourth day the week as a date object"""
        return self.day(3)

    def friday(self):
        """Return the fifth day the week as a date object"""
        return self.day(4)

    def saturday(self):
        """Return the sixth day the week as a date object"""
        return self.day(5)

    def sunday(self):
        """Return the last day the week as a date object"""
        return self.day(6)

    def days(self):
        """Return the 7 days of the week as a list (of datetime.date objects)"""
        monday = self.day(0)
        return [monday + timedelta(days=i) for i in range(7)]

    def contains(self, day):
        """Check if the given datetime.date falls within the week"""
        return self.day(0) <= day < self.day(7)

    def toordinal(self):
        """Return the proleptic Gregorian ordinal the week, where January 1 of year 1 starts the first week."""
        return self.monday().toordinal() // 7 + 1

    def replace(self, year=None, week=None):
        """Return a Week with either the year or week attribute value replaced"""
        return self.__class__(self.year if year is None else year,
                              self.week if week is None else week)

    def year_week(self):
        """Return a regular tuple containing the (year, week)"""
        return self.year, self.week

    def __str__(self):
        """Return a ISO formatted week string like "2011W08". """
        return '%04dW%02d' % self

    isoformat = __str__  # compatibility with datetime.date

    def __repr__(self):
        """Return a string like "isoweek.Week(2011, 35)"."""
        return __name__ + '.' + self.__class__.__name__ + '(%d, %d)' % self

    def __add__(self, other):
        """Adding integers to a Week gives the week that many number of weeks into the future.
        Adding with datetime.timedelta is also supported.
        """
        if isinstance(other, timedelta):
            other = other.days // 7
        return self.__class__.fromordinal(self.toordinal() + other)

    def __sub__(self, other):
        """Subtracting two weeks give the number of weeks between them as an integer.
        Subtracting an integer gives another Week in the past."""
        if isinstance(other, (int, long, timedelta)):
            return self.__add__(-other)
        return self.toordinal() - other.toordinal()

Week.min = Week(1,1)
Week.max = Week(9999,52)
Week.resolution = timedelta(weeks=1)
