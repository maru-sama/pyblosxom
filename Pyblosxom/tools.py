#######################################################################
# This file is part of PyBlosxom.
#
# Copyright (c) 2003, 2004, 2005, 2006 Wari Wahab
# 
# PyBlosxom is distributed under the MIT license.  See the file LICENSE
# for distribution details.
#
# $Id$
#######################################################################
"""Utility module for functions that are useful to PyBlosxom and
plugins.

:var:
   month2num : dict
      dict of month name (i.e. ``Jan``) to number (i.e. ``1``)
   num2month : dict
      dict of number (i.e. ``1``) to month name (i.e. ``Jan``)
   MONTHS : list of strings and ints
      list of all valid month names and month numbers
   VAR_REGEXP : regexp instance
      regular expression instance for picking out template variables
"""

__revision__ = "$Revision$"

import sgmllib
import re
import os
import time
import os.path
import stat
import sys
import locale
import urllib
import inspect

try:
    from xml.sax.saxutils import escape
except ImportError:
    from cgi import escape


# Pyblosxom imports
from Pyblosxom import plugin_utils

# Month names tend to differ with locale
month2num = None
num2month = None
MONTHS    = None

# regular expression for detection and substituion of variables.
VAR_REGEXP = re.compile(ur"""
    (?<!\\)   # if the $ is escaped, then this isn't a variable
    \$        # variables start with a $
    (
        (?:\w|\-|::\w)+       # word char, - or :: followed by a word char
        (?:
            \(                # an open paren
            .*?               # followed by non-greedy bunch of stuff
            (?<!\\)\)         # with an end paren that's not escaped
        )?    # 0 or 1 of these ( ... ) blocks
    |
        \(
        (?:\w|\-|::\w)+       # word char, - or :: followed by a word char
        (?:
            \(                # an open paren
            .*?               # followed by non-greedy bunch of stuff
            (?<!\\)\)         # with an end paren that's not escaped
        )?    # 0 or 1 of these ( ... ) blocks
        \)
    ) 
    """, re.VERBOSE)


# reference to the pyblosxom config dict
_config = None

def initialize(config):
    """Initializes the tools module.

    This gives the module a chance to use configuration from the pyblosxom 
    config.py file.

    This should be called from Pyblosxom.pyblosxom.PyBlosxom.initialize.
    """
    global _config
    _config = config

    # Month names tend to differ with locale
    global month2num
    try:
        month2num = { 'nil' : '00',
                      locale.nl_langinfo(locale.ABMON_1) : '01',
                      locale.nl_langinfo(locale.ABMON_2) : '02',
                      locale.nl_langinfo(locale.ABMON_3) : '03',
                      locale.nl_langinfo(locale.ABMON_4) : '04',
                      locale.nl_langinfo(locale.ABMON_5) : '05',
                      locale.nl_langinfo(locale.ABMON_6) : '06',
                      locale.nl_langinfo(locale.ABMON_7) : '07',
                      locale.nl_langinfo(locale.ABMON_8) : '08',
                      locale.nl_langinfo(locale.ABMON_9) : '09',
                      locale.nl_langinfo(locale.ABMON_10) : '10',
                      locale.nl_langinfo(locale.ABMON_11) : '11',
                      locale.nl_langinfo(locale.ABMON_12) : '12'}

    except:
        # Windows doesn't have nl_langinfo, so we use one that 
        # only return English.
        # FIXME - need a better hack for this issue.
        month2num = { 'nil' : '00',
                      "Jan" : '01',
                      "Feb" : '02',
                      "Mar" : '03',
                      "Apr" : '04',
                      "May" : '05',
                      "Jun" : '06',
                      "Jul" : '07',
                      "Aug" : '08',
                      "Sep" : '09',
                      "Oct" : '10',
                      "Nov" : '11',
                      "Dec" : '12'}

    # This is not python 2.1 compatible (Nifty though)
    # num2month = dict(zip(month2num.itervalues(), month2num))
    global num2month
    num2month = {}
    for month_abbr, month_num in month2num.items():
        num2month[month_num] = month_abbr
        num2month[int(month_num)] = month_abbr
    
    # all the valid month possibilities
    global MONTHS
    MONTHS = num2month.keys() + month2num.keys()

