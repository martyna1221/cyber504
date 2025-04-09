FROM alpine
RUN apk add --no-cache curl bash jq openssl
COPY sync-key.sh /sync-key.sh
RUN chmod +x /sync-key.sh
CMD ["/sync-key.sh"]
