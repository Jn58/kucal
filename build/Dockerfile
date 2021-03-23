FROM python:alpine
RUN apk add --no-cache dcron tzdata &&\
    cp /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
    echo "Asia/Seoul" > /etc/timezone && \
    apk del tzdata && \
    echo -e '0\t3\t*\t*\t*\t/usr/local/bin/python /app/cal.py' > /etc/crontabs/root
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
RUN rm /requirements.txt
WORKDIR /app
COPY entry.sh /entry.sh
RUN chmod 755 /entry.sh
CMD ["/entry.sh"]
