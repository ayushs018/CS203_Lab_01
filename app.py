# Importing required libraries
import json  # For handling JSON data
import os  # For interacting with the operating system
import logging  # For logging events and messages
from flask import Flask, render_template, request, redirect, url_for, flash  # Flask modules for web app functionality
from opentelemetry import trace  # For tracing capabilities
from opentelemetry.sdk.resources import Resource  # To define service resources
from opentelemetry.sdk.trace import TracerProvider  # To provide tracing capabilities
from opentelemetry.sdk.trace.export import BatchSpanProcessor  # To process and export spans in batches
from opentelemetry.exporter.jaeger.thrift import JaegerExporter  # Jaeger exporter for trace visualization
from opentelemetry.instrumentation.flask import FlaskInstrumentor  # To integrate OpenTelemetry with Flask
from opentelemetry.trace import SpanKind  # Enum for different span kinds
import socket  # For working with IP addresses

# Flask App Initialization
app = Flask(__name__)  # Initialize Flask app
app.secret_key = 'secret'  # Set a secret key for session management
COURSE_FILE = 'course_catalog.json'  # File to store course data

# OpenTelemetry Setup
resource = Resource.create({"service.name": "course-catalog-service"})  # Define service name
trace.set_tracer_provider(TracerProvider(resource=resource))  # Set tracer provider with defined resource
tracer = trace.get_tracer(__name__)  # Create tracer instance
jaeger_exporter = JaegerExporter(  # Configure Jaeger exporter
    agent_host_name="localhost",
    agent_port=6831,
)
span_processor = BatchSpanProcessor(jaeger_exporter)  # Configure span processor
trace.get_tracer_provider().add_span_processor(span_processor)  # Add processor to tracer provider
FlaskInstrumentor().instrument_app(app)  # Instrument Flask app for tracing




# Custom JSON Formatter for logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        ip_address = getattr(record, 'ip', socket.gethostbyname(socket.gethostname()))  # Get IP address
        log_entry = {  # Format log as JSON
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
            'filename': record.pathname,
            'line': record.lineno,
            'ip_address': ip_address,  # Include IP address
        }
        return json.dumps(log_entry, indent=4)  # Return formatted log entry

# Logger Setup
handler = logging.StreamHandler()  # Create stream handler
handler.setFormatter(JsonFormatter())  # Set custom formatter
logger = logging.getLogger(__name__)  # Create logger
logger.setLevel(logging.INFO)  # Set log level to INFO
logger.addHandler(handler)  # Attach handler to logger

# Utility Functions
def load_courses():
    """Load courses from JSON file."""
    with tracer.start_as_current_span("load_courses", kind=SpanKind.INTERNAL) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"  # Get trace ID
        logger.info(f"Trace ID: {trace_id} - Loading courses")
        if not os.path.exists(COURSE_FILE):  # Check if file exists
            return []  # Return empty list if not
        with open(COURSE_FILE, 'r') as file:  # Open file
            return json.load(file)  # Load JSON data

def save_courses(data):
    """Save a course to JSON file."""
    with tracer.start_as_current_span("save_courses", kind=SpanKind.INTERNAL) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"  # Get trace ID
        logger.info(f"Trace ID: {trace_id} - Saving course {data['code']}")
        courses = load_courses()  # Load existing courses
        courses.append(data)  # Add new course
        with open(COURSE_FILE, 'w') as file:  # Open file in write mode
            json.dump(courses, file, indent=4)  # Write updated data to file

# Flask Routes
@app.route('/')
def index():
    """Render the homepage."""
    return render_template('index.html')

@app.route('/catalog')
def course_catalog():
    """Render the course catalog."""
    with tracer.start_as_current_span("render_course_catalog", kind=SpanKind.SERVER) as span:
        courses = load_courses()  # Load courses
        trace_id = f"{span.get_span_context().trace_id:032x}"  # Get trace ID
        span.set_attribute("total_courses", len(courses))  # Add attributes to span
        span.set_attribute("user_ip", request.remote_addr)  # Log user IP
        logger.info(f"Trace ID: {trace_id} - Rendering course catalog with {len(courses)} courses")
        return render_template('course_catalog.html', courses=courses)  # Render template

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    """Handle adding a new course."""
    with tracer.start_as_current_span("add_course", kind=SpanKind.SERVER) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"  # Get trace ID
        if request.method == 'POST':  # Handle POST request
            errors = {}
            course = {
                'code': request.form.get('code'),
                'name': request.form.get('name'),
                'instructor': request.form.get('instructor'),
            }
            # Validate form data
            if not course['code']:
                errors['code'] = "Course code is required."
            if not course['name']:
                errors['name'] = "Course name is required."
            if not course['instructor']:
                errors['instructor'] = "Instructor name is required."

            if errors:  # Handle validation errors
                span.set_attribute("error", True)
                span.set_attribute("validation_errors", errors)
                logger.warning(f"Trace ID: {trace_id} - Validation errors: {errors}")
                flash("Please fix the errors and try again.", "danger")
                return render_template('add_course.html', errors=errors)

            save_courses(course)  # Save course data
            span.set_attribute("course_code", course['code'])
            logger.info(f"Trace ID: {trace_id} - Course '{course['code']}' added successfully")
            flash(f"Course '{course['name']}' added successfully!", "success")
            return render_template('add_course.html', errors={})

        logger.info(f"Trace ID: {trace_id} - Rendering add_course page")
        return render_template('add_course.html', errors={})

@app.route('/course/<code>')
def course_details(code):
    """Display details for a specific course."""
    with tracer.start_as_current_span("course_details", kind=SpanKind.SERVER) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"  # Get trace ID
        courses = load_courses()  # Load courses
        course = next((course for course in courses if course['code'] == code), None)  # Find course by code
        if not course:  # Handle missing course
            span.set_attribute("error", True)
            span.set_attribute("course_code", code)
            logger.error(f"Trace ID: {trace_id} - No course found with code '{code}'")
            flash(f"No course found with code '{code}'.", "danger")
            return redirect(url_for('course_catalog'))
        span.set_attribute("course_code", code)
        logger.info(f"Trace ID: {trace_id} - Displaying details for course '{code}'")
        return render_template('course_details.html', course=course)  # Render template

# Run the app
if __name__ == '__main__':
    app.run(debug=True)  # Run Flask app in debug mode