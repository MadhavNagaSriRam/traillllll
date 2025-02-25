# import google.generativeai as genai
# import PIL.Image
# import os
# import json
# from datetime import datetime
# from io import BytesIO
# import fitz 
# from fastapi import FastAPI, File, UploadFile, HTTPException
# from fastapi.responses import JSONResponse

# from dotenv import load_dotenv
# load_dotenv()  # Load environment variables from .env file

# # GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")



# # Configure the API key securely from environment variable
# GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# genai.configure(api_key=GOOGLE_API_KEY)

# # FastAPI app initialization
# app = FastAPI()

# def validate_pdf(filename: str, content: bytes) -> bool:
#     """Validate if the file is a PDF"""
#     if not filename.lower().endswith('.pdf'):
#         return False
    
#     try:
#         doc = fitz.open(stream=content, filetype="pdf")
#         doc.close()
#         return True
#     except fitz.FitzError:
#         return False

# def convert_pdf_to_image(pdf_path: str) -> BytesIO:
#     """Convert first page of PDF to image"""
#     try:
#         pdf_document = fitz.open(pdf_path)
#         if pdf_document.page_count < 1:
#             raise HTTPException(status_code=400, detail="PDF has no pages.")
        
#         page = pdf_document.load_page(0)  # Load first page
#         pix = page.get_pixmap()
#         img_data = BytesIO(pix.tobytes("png"))
#         pdf_document.close()
#         return img_data
#     except Exception as e:
#         print(f"Error converting PDF to image: {str(e)}")
#         return None

# def extract_aadhaar_data(image_source: BytesIO) -> dict:
#     """
#     Extract Aadhaar card data using Google's Generative AI
#     """
#     model = genai.GenerativeModel('gemini-1.5-flash')

#     try:
#         img = PIL.Image.open(image_source)

#         # Define prompt for Aadhaar extraction
#         prompt = """
#         Analyze this Aadhaar card image and extract the following details:
#         - Full name
#         - Date of birth
#         - Gender
#         - Aadhaar number
#         - Address
#         -S/O, D/O
#         Return the information in this JSON format:
#         {
#             "name": "",
#             "date_of_birth": "",
#             "date_of_birth_year": "",
#             "gender": "",
#             "aadhaar_number": "",
#             "address": "",
#             "Parent": "",
#             "confidence": 0-100
#         }
#         """

#         response = model.generate_content([prompt, img])
#         json_str = response.text.strip()
#         json_str = json_str.replace('```json', '').replace('```', '').strip()
        
#         try:
#             return json.loads(json_str)
#         except json.JSONDecodeError:
#             print("Failed to decode JSON response from AI.")
#             return None
    
#     except Exception as e:
#         print(f"Error extracting Aadhaar data: {str(e)}")
#         return None

# @app.post("/extract-aadhaar-data/")
# async def extract_aadhaar(aadhaar: UploadFile = File(...)):
#     """
#     Extract data from Aadhaar card and return JSON format
#     """
#     try:
#         # Read Aadhaar content
#         aadhaar_content = await aadhaar.read()

#         # Validate PDF
#         if not validate_pdf(aadhaar.filename, aadhaar_content):
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"File {aadhaar.filename} must be a valid PDF"
#             )

#         # Save PDF temporarily
#         temp_filename = f"temp_aadhaar_{datetime.now().timestamp()}.pdf"
#         with open(temp_filename, 'wb') as f:
#             f.write(aadhaar_content)

#         # Convert to image
#         img_data = convert_pdf_to_image(temp_filename)
#         if not img_data:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Failed to process {aadhaar.filename}"
#             )

#         # Extract Aadhaar data
#         aadhaar_data = extract_aadhaar_data(img_data)
#         if not aadhaar_data:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Failed to extract data from {aadhaar.filename}"
#             )

#         # Clean up temporary file
#         try:
#             os.remove(temp_filename)
#         except Exception as e:
#             print(f"Error deleting temporary file: {str(e)}")

#         return JSONResponse(status_code=200, content=aadhaar_data)
    
#     except HTTPException as he:
#         return JSONResponse(status_code=he.status_code, content={"error": he.detail})
#     except Exception as e:
#         return JSONResponse(status_code=500, content={"error": str(e)})

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="127.0.0.1", port=8000)





from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
import PIL.Image
import fitz
from io import BytesIO
import json
import os
from dotenv import load_dotenv

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

# Ensure the 'pdf' folder exists
if not os.path.exists('pdf'):
    os.makedirs('pdf')

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

def extract_data(image_source: BytesIO, prompt: str) -> dict:
    """
    Extract data from an image using Google's Generative AI
    """
    model = genai.GenerativeModel('gemini-1.5-flash')

    try:
        img = PIL.Image.open(image_source)
        response = model.generate_content([prompt, img])
        json_str = response.text.strip()
        json_str = json_str.replace('```json', '').replace('```', '').strip()
        return json.loads(json_str)
    except Exception as e:
        print(f"Error extracting data: {str(e)}")
        return None

@app.post("/extract-aadhaar-data/")
async def extract_aadhaar(aadhaar: UploadFile = File(...), filename: str = ''):
    """
    Extract data from Aadhaar card and return JSON format
    """
    aadhaar_prompt = """
    Analyze this Aadhaar card image and extract the following details:
    - Full name
    - Date of birth
    - Gender
    - Aadhaar number
    - Address
    - S/O, D/O
    Return the information in JSON format as specified.
    """
    return await process_pdf(aadhaar, filename, aadhaar_prompt)

@app.post("/extract-marksheet-data/")
async def extract_marksheet(marksheet: UploadFile = File(...), filename: str = ''):
    """
    Extract data from marksheet and return JSON format
    """
    marksheet_prompt = """
    Analyze this marksheet image and extract the following details:
    - Full name of the student
    - Roll number
    - Course/program name
    - Academic year/semester
    - Subjects and corresponding grades/marks
    - Total marks
    - School name
    Return the information in JSON format as specified.
    """
    return await process_pdf(marksheet, filename, marksheet_prompt)

async def process_pdf(file: UploadFile, filename: str, prompt: str):
    """
    General function to process a PDF and extract data using a specific prompt
    """
    try:
        file_content = await file.read()

        # Validate PDF
        if not validate_pdf(file.filename, file_content):
            raise HTTPException(
                status_code=400,
                detail=f"File {file.filename} must be a valid PDF"
            )

        # Set the filename for saving
        save_filename = f"pdf/{filename}.pdf" if filename else f"pdf/{file.filename}"

        # Save PDF to the 'pdf' folder
        with open(save_filename, 'wb') as f:
            f.write(file_content)

        # Convert PDF to image
        img_data = convert_pdf_to_image(save_filename)
        if not img_data:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to process {file.filename}"
            )

        # Extract data using the provided prompt
        extracted_data = extract_data(img_data, prompt)
        if not extracted_data:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract data from {file.filename}"
            )

        # Return extracted data as JSON
        return JSONResponse(content={"data": extracted_data})
    
    except HTTPException as he:
        return JSONResponse(status_code=he.status_code, content={"error": he.detail})
    except Exception as e:
        print(f"Internal server error: {str(e)}")
        return JSONResponse(status_code=500, content={"error": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
