from django.contrib import messages
from django.contrib.auth import logout, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _
from django.views.decorators.http import require_POST
from guardian.shortcuts import assign_perm

from imagetagger.images.forms import ImageSetCreationForm
from imagetagger.images.models import ImageSet
from imagetagger.users.forms import RegistrationForm, TeamCreationForm
from .models import Team


@login_required
def create_team(request):
    form = TeamCreationForm()
    if request.method == 'POST':
        form = TeamCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                form.instance.members = Group.objects.create(
                    name='{}_members'.format(form.instance.name))
                form.instance.admins = Group.objects.create(
                    name='{}_admins'.format(form.instance.name))
                form.instance.members.user_set.add(request.user)
                form.instance.admins.user_set.add(request.user)
                form.instance.save()
                assign_perm('user_management', form.instance.admins, form.instance)
                assign_perm('create_set', form.instance.members, form.instance)
            return redirect(reverse('users:team', args=(form.instance.id,)))
    return render(request, 'users/create_team.html', {
        'form': form,
    })


@login_required
@require_POST
def revoke_team_admin(request, team_id, user_id):
    user = get_object_or_404(User, id=user_id)
    team = get_object_or_404(Team, id=team_id)

    if user == request.user:
        messages.warning(
            request, _('You can not revoke your own admin privileges.').format(
                team.name))
        return redirect(reverse('users:team', args=(team.id,)))

    if request.user.has_perm('user_management', team):
        team.admins.user_set.remove(user)
    else:
        messages.warning(
            request,
            _('You do not have permission to revoke this users admin '
              'privileges in the team {}.').format(team.name))

    return redirect(reverse('users:team', args=(team.id,)))


@login_required
@require_POST
def grant_team_admin(request, team_id, user_id):
    user = get_object_or_404(User, id=user_id)
    team = get_object_or_404(Team, id=team_id)

    if not team.members.user_set.filter(pk=request.user.pk).exists():
        messages.warning(request, _('You are no member of the team {}.').format(
            team.name))
        return redirect(reverse('users:explore_team'))

    # Allow granting of admin privileges any team member if there is no admin
    if request.user.has_perm('user_management', team) or not team.admins.user_set.exists():
        team.admins.user_set.add(user)
    else:
        messages.warning(
            request,
            _('You do not have permission to grant this user admin '
              'privileges in the team {}.').format(team.name))
    return redirect(reverse('users:team', args=(team.id,)))


@login_required
def explore_team(request):
    teams = Team.objects.all()
    if request.method == 'POST':
        teams = teams.filter(name__icontains=request.POST['searchquery'])

    return render(request, 'base/explore.html', {
        'mode': 'team',
        'teams': teams,
    })


@login_required
def explore_user(request):
    users = User.objects.all()
    if request.method == 'POST':
        users = users.filter(username__contains=request.POST['searchquery'])

    return render(request, 'base/explore.html', {
        'mode': 'user',
        'users': users,
    })


@login_required
def leave_team(request, team_id, user_id=None):
    team = get_object_or_404(Team, id=team_id)
    user = request.user
    warning = _('You are not in the team.')

    if user_id:
        user = get_object_or_404(User, id=user_id)
        warning = _('The user is not in the team.')

        if not request.user.has_perm('user_management', team):
            messages.warning(
                request,
                _('You do not have the permission to kick other users from this team.'))
            return redirect(reverse('users:team', args=(team.id,)))

    if not team.members.user_set.filter(pk=user.pk).exists():
        messages.warning(request, warning)
        return redirect(reverse('users:team', args=(team.id,)))

    if request.method == 'POST':
        team.members.user_set.remove(user)
        team.admins.user_set.remove(user)
        if user == request.user:
            return redirect(reverse('users:explore_team'))
        return redirect(reverse('users:team', args=(team.id,)))

    return render(request, 'users/leave_team.html', {
        'user': user,
        'team': team,
    })


def logout_view(request):
    logout(request)
    return redirect(reverse('images:index'))


@login_required
def view_team(request, team_id):
    team = get_object_or_404(Team, id=team_id)
    if request.method == 'POST' and request.user.has_perm('user_management', team):
        user_to_add = User.objects.filter(username=request.POST['username'])[0]
        if user_to_add:
            team.members.user_set.add(user_to_add)

    members = team.members.user_set.all()
    is_member = request.user in members
    admins = team.admins.user_set.all()
    is_admin = request.user in admins  # The request.user is an admin of the team
    no_admin = len(admins) == 0  # Team has no admin, so every member can claim the Position
    imagesets = ImageSet.objects.filter(team=team)
    pub_imagesets = imagesets.filter(public=True).order_by('id')
    priv_imagesets = imagesets.filter(public=False).order_by('id')
    return render(request, 'users/view_team.html', {
        'team': team,
        'memberset': members,
        'is_member': is_member,
        'is_admin': is_admin,
        'no_admin': no_admin,
        'admins': admins,
        'pub_imagesets': pub_imagesets,
        'priv_imagesets': priv_imagesets,
        'imageset_creation_form': ImageSetCreationForm(),
    })


@login_required
def user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    userteams = Team.objects.filter(members__in=user.groups.all())

    # TODO: count the points
    points = 0

    return render(request, 'users/view_user.html', {
        'user': user,
        'userteams': userteams,
        'userpoints': points,
    })


def login_view(request):
    if request.user.is_authenticated:
        return redirect(reverse('images:index'))

    authentication_form = AuthenticationForm()
    registration_form = RegistrationForm()
    registration_success = False

    if request.method == 'POST':
        if request.POST.get('login') is not None:
            authentication_form = AuthenticationForm(request=request, data=request.POST)
            if authentication_form.is_valid():
                login(request, authentication_form.user_cache)
                return redirect(reverse('images:index'))
        else:
            # registration
            registration_form = RegistrationForm(request.POST)

            if registration_form.is_valid():
                if User.objects.filter(username=registration_form.instance.username).exists():
                    registration_form.add_error(
                        'username',
                        _('A user with that username or email address exists.'))
                else:
                    User.objects.create_user(**registration_form.cleaned_data)
                    registration_success = True
                    messages.success(request, _('Your account was successfully created.'))

    return render(request, 'users/login.html', {
        'authentication_form': authentication_form,
        'registration_form': registration_form,
        'registration_success': registration_success,
    })
