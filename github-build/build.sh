# build and copy for pip
$PYTHON setup.py bdist_wheel
echo "-----------ls-------------"
ls
echo "-----------ls dist-------------"
ls dist
echo "------runner?-----------"
echo "runner $RUNNER_WORKSPACE"
cp dist/*.whl $RUNNER_WORKSPACE
# install for conda
$PYTHON -m pip install --no-deps --ignore-installed --global-option=build .
