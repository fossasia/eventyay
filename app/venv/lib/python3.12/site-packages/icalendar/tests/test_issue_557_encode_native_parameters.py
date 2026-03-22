"""These are tests for Issue #557

TL;DR: Component._encode lost given parameters
if the object to encode was already of native type,
making its behavior unexpected.

see https://github.com/collective/icalendar/issues/557
"""

import unittest

from icalendar.cal.component import Component


class TestComponentEncode(unittest.TestCase):
    def test_encode_non_native_parameters(self):
        """Test _encode to add parameters to non-natives"""
        self.__assert_native_content(self.summary)
        self.__assert_native_kept_parameters(self.summary)

    def test_encode_native_keep_params_None(self):
        """_encode should keep parameters on natives
        if parameters=None
        """
        new_sum = self.__add_params(
            self.summary,
            parameters=None,
        )
        self.__assert_native_content(new_sum)
        self.__assert_native_kept_parameters(new_sum)

    def test_encode_native_keep_params_empty(self):
        """_encode should keep paramters on natives
        if parameters={}
        """
        new_sum = self.__add_params(
            self.summary,
            parameters={},
        )
        self.__assert_native_content(new_sum)
        self.__assert_native_kept_parameters(new_sum)

    def test_encode_native_append_params(self):
        """_encode should append paramters on natives
        keeping old parameters
        """
        new_sum = self.__add_params(
            self.summary,
            parameters={"X-PARAM": "Test123"},
        )
        self.__assert_native_content(new_sum)
        self.__assert_native_kept_parameters(new_sum)
        self.assertParameter(new_sum, "X-PARAM", "Test123")

    def test_encode_native_overwrite_params(self):
        """_encode should overwrite single parameters
        if they have the same name as old ones"""
        new_sum = self.__add_params(
            self.summary,
            parameters={"LANGUAGE": "de"},
        )
        self.__assert_native_content(new_sum)
        self.assertParameter(new_sum, "LANGUAGE", "de")

    def test_encode_native_remove_params(self):
        """_encode should remove single parameters
        if they are explicitly set to None"""
        new_sum = self.__add_params(
            self.summary,
            parameters={"LANGUAGE": None},
        )
        self.__assert_native_content(new_sum)
        self.assertParameterMissing(new_sum, "LANGUAGE")

    def test_encode_native_remove_already_missing(self):
        """_encode should ignore removing a parameter
        that was already missing"""
        self.assertParameterMissing(self.summary, "X-MISSING")
        new_sum = self.__add_params(
            self.summary,
            parameters={"X-MISSING": None},
        )
        self.__assert_native_content(new_sum)
        self.__assert_native_kept_parameters(new_sum)
        self.assertParameterMissing(self.summary, "X-MISSING")

    def test_encode_native_full_test(self):
        """full test case with keeping, overwriting & removing properties"""
        # preperation
        orig_sum = self.__add_params(
            self.summary,
            parameters={
                "X-OVERWRITE": "overwrite me!",
                "X-REMOVE": "remove me!",
                "X-MISSING": None,
            },
        )
        # preperation check
        self.__assert_native_content(orig_sum)
        self.__assert_native_kept_parameters(orig_sum)
        self.assertParameter(orig_sum, "X-OVERWRITE", "overwrite me!")
        self.assertParameter(orig_sum, "X-REMOVE", "remove me!")
        self.assertParameterMissing(orig_sum, "X-MISSING")
        # modification
        new_sum = self.__add_params(
            orig_sum,
            parameters={
                "X-OVERWRITE": "overwritten",
                "X-REMOVE": None,
                "X-MISSING": None,
            },
        )
        # final asserts
        self.__assert_native_content(new_sum)
        self.__assert_native_kept_parameters(new_sum)
        self.assertParameter(new_sum, "X-OVERWRITE", "overwritten")
        self.assertParameterMissing(new_sum, "X-REMOVE")
        self.assertParameterMissing(new_sum, "X-MISSING")

    def setUp(self):
        self.summary = self.__gen_native()

    def __assert_native_kept_parameters(self, obj):
        self.assertParameter(obj, "LANGUAGE", "en")

    def __assert_native_content(self, obj):
        assert obj == "English Summary"

    def __add_params(self, obj, parameters):
        return Component._encode(
            "SUMMARY",
            obj,
            parameters=parameters,
            encode=True,
        )

    def __gen_native(self):
        return Component._encode(
            "SUMMARY",
            "English Summary",
            parameters={
                "LANGUAGE": "en",
            },
            encode=True,
        )

    def assertParameterMissing(self, obj, name):
        assert name not in obj.params

    def assertParameter(self, obj, name, val):
        assert name in obj.params
        assert obj.params[name] == val
