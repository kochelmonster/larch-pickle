::build and copy for pip
%PYTHON% setup.py bdist_wheel

echo "*****COPY WHEEL TO %RUNNER_WORKSPACE%"
COPY dist\*.whl %RUNNER_WORKSPACE%
::install for conda
%PYTHON% -m pip install --no-deps --ignore-installed --global-option=build .
