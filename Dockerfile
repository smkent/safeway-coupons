FROM python:3.6.7
ENV SAFEWAY_ACCOUNT john@doe.com
ENV SAFEWAY_PASSWORD secret
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY safeway-coupons .
COPY create-config .
CMD ./create-config && ./safeway-coupons -c config.ini
