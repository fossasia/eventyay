def has_ipdb():
    try:
        import ipdb
        import IPython
        return True
    except ImportError:
        return False


def get_ipdb():
    def_colors = get_def_colors()
    try:
        import ipdb
        from ipdb import __main__
        return ipdb.__main__.Pdb(def_colors)
    except ImportError:  # old versions of ipdb
        return ipdb.Pdb(def_colors)


def get_pdb_set_trace():
    # for the templatetags because the file is named 'pdb' and that cause an importation conflict
    from pdb import set_trace
    return set_trace


def get_def_colors():
    # Inspirated in https://github.com/gotcha/ipdb/blob/master/ipdb/__main__.py
    def_colors = 'Linux'
    import IPython
    if IPython.__version__ > '0.10.2':
        from IPython.core.debugger import Pdb
        try:
            get_ipython
        except NameError:
            from IPython.frontend.terminal.embed import InteractiveShellEmbed
            ipshell = InteractiveShellEmbed()
            def_colors = ipshell.colors
        else:
            try:
                def_colors = get_ipython.im_self.colors
            except AttributeError:
                def_colors = get_ipython.__self__.colors
    else:
        from IPython.Debugger import Pdb
        from IPython.Shell import IPShell
        from IPython import ipapi
        ip = ipapi.get()
        if ip is None:
            IPShell(argv=[''])
            ip = ipapi.get()
        def_colors = ip.options.colors
    return def_colors
