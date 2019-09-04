# coding: utf-8
# /*##########################################################################
#
# Copyright (c) 2019-2019 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
# ###########################################################################*/
"""tests for the dense correlator.

"""

__authors__ = ["P. Paleo"]
__license__ = "MIT"
__date__ = "04/09/2019"


from time import time
import logging
import unittest
import numpy as np
from dynamix.test.utils import XPCSDataset
from dynamix.correlator.dense import DenseCorrelator, py_dense_correlator, CUFFT, DenseFFTCorrelator

# logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


if CUFFT is not None:
    import pycuda.autoinit # get context


class TestDense(unittest.TestCase):

    ref = None

    def setUp(self):
        logger.debug("Loading data")
        self.dataset = XPCSDataset("eiger_514_10k")
        logger.setLevel(logging.DEBUG)
        self.shape = self.dataset.dataset_desc.frame_shape
        self.nframes = self.dataset.dataset_desc.nframes
        self.tol = 5e-3
        self.compute_reference_correlation()

    def tearDown(self):
        pass

    def compute_reference_correlation(self):
        if self.ref is not None:
            return # dont re-compute ref
        t0 = time()
        ref = np.zeros(
            (self.dataset.dataset_desc.bins, self.dataset.dataset_desc.nframes -1),
            dtype=np.float32
        )
        for bin_val in range(1, self.dataset.dataset_desc.bins+1):
            mask = (self.dataset.qmask == bin_val)
            ref[bin_val-1] = py_dense_correlator(self.dataset.data, mask)
        logger.info("Numpy dense correlator took %.1f ms" % ((time() - t0)*1e3))
        self.ref = ref


    def compare(self, res, method_name):
        errors = res[:, 1:] - self.ref
        errors_max = np.max(np.abs(errors), axis=1)

        for bin_idx in range(errors_max.shape[0]):
            self.assertLess(
                errors_max[bin_idx], self.tol,
                "%s: something wrong in bin index %d" % (method_name, bin_idx)
            )

    def test_dense_correlator(self):
        self.correlator = DenseCorrelator(
            self.shape,
            self.nframes,
            qmask=self.dataset.qmask,
            dtype=self.dataset.dataset_desc.dtype,
            profile=True
        )
        t0 = time()
        res = self.correlator.correlate(
            self.dataset.data
        )
        logger.info("OpenCL dense correlator took %.1f ms" % ((time() - t0)*1e3))
        self.compare(res, "OpenCL dense correlator")

    def test_fft_dense_correlator(self):
        if not(CUFFT):
            self.skipTest("Need pycuda and scikit-cuda")
        self.fftcorrelator = DenseFFTCorrelator(
            self.shape,
            self.nframes,
            qmask=self.dataset.qmask,
            extra_options={"save_fft_plans": False}
        )
        t0 = time()
        res = self.fftcorrelator.correlate(self.dataset.data)
        logger.info("Cuda FFT dense correlator took %.1f ms" % ((time() - t0)*1e3))
        self.compare(res, "Cuda FFT dense correlator")


def suite():
    testsuite = unittest.TestSuite()
    testsuite.addTest(
        unittest.defaultTestLoader.loadTestsFromTestCase(TestDense)
    )
    return testsuite


if __name__ == '__main__':
    unittest.main(defaultTest="suite")

