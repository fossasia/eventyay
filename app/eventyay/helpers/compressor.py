import logging
import re
import shlex
from pathlib import Path

from compressor.exceptions import FilterError
from compressor.filters import CompilerFilter
from django.conf import settings

from ..consts import FRONTEND_DEV_DIR

logger = logging.getLogger(__name__)


class VueCompiler(CompilerFilter):
    # Based on work (c) Laura Klünder in https://github.com/codingcatgirl/django-vue-rollup
    # Released under Apache License 2.0

    def __init__(self, content, attrs, **kwargs):
        cwd = Path.cwd()
        config_dir = FRONTEND_DEV_DIR / 'webcheckin-bundler'
        node_path = FRONTEND_DEV_DIR / 'webcheckin-bundler' / 'node_modules'
        self.rollup_bin = node_path / '.bin' / 'rollup'
        rollup_config = config_dir / 'rollup.config.js'
        if not (self.rollup_bin.exists()) and not settings.DEBUG:
            raise FilterError(
                f'Rollup not installed or system not built properly, please install Rollup in {config_dir} directory.'
            )
        command = (
            ' '.join(
                (
                    'NODE_PATH=' + shlex.quote(str(node_path.relative_to(cwd))),
                    shlex.quote(str(self.rollup_bin.relative_to(cwd))),
                    '-c',
                    shlex.quote(str(rollup_config.relative_to(cwd))),
                )
            )
            + ' --input {infile} -n {export_name} --file {outfile}'
        )
        super().__init__(content, command=command, **kwargs)

    def input(self, **kwargs):
        if self.filename is None:
            raise FilterError('VueCompiler can only compile files, not inline code.')
        if not self.rollup_bin.exists():
            dir = self.rollup_bin.parent.parent
            raise FilterError(f'Rollup not installed, please install Rollup in {dir}.')
        self.options += (
            (
                'export_name',
                re.sub(
                    r'^([a-z])|[^a-z0-9A-Z]+([a-zA-Z0-9])?',
                    lambda s: s.group(0)[-1].upper(),
                    Path(self.filename).stem,
                ),
            ),
        )
        return super().input(**kwargs)