def cleanup():
    """Cleanup the tools module.

    This should be called from Pyblosxom.pyblosxom.PyBlosxom.cleanup.
    """
    global _loghandler_registry
    # try:
    #     import logging
    #     if _use_custom_logger:
    #         raise ImportError, "whatever"
    # except ImportError:
    #     import _logging as logging

    # try:
    #     logging.shutdown()
    #     _loghandler_registry = {}
    # except ValueError:
    #     pass
    pass

class ConfigSyntaxErrorException(Exception):
    pass

def convert_configini_values(configini):
    """Takes a dict containing config.ini style keys and values, converts
    the values, and returns a new config dict.

    :Parameters:
       configini : dict
          dict containing config.ini style keys and values

    :Exceptions:
       ConfigSyntaxErrorException
          raised when there's a syntax error
    """
    def s_or_i(s):
        if s.startswith('"'):
            if s.endswith('"'):
                return s[1:-1]
            else:
                raise ConfigSyntaxErrorException("config syntax error: string '%s' missing end \"" % s)
        elif s.startswith("'"):
            if s.endswith("'"):
                return s[1:-1]
            else:
                raise ConfigSyntaxErrorException("config syntax error: string '%s' missing end '" % s)
        elif s.isdigit():
            return int(s)
        return s

    config = {}
    for key, value in configini.items():
        # in configini.items, we pick up a local_config which seems
        # to be a copy of what's in configini.items--puzzling.
        if type(value) == type( {} ):
            continue
        value = value.strip()
        if value.startswith("["):
            if value.endswith("]"):
                value2 = value[1:-1].strip().split(",")
                if len(value2) == 1 and value2[0] == "":
                    # handle the foo = [] case
                    config[key] = []
                else:
                    config[key] = [s_or_i(s.strip()) for s in value2]
            else:
                raise ConfigSyntaxErrorException("config syntax error: list '%s' missing end ]" % value)
        else:
            config[key] = s_or_i(value)

    return config


def escape_text(s):
    """Takes in a string and converts ``'`` to ``&apos;`` and ``"`` to 
    ``&quot;``.

    Note: if ``s`` is ``None``, then we return ``None``.

    >>> escape_text(None)
    None
    >>> escape_text("")
    ""
    >>> escape_text("a'b")
    "a&apos;b"
    >>> escape_text('a"b')
    "a&quot;b"
    """
    if not s: 
        return s

    return escape(s, {"'": "&apos;", '"': "&quot;"} )


def urlencode_text(s):
    """Calls ``urllib.quote`` on the string ``s``.

    Note: if ``s`` is ``None``, then we return ``None``.

    >>> urlencode_text(None)
    None
    >>> urlencode_text("")
    ""
    >>> urlencode_text("a c")
    "a%20c"
    >>> urlencode_text("a&c")
    "a%26c"
    >>> urlencode_text("a=c")
    "a%3Dc"

    """
    if not s: 
        return s

    return urllib.quote(s)

STANDARD_FILTERS = { "escape": lambda req, vd, s : escape_text(s),
                     "urlencode": lambda req, vd, s : urlencode_text(s) }


class Stripper(sgmllib.SGMLParser):
    """
    SGMLParser that removes HTML formatting code.
    """
    def __init__(self):
        """
        Initializes the instance.
        """
        self.data = []
        sgmllib.SGMLParser.__init__(self)

    def unknown_starttag(self, tag, attrs): 
        """
        Implements unknown_starttag.  Appends a space to the buffer.
        """
        self.data.append(" ")

    def unknown_endtag(self, tag): 
        """
        Implements unknown_endtag.  Appends a space to the buffer.
        """
        self.data.append(" ")

    def handle_data(self, data): 
        """
        Implements handle_data.  Appends data to the buffer.
        """
        self.data.append(data)

    def gettext(self): 
        """
        Returns the buffer.
        """
        return "".join(self.data)

def commasplit(s):
    """
    Splits a string that contains strings by comma.  This is
    more involved than just an ``s.split(",")`` because this handles
    commas in strings correctly.

    Note: commasplit doesn't remove extranneous spaces.

    >>> tools.commasplit(None)
    []
    >>> tools.commasplit("")
    [""]
    >>> tools.commasplit("a")
    ["a"]
    >>> tools.commasplit("a, b, c")
    ["a", " b", " c"]
    >>> tools.commasplit("'a', 'b, c'")
    ["a", " 'b, c'"]
    >>> tools.commasplit("'a', \"b, c\"")
    ["a", " \"b, c\""]

    This returns a list of strings.

    :Parameters:
       s : string
          the string to split
    """
    if s is None:
        return []

    if not s:
        return [""]

    startstring = None
    t = []
    l = []

    for c in s:
        if c == startstring:
            startstring = None
            t.append(c)

        elif c == "'" or c == '"':
            startstring = c
            t.append(c)

        elif not startstring and c == ",":
            l.append("".join(t))
            t = []

        else:
            t.append(c)

    if t:
        l.append("".join(t))

    return l


