FROM ubuntu:16.04

ENV LANG="en_US.UTF-8" \
    LC_ALL="en_US.UTF-8" \
    LANGUAGE="en_US.UTF-8" \
    TERM="xterm" \
    DEBIAN_FRONTEND="noninteractive"

EXPOSE 80

RUN apt-get update -q && \
    apt-get install -qy software-properties-common language-pack-en-base && \
    export LC_ALL=en_US.UTF-8 && \
    export LANG=en_US.UTF-8 && \
    apt-get update -q && \
    apt-get install --no-install-recommends -qy \
        curl \
        vim \
        python-pip \
        nginx \
        git \
        supervisor \
        gunicorn \
        build-essential \
        python-dev

RUN pip install --upgrade pip

COPY . /app
WORKDIR /app

RUN pip install -e .
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
