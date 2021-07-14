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
    if (package_prefix) {
        $0 = gensub(/[[:alnum:]_]+\.ttypes/, package_prefix ".\\0", "g", $0);
    }
    print
}