class Replacer:
    """
    Class for replacing variables in a template

    This class is a utility class used to provide a bound method to the
    C{re.sub()} function.  

    Originally based on OPAGCGI, but mostly re-written.
    """
    def __init__(self, request, encoding, var_dict):
        """
        Its only duty is to populate itself with the replacement dictionary
        passed.

        @param request: the Request object
        @type  request: Request 

        @param encoding: the encoding to use
        @type  encoding: string

        @param var_dict: The dict for variable substitution
        @type var_dict: dict
        """
        self._request = request
        self._encoding = encoding
        self.var_dict = var_dict

    def replace(self, matchobj):
        """
        This is passed a match object by ``re.sub()`` which represents a
        template variable without the ``$``.  parse manipulates the variable
        and returns the expansion of that variable using the following
        rules:

        1. if the variable ``v`` is an identifier, but not in the variable
           dict, then we return the empty string, or

        2. if the variable ``v`` is an identifier in the variable dict, then
           we return ``var_dict[v]``, or

        3. if the variable ``v`` is a function call where the function is
           an identifier in the variable dict, then

           - if ``v`` has no passed arguments and the function takes no
             arguments we return ``var_dict[v]()`` (this is the old
             behavior

           - if ``v`` has no passed arguments and the function takes two
             arguments we return ``var_dict[v](request, vd)``

           - if ``v`` has passed arguments, we return 
             ``var_dict[v](request, vd, *args)`` after some mild 
             processing of the arguments

        Also, for backwards compatability reasons, we convert things like::

            $id_escaped
            $id_urlencoded
            $(id_escaped)
            $(id_urlencoded)

        to::

            $escape(id)
            $urlencode(id)

        It returns the substituted string.

        :Parameters:
           matchobj : re.matchobj
              regular expression match object
        """
        vd = self.var_dict
        request = self._request
        key = matchobj.group(1)

        # if the variable is using $(foo) syntax, then we strip the
        # outer parens here.
        if key.startswith("(") and key.endswith(")"):
            key = key[1:-1]

        # do this for backwards-compatability reasons
        if key.endswith("_escaped"):
            key = "escape(%s)" % key[:-8]
        elif key.endswith("_urlencoded"):
            key = "urlencode(%s)" % key[:-11]

        if key.find("(") != -1 and key.rfind(")") > key.find("("):
            args = key[key.find("(")+1:key.rfind(")")]
            key = key[:key.find("(")]
        else:
            args = None

        if not vd.has_key(key):
            return u''

        r = vd[key]

        # if the value turns out to be a function, then we call it
        # with the args that we were passed.
        if callable(r):
            if args:
                def fix(s, vd=vd):
                    # if it's an int, return an int
                    if s.isdigit(): 
                        return int(s)
                    # if it's a string, return a string
                    if s.startswith("'") or s.startswith('"'):
                        return s[1:-1]
                    # otherwise it might be an identifier--check
                    # the vardict and return the value if it's in
                    # there
                    if vd.has_key(s):
                        return vd[s]
                    if s.startswith("$") and vd.has_key(s[1:]):
                        return vd[s[1:]]
                    return s
                args = [fix(arg.strip()) for arg in commasplit(args)]

                # stick the request and var_dict in as the first and second
                # arguments
                args.insert(0, vd)
                args.insert(0, request)

                r = r(*args)

            elif len(inspect.getargspec(r)[0]) == 2:
                r = r(request, vd)

            else:
                # this case is here for handling the old behavior where
                # functions took no arguments
                r = r()

        # if the result is not a string or unicode object, we call str on 
        # it.
        if not isinstance(r, str) and not isinstance(r, unicode):
            r = str(r)

        # then we convert it to unicode
        if not isinstance(r, unicode):
            # convert strings to unicode, assumes strings in iso-8859-1
            r = unicode(r, self._encoding, 'replace')

        return r

