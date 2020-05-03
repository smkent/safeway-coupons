import datetime
import logging

import azure.functions as func
from . import safeway_coupons

def main(ClipCouponsTimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    if ClipCouponsTimer.past_due:
        logging.info('The timer is past due!')
    
    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    safeway_coupons.run()

