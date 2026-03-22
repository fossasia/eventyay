import base64
import json
import re
import os

import django
from django.conf import settings
from django.contrib.staticfiles.finders import get_finders
if django.VERSION >= (1,10):
    from django.templatetags.static import static as django_static
else:
    from django.contrib.staticfiles.templatetags.staticfiles import static as django_static

import sass
from compressor.filters.base import FilterBase


def static(path):
    """
    Use the Django builtin static file resolver to return an absolute path
    usable as CSS url() argument. Sass equivalent of the 'static' template
    tag.
    """
    return django_static(path)


OUTPUT_STYLE = getattr(settings, 'LIBSASS_OUTPUT_STYLE', 'nested')
SOURCE_COMMENTS = getattr(settings, 'LIBSASS_SOURCE_COMMENTS', settings.DEBUG)
CUSTOM_FUNCTIONS = getattr(settings, 'LIBSASS_CUSTOM_FUNCTIONS', {'static': static})
SOURCEMAPS = getattr(settings, 'LIBSASS_SOURCEMAPS', False)
PRECISION = getattr(settings, 'LIBSASS_PRECISION', None)  # None use libsass default
ADDITIONAL_INCLUDE_PATHS = getattr(settings, 'LIBSASS_ADDITIONAL_INCLUDE_PATHS', None)


INCLUDE_PATHS = None  # populate this on first call to 'get_include_paths'


def get_include_paths():
    """
    Generate a list of include paths that libsass should use to find files
    mentioned in @import lines.
    """
    global INCLUDE_PATHS
    if INCLUDE_PATHS is not None:
        return INCLUDE_PATHS

    include_paths = []

    # Look for staticfile finders that define 'storages'
    for finder in get_finders():
        try:
            storages = finder.storages
        except AttributeError:
            continue

        for storage in storages.values():
            try:
                include_paths.append(storage.path('.'))
            except NotImplementedError:
                # storages that do not implement 'path' do not store files locally,
                # and thus cannot provide an include path
                pass

    global ADDITIONAL_INCLUDE_PATHS
    if ADDITIONAL_INCLUDE_PATHS:
        include_paths.extend(ADDITIONAL_INCLUDE_PATHS)

    INCLUDE_PATHS = include_paths
    return include_paths


def prefix_sourcemap(sourcemap, base_path):
    decoded_sourcemap = json.loads(sourcemap)
    source_urls = []
    include_paths = get_include_paths()

    for source_filename in decoded_sourcemap['sources']:
        # expand source_filename into an absolute file path
        full_source_path = os.path.normpath(os.path.join(base_path, source_filename))

        # look for a path in include_paths that is a prefix of full_source_path
        for path in include_paths:
            if full_source_path.startswith(path):
                # A matching path has been found; take the remainder as a relative path.
                # include_paths entries do not include a trailing slash;
                # [len(path) + 1:] ensures that we trim the path plus trailing slash
                remainder = full_source_path[len(path) + 1:]

                # Invoke the 'static' template tag to turn the relative path into a URL
                source_urls.append(django_static(remainder))
                break
        else:
            # no matching path was found in include_paths; return the original source filename
            # as a fallback
            source_urls.append(source_filename)

    decoded_sourcemap['sources'] = source_urls
    return json.dumps(decoded_sourcemap)


def embed_sourcemap(output, sourcemap):
    encoded_sourcemap = base64.standard_b64encode(
        sourcemap.encode('utf-8')
    )
    sourcemap_fragment = 'sourceMappingURL=data:application/json;base64,{} '\
        .format(encoded_sourcemap.decode('utf-8'))
    url_re = re.compile(r'sourceMappingURL=[^\s]+', re.M)
    output = url_re.sub(sourcemap_fragment, output)

    return output


def compile(**kwargs):
    """Perform sass.compile, but with the appropriate include_paths for Django added"""
    kwargs = kwargs.copy()
    if PRECISION is not None:
        kwargs['precision'] = PRECISION
    kwargs['include_paths'] = (kwargs.get('include_paths') or []) + get_include_paths()

    custom_functions = CUSTOM_FUNCTIONS.copy()
    custom_functions.update(kwargs.get('custom_functions', {}))
    kwargs['custom_functions'] = custom_functions

    if SOURCEMAPS and kwargs.get('filename', None):
        # We need to pass source_map_file to libsass so it generates
        # correct paths to source files.
        base_path = os.path.dirname(kwargs['filename'])
        sourcemap_filename = os.path.join(base_path, 'sourcemap.map')
        kwargs['source_map_filename'] = sourcemap_filename

        libsass_output, sourcemap = sass.compile(**kwargs)
        sourcemap = prefix_sourcemap(sourcemap, base_path)
        output = embed_sourcemap(libsass_output, sourcemap)
    else:
        output = sass.compile(**kwargs)
    return output


class SassCompiler(FilterBase):
    def __init__(self, content, attrs=None, filter_type=None, charset=None, filename=None):
        # FilterBase doesn't handle being passed attrs, so fiddle the signature
        super(SassCompiler, self).__init__(content=content,
                                           filter_type=filter_type,
                                           filename=filename)

    def input(self, **kwargs):
        if self.filename:
            return compile(filename=self.filename,
                           output_style=OUTPUT_STYLE,
                           source_comments=SOURCE_COMMENTS)
        else:
            return compile(string=self.content,
                           output_style=OUTPUT_STYLE)
