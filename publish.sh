#!/bin/bash

set -e

IS_DIRTY_CLONE=$(git status --short --porcelain | wc -l)
if [ "$IS_DIRTY_CLONE" -gt 0 ]; then
    echo "ERROR: this clone is not clean! Commit and re-run."
    exit 1
fi

GIT_BRANCH=$(git branch 2>/dev/null| sed -n '/^\*/s/^\* //p')
if [ "$GIT_BRANCH" != "master" ]; then
    echo "ERROR: forbidden to release any branch other than master"
    exit 1
fi

echo "=> Making sure local and remote branch are in sync"
GIT_DIFF_REMOTE=$(git diff master origin | wc -l)
if [ "$GIT_DIFF_REMOTE" -ne 0 ]; then
    echo "ERROR: this clone differs from origin. Please push to origin before releasing!"
    exit 1
fi

GIT_COUNT=$(git rev-list HEAD --count)
VERSION="1.0.$GIT_COUNT"
echo "=> VERSION=$VERSION"

echo "=> Running nosetests"
nosetests

echo "=> Build+Upload dist"
python setup.py sdist upload -r pypi --version $VERSION

echo "=> Tell slack"
tell_slack "Released version $VERSION of klue-client-server"

