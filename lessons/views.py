from __future__ import division
from numbers import Number

from django.shortcuts import render, render_to_response, get_object_or_404, redirect
from django.http import HttpResponse, HttpRequest, JsonResponse
from django.template import loader
from django.template.context import RequestContext
from django.core.context_processors import csrf
from django.template.context_processors import csrf
from django.contrib.auth import authenticate,login, logout

from django.http import HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.conf import settings
import datetime
import json

from lessons.models import *
from .forms import *

@login_required(login_url = '/lessons/login/')
def index(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	courses_enrolled = user_profile.courses_enrolled.all()
	courses_managed = user_profile.courses_managed.all()


	for course in courses_enrolled:
		instructor = UserProfile.objects.filter(courses_managed = course)[0].user
		course.instructor = instructor.first_name + " " + instructor.last_name
		if CourseLogo.objects.filter(course = course).count() == 1:
			course.logo = CourseLogo.objects.get(course = course).docfile.url
		if course in courses_managed:
			course.relationship = "Manager"
		else: 
			course.relationship = "Student"
			modules = Module.objects.filter(course=course).count()
			points = CourseStatus.objects.get(user = user_profile, course = course).points
			if points == modules:
				course.status = "Completed"
			else: 
				course.status = "On module " + str(points+1) + " of " + str(modules)
	return render_to_response('lessons/index.html', {
		'user':user,
		'mycourses': courses_enrolled
	})

@login_required(login_url = '/lessons/login/')
def course(request,course_pk):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)

	# if user enrolled, go to course
	if user_profile.courses_enrolled.filter(pk=course_pk).count() == 1:
		course = Course.objects.get(pk=course_pk)
		modules = Module.objects.filter(course=course)
		points = CourseStatus.objects.get(course=course,user=user_profile).points

		#Divide lessons into completed, current, and future 
		completed_modules = modules.filter(index__lte = points)
		current_module = modules.filter(index = (points + 1))
		future_modules = modules.filter(index__gt = (points + 1))

		return render_to_response('lessons/course.html', {
			'user':user,
			'course': course,
			'completed_modules': completed_modules,
			'current_module': current_module,
			'future_modules': future_modules,
		})

	# if not enrolled, redirect to same page 
	else:
		return redirect('/lessons/') 

def getDocumentLinks(module_element):
	downloads = Document.objects.filter(moduleElement = module_element)
	content = ""
	for download in downloads:
		content += "<p><a class = 'btn btn-info' download href='" + download.docfile.url + "'>" + download.docfile.name.split("/")[-1] +"</a></p>"
	return content

