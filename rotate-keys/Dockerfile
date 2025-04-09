FROM alpine

RUN apk add --no-cache bash curl openssl

#Copy your key rotation script
COPY rotate-keys.sh /rotate-keys.sh
RUN chmod +x /rotate-keys.sh

#set up cron job: every 6 hours
RUN echo "0 */6 * * * /rotate-keys.sh >> /var/log/rotate.log 2>&1" > /etc/crontabs/root

#run crond in the foreground
RUN /rotate-keys.sh || true
CMD ["crond", "-f", "-L", "/dev/stdout"]
