#!/bin/bash
if [ -z "$1" ]; then
  echo "Usage: $0 <healthcheck-uuid> <command...>" >&2
  exit 1
fi
UUID=$1
shift
# signal that we are starting a job run
curl -fsS --retry 3 https://hc-ping.com/$UUID/start;
# run the actual job with arguments
"$@"
# save exit code
exit_code=$?
# forward exit code to healthcheck
if [ $exit_code = 0 ] ; then
  # signal success
  curl -fsS --retry 3 https://hc-ping.com/$UUID
else
  curl -fsS --retry 3 https://hc-ping.com/$UUID/$exit_code
fi
exit $exit_code
