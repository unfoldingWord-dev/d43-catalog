import os

from signer import Signer
# default private pem. This is encrypted by AWS
ENC_PRIV_PEM_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'uW-sk.enc')