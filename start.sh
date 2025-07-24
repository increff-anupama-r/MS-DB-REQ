
echo "Starting DB Request Chatbot..."

# Set environment variables for testing
export WEBUI_AUTH=False
export WEBUI_SECRET_KEY=t0p-s3cr3t
export WEBUI_JWT_SECRET_KEY=t0p-s3cr3t
export PORT=8081
export HOST=0.0.0.0

if [ -f .env ]; then
    source .env
    echo "Environment variables loaded from .env file"
else
    echo "No .env file found, using default configuration for testing"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "Warning: OPENAI_API_KEY not set. AI features will use fallback mode."
    export OPENAI_API_KEY="sk-proj-test-key"
fi

cleanup() {
    echo "Stopping server..."
    kill $BACKEND_PID 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting backend server..."
cd backend
python3 -m uvicorn open_webui.main:app --host 0.0.0.0 --port 8081 &
BACKEND_PID=$!
cd ..

echo "Installing frontend dependencies..."
npm install

echo "Building frontend..."
npm run build

sleep 5

if curl -s http://localhost:8081/ >/dev/null 2>&1; then
    echo "Backend server is running"
else
    echo "Backend server failed to start"
    exit 1
fi

if [ ! -d "build" ]; then
    echo "Frontend build directory not found"
    exit 1
else
    echo "Frontend build found"
fi

echo ""
echo "DB Requirement Chatbot is ready!"
echo ""
echo "Access your application:"
echo "Main App: http://localhost:8081"
echo "Log in with your admin credentials"
echo "Navigate to the MS-Form page"

echo ""
echo "Press Ctrl+C to stop the server"
wait 
