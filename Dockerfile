FROM python:3-alpine
RUN mkdir -p /app/
ADD safeway-coupons /app/
RUN chmod +x /app/safeway-coupons
CMD ["/app/safeway-coupons", "/app/config.ini"]