#link to dynamic lessons page with jQuery elements
@login_required(login_url = '/lessons/login/')
def module(request,course_pk,module_index):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	course = Course.objects.get(pk=course_pk)
	courseStatus = CourseStatus.objects.get(user=user_profile,course=course)
	
	#verify user has access to lesson
	if (int(courseStatus.points) + 1) < int(module_index):
		return redirect('/lessons/course/'+ str(course_pk))
	else:
		module = Module.objects.get(course=course, index=module_index)
		module_element_count = len(ModuleElement.objects.filter(module=module))
		hints = module.hints;
		content = ""
		answer_key = []

		for i in range(0,module_element_count):
			module_element = get_object_or_404(ModuleElement, module = module, index = i+1)
			
			# append Content module elements
			if module_element.element_type == 'Content':
				module_html = "<div class = 'lessonElement' id = '" + str(i+1) +"'>" + module_element.text 
				content += module_html
				content += getDocumentLinks(module_element)
				content += "</div>"
			
			# append Quiz module elements
			elif module_element.element_type == 'Quiz':
				#quiz header text
				content+= "<div class = 'lessonElement' id = '" + str(i+1) +"'>" + module_element.text
				content += getDocumentLinks(module_element) 
				questions= Question.objects.filter(moduleElement=module_element)
				for i in range(0,len(questions)):
					question = Question.objects.get(moduleElement=module_element, index= i+1)
					answer_key.append(question.answer)
					#if form question
					if question.question_type == "Form":
						content+= "<h4>" + str(i+1) +". " + question.text + "</h4><form class='Question' type='text'><input type='text'><p class = 'verificationText'> </p></form>"
					#if radio question
					else:
						content+="<h4>" + question.text + "</h4><form class='Question' type='radio'>"
						answer_set = AnswerChoice.objects.filter(question=question)
						for j in range(0,len(answer_set)):
							content+="<input type='radio' name='Question" + str(i) +"' value='" + answer_set[j].text + "'> " + answer_set[j].text + "<br>"
						content+= "<p class = 'verificationText'> </p></form>"
				content+= "<br/><div class='submitButton btn btn-info'> Check Answers </div><br/></div>"

			# append Test module elements - same as Quiz but no answer key passed to template
			else:
				#test header text
				content+= "<div class = 'lessonElement' id = '" + str(i+1) +"'><h3>" + module_element.text +"</h3>"
				questions= Question.objects.filter(moduleElement=module_element)
				content+="<form action='/lessons/test_result/" + course_pk + "/" + module_index + "/' method='post'>"
				for i in range(0,len(questions)):
					question = Question.objects.get(moduleElement=module_element, index= i+1)
					#answer_key.append(question.answer)
					#if form question
					if question.question_type == "Form":
						content+= "<h4>" + str(i+1) + ". " + question.text + "</h4><input type='text' name='answer" + str(i+1) + "''>"
					
					#if radio question
					else:
						content+="<br><br><h4>" + str(i+1) + ". " + question.text + "</h4>"
						answer_set = AnswerChoice.objects.filter(question=question)
						#add hidden field with value "none", so that POST does not have an empty key-value pair
						content+="<h4><input type='hidden' name='answer" + str(i+1) + "' value = 'none'></h4>"
						for j in range(0,len(answer_set)):
							content+="<h4><input type='radio' name='answer" + str(i+1) + "' value = '" +  answer_set[j].text + "'> " + answer_set[j].text + "</h4>"
						content+="<br>"
				content+= "<br><br><input class='testSubmit btn btn-info' type='submit' value='Submit'>"
				content+= "</form></div>"


		answer_key = json.dumps(answer_key)

		return render_to_response('lessons/lesson.html', {
			'user':user,
			'course':course,
			'module': module,
			'content':content,
			'answer_key': answer_key, 
			'hints':hints,
			'module_index': module_index,
		})

#creates new user entry in database
def new_user(request):
	status = ""
	message = ""
	if request.method == 'GET':
		form = NewUserForm()
		method = "GET"
		return render(request, 'lessons/new_user.html', {'form': form, 'method':method})
	else:
		#create new user
		form = request.POST
		if len(User.objects.filter(username__iexact=form['username'])) != 0:
			status = "This username is taken. Please choose another username."
		elif len(User.objects.filter(email__iexact=form['email'])) != 0:
			status = "This email is taken. Please user another email."
		else:
			def capitalize(string):
				first_letter = string[0].upper()
				rest_of_string = ""
				for i in range (0,len(string) - 1):
					rest_of_string += string[i + 1]
				return first_letter + rest_of_string

			user = User.objects.create_user(
				username=form['username'],
				first_name = capitalize(form['first_name']),
				last_name = capitalize(form['last_name']),
				email=form['email'],
				password=form['password']
			)
			user_profile = UserProfile(user = user, points = 0)
			user_profile.save()
			
			# Add course #1-2 (demo) to all new users' accounts and matching CourseStatus object
			"""demo = Course.objects.get(name ="Tennis Greats")
			demo.save()
			
			courseStatus = CourseStatus.objects.create(
				course = demo,
				user = user_profile,
				points = 0)
			user_profile.courses_enrolled.add(demo)
			user_profile.save()
			"""

			#must call authenticate before login, even though we just created the user 
			user_login = authenticate(username=request.POST['username'], password=request.POST['password'])
			login(request,user_login)
			status = "success"
			message = "Hi " + user.first_name + ", thanks for registering!"
		return JsonResponse({'status': status, 'message': message})	

