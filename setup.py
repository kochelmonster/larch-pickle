import sys
import os.path
import os
from setuptools import setup, find_packages
from contextlib import contextmanager
from setuptools import Extension, setup
try:
    from Cython.Build import cythonize
except Exception:
    def cythonize(extension): 
        return extension


compile_debug = os.environ.get("LARCH_INSTALL_FOR_TEST")


class LarchExtension(Extension):
    dbase = os.path.join("larch", "pickle")

    def __init__(self, *args, **kwds):
        kwds["name"] = self.name
        kwds["sources"] = []
        super(LarchExtension, self).__init__(**kwds)

        #Extension.__init__(self, self.name, [], cython_c_in_temp=True)
        self.cython_compile_time_env = {
            "PY_MAJOR_VERSION": sys.version_info[0]}
        self.make()
        self.check_cplusplus()
        self.add_optimize_flag()

        conda_prefix = os.environ.get("CONDA_PREFIX")
        if conda_prefix:
            self.include_dirs.append(os.path.join(conda_prefix, "include"))
            if self.platform == "win32":
                self.include_dirs.append(
                    os.path.join(conda_prefix, "Library", "include"))

        self.include_dirs.append(self.dbase)
        self.include_dirs = list(set(self.include_dirs))
        self.libraries = list(set(self.libraries))
        self.library_dirs = list(set(self.library_dirs))
        self.define_macros = list(set(self.define_macros))
        self.extra_link_args = list(set(self.extra_link_args))

    @property
    def platform(self):
        platform = sys.platform
        if platform.startswith('linux'):
            platform = 'linux'
        return platform

    def check_cplusplus(self):
        is_cpp = lambda fn: fn.endswith(".hpp") or fn.endswith(".cpp")
        if (any(is_cpp(fn) for fn in self.sources)
                or any(is_cpp(fn) for fn in self.depends)):
            self.language = "c++"
            if self.platform == "win32":
                self.extra_compile_args.append("/EHsc")

    @contextmanager
    def add(self, add_list, *path):
        directory = os.path.join(*path)

        def add(fname):
            add_list.append(os.path.join(directory, fname))
        yield add

    def add_optimize_flag(self):
        # optimation
        if compile_debug:
            CFLAGS = {"win32": ["/Zi"]}
            LFLAGS = {"win32": ["/DEBUG"]}
            self.extra_compile_args.extend(CFLAGS.get(self.platform, ["-g"]))
            self.extra_link_args.extend(LFLAGS.get(self.platform, []))
            self.define_macros.extend([("DEBUG", None)])

            # profile
            # self.libraries.extend(["profiler"])
            # self.define_macros.extend([ ("CYTHON_TRACE", 1) ])

        else:
            FLAGS = {"win32": ["/O2", "/Oi"]}
            self.extra_compile_args.extend(
                FLAGS.get(self.platform, ["-O3"]))


class Pickle(LarchExtension):
    name = "larch.pickle.pickle"

    def make(self):
        boost_dir = os.environ.get("BOOST_DIR")
        if boost_dir is not None:
            self.include_dirs.append(os.path.join(boost_dir, "include"))

        elif self.platform == "win32" and not os.environ.get("CONDA_PREFIX"):
            boost_root = "c:\\local"
            try:
                boost_dir = (
                    dname for dname in os.listdir(boost_root)
                    if dname.startswith("boost"))
                boost_dir = max(sorted(
                    (map(int, dname.split("_")[1:]), dname)
                    for dname in boost_dir))[1]
            except Exception:
                pass
            else:
                boost_dir = os.path.join(boost_root, boost_dir)
                self.include_dirs.append(boost_dir)

        if self.platform == "darwin":
            self.extra_compile_args.append("-std=c++11")
        
        # disable cython typedef of uint8_t
        self.define_macros.extend([("_MSC_STDINT_H_", None)])

        with self.add(self.sources, self.dbase) as add:
            add("pickle.pyx")

        with self.add(self.depends, self.dbase) as add:
            add("compiled_version")
            add("pickle.hpp")
            add("unpack.hpp")
            add("pack.hpp")

ext_modules = [Pickle()]


module_dir = os.path.dirname(os.path.abspath(__file__))

setup(
    name="larch-pickle",
    version="1.4.3",
    packages=find_packages(),
    exclude=["pickle.pyx"], # don't generate auto extension

    # metadata for upload to PyPI
    author='Michael Reithinger',

    # Project uses reStructuredText, so ensure that the docutils get
    # installed or upgraded on the target machine
    include_package_data=False,
    namespace_packages=['larch'],
    zip_safe=False,

    license="BSD",
    description="A faster python pickle replacement",
    keywords="library",
    url="https://github.com/kochelmonster/larch-pickle",
    long_description=open(os.path.join(module_dir, "README.rst"), "r").read(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Libraries :: Python Modules"],
    ext_modules=cythonize(ext_modules))