def parse(request, encoding, var_dict, template):
    """
    This method parses the ``template`` passed in using ``Replacer`` to 
    expand template variables using values in the ``var_dict``.

    Originally based on OPAGCGI, but mostly re-written.

    This returns the template string with template variables expanded.

    :Parameters:
       request : Request object
          the request object context
       encoding : string
          the encoding to use for ascii -> unicode conversions
       var_dict : dict
          the name value pair list containing variable replacements
       template : string
          the template we're expanding template variables in
    """
    if not isinstance(template, unicode):
        # convert strings to unicode using the user's defined encoding
        template = unicode(template, encoding, 'replace')

    replacer = Replacer(request, encoding, var_dict)

    return u'' + VAR_REGEXP.sub(replacer.replace, template)

def walk( request, root='.', recurse=0, pattern='', return_folders=0 ):
    """
    This function walks a directory tree starting at a specified root folder,
    and returns a list of all of the files (and optionally folders) that match
    our pattern(s). Taken from the online Python Cookbook and modified to own
    needs.

    It will look at the config "ignore_directories" for a list of 
    directories to ignore.  It uses a regexp that joins all the things
    you list.  So the following::

       config.py["ignore_directories"] = ["CVS", "dev/pyblosxom"]

    turns into the regexp::

       .*?(CVS|dev/pyblosxom)$

    It will also skip all directories that start with a period.

    Returns a list of file paths.

    :Parameters:
       request : Request
          the PyBlosxom request
       root : string
          the starting directory to walk from
       recurse : int
          the depth of recursion, defaults to ``0`` which is all the
          way down
       pattern : regexp object
          filters out all files that don't match this pattern, defaults
          to ``''``
       return_folders : boolean
          returns a list of folders if True, returns folders and files
          otherwise
    """
    # expand pattern
    if not pattern:
        ext = request.getData()['extensions']
        pattern = re.compile(r'.*\.(' + '|'.join(ext.keys()) + r')$')

    ignore = request.getConfiguration().get("ignore_directories", None)
    if isinstance(ignore, str):
        ignore = [ignore]

    if ignore:
        ignore = map(re.escape, ignore)
        ignorere = re.compile(r'.*?(' + '|'.join(ignore) + r')$')
    else:
        ignorere = None

    # must have at least root folder
    if not os.path.isdir(root):
        return []

    return __walk_internal(root, recurse, pattern, ignorere, return_folders)

# We do this for backwards compatibility reasons.
def Walk(*args, **kwargs):
    """Deprecated.  Use ``tools.walk`` instead."""
    return walk(*args, **kwargs)

def __walk_internal( root, recurse, pattern, ignorere, return_folders ):
    """
    Note: This is an internal function--don't use it and don't expect it to
    stay the same between PyBlosxom releases.

    FIXME - we should either ditch this function and use os.walk or something
    similar, or optimize this version by removing the multiple stat calls
    that happen as a result of islink, isdir and isfile.
    """
    # initialize
    result = []

    try:
        names = os.listdir(root)
    except:
        return []

    # check each file
    for name in names:
        fullname = os.path.normpath(os.path.join(root, name))

        # grab if it matches our pattern and entry type
        if pattern.match(name):
            if ((os.path.isfile(fullname) and not return_folders) or
                (return_folders and os.path.isdir(fullname) and
                 (not ignorere or not ignorere.match(fullname)))):
                result.append(fullname)
                
        # recursively scan other folders, appending results
        if (recurse == 0) or (recurse > 1):
            if name[0] != "." and os.path.isdir(fullname) and \
                    not os.path.islink(fullname) and \
                    (not ignorere or not ignorere.match(fullname)):
                result = result + \
                         __walk_internal(fullname, 
                                        (recurse > 1 and [recurse - 1] or [0])[0], 
                                        pattern, ignorere, return_folders)

    return result


def filestat(request, filename):     
    """     
    Returns the filestat on a given file.  We store the filestat in case 
    we've already retrieved it during this PyBlosxom request.
    
    This returns the mtime of the file (same as returned by 
    ``time.localtime()``) -- tuple of 9 ints.

    :Parameters:
       request : Request object
          the request object
       filename : string
          the file name of the file to stat
    """     
    data = request.getData()    
    filestat_cache = data.setdefault("filestat_cache", {})      
    
    if filename in filestat_cache:
        return filestat_cache[filename]     
    
    argdict = { "request": request,
                "filename": filename,    
                "mtime": (0,) * 10 }

    MT = stat.ST_MTIME

    argdict = run_callback("filestat",      
                           argdict,     
                           mappingfunc = passmutated,
                           donefunc = lambda x:x and x["mtime"][MT] != 0,
                           defaultfunc = lambda x:x)

    # no plugin handled cb_filestat; we default to asking the
    # filesystem
    if argdict["mtime"][MT] == 0:
        argdict["mtime"] = os.stat(filename)

    timetuple = time.localtime(argdict["mtime"][MT])
    filestat_cache[filename] = timetuple    
     
    return timetuple

