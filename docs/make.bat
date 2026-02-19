@ECHO OFF

pushd %~dp0

set SPHINXOPTS=-W --keep-going -n
set SPHINXBUILD=sphinx-build
set SOURCEDIR=.
set BUILDDIR=_build

if "%1" == "" goto help
if "%1" == "html" goto html
if "%1" == "clean" goto clean
goto help

:html
%SPHINXBUILD% -b html %SPHINXOPTS% %SOURCEDIR% %BUILDDIR%/html
echo Build finished. HTML pages are in %BUILDDIR%/html.
goto end

:clean
if exist %BUILDDIR% rmdir /s /q %BUILDDIR%
goto end

:help
%SPHINXBUILD% -M help %SOURCEDIR% %BUILDDIR% %SPHINXOPTS%

:end
popd
