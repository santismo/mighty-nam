# Release verification and historical hardware trials

`updater.py` checks a local image, restore image and release manifest. It can open the official NUX updater but never selects or flashes an image itself.

The `namlnk06-trial`, `namlnk07-trial`, and `namlnk08-trial` folders preserve historical manual hardware experiments. Some send controls or explicitly enable headphone audio. They target their named older builds and are **not** part of the Mac installer or automatic offline tests. Read their sources and local-input requirements before use. The output-pipeline experiment is offline research.