def what_ext(extensions, filepath):
    """
    Takes in a filepath and a list of extensions and tries them all until
    it finds the first extension that works.

    Returns the extension (string) of the file or ``None``.

    :Parameters:
       extensions : list of strings
          the list of extensions to test
       filepath : string
          the complete file path (minus the extension) to test
    """
    for ext in extensions:
        if os.path.isfile(filepath + '.' + ext):
            return ext
    return None


def is_year(s):
    """
    Checks to see if the string is likely to be a year or not.  In order to 
    be considered to be a year, it must pass the following criteria:

    1. four digits
    2. first two digits are either 19 or 20.

    Returns ``True`` if it is a year and ``False`` otherwise.

    :Parameters:
       s : string
          the string to check for "year-hood"
    """
    if not s:
        return False

    if len(s) == 4 and s.isdigit() and \
            (s.startswith("19") or s.startswith("20")):
        return True
    return False


def importname(modulename, name):
    """
    Safely imports modules for runtime importing.

    Returns the module object or ``None`` if there were problems
    importing.

    :Parameters:
       modulename : string
          The package name of the module to import from
       name : string
          The name of the module to import
    """
    logger = getLogger()
    if not modulename:
        m = name
    else:
        m = "%s.%s" % (modulename, name)

    try:
        module = __import__(m)
        for c in m.split(".")[1:]:
            module = getattr(module, c)
        return module

    except ImportError, ie:
        logger.error("Module %s in package %s won't import: %s" % \
                     (repr(modulename), repr(name), ie))

    except Exception, e:
        logger.error("Module %s not in in package %s: %s" % \
                     (repr(modulename), repr(name), e))

    return None

def generateRandStr(minlen=5, maxlen=10):
    """
    Generate a random string between ``minlen`` and ``maxlen`` characters
    long.

    The generated string consists of letters and numbers.
    
    :Parameters:
       minlen : int
          the minimum length of the generated random string
       maxlen : int
          the maximum length of the generated random string
    """
    import random, string
    chars = string.letters + string.digits
    randstr = []
    randstr_size = random.randint(minlen, maxlen)
    x = 0
    while x < randstr_size:
        randstr.append(random.choice(chars))
        x += 1
    return "".join(randstr)

def passoriginal(x, y): 
    """
    mappingfunc for callbacks which takes the original input, the
    output from the last function and returns the original input.

    All functions in the callback chain get the original input
    as input.
    """
    return x

def passmutated(x, y):
    """
    mappingfunc for callbacks which takes the original input,
    the output from the last function and returns the output from
    the last function.

    Functions in the callback get the output from the previous function
    as input.
    """
    return y

def neverdone(x): 
    """
    donefunc for callbacks which always returns ``False`` causing all
    functions in the callback chain to run.
    """
    return False

def donewhentrue(x):
    """
    donefunc for callbacks which stops the callback when the
    last function returned a True value.
    """
    return x

