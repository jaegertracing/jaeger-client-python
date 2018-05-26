BEGIN {six=0}

/^$/ {
    if (six == 0) {
        print "import six";
        print "from six.moves import xrange";
    }
    six = 1
}

{
    gsub(/from ttype/, "from .ttype", $0);
    gsub(/self.__dict__.iteritems\(\)/, "six.iteritems(self.__dict__)", $0);
    print
}