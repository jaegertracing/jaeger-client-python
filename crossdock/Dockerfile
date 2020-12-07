FROM python:2.7

ARG tornado
ENV APPDIR /usr/src/app/
ENV TORNADO=$tornado
WORKDIR ${APPDIR}

# Application installation
COPY requirements-dev.txt requirements-tests.txt requirements.txt setup.py setup.cfg ${APPDIR}
COPY jaeger_client ${APPDIR}/jaeger_client/
COPY idl ${APPDIR}/idl/

# RUN pip install -U 'pip>=7,<8'
RUN pip install --no-cache-dir -r requirements-dev.txt -r requirements-tests.txt -r requirements.txt && \
    python setup.py install && \
    pip install --no-cache-dir "tornado${TORNADO}"

COPY crossdock ${APPDIR}/crossdock/
COPY crossdock/setup_crossdock.py ${APPDIR}
RUN python setup_crossdock.py install

# TODO Remove this after the tchannel-python crossdock is no longer a package
RUN rm -rf /usr/local/lib/python2.7/site-packages/crossdock

CMD ["crossdock"]
EXPOSE 8080-8082
