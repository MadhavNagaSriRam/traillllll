from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import PIL.Image
import fitz
from io import BytesIO
import json
import os
from dotenv import load_dotenv
from gtts import gTTS
from confluent_kafka import Producer, Consumer, KafkaException, KafkaError

# Load environment variables
load_dotenv()

# Configure the API key for Google Generative AI from environment variables
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Google API Key is missing. Set it in the environment variables.")
genai.configure(api_key=GOOGLE_API_KEY)

# FastAPI app initialization
app = FastAPI()

# Add CORS middleware to allow requests from your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow Angular frontend
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize Kafka Producer
producer = Producer({'bootstrap.servers': 'localhost:9092'})

# Ensure the 'pdf' folder exists
if not os.path.exists('pdf'):
    os.makedirs('pdf')

def delivery_report(err, msg):
    """Called once for each message produced to indicate delivery result"""
    if err is not None:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")

def send_message_to_kafka(topic: str, message: str):
    """Send message to Kafka"""
    producer.produce(topic, message.encode('utf-8'), callback=delivery_report)
    producer.flush()

def validate_pdf(filename: str, content: bytes) -> bool:
    """Validate if the file is a PDF"""
    if not filename.lower().endswith('.pdf'):
        return False
    
    try:
        doc = fitz.open(stream=content, filetype="pdf")
        doc.close()
        return True
    except Exception:
        return False

def convert_pdf_to_image(pdf_path: str) -> BytesIO:
    """Convert the first page of PDF to image"""
    try:
        pdf_document = fitz.open(pdf_path)
        page = pdf_document.load_page(0)  # Load the first page
        pix = page.get_pixmap()
        img_data = BytesIO(pix.tobytes("png"))
        pdf_document.close()
        return img_data
    except Exception as e:
        print(f"Error converting PDF to image: {str(e)}")
        return None

def extract_aadhaar_data(image_source: BytesIO) -> dict:
    """Extract Aadhaar card data using Google's Generative AI"""
    model = genai.GenerativeModel('gemini-1.5-flash')

    try:
        img = PIL.Image.open(image_source)

        prompt = """
        Analyze this Aadhaar card image and extract the following details:
        - Full name
        - Date of birth
        - Gender
        - Aadhaar number
        - Address
        - S/O, D/O
        Return the information in this JSON format:
        {
            "name": "",
            "date_of_birth": "",
            "date_of_birth_year": "",
            "gender": "",
            "aadhaar_number": "",
            "address": "",
            "Parent": "",
            "confidence": 0-100
        }
        """
        
        response = model.generate_content([prompt, img])
        json_str = response.text.strip()
        json_str = json_str.replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)
    
    except Exception as e:
        print(f"Error extracting Aadhaar data: {str(e)}")
        return None

def extract_marksheet_data(image_source: BytesIO) -> dict:
    """Extract marksheet data using Google's Generative AI"""
    model = genai.GenerativeModel('gemini-1.5-flash')

    try:
        img = PIL.Image.open(image_source)

        prompt = """
        Analyze this marksheet image and extract the following details:
        - Full name of the student
        - Roll number
        - Course/program name
        - Academic year/semester
        - Subjects and corresponding grades/marks
        - Total marks
        - School name
        Return the information in this JSON format:
        {
            "name": "",
            "roll_number": "",
            "Examination": "",
            "academic_year": "",
            "subjects": [
                {"subject": "", "marks": "", "grade": ""}
            ],
            "Total": "",
            "School": "",
            "confidence": 0-100
        }
        """
        
        response = model.generate_content([prompt, img])
        json_str = response.text.strip()
        json_str = json_str.replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)
    
    except Exception as e:
        print(f"Error extracting marksheet data: {str(e)}")
        return None

def generate_audio_response(message: str) -> str:
    """Generate an audio response (speech) from a text message"""
    try:
        tts = gTTS(message)
        audio_path = "audio_update.mp3"
        tts.save(audio_path)
        return audio_path
    except Exception as e:
        print(f"Error generating audio: {str(e)}")
        return None

@app.post("/extract-aadhaar-data/")
async def extract_aadhaar(aadhaar: UploadFile = File(...), filename: str = ''):
    try:
        aadhaar_content = await aadhaar.read()

        if not validate_pdf(aadhaar.filename, aadhaar_content):
            raise HTTPException(status_code=400, detail=f"File {aadhaar.filename} must be a valid PDF")

        if filename:
            save_filename = f"pdf/{filename}.pdf"
        else:
            save_filename = f"pdf/{aadhaar.filename}"

        with open(save_filename, 'wb') as f:
            f.write(aadhaar_content)

        img_data = convert_pdf_to_image(save_filename)
        if not img_data:
            raise HTTPException(status_code=400, detail=f"Failed to process {aadhaar.filename}")

        aadhaar_data = extract_aadhaar_data(img_data)
        if not aadhaar_data:
            raise HTTPException(status_code=400, detail=f"Failed to extract data from {aadhaar.filename}")

        # Send extracted Aadhaar data to Kafka
        send_message_to_kafka("file-data", json.dumps(aadhaar_data))

        # Generate an audio update
        audio_path = generate_audio_response("Aadhaar data extraction was successful.")
        
        return JSONResponse(content={"aadhaar_data": aadhaar_data, "audio_update": audio_path})
    
    except HTTPException as he:
        return JSONResponse(status_code=he.status_code, content={"error": he.detail})
    
    except Exception as e:
        print(f"Internal server error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/extract-marksheet-data/")
async def extract_marksheet(marksheet: UploadFile = File(...), filename: str = ''):
    try:
        marksheet_content = await marksheet.read()

        if not validate_pdf(marksheet.filename, marksheet_content):
            raise HTTPException(status_code=400, detail=f"File {marksheet.filename} must be a valid PDF")

        if filename:
            save_filename = f"pdf/{filename}.pdf"
        else:
            save_filename = f"pdf/{marksheet.filename}"

        with open(save_filename, 'wb') as f:
            f.write(marksheet_content)

        img_data = convert_pdf_to_image(save_filename)
        if not img_data:
            raise HTTPException(status_code=400, detail=f"Failed to process {marksheet.filename}")

        marksheet_data = extract_marksheet_data(img_data)
        if not marksheet_data:
            raise HTTPException(status_code=400, detail=f"Failed to extract data from {marksheet.filename}")

        # Send extracted marksheet data to Kafka
        send_message_to_kafka("file-data", json.dumps(marksheet_data))

        return JSONResponse(content={"marksheet_data": marksheet_data})
    
    except HTTPException as he:
        return JSONResponse(status_code=he.status_code, content={"error": he.detail})
    
    except Exception as e:
        print(f"Internal server error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/audio-update/")
async def get_audio_update():
    audio_path = "audio_update.mp3"
    if os.path.exists(audio_path):
        return FileResponse(audio_path)
    else:
        raise HTTPException(status_code=404, detail="Audio file not found")

# Kafka Consumer for processing messages
def consume_messages():
    consumer = Consumer({
        'bootstrap.servers': 'localhost:9092',
        'group.id': 'file-processing-group',
        'auto.offset.reset': 'earliest'
    })

    consumer.subscribe(['file-data'])
    try:
        while True:
            msg = consumer.poll(1.0)  # Wait for message or timeout
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    print(f"End of partition reached {msg.topic()} [{msg.partition()}]")
                else:
                    raise KafkaException(msg.error())
            else:
                print(f"Received message: {msg.value().decode('utf-8')}")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()

if __name__ == "__main__":
    import uvicorn
    print("Starting FastAPI server...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
