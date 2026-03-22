"""
Copyright (c) 2017-2023 Raphael Michel and contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is furnished
to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import os


class ValidationError(Exception):
    pass


def try_valid_xml(xmlout, schema):
    import xmlschema  # xmlschema does some weird monkeypatching in etree, if we import it globally, things fail
    try:
        my_schema = xmlschema.XMLSchema(os.path.join(os.path.dirname(__file__), 'schemas', schema + '.xsd'))
        my_schema.validate(xmlout.decode())

    except xmlschema.XMLSchemaValidationError as e:
        raise ValidationError(
            "The output SEPA file contains validation errors. This is likely due to an illegal value in one of "
            "your input fields."
        ) from e
