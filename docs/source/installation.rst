Installation
=============
This document will guide you through the installation process and will help you configure the library for the newest release.

You can install the library using the pip command:

.. code:: console

    $ pip install qf-lib


Alternatively, to install the library from sources, you can download the project and in the qf_lib directory (same one where you found this file after cloning the repository) execute the following command:

.. code:: console

    $ python setup.py install

Prerequisites
--------------

QF-Lib currently supports Python 3.8-3.11. The library has been tested on Windows, macOS, and Ubuntu.

The library uses matplotlib to export documents to PDF. All required dependencies are included in the standard installation.



Installing optional data providers
------------------------------------

Bloomberg Data Provider
^^^^^^^^^^^^^^^^^^^^^^^^^
For Bloomberg API there are prebuilt binaries in both 32 and 64 bits, for Windows, macOS, and most versions
of Linux. On Linux, ‘pip’ >= 19.0 is required to install these binaries. You can install Bloomberg using the pip command:

.. code:: console

   $ pip install --index-url=https://bcms.bloomberg.com/pip/simple/ blpapi==3.20.1


Quandl Data Provider
^^^^^^^^^^^^^^^^^^^^^
You can install Quandl using the pip command:

.. code:: console

   $  pip install quandl==3.6.1


Interactive Brokers
^^^^^^^^^^^^^^^^^^^
In order to install all dependencies necessary to use the Interactive Brokers platform:

   -  Download the TWS API Stable for your operating system (Version:
      API 9.76).
   -  Link for windows msi file:
      ``http://interactivebrokers.github.io/downloads/TWS%20API%20Install%20976.01.msi``.
   -  Install TWS API by running the downloaded file.
   -  Go to ``TWS API\source\pythonclient`` and run
      ``python setup.py install``.
