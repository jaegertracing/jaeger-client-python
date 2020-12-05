#!/bin/bash

set -euxf -o pipefail

make crossdock

REPO=jaegertracing/xdock-py
BRANCH=${BRANCH:?'missing BRANCH env var'}
TORNADO=${TORNADO:?'missing TORNADO env var'}
TAG=$([ "$BRANCH" == "master" ] && echo "latest" || echo "$BRANCH")
COMMIT=${GITHUB_SHA::8}
DOCKERHUB_LOGIN=${DOCKERHUB_LOGIN:-false}

echo "REPO=$REPO, BRANCH=$BRANCH, TAG=$TAG, TORNADO=$TORNADO, COMMIT=$COMMIT"

# Only push the docker container to dockerhub for master branch and when dockerhub login is done
if [[ "$BRANCH" == "master" && "$DOCKERHUB_LOGIN" == "true" ]]; then
  echo 'upload to Docker Hub'
else 
  echo 'skip docker upload for PR'
  exit 0
fi

docker build -f crossdock/Dockerfile \
	--build-arg tornado=$TORNADO \
	--tag $REPO:$COMMIT .

docker tag $REPO:$COMMIT $REPO:$TAG
docker tag $REPO:$COMMIT $REPO:gh-$GITHUB_RUN_NUMBER
docker push $REPO
