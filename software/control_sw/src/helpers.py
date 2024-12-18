import os
import sys
import logging
import numpy as np

logger = logging.getLogger(__name__)
NOTIFY = logging.INFO + 1
logging.addLevelName(NOTIFY, "NOTIFY")

IS_INITIALIZED_ATTR = "_has_default_handlers"

def add_default_log_handlers(logger, fglevel=logging.INFO, bglevel=NOTIFY):
    if getattr(logger, IS_INITIALIZED_ATTR, False):
        return logger
    setattr(logger, IS_INITIALIZED_ATTR, True)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    formatter = logging.Formatter('%(asctime)s - %(name)20s - %(levelname)s - %(message)s')

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setLevel(fglevel)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    syslog_handler.setLevel(bglevel)
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)
    return logger

def file_exists(f, logger):
    if not os.path.isfile(f):
        logger.error(f"File {f} doesn't exist")
        raise RuntimeError(f"File {f} doesn't exist")

def get_casper_fft_descramble(n_bit_fft, n_bit_parallel):
    """
    Get the descramble map for a CASPER FFT with
    2**n_bit_fft channels, presenting 2**n_bit_parallel
    on each cycle
    """ 
    n_fft = 2**n_bit_fft
    n_parallel = 2**n_bit_parallel
    return np.arange(n_fft).reshape(n_fft // n_parallel, n_parallel).transpose().flatten()

def get_casper_fft_scramble(n_bit_fft, n_bit_parallel):
    """
    Get the scramble map for a CASPER FFT with
    2**n_bit_fft channels, presenting 2**n_bit_parallel
    on each cycle
    """
    descramble = get_casper_fft_descramble(n_bit_fft, n_bit_parallel)
    scramble = np.zeros_like(descramble)
    for i,j in enumerate(descramble):
        scramble[j] = i
    return scramble

def cplx2uint(d, nbits):
    """
    Convert a floating point real, imag pair
    to a UFix<nbits>_<nbits-1> CASPER-standard
    complex number.
    """
    real = int(np.round(d.real * 2**(nbits-1)))
    imag = int(np.round(d.imag * 2**(nbits-1)))
    # Saturate
    if real > 2**(nbits-1) - 1:
        real = 2**(nbits-1) -1
    if imag > 2**(nbits-1) - 1:
        imag = 2**(nbits-1) -1
    # interpret as uint
    if real < 0:
        real += 2**nbits
    if imag < 0:
        imag += 2**nbits
    return (real << nbits) + imag

def uint2cplx(d, nbits):
    """
    Convert a CASPER-standard UFix<nbits>_<nbits-1>
    complex number to a real, imag pair.
    """
    real = (d >> nbits) & (2**nbits-1)
    imag = d & (2**nbits-1)
    if real >= 2**(nbits-1):
        real -= 2**nbits
    if imag >= 2**(nbits-1):
        imag -= 2**nbits
    return (real + 1j*imag) / 2**(nbits-1)

