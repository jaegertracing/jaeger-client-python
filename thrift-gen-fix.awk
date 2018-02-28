BEGIN {six=0; xrange=0}

/^$/ {
    # if in the future we need six, it can be added with the following line
    # if (six == 0) print "import six"
    six = 1
    if (xrange ==0) print "from six.moves import xrange"
    xrange = 1
}

{
        gsub(/from ttype/, "from .ttype",$0); 
        print
}
