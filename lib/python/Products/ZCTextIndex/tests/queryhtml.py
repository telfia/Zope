import os
from time import clock

import ZODB
from ZODB.FileStorage import FileStorage

QUERIES = ["nested recursive functions",
           "explicit better than implicit",
           "build hpux",
           "cannot create 'method-wrapper' instances",
            "extension module C++",
           "class method",
           "instance variable",
           "articulate information",
           "import default files",
           "gopher ftp http",
           "documentation",
           ]

def path2url(p):
    # convert the paths to a python.org URL
    # hack: only works for the way Jeremy indexed his copy of python.org
    marker = "www.python.org/."
    i = p.find(marker)
    if i == -1:
        return p
    i += len(marker)
    return "http://www.python.org" + p[i:]

def main(rt):
    index = rt["index"]
    files = rt["files"]
    times = {}
    for i in range(11):
        for q in QUERIES:
            terms = q.split()
            for c in " OR ", " AND ":
                query = c.join(terms)
                t0 = clock()
                results, num = index.query(query)
                t1 = clock()
                print "<p>Query: \"%s\"" % query
                print "<br>Num results: %d" % num
                print "<br>time.clock(): %s" % (t1 - t0)
                key = query
                if i == 0:
                    print "<ol>"
                    for docid, score in results:
                        url = path2url(files[docid])
                        fmt = '<li><a href="%s">%s</A> score = %s'
                        print fmt % (url, url, score)
                    print "</ol>"
                    continue
                l = times.setdefault(key, [])
                l.append(t1 - t0)

    l = times.keys()
    l.sort()
    print "<hr>"
    for k in l:
        v = times[k]
        print "<p>Query: \"%s\"" % k
        print "<br>Min time: %s" % min(v)
        print "<br>All times: %s" % " ".join(map(str, v))

if __name__ == "__main__":
    import sys
    import getopt

    VERBOSE = 0
    FSPATH = "Data.fs"

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'vf:')
    except getopt.error, msg:
        print msg
        print __doc__
        sys.exit(2)

    for o, v in opts:
        if o == '-v':
            VERBOSE += 1
        if o == '-f':
            FSPATH = v

    fs = FileStorage(FSPATH, read_only=1)
    db = ZODB.DB(fs, cache_size=10000)
    cn = db.open()
    rt = cn.root()
    main(rt)
