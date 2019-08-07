rm -rf build
rm -rf dist
$PYTHON setup.py bdist_egg --exclude-source-files
$PYTHON -m easy_install --no-deps dist/*.egg
