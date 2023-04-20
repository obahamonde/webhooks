import os
import asyncio
from uuid import uuid4
import aiohttp_cors
from aiohttp import ClientSession
from aiofauna import Api, AioModel, json_response as j, sse_response, Response, Request
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()

FAUNA_SECRET = os.getenv("FAUNA_SECRET")
SEND_IN_BLUE_API_KEY = os.getenv("SEND_IN_BLUE_API_KEY")

app = Api()

class Contact(AioModel):
    message_id: str = Field(default_factory=lambda: str(uuid4()), unique=True)
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=100, index=True)
    message: str = Field(..., max_length=1000)

@app.get("/api/contact")
async def send_email(name: str, email: str, message: str):
    method = "POST"     
    url = "https://api.sendinblue.com/v3/smtp/email"
    headers = {
        "api-key": SEND_IN_BLUE_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    json = {
        "sender": {"name": name, "email": email,},
        "to": [{"name": "Oscar Bahamonde", "email": "oscar.bahamonde.dev@gmail.com",}],
        "subject": f"Message from {name} <{email}>",
        "htmlContent": message,
    }
    async with ClientSession() as session:
        async with session.request(method, url, headers=headers, json=json) as response:
            message_id = (await response.json())["messageId"]
 
            contact = Contact(name=name, email=email, message=message, message_id=message_id)
            response = await contact.upsert()
            print(response.to_dict())
            return j(response.to_dict())

@app.post("/api/webhook/{ref}")   
async def webhook(ref:str):
    url = "https://hooks.slack.com/services/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"
    method = "POST"
    headers = {
        "Content-Type": "application/json",
    }
    contact = await Contact.find_unique("message_id", ref)
    if isinstance(contact, Contact):
        async with ClientSession() as session:
            async with session.request(method, url, headers=headers, json={"text": f"{contact.name} <{contact.email}> sent a message: {contact.message} | {contact.ref}"}) as response:
                if response.status != 200:
                    return j({"message": "Something went wrong", "status":"error"}, status=500)
                return j({"message": "Your message was delivered to my slack channel", "status": "success"})
    return j({"message": "Something went wrong", "status":"error"}, status=500)
    
connections = {}

async def sse(request: Request):
    async with sse_response(request) as resp:    
        ref = request.query.get("ref")
        while True:
            if not ref or ref in ["null", "undefined"]:
                break
            await resp.prepare(request)
            await resp.send("ping")
            print(ref)
            if ref not in connections:
                connections[ref] = []
            connections[ref].append(resp)
            await asyncio.sleep(120)
            if resp.status == 200:
                connections[ref].remove(resp)
            return resp
    return resp
app.router.add_get("/api/sse", sse)

@app.post("/api/sse")
async def sse_post(ref: str, message: str):
    print(connections)
    if ref in connections:
        for connection in connections[ref]:
            if connection.status == 200:
                connections[ref].remove(connection)
            await connection.send(message)
    return j({"message": "Message sent"})
cors = aiohttp_cors.setup(app, defaults={
    "*": aiohttp_cors.ResourceOptions(
        allow_credentials=True,
        expose_headers="*",
        allow_headers="*",
        allow_methods="*",
    )
})

for route in list(app.router.routes()):
    cors.add(route)

async def create_app():
    await app.listen()
    return app
