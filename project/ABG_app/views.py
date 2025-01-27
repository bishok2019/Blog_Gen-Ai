from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import os
import assemblyai as aai
import openai
from pytube import YouTube
from django.conf import settings

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
  if request.method != 'POST':
    # Reject requests that are not POST requests (e.g., GET requests)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

  try:
    # Parse the JSON data sent in the request body
    data = json.loads(request.body)
    yt_link = data['link']

    # Download the audio from the YouTube video link
    audio_file = download_audio(yt_link)
    print(f"Downloaded audio file: {audio_file}") # Added print statement
    if not audio_file:
      # Handle download failure (e.g., invalid link, geo-restricted video)
      return JsonResponse({'error': 'Failed to download audio from YouTube'}, status=500)

    # Get the transcript from the downloaded audio file
    transcription = get_transcription(audio_file)
    print(f"Transcription: {transcription[:20]}...") # Print only a snippet
    if not transcription:
      # Handle transcription failure (e.g., AssemblyAI error)
      return JsonResponse({'error': 'Failed to get transcript'}, status=500)

    # Generate blog content from the transcript using OpenAI
    blog_content = generate_blog_from_transcription(transcription)
    print(f"Generated blog content length: {len(blog_content)} characters")  # Added print statement
    if not blog_content:
      # Handle OpenAI generation failure
      return JsonResponse({'error': 'Failed to generate blog article'}, status=500)

    # Successful generation, return blog content as JSON response
    return JsonResponse({'content': blog_content})

  except (KeyError, json.JSONDecodeError) as e:
    # Handle invalid JSON data sent in the request
    return JsonResponse({'error': 'Invalid data sent'}, status=400)
  except Exception as e:
    # Catch any other unexpected exceptions
    return JsonResponse({'error': f'Error generating blog article: {str(e)}'}, status=500)

def download_audio(link):
  yt = YouTube(link)
  video = yt.streams.filter(only_audio=True).first()
  out_file = video.download(output_path=settings.MEDIA_ROOT)
  base, ext = os.path.splitext(out_file)
  new_file = base + '.mp3'
  return new_file

def yt_title(link):
  yt = YouTube(link)
  title = yt.title
  return title

def get_transcription(link):
  audio_file = download_audio(link)
  aai.settings.api_key = settings.ASSEMBLYAI_API_KEY
  transcriber = aai.transcriber()
  transcript = transcriber.transcribe(audio_file)
  return transcript.text

def generate_blog_from_transcription(transcription):
  openai.api_key = settings.OPENAI_API_KEY
  prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article:\n\n{transcription}\n\nArticle:"
  
  response = openai.Completion.create(
      model="text-davinci-003",
      prompt=prompt,
      max_tokens=1000
  )
  generated_content = response.choices[0].text.strip()
  return generated_content

def user_signup(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        cpassword = request.POST.get('cpassword')
        
        if not username or not email or not password or not cpassword:
            error_message = 'All fields are required'
            return render(request, 'signup.html', {'error_message': error_message})

        if password != cpassword:
            error_message = 'Passwords do not match'
            return render(request, 'signup.html', {'error_message': error_message})
        
        try:
            validate_password(password)
        except ValidationError as e:
            return render(request, 'signup.html', {'error_message': e.messages})

        try:
            if User.objects.filter(username=username).exists():
                error_message = 'Username already taken'
                return render(request, 'signup.html', {'error_message': error_message})

            if User.objects.filter(email=email).exists():
                error_message = 'Email already registered'
                return render(request, 'signup.html', {'error_message': error_message})

            user = User.objects.create_user(username, email, password)
            user.save()
            login(request, user)
            return redirect('index')  
        except Exception as e:
            error_message = f'Error creating account: {str(e)}'
            return render(request, 'signup.html', {'error_message': error_message})

    return render(request, 'signup.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if not username or not password:
            error_message = 'Both username and password are required'
            return render(request, 'login.html', {'error_message': error_message})

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('index') 
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_logout(request):
    logout(request)
    messages.success(request, "Logged out successfully!")
    return redirect('login')  
