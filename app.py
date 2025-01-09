import json
import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import SpanKind

# Flask App Initialization
app = Flask(__name__)
app.secret_key = 'secret'
COURSE_FILE = 'course_catalog.json'

# OpenTelemetry Setup
resource = Resource.create({"service.name": "course-catalog-service"})
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer = trace.get_tracer(__name__)
jaeger_exporter = JaegerExporter(
    agent_host_name="localhost",
    agent_port=6831,
)
span_processor = BatchSpanProcessor(jaeger_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
FlaskInstrumentor().instrument_app(app)

#  JSON Formatter for Structured Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
            'filename': record.pathname,
            'line': record.lineno,
        }
        return json.dumps(log_entry, indent=4)  #  indentation


# Logging Setup
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger = logging.getLogger('JsonLogger')
logger.setLevel(logging.INFO)
logger.addHandler(handler)



# Utility Functions
def load_courses():
    """Load courses from the JSON file."""
    if not os.path.exists(COURSE_FILE):
        return []  # Return an empty list if the file doesn't exist
    with open(COURSE_FILE, 'r') as file:
        return json.load(file)


def save_courses(data):
    """Save new course data to the JSON file."""
    courses = load_courses()  # Load existing courses
    courses.append(data)  # Append the new course
    with open(COURSE_FILE, 'w') as file:
        json.dump(courses, file, indent=4)


# Routes
@app.route('/')
def index():
    # tracing 
    with tracer.start_as_current_span("render_index_page") as span : 
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user.ip", request.remote_addr)
        # logging 
        logger.info("Index page accesed" , extra={"route" : "/" , "method" : request.method})
        return render_template('index.html')


@app.route('/catalog')
def course_catalog():
    # tracing 
    with tracer.start_as_current_span("render_course_catalog") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user.ip", request.remote_addr)

        courses = load_courses()
        # logging
        logger.info("Course catalog viewed", extra={"route": "/catalog", "courses_count": len(courses)})
        return render_template('course_catalog.html', courses=courses)

@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    with tracer.start_as_current_span("add_course_page") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user.ip", request.remote_addr)

        if request.method == 'POST':
            course_name = request.form['name']
            instructor = request.form['instructor']
            course_code = request.form['code']
            semester = request.form['semester']
            schedule = request.form['schedule']
            classroom = request.form['classroom']
            prerequisites = request.form['prerequisites']
            grading = request.form['grading']
            description = request.form['description']

            # Validate and log missing required fields
            missing_fields = []
            if not course_name:
                missing_fields.append("Course name")
                logger.error("Course name is missing", extra={"route": "/add_course", "field": "name"})
            if not instructor:
                missing_fields.append("Instructor")
                logger.error("Instructor is missing", extra={"route": "/add_course", "field": "instructor"})
            if not course_code:
                missing_fields.append("Course code")
                logger.error("Course code is missing", extra={"route": "/add_course", "field": "code"})
            if not semester:
                missing_fields.append("Semester")
                logger.error("Semester is missing", extra={"route": "/add_course", "field": "semester"})
            if not schedule:
                missing_fields.append("Schedule")
                logger.error("Schedule is missing", extra={"route": "/add_course", "field": "schedule"})
            if not classroom:
                missing_fields.append("Classroom")
                logger.error("Classroom is missing", extra={"route": "/add_course", "field": "classroom"})
            if not prerequisites:
                missing_fields.append("Prerequisites")
                logger.error("Prerequisites are missing", extra={"route": "/add_course", "field": "prerequisites"})
            if not grading:
                missing_fields.append("Grading")
                logger.error("Grading is missing", extra={"route": "/add_course", "field": "grading"})
            if not description:
                missing_fields.append("Description")
                logger.error("Description is missing", extra={"route": "/add_course", "field": "description"})

            # If there are missing fields, notify the user and prevent form submission
            if missing_fields:
                flash(f"Missing required fields: {', '.join(missing_fields)}", "error")
                return redirect(url_for('add_course'))

            # Save course if all fields are filled
            course = {
                'code': course_code,
                'name': course_name,
                'instructor': instructor,
                'semester': semester,
                'schedule': schedule,
                'classroom': classroom,
                'prerequisites': prerequisites,
                'grading': grading,
                'description': description
            }

            save_courses(course)
            # logging
            logger.info(f"Course '{course['name']}' added successfully", extra={"route": "/add_course"})
            flash(f"Course '{course['name']}' added successfully!", "success")
            return redirect(url_for('course_catalog'))
        
        return render_template('add_course.html')


@app.route('/course/<code>')
def course_details(code):
    with tracer.start_as_current_span("view_course_details") as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.set_attribute("user.ip", request.remote_addr)

        courses = load_courses()
        course = next((course for course in courses if course['code'] == code), None)
        
        if not course:
            flash(f"No course found with code '{code}'.", "error")
            return redirect(url_for('course_catalog'))
        logger.info(f"Course details viewed for code: {code}", extra={"route": f"/course/{code}"})
        return render_template('course_details.html', course=course)


@app.route("/manual-trace")
def manual_trace():
    # Start a span manually for custom tracing
    with tracer.start_as_current_span("manual-span", kind=SpanKind.SERVER) as span:
        span.set_attribute("http.method", request.method)
        span.set_attribute("http.url", request.url)
        span.add_event("Processing request")
        return "Manual trace recorded!", 200


@app.route("/auto-instrumented")
def auto_instrumented():
    # Automatically instrumented via FlaskInstrumentor
    return "This route is auto-instrumented!", 200


if __name__ == '__main__':
    app.run(debug=True)