def run_callback(chain, input, 
        mappingfunc = passoriginal,
        donefunc = neverdone,
        defaultfunc = None,
        exclude = None):
    """
    Executes a callback chain on a given piece of data.
    passed in is a dict of name/value pairs.  Consult the documentation
    for the specific callback chain you're executing.

    Callback chains should conform to their documented behavior.
    This function allows us to do transforms on data, handling data,
    and also callbacks.

    The difference in behavior is affected by the mappingfunc passed
    in which converts the output of a given function in the chain
    to the input for the next function.

    If this is confusing, read through the code for this function.

    Returns the result of ``mappingfunc`` after the last function in
    the function chain.

    :Parameters:
       chain : string or list of functions
          the name of the callback to run or the list of functions
          to run the callback on
       input : dict
          the initial args dict filled with key/value pairs that
          gets passed to the first function in the callback chain
       mappingfunc : function
          the function that maps output arguments to input arguments 
          for the next iteration.  It must take two arguments: the 
          original dict and the return from the previous function.  It 
          defaults to returning the original dict.
       donefunc : function
          this function tests whether we're done doing what we're 
          doing.  This function takes as input the output of the most 
          recent iteration.  If this function returns true (1) then 
          we'll drop out of the loop.  For example, if you wanted a 
          callback to stop running when one of the registered functions 
          returned a True, then you would pass in::

              donefunc = lambda x : x

       defaultfunc : function
          if this is set and we finish going through all the functions 
          in the chain and none of them have returned something that 
          satisfies the donefunc, then we'll execute the defaultfunc with 
          the latest version of the input dict.
       exclude : list of functions
          this is the list of functions to skip over when executing the
          callback.

    @returns: the transformed dict
    @rtype: dict
    """
    if exclude == None:
        exclude = []

    if type(chain) == type(""):
        chain = plugin_utils.get_callback_chain(chain)

    output = None

    for func in chain:
        if func in exclude:
            continue

        # we call the function with the input dict it returns an output.
        output = func(input)

        # we fun the output through our donefunc to see if we should stop
        # iterating through the loop.  if the donefunc returns something
        # true, then we're all done; otherwise we continue.
        if donefunc(output):
            break

        # we pass the input we just used and the output we just got
        # into the mappingfunc which will give us the input for the
        # next iteration.  in most cases, this consists of either
        # returning the old input or the old output--depending on
        # whether we're transforming the data through the chain or not.
        input = mappingfunc(input, output)

    # if we have a defaultfunc and we haven't satisfied the donefunc
    # conditions, then we return whatever the defaultfunc returns
    # when given the current version of the input.
    if callable(defaultfunc) and not donefunc(output):
        return defaultfunc(input)
        
    # we didn't call the defaultfunc--so we return the most recent
    # output.
    return output


def create_entry(datadir, category, filename, mtime, title, metadata, body):
    """
    Creates a new entry in the blog.

    This is primarily used by the testing system, but it could be
    used by scripts and other tools.

    :Parameters:
       datadir : string
          the directory of the datadir where the blog entries are stored
       category : string
          the category of the entry
       filename : string
          the name of the blog entry (filename and extension--no directory)
       mtime : float
          the mtime for the entry in seconds since the epoch
       title : string
          the entry title
       metadata : dict
          the metadata for the entry in a dict of key/value pairs
       body : string
          the body of the entry

    :Except:
       IOError
          if the datadir + category directory exists, but isn't a directory
    """

    def addcr(s):
        if not s.endswith("\n"):
            return s + "\n"
        return s

    # format the metadata lines for the entry
    # FIXME - metadatalines = ["#%s %s" % (key, metadata[key])
    #                  for key in metadata.keys()]
    metadatalines = ["#%s %s" % (key, metadata[key])
                     for key in metadata]

    entry = addcr(title) + "\n".join(metadatalines) + body

    # create the category directories
    d = os.path.join(datadir, category)
    if not os.path.exists(d):
        os.makedirs(d)

    if not os.path.isdir(d):
        raise IOError("%s exists, but isn't a directory." % d)
    
    # create the filename
    fn = os.path.join(datadir, category, filename)

    # write the entry to disk
    f = open(fn, "w")
    f.write(entry)
    f.close()

    # set the mtime on the entry
    os.utime(fn, (mtime, mtime))


def update_static_entry(cdict, entry_filename):
    """
    This is a utility function that allows plugins to easily update
    statically rendered entries without going through all the rigamarole.

    First we figure out whether this blog is set up for static rendering.
    If not, then we return--no harm done.

    If we are, then we call ``render_url`` for each ``static_flavour`` of 
    the entry and then for each ``static_flavour`` of the index page.

    :Parameters:
       cdict : dict
          the ``config.py`` dict
       entry_filename : string
          the url path of the entry to be updated.  ex. ``/movies/xmen2``
    """
    staticdir = cdict.get("static_dir", "")

    if not staticdir:
        return

    staticflavours = cdict.get("static_flavours", ["html"])

    renderme = []
    for mem in staticflavours:
        renderme.append( "/index" + "." + mem, "" )
        renderme.append( entry_filename + "." + mem, "" )
   
    for mem in renderme:
        render_url_statically(cdict, mem[0], mem[1])


def render_url_statically(cdict, url, q):
    staticdir = cdict.get("static_dir", "")

    response = render_url(cdict, url, q)
    response.seek(0)

    fn = os.path.normpath(staticdir + os.sep + url)
    if not os.path.isdir(os.path.dirname(fn)):
        os.makedirs(os.path.dirname(fn))

    # by using the response object the cheesy part of removing 
    # the HTTP headers from the file is history.
    f = open(fn, "w")
    f.write(response.read())
    f.close()
 
def render_url(cdict, pathinfo, querystring=""):
    """
    Takes a url and a querystring and renders the page that corresponds
    with that by creating a Request and a PyBlosxom object and passing
    it through.  It then returns the resulting Response.

    This returns a PyBlosxom ``Response`` object.

    :Parameters:
       cdict : dict
          the ``config``.py dict
       pathinfo : string
          the ``path_info`` string.  ex. ``/dev/pyblosxom/firstpost.html``
    """
    staticdir = cdict.get("static_dir", "")

    # if there is no staticdir, then they're not set up for static
    # rendering.
    if not staticdir:
        raise Exception("You must set static_dir in your config file.")

    from pyblosxom import PyBlosxom

    env = {
        "HTTP_HOST": "localhost",
        "HTTP_REFERER": "",
        "HTTP_USER_AGENT": "static renderer",
        "PATH_INFO": pathinfo,
        "QUERY_STRING": querystring,
        "REMOTE_ADDR": "",
        "REQUEST_METHOD": "GET",
        "REQUEST_URI": pathinfo + "?" + querystring,
        "SCRIPT_NAME": "",
        "wsgi.errors": sys.stderr,
        "wsgi.input": None
    }
    data = {"STATIC": 1}
    p = PyBlosxom(cdict, env, data)
    p.run(static=True)
    return p.getResponse()



#******************************
# Logging
#******************************

# If you have Python >=2.3 and want to use/test the custom logging 
# implementation set this flag to True.
_use_custom_logger = False

try:
    import logging
    if _use_custom_logger:
        raise ImportError, "whatever"
except ImportError:
    from Pyblosxom import _logging as logging

# A dict to keep track of created log handlers.
# Used to prevent multiple handlers from beeing added to the same logger.
_loghandler_registry = {}


class LogFilter(object):
    """
    Filters out messages from log-channels that are not listed in the
    log_filter config variable.
    """
    def __init__(self, names=None):
        """
        Initializes the filter to the list provided by the names
        argument (or ``[]`` if ``names`` is ``None``).

        :Parameters:
           names : list of strings
              the list of strings to filter out
        """
        if names == None:
            names = []
        self.names = names

    def filter(self, record):
        if record.name in self.names:
            return 1
        return 0

def getLogger(log_file=None):
    """
    Creates and retuns a log channel.

    If no log_file is given the system-wide logfile as defined in config.py
    is used. If a log_file is given that's where the created logger logs to.

    Returns a log channel (logger instance) which you can call ``error``,
    ``warning``, ``debug``, ``info``, ... on.

    :Parameters:
       log_file : string
          the file to log to, defaults to ``None``
    """
    custom_log_file = False
    if log_file == None:
        log_file = _config.get('log_file', 'stderr')
        f = sys._getframe(1)
        filename = f.f_code.co_filename
        module = f.f_globals["__name__"]
        # by default use the root logger
        log_name = ""
        for path in _config.get('plugin_dirs', []):
            if filename.startswith(path):
                # if it's a plugin, use the module name as the log channels 
                # name
                log_name = module
                break
        # default to log level WARNING if it's not defined in config.py
        log_level = _config.get('log_level', 'warning')
    else:
        # handle custom log_file
        custom_log_file = True
        # figure out a name for the log channel
        log_name = os.path.splitext(os.path.basename(log_file))[0]
        # assume log_level debug (show everything)
        log_level = "debug"

    global _loghandler_registry

    # get the logger for this channel
    logger = logging.getLogger(log_name)
    # don't propagate messages up the logger hierarchy
    logger.propagate = 0

    # setup the handler if it doesn't allready exist.
    # only add one handler per log channel.
    key = "%s|%s" % (log_file, log_name)
    if not key in _loghandler_registry:

        # create the handler
        if log_file == "stderr":
            hdlr = logging.StreamHandler(sys.stderr)
        else:
            if log_file == "NONE": # user disabled logging
                if os.name == 'nt': # windoze
                    log_file = "NUL"
                else: # assume *nix
                    log_file = "/dev/null"
            try:
                hdlr = logging.FileHandler(log_file)
            except IOError:
                # couldn't open logfile, fallback to stderr
                hdlr = logging.StreamHandler(sys.stderr)

        # create and set the formatter
        if log_name:
            fmtr_s = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        else: # root logger
            fmtr_s = '%(asctime)s [%(levelname)s]: %(message)s'

        hdlr.setFormatter(logging.Formatter(fmtr_s))

        logger.addHandler(hdlr)
        int_level = getattr(logging, log_level.upper())
        logger.setLevel(int_level)

        if not custom_log_file:
            # only log messages from plugins listed in log_filter.
            # add 'root' to the log_filter list to still allow application 
            # level messages.
            log_filter = _config.get('log_filter', None)
            if log_filter:
                lfilter = LogFilter(log_filter)
                logger.addFilter(lfilter)

        # remember that we've seen this handler
        _loghandler_registry[key] = True

    return logger

