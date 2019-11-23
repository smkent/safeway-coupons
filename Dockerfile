FROM python:3-alpine
RUN mkdir -p /app/
ADD safeway-coupons /app/
ADD requirements.txt /tmp/requirements.txt
RUN chmod +x /app/safeway-coupons && \
	pip install -r /tmp/requirements.txt && \
	rm /tmp/requirements.txt