#!/bin/bash
set -e

echo "=== Testing Documentation Build ==="
echo ""

# Set environment variables
export DJANGO_SETTINGS_MODULE=eventyay.config.settings
export EVENTYAY_CONFIG_FILE=/dev/null
export DATABASE_URL="sqlite:////:memory:"
export REDIS_URL="redis://localhost:6379/0"

echo "1. Building main documentation..."
make clean
make html 2>&1 | tee build-main.log
echo "   ✓ Main docs built"
echo ""

echo "2. Building Talk documentation..."
cd talk
make clean
make html 2>&1 | tee build-talk.log
cd ..
echo "   ✓ Talk docs built"
echo ""

echo "3. Building Video documentation..."
cd video
make clean
make html 2>&1 | tee build-video.log
cd ..
echo "   ✓ Video docs built"
echo ""

echo "=== Build Complete ==="
echo ""
echo "View documentation:"
echo "  Main:  open _build/html/index.html"
echo "  Talk:  open talk/_build/html/index.html"
echo "  Video: open video/_build/html/index.html"
echo ""
echo "Check logs if there were warnings:"
echo "  Main:  cat build-main.log"
echo "  Talk:  cat talk/build-talk.log"
echo "  Video: cat video/build-video.log"