#login function; redirects to log-in page and also logs-out user
def validate_user(request):
	if request.method == 'GET':
		logout(request)
		form = UserForm()
		response = "success"
		return render(request,'lessons/login.html', {'form':form})
	else:
		post = request.POST 
		username = post['username']
		password = post['password']
		user = authenticate(username=username, password=password)
		#if valid login
		if user is not None:
			login(request,user)
			status = "success"
		# if invalid login, redirect user to login page with blank UserForm
		else:
			status = "Please try a different username / password "
		return JsonResponse({'status': status})	
		
#show user profile
@login_required(login_url = '/lessons/login/')
def profile(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	completions = Completion.objects.filter (user = user_profile)
	return render_to_response('lessons/profile.html', {'user':user, 'user_profile': user_profile, 'completions':completions})

# NOT FOR DEPLOYMENT
#link to demo page with jQuery elements
@login_required(login_url = '/lessons/login/')
def demo(request):
	user = request.user
	return render_to_response('lessons/demo.html', {'user':user})

#displays test results
@login_required(login_url = '/lessons/login/')	
def test_result(request,course_pk,module_index):
	user = request.user
	answer_set = []
	answer_key = []
	content = ""
	message_type = "results"
	passed = ""
	correct_count = 0
	next_module ={}


	course = Course.objects.get(pk=course_pk)
	module = Module.objects.get(course = course, index = module_index)
	
	module_element = ModuleElement.objects.filter(module = module, element_type="Test")
	if module_element.count() != 1:
		error = "Error: Number of tests in module not equal to 1"
		return render_to_response('lessons/result.html', {"error": error})	
	else:
		questions= Question.objects.filter(moduleElement=module_element)
		# assemble answer_key and answer_set
		content += "<table><tr><th> Question </th><th> Your Answer </th><th> Correct Answer </th><th></th></tr>"
		for i in range(0,len(questions)):
			question = Question.objects.get(moduleElement=module_element, index= i+1)
			answer_key.append(question.answer)
			answer_set.append(request.POST['answer'+ str(i+1)])
			
			content +=("<tr><td><h4>" + str(i+1) + ". " + question.text + "</h4></td>")
			content +=("<td><h4>" + answer_set[i] + "</h4></td>")

			if answer_set[i].upper() == answer_key[i].upper():
				content+= ("<td><h4>" + answer_key[i] + "</h4></td>")
				content += ("<td><h4 class = 'verificationText' style='color: green;'> Correct </h4></td></tr>")
				correct_count += 1
			else: 
				content+= ("<td><h4>" + answer_key[i] + "</h4></td>")
				content += ("<td><h4 class = 'verificationText' style='color: red;'> Incorrect </h4></td></tr>")
		score = int((correct_count / len(questions)) * 100)
		content += ("</table><br><h2> <strong> You answered " + str(correct_count) + " out of " + str(len(questions)) + " questions correctly (" +  str(score) + "%) </strong></h2>")

		MINIMUM_SCORE = 50

		if score >= MINIMUM_SCORE:
			passed = "yes"
			user_profile = get_object_or_404(UserProfile, user_id = user.id)
			courseStatus = CourseStatus.objects.get(user = user_profile, course = course)
			if module.index != Module.objects.filter(course = course).count():
				next_module = Module.objects.get(course = course, index = (int(module_index) + 1))
			
			#only add points if course has not been completed
			if (courseStatus.points + 1)== Module.objects.filter(course=course).count():
				courseStatus.points += 1
				courseStatus.save()
				message_type = "course_finished"
			elif courseStatus.points >= Module.objects.filter(course=course).count():
				message_type = "course_finished"
			else: 
				courseStatus.points += 1
				courseStatus.save()
				message_type = "results"
				

			#check if completion object already exists for this course; if not create one
			if not Completion.objects.filter(user = user_profile, name = module):
				completion = Completion(user = user_profile, name = module, score = score, date = datetime.datetime.now())
				completion.save()
		else: 
			passed = "no"

	return render_to_response('lessons/result.html', {
		'user': user,
		'course': course,
		'content':content,
		'module': module,
		'next_module': next_module,
		'message_type': message_type,
		'passed': passed
	})

#display lesson creation page
@login_required(login_url = '/lessons/login/')
def create(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	moduleForm = ModuleForm()
	courses = user_profile.courses_managed.all() 
	return render(request, 'lessons/create.html', {
		'user':user, 
		'courses': courses,
		'moduleForm':moduleForm 
	})

@login_required(login_url = '/lessons/login/')
def create_module(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	
	if request.method == 'POST':
		post = request.POST 
		name = post['module[module_name]']
		hints = post['module[module_hints]']
		course = post['module[module_course]']
		course = Course.objects.get(name=course)
		courseStatus = CourseStatus.objects.get(user=user_profile,course=course)

		# verify module name not taken
		if Module.objects.filter(name= name).count() != 0:
			jsonResponseMessage = "That module name is taken. Please use another name"
			return JsonResponse({'jsonResponseMessage': jsonResponseMessage})	

		# create module
		else: 
			index = len(Module.objects.filter(course=course)) + 1
			module = Module.objects.create(
				name=name, 
				hints = hints,
				course = course,
				index = index)
			module.save
	
			# ensure manager has access to all modules in course
			courseStatus.points = Module.objects.filter(course=course).count()
			courseStatus.save()
			
			# create module elements until module element name not found, then
			# set module_element_count for rest of function
			module_element_count = 1
			module_element_loop = True
			while (module_element_loop == True):
				module_element = 'module[module_element_name.'+str(module_element_count)+']'
				if module_element in post:
					name = post['module[module_element_name.'+str(module_element_count)+']']
					text = post['module[module_element_text.'+str(module_element_count)+']']
					element_type = post['module[module_element_type.'+str(module_element_count)+']']
					module_element = ModuleElement.objects.create(
						module = module,
						name=name, 
						text = text,
						element_type = element_type, 
						index = module_element_count)
					module_element.save
					module_element_count += 1
				else:
					module_element_count -= 1
					module_element_loop = False

			# create questions for each module element until question text not found
			for i in range(0,module_element_count):
				question_loop = True
				index = 1
				while (question_loop == True):
					question = 'module[question_text.' + str(i+1) + '.' + str(index) + ']'
					if question in post:
						text = post['module[question_text.'+str(i+1)+ '.' + str(index) + ']']
						answer = post['module[question_answer.'+str(i+1)+ '.' + str(index) + ']']
						question_type = post['module[question_type.'+str(i+1)+ '.' + str(index) + ']']
						question = Question.objects.create(
							moduleElement = ModuleElement.objects.get(module=module, index=i+1),
							text = text,
							answer = answer,
							question_type = question_type, 
							index = index)
						question.save
						index += 1
					else:
						question_loop = False

			# create answer choices for each radio question until answer choice not found
			for i in range(0,module_element_count):
				moduleElement = ModuleElement.objects.get(module=module, index=i+1)
				question_count = Question.objects.filter(moduleElement=moduleElement).count()
				for j in range(0,question_count):
					answer_loop = True
					index = 1
					while (answer_loop == True):
						answer = 'module[answerChoice.'+str(i+1)+ '.' + str(j+1)+ '.'+ str(index) + ']'
						if answer in post:
							text = post['module[answerChoice.'+str(i+1)+ '.' + str(j+1)+ '.'+ str(index) + ']']
							answer = AnswerChoice.objects.create(
								question = Question.objects.get(moduleElement=moduleElement, index=j+1),
								text = text)
							answer.save
							index += 1
						else:
							answer_loop = False

			jsonResponseMessage = "Success! You have created new module: <a class='btn btn-info' href='/lessons/course/" + str(course.pk) + "/" + str(module.index)  +"/'>" + module.name + "</a>"
			return JsonResponse({'jsonResponseMessage': jsonResponseMessage})

	# if request.method = GET
	else:
		jsonResponseMessage = "Error: no module created"
		return JsonResponse({'jsonResponseMessage': jsonResponseMessage})

@login_required(login_url = '/lessons/login/')
def create_course(request):
	user = request.user
	
	if request.method == 'POST':
		post = request.POST 
		name = post['course[course_name]']
		genre = post['course[course_genre]']
		description = post['course[course_description]']

		# verify course name not taken
		if Course.objects.filter(name= name).count() != 0:
			jsonResponseMessage = "That course name is taken. Please use another name"
			return JsonResponse({'jsonResponseMessage': jsonResponseMessage})	

		# create course
		else: 
			course = Course.objects.create(
				name=name, 
				genre = genre, 
				description = description)
			
			user_profile = get_object_or_404(UserProfile, user_id = user.id)
			user_profile.courses_managed.add(course)
			user_profile.save()

			"""
			courseStatus = CourseStatus.objects.create(
				user = user_profile,
				course = course)
			"""

			jsonResponseMessage = "Success! You have created new course: <a class='btn btn-info' href='/lessons/course/" +str(course.pk)  +"/'>" + course.name + "</a>"
			return JsonResponse({'jsonResponseMessage': jsonResponseMessage})

	# if request.method = GET
	else:
		jsonResponseMessage = "Error: no course created"
		return JsonResponse({'jsonResponseMessage': jsonResponseMessage})

@login_required(login_url = '/lessons/login/')
def my_courses(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	mycourses = user_profile.courses_enrolled.all()
	othercourses = []
	for course in Course.objects.all():
		if mycourses.filter(name=course.name).count() == 0:
			othercourses.append(course)
	return render(request, 'lessons/my_courses.html', {
		'user':user, 
		'mycourses': mycourses,
		'othercourses': othercourses
	})

# manage enrollment
@login_required(login_url = '/lessons/login/')
def manage_enrollment(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	
	if request.method == 'POST':
		post = request.POST 
		coursepk = post['coursepk']
		call = post['call']
		course = Course.objects.get(pk=coursepk)

		# remove specified course
		if call == "remove":
			user_profile.courses_enrolled.remove(course)
			CourseStatus.objects.get(course = course, user = user_profile).delete()

		# remove specified course
		if call == "enroll":
			user_profile.courses_enrolled.add(course)
			courseStatus = CourseStatus.objects.create(
				course = course,
				user = user_profile,
				points = 0)

		success = "success"
		return JsonResponse({'success': success})

	else:
		jsonResponseMessage = "Error: no module created"
		return JsonResponse({'jsonResponseMessage': jsonResponseMessage})

# serve edit page showing courses user manages
@login_required(login_url = '/lessons/login/')
def edit(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	courses = user_profile.courses_managed.all()
	
	return render(request, 'lessons/edit.html', {
		'user':user, 
		'courses': courses,
	})

# to be called in edit_data function
def getObject(object_type,course, moduleIndex, moduleElementIndex, questionIndex):
	obj = {}
	if object_type == "course":
		obj = course
	elif object_type == "module":
		obj = Module.objects.get(course = course, index = moduleIndex)
	elif object_type == "moduleElement":
		module = Module.objects.get(course = course, index = moduleIndex)
		obj = ModuleElement.objects.get(module = module, index = moduleElementIndex)
	elif object_type == "question":
		module = Module.objects.get(course = course, index = moduleIndex)
		moduleElement = ModuleElement.objects.get(module = module, index = moduleElementIndex)
		obj = Question.objects.get(moduleElement = moduleElement, index = questionIndex)
	else:
		obj = {}
	return obj

def getSubsequentObjects(object_type,course, moduleIndex, moduleElementIndex, questionIndex):
	# Does not apply to Course 
	if object_type == "module":
		subsequentObjects= Module.objects.filter(course = course, index__gt = moduleIndex)
	elif object_type == "moduleElement":
		module = Module.objects.get(course = course, index = moduleIndex)
		subsequentObjects= ModuleElement.objects.filter(module = module, index__gt = moduleElementIndex)
	elif object_type == "question":
		module = Module.objects.get(course = course, index = moduleIndex)
		moduleElement = ModuleElement.objects.get(module = module, index = moduleElementIndex)
		subsequentObjects= Question.objects.filter(moduleElement = moduleElement, index__gt= questionIndex)
	else:
		subsequentObjects= {}
	return subsequentObjects

# manage course editing
@login_required(login_url = '/lessons/login/')
def edit_data(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	courses = user_profile.courses_managed.all()
	
	if request.method == 'GET':
		return render(request, 'lessons/edit.html', {
			'user':user, 
			'courses': courses,
		})

	else: 
		post = request.POST 
		call = post['call']
		if call == "get_courses":
			course_set = []
			for course in courses:
				temp = {}
				temp['name'] = course.name
				temp['pk'] = course.pk
				course_set.append(temp)
			return JsonResponse({'courses': course_set})

		else: 
			coursepk = post['coursepk']
			course = Course.objects.get(pk=coursepk)
			courseobj = {}
			courseobj['name'] = course.name
			courseobj['genre'] = course.genre
			courseobj['description'] = course.description
			success = ""

			if call == "get_modules":
				module_set = Module.objects.filter(course=course).order_by('index')
				modules = []
				for module in module_set:
					temp = {}
					temp['name'] = module.name
					modules.append(temp)
				return JsonResponse({'courseobj': courseobj, 'modules': modules})

			elif call == "get_module_elements":
				moduleIndex = post['moduleIndex']
				moduleobj = Module.objects.get(course=course,index=moduleIndex)
				module_element_set = ModuleElement.objects.filter(module=moduleobj).order_by('index')
				
				module = {}
				module['name'] = moduleobj.name
				module['index'] = moduleobj.index
				module['hints'] = moduleobj.hints

				moduleElements = []
				for module_element in module_element_set:
					temp = {}
					temp['name'] = module_element.name
					moduleElements.append(temp)
				return JsonResponse({'courseobj': courseobj,'module': module, 'moduleElements': moduleElements})

			elif call == "get_questions":
				moduleIndex = post['moduleIndex']
				moduleElementIndex = post['moduleElementIndex']
				module = Module.objects.get(course=course,index=moduleIndex)
				moduleElementobj = ModuleElement.objects.get(module=module,index=moduleElementIndex)
				question_set = Question.objects.filter(moduleElement=moduleElementobj).order_by('index')

				moduleElement = {}
				moduleElement['name'] = moduleElementobj.name
				moduleElement['type'] = moduleElementobj.element_type
				moduleElement['text'] = moduleElementobj.text

				questions = []
				for question in question_set:
					temp = {}
					temp['text'] = question.text
					questions.append(temp)
				return JsonResponse({'courseobj': courseobj, 'moduleElement': moduleElement, 'questions': questions})

			elif call == "get_answers":
				moduleIndex = post['moduleIndex']
				moduleElementIndex = post['moduleElementIndex']
				questionIndex = post['questionIndex']
				module = Module.objects.get(course=course,index=moduleIndex)
				moduleElement = ModuleElement.objects.get(module=module,index=moduleElementIndex)
				questionobj = Question.objects.get(moduleElement=moduleElement,index = questionIndex)
				answer_set = AnswerChoice.objects.filter(question=questionobj)

				question = {}
				question['type'] = questionobj.question_type
				question['text'] = questionobj.text
				question['answer'] = questionobj.answer
				
				answers = []
				for answer in answer_set:
					answers.append(answer.text)
				return JsonResponse({'courseobj': courseobj, 'question': question,'answers':answers})

			elif call == "edit":
				obj = getObject(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'],post['questionIndex'])
				success = ""
				if obj.__class__.__name__ == "Course":
					obj.name = post['course[name]']
					obj.genre = post['course[genre]']
					obj.description = post['course[description]']
					obj.save()
					success = "Course saved"

				elif obj.__class__.__name__ == "Module":
					obj.name = post['module[name]']
					obj.hints = post['module[hints]']
					obj.save()
					success = "Module saved"

				elif obj.__class__.__name__ == "ModuleElement":
					obj.name = post['moduleElement[name]']
					obj.element_type = post['moduleElement[type]']
					obj.text = post['moduleElement[text]']
					obj.save()
					success = "Module Element saved"

				elif obj.__class__.__name__ == "Question":
					obj.answer = post['question[answer]']
					obj.text = post['question[text]']
					obj.question_type = post['question[type]']
					obj.save()
					# if radio question, replace answerChoice set
					if post['question[type]'] == "Radio":
						answer_set = AnswerChoice.objects.filter(question = obj)
						for answer in answer_set:
							answer.delete()
						i = 0
						while True:
							if 'answers[choice'+str(i)+']' in post:
								if post['answers[choice'+str(i)+']']!= "":
									a = AnswerChoice.objects.create(
										text = post['answers[choice'+str(i)+']'],
										question = obj)
								i+=1
							else:
								break
					success = "Question saved"

				else:
					success = "Error: not saved"
				
				return JsonResponse({'success': success})

			elif call == "create":
				if post['object_type'] == "module":
					course = Course.objects.get(pk = post['coursepk'])
					obj = Module.objects.create(
						course = course,
						name = post['module[name]'], 
						hints = post['module[hints]'],
						index = Module.objects.filter(course = course).count() + 1
					)
					success = "Module saved"
				elif post['object_type'] == "moduleElement":
					course = Course.objects.get(pk = post['coursepk'])
					module = Module.objects.get(course = course, index = post['moduleIndex'])
					obj = ModuleElement.objects.create (
						module = module,
						name = post['moduleElement[name]'], 
						element_type = post['moduleElement[type]'], 
						text = post['moduleElement[text]'],
						index = ModuleElement.objects.filter(module = module).count() + 1
					)
					success = "Module Element saved"
				elif post['object_type'] == "question":
					course = Course.objects.get(pk = post['coursepk'])
					module = Module.objects.get(course = course, index = post['moduleIndex'])
					moduleElement = ModuleElement.objects.get(module = module, index = post['moduleElementIndex'])
					obj = Question.objects.create(
						moduleElement = moduleElement,
						answer = post['question[answer]'], 
						text = post['question[text]'], 
						question_type = post['question[type]'],
						index = Question.objects.filter(moduleElement = moduleElement).count() + 1
					)
					if post['question[type]'] == "Radio":
						i = 0
						while True:
							if 'answers[choice'+str(i)+']' in post:
								if post['answers[choice'+str(i)+']'] != "":
									AnswerChoice.objects.create(
										text = post['answers[choice'+str(i)+']'],
										question = obj)
								i+=1
							else:
								break
					success = "Question saved"
				else:
					success = "Error: not saved"
				return JsonResponse({'success': success})

			elif call == "delete":
				obj = getObject(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'],post['questionIndex'])
				obj.delete()
				subsequentObjects = getSubsequentObjects(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'],post['questionIndex'])
				for subsequentObject in subsequentObjects:
					subsequentObject.index -= 1
					subsequentObject.save()
				success = post['object_type'] + " deleted" 
				return JsonResponse({'success': success})

			elif call == "move_forward":
				objForward = getObject(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'],post['questionIndex'])
				if objForward.index == 1:
					success = "Already first - cannot move forward"
				else: 
					if post['object_type'] == "module":
						objBack = getObject(post['object_type'],course, int(post['moduleIndex']) - 1 ,post['moduleElementIndex'],post['questionIndex'])
					elif post['object_type'] == "moduleElement":
						objBack = getObject(post['object_type'],course, post['moduleIndex'],int(post['moduleElementIndex']) - 1, post['questionIndex'])
					else:
						objBack = getObject(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'], int(post['questionIndex']) - 1)
					objBack.index += 1
					objBack.save()
					objForward.index -= 1
					objForward.save()
					success = "Moved forward"
				return JsonResponse({'success': success})

			elif call == "move_back":
				objBack = getObject(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'],post['questionIndex'])
				if len(getSubsequentObjects(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'],post['questionIndex'])) == 0:
					success = "Already last - cannot move back"
				else:	
					if post['object_type'] == "module":
						objForward = getObject(post['object_type'],course, int(post['moduleIndex']) + 1 ,post['moduleElementIndex'],post['questionIndex'])
					elif post['object_type'] == "moduleElement":
						objForward = getObject(post['object_type'],course, post['moduleIndex'],int(post['moduleElementIndex']) + 1, post['questionIndex'])
					else:
						objForward = getObject(post['object_type'],course, post['moduleIndex'],post['moduleElementIndex'], int(post['questionIndex']) + 1)
					objBack.index += 1
					objBack.save()
					objForward.index -= 1
					objForward.save()
					success = "Moved back"
					
				return JsonResponse({'success': success})	

# manage course editing
@login_required(login_url = '/lessons/login/')
def analyze(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	courses = user_profile.courses_managed.all()

	if request.method == 'GET':
		return render(request, 'lessons/analyze.html', {
			'user':user, 
			'courses': courses,
		})

	else: 
		course = Course.objects.get(pk = request.POST['coursepk'])
		enrollees = UserProfile.objects.filter(courses_enrolled = course)
		total_enrolled = enrollees.count()
		enrollee_set = []
		for enrollee in enrollees:
			temp = {}
			temp['name'] = enrollee.user.first_name + " " + enrollee.user.last_name
			temp['completion_data'] = []
			
			completions = Completion.objects.filter(
				user = enrollee,
				name = Module.objects.filter(course = course)
			)
			for completion in completions:
				tc = {}
				tc['name'] = completion.name.name # "name.name" because completion's FK is module, then reference module name
				tc['score'] = completion.score
				tc['date'] = completion.date
				temp['completion_data'].append(tc)

			enrollee_set.append(temp)

		module_count = Module.objects.filter(course = course).count()
		module_completion_set = []
		for i in range(0,module_count):
			temp = {}
			module = Module.objects.get(course = course, index = i + 1)
			temp['name'] = module.name
			completions = Completion.objects.filter(name = module)
			temp['count'] = completions.count()
			temp ['percent_of_total'] = round(float(temp['count'] / total_enrolled) * 100, 0)
			points = 0
			for  completion in completions:
				points += completion.score

			temp['avg_score'] = round(float(points / temp['count']), 0)
			module_completion_set.append(temp)

		return JsonResponse({'module_completion_set': module_completion_set, 
			'enrollees': enrollee_set, 
			'total_enrolled': total_enrolled,
		})
			

""" 
TO BE DELETED
def list(request):
	# Handle file upload
	if request.method == 'POST':
		form = DocumentForm(request.POST, request.FILES)
		if form.is_valid():
			newdoc = Document(docfile=request.FILES['docfile'])
			newdoc.save()		
			# Redirect to the document list after POST
			return HttpResponseRedirect(reverse('lessons.views.list'))
		else:
			form = DocumentForm()  # A empty, unbound form

	# Load documents for the list page
	documents = Document.objects.all()

	# Render list page with the documents and the form
	return render_to_response(
		'lessons/list.html',
		{'documents': documents, 'form': form},
		context_instance=RequestContext(request)
	)
"""

@login_required(login_url = '/lessons/login/')
def add_media(request):
	user = request.user
	user_profile = get_object_or_404(UserProfile, user_id = user.id)
	courses = user_profile.courses_managed.all()
	courseLogoForm = CourseLogoForm()
	courseLogoForm.fields['course'].queryset = user_profile.courses_managed.all()
	course_success = ""

	modules = Module.objects.filter(course = courses)
	documentForm = DocumentForm()
	documentForm.fields['moduleElement'].queryset = ModuleElement.objects.filter(module = modules)
	module_element_success = ""
	
	if request.method == 'POST':
		if request.POST['post_type'] == "course": 
			if request.POST['course'] != "":
				course = Course.objects.get(pk = request.POST['course'])
				CourseLogo.objects.filter(course = course).delete()

				courseLogo = CourseLogo(
					course = course,
					docfile = request.FILES['docfile']
				)
				courseLogo.save()
				course_success = "Logo saved"
			else:
				course_success = "Not saved - please choose a course"
		#elif request.POST['post_type'] == "module_element": 
		else:
			if request.POST['moduleElement'] != "":
				if request.POST['action'] == "add":
					document = Document(
						moduleElement = ModuleElement.objects.get(pk = request.POST['moduleElement']),
						docfile = request.FILES['docfile']
					)
					document.save()
					module_element_success = "Document saved"
				else: 
					moduleElement = ModuleElement.objects.get(pk = request.POST['moduleElement'])
					Document.objects.filter(moduleElement = moduleElement).delete()
					module_element_success = "Documents deleted"
			else:
				module_element_success = "Not saved - please choose a module element"

		
	return render(request, 'lessons/add_media.html', {
		'user':user, 
		'courses': courses,
		'courseLogoForm':courseLogoForm,
		'documentForm':documentForm,
		'course_success': course_success,
		'module_element_success': module_element_success
	})