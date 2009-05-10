from django.shortcuts import render_to_response

def index(request):
    return render_to_response('techjunkie/index.html');

def style(request):
    return render_to_response('techjunkie/style.html');
