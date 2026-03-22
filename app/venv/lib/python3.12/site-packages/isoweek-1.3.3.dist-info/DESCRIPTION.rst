ISO Week
========

The isoweek module provide the class *Week*.  Instances represent specific weeks
spanning Monday to Sunday.  There are 52 or 53 numbered weeks in a year.  Week
1 is defined to be the first week with 4 or more days in January.

It's called isoweek because this is the week definition of ISO 8601.  This
standard also define a notation for identifying weeks; yyyyWww (where the "W"
is a literal).  An example is "2011W08" which denotes the 8th week of year
2011.  *Week* instances stringify to this form.

See also http://en.wikipedia.org/wiki/ISO_week_date

The *Week* instances are light weight and immutable with an interface similar
to the datetime.date objects.  Example code::

    from isoweek import Week
    w = Week(2011, 20)
    print "Week %s starts on %s" % (w, w.monday())

    print "Current week number is", Week.thisweek().week
    print "Next week is", Week.thisweek() + 1

Reference
----------

Constructor:

*class* isoweek.Week(*year*, *week*)
    All arguments are required.  Arguments should be ints.

    If the week number isn't within the range of the given year,
    the year is adjusted to make week number within range.  The
    final year must be within range 1 to 9999.  If not ValueError
    is raised.

Other constructors, all class methods:

*classmethod* Week.thisweek()
    Return the current week (local time).

*classmethod* Week.fromordinal(*ordinal*)
    Return the week corresponding to the proleptic Gregorian ordinal,
    where January 1 of year 1 starts the week with ordinal 1.

*classmethod* Week.fromstring(*isostring*)
    Return a week initialized from an ISO formatted string like "2011W08"
    or "2011-W08".  Note that weeks always stringify back in the former
    and more compact format.

*classmethod* Week.withdate(*date*)
    Return the week that contains the given datetime.date.

*classmethod* Week.weeks_of_year(*year*)
    Return an iterator over the weeks of the given year.

*classmethod* Week.last_week_of_year(*year*)
    Return the last week of the given year.

Instance attributes (read-only):

Week.year
    Between 1 and 9999 inclusive.

Week.week
    Between 1 and 53 inclusive (52 for most years).

Supported operations:

     ====================     ==========================================================
     Operation                Result
     ====================     ==========================================================
     week1 = week2 + int      week2 is int weeks removed from week1.
     week1 = week2 - int      Computes week2 such that week2 + int == week1
     int = week1 - week2      Computes int such that week2 + int == week1
     week1 < week2            week1 is considered less than week2 when week1 precedes week2 in time.
     ====================     ==========================================================

Instance methods:

Week.replace(*year*, *week*)
    Return a Week with the same value, except for those parameters
    given new values by whichever keyword arguments are specified.

Week.toordinal()
    Return the proleptic Gregorian ordinal the week, where January 1 of year 1
    starts the first week.

Week.day(*num*)
    Return the given day of week as a datetime.date object.
    Day 0 is Monday.

Week.monday(), Week.tuesday(),.. Week.sunday()
    Return the given day of week as a datetime.date object.

Week.days()
    Return the 7 days of the week as a list.

Week.contains(day)
    Check if the given datetime.date falls within the week.

Week.isoformat()
    Return a string representing the week in ISO 8601 format; "yyyyWww".
    For example Week(2011, 8).isoformat() == '2011W08'.

Week.__str__()
    For a Week w, str(w) is equivalent to w.isoformat()

Week.__repr__()
    Return a string like "isoweek.Week(2011, 2)".


