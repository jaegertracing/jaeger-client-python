FROM python:2.7-alpine

ENV APPDIR /usr/src/app/
RUN mkdir -p ${APPDIR}
WORKDIR ${APPDIR}

# Application installation
COPY requirements-dev.txt ${APPDIR}
COPY requirements-tests.txt ${APPDIR}
COPY requirements.txt ${APPDIR}

COPY setup.py ${APPDIR}
COPY setup.cfg ${APPDIR}
COPY jaeger_client ${APPDIR}/jaeger_client/
COPY idl ${APPDIR}/idl/

# RUN pip install -U 'pip>=7,<8'
RUN pip install --no-cache-dir -r requirements-dev.txt
RUN pip install --no-cache-dir -r requirements-tests.txt
RUN pip install --no-cache-dir -r requirements.txt
RUN python setup.py install

COPY crossdock ${APPDIR}/crossdock/
COPY crossdock/setup_crossdock.py ${APPDIR}
RUN python setup_crossdock.py install

# TODO Remove this after the tchannel-python crossdock is no longer a package
RUN rm -rf /usr/local/lib/python2.7/site-packages/crossdock

CMD ["crossdock"]
EXPOSE 8080-8082