def log_exception(log_file=None):
    """
    Logs an exception to the given file.
    Uses the system-wide log_file as defined in config.py if none 
    is given here.

    :Parameters:
       log_file : string
          the file to log to, defaults to ``None``
    """
    log = getLogger(log_file)
    log.exception("Exception occured:")

def log_caller(frame_num=1, log_file=None):
    """
    Logs some info about the calling function/method.
    Useful for debugging.

    Usage::

        import tools
        tools.log_caller() # logs frame 1
        tools.log_caller(2)
        tools.log_caller(3, log_file="/path/to/file")

    :Parameters:
       frame_num : int
          index of the frame to log, defaults to ``1``
       log_file : string
          the file to log to, defaults to ``None``
    """
    f = sys._getframe(frame_num)
    module = f.f_globals["__name__"]
    filename = f.f_code.co_filename
    line = f.f_lineno
    subr = f.f_code.co_name

    log = getLogger(log_file)
    log.info("\n  module: %s\n  filename: %s\n  line: %s\n  subroutine: %s", 
             module, filename, line, subr)


# %<-------------------------
# BEGIN portalocking block from Python Cookbook.
# LICENSE is located in docs/LICENSE.portalocker.
# It's been modified for use in Pyblosxom.

# """Cross-platform (posix/nt) API for flock-style file locking.
# 
# Synopsis:
# 
#    import portalocker
#    file = open("somefile", "r+")
#    portalocker.lock(file, portalocker.LOCK_EX)
#    file.seek(12)
#    file.write("foo")
#    file.close()
# 
# If you know what you're doing, you may choose to
# 
#    portalocker.unlock(file)
# 
# before closing the file, but why?
# 
# Methods:
# 
#    lock( file, flags )
#    unlock( file )
# 
# Constants:
# 
#    LOCK_EX
#    LOCK_SH
#    LOCK_NB
# 
# I learned the win32 technique for locking files from sample code
# provided by John Nielsen <nielsenjf@my-deja.com> in the documentation
# that accompanies the win32 modules.
# 
# Author: Jonathan Feinberg <jdf@pobox.com>
# Version: $Id$

if os.name == 'nt':
    import win32con
    import win32file
    import pywintypes
    LOCK_EX = win32con.LOCKFILE_EXCLUSIVE_LOCK
    LOCK_SH = 0 # the default
    LOCK_NB = win32con.LOCKFILE_FAIL_IMMEDIATELY
    # is there any reason not to reuse the following structure?
    __overlapped = pywintypes.OVERLAPPED()
elif os.name == 'posix':
    import fcntl
    LOCK_EX = fcntl.LOCK_EX
    LOCK_SH = fcntl.LOCK_SH
    LOCK_NB = fcntl.LOCK_NB
else:
    raise RuntimeError("PortaLocker only defined for nt and posix platforms")

if os.name == 'nt':
    def lock(f, flags):
        hfile = win32file._get_osfhandle(f.fileno())
        win32file.LockFileEx(hfile, flags, 0, 0xffff0000, __overlapped)

    def unlock(f):
        hfile = win32file._get_osfhandle(f.fileno())
        win32file.UnlockFileEx(hfile, 0, 0xffff0000, __overlapped)

elif os.name =='posix':
    def lock(f, flags):
        fcntl.flock(f.fileno(), flags)

    def unlock(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# END portalocking block from Python Cookbook.
# %<-------------------------
