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
import socket

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




#custom json formatter 
class JsonFormatter(logging.Formatter):
    def format(self, record):
        ip_address = getattr(record, 'ip', socket.gethostbyname(socket.gethostname()))        
        log_entry = {
            'timestamp': self.formatTime(record),
            'level': record.levelname,
            'message': record.getMessage(),
            'logger': record.name,
            'filename': record.pathname,
            'line': record.lineno,
            'ip_address': ip_address,  # Adding IP address
        }
        return json.dumps(log_entry, indent=4)




# Logger Setup
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())  # Set the custom JSON formatter
logger = logging.getLogger(__name__) 
logger.setLevel(logging.INFO)  # Set the log level to INFO
logger.addHandler(handler)  # adding handler




# Utility Functions
def load_courses():
    with tracer.start_as_current_span("load_courses", kind=SpanKind.INTERNAL) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"
        logger.info(f"Trace ID: {trace_id} - Loading courses")
        if not os.path.exists(COURSE_FILE):
            return []
        with open(COURSE_FILE, 'r') as file:
            return json.load(file)


def save_courses(data):
    with tracer.start_as_current_span("save_courses", kind=SpanKind.INTERNAL) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"
        logger.info(f"Trace ID: {trace_id} - Saving course {data['code']}")
        courses = load_courses()
        courses.append(data)
        with open(COURSE_FILE, 'w') as file:
            json.dump(courses, file, indent=4)


# Routes
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/catalog')
def course_catalog():
    #trace setup 
    with tracer.start_as_current_span("render_course_catalog", kind=SpanKind.SERVER) as span:
        courses = load_courses()
        trace_id = f"{span.get_span_context().trace_id:032x}"
        span.set_attribute("total_courses", len(courses))
        span.set_attribute("user_ip", request.remote_addr)
        logger.info(f"Trace ID: {trace_id} - Rendering course catalog with {len(courses)} courses")
        return render_template('course_catalog.html', courses=courses)


@app.route('/add_course', methods=['GET', 'POST'])
def add_course():
    with tracer.start_as_current_span("add_course", kind=SpanKind.SERVER) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"
        if request.method == 'POST':
            errors = {}
            course = {
                'code': request.form.get('code'),
                'name': request.form.get('name'),
                'instructor': request.form.get('instructor'),
            }
            if not course['code']:
                errors['code'] = "Course code is required."  # checking all the fields are field 
            if not course['name']:
                errors['name'] = "Course name is required."  # checking all the fields are field 
            if not course['instructor']:
                errors['instructor'] = "Instructor name is required."  # checking all the fields are field 

            if errors: # throw errors 
                span.set_attribute("error", True)
                span.set_attribute("validation_errors", errors)
                logger.warning(f"Trace ID: {trace_id} - Validation errors: {errors}")
                flash("Please fix the errors and try again.", "danger")
                return render_template('add_course.html', errors=errors)

            save_courses(course) #saving
            span.set_attribute("course_code", course['code'])
            logger.info(f"Trace ID: {trace_id} - Course '{course['code']}' added successfully")
            flash(f"Course '{course['name']}' added successfully!", "success")
            return render_template('add_course.html', errors={})

        logger.info(f"Trace ID: {trace_id} - Rendering add_course page")
        return render_template('add_course.html', errors={})


@app.route('/course/<code>')
def course_details(code):
    with tracer.start_as_current_span("course_details", kind=SpanKind.SERVER) as span:
        trace_id = f"{span.get_span_context().trace_id:032x}"
        courses = load_courses()
        course = next((course for course in courses if course['code'] == code), None)
        if not course:
            span.set_attribute("error", True)
            span.set_attribute("course_code", code)
            logger.error(f"Trace ID: {trace_id} - No course found with code '{code}'")
            flash(f"No course found with code '{code}'.", "danger")
            return redirect(url_for('course_catalog'))
        span.set_attribute("course_code", code)
        logger.info(f"Trace ID: {trace_id} - Displaying details for course '{code}'")
        return render_template('course_details.html', course=course)


if __name__ == '__main__':
    app.run(debug=True)