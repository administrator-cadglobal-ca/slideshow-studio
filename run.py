"""Development server entry point."""
import os
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "default"))

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Slideshow Studio")
    print("  http://localhost:5000")
    print("="*55 + "\n")
    app.run(
        host   = "0.0.0.0",
        port   = int(os.environ.get("PORT", 5000)),
        debug  = True,
        use_reloader = True,
    )
