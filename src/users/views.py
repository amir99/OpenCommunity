import time
import json

from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.core.urlresolvers import reverse
from django.db.utils import IntegrityError
from django.http.response import HttpResponse, HttpResponseForbidden,\
    HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.utils.translation import ugettext_lazy as _
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic.detail import DetailView
from django.views.generic.edit import DeleteView
from django.views.generic.list import BaseListView, ListView
from django.views.generic import FormView
from django.template import RequestContext

from ocd.base_views import CommunityMixin
from users import models
from users.forms import InvitationForm, QuickSignupForm, ImportInvitationsForm
from users.models import Invitation, OCUser, Membership

class MembershipMixin(CommunityMixin):

    model = models.Membership

    def get_queryset(self):
        return models.Membership.objects.filter(community=self.community)


    def validate_invitation(self, email):
        # somewhat of a privacy problem next line. should probably fail silently
        if Membership.objects.filter(community=self.community,
                                 user__email=email).exists():
            return HttpResponseBadRequest(
                         _("This user already a member of this community."))

        if Invitation.objects.filter(community=self.community,
                                 email=email).exists():
            return HttpResponseBadRequest(
                         _("This user is already invited to this community."))
        return None

class MembershipList(MembershipMixin, ListView):

    required_permission = 'community.invite_member'

    def get_context_data(self, **kwargs):
        d = super(MembershipList, self).get_context_data(**kwargs)

        d['invites'] = Invitation.objects.filter(community=self.community)
        d['form'] = InvitationForm(initial={'message':
                                            Invitation.DEFAULT_MESSAGE %
                                            self.community.get_board_name()})

        return d

    def post(self, request, *args, **kwargs):

        form = InvitationForm(request.POST)

        if not form.is_valid():
            return HttpResponseBadRequest(
                                 _("Form error. Please supply a valid email."))

        v_err = self.validate_invitation(form.instance.email)
        if v_err:
            return v_err

        form.instance.community = self.community
        form.instance.created_by = request.user

        i = form.save()
        i.send(sender=request.user, recipient_name=form.cleaned_data['name'])

        return render(request, 'users/_invitation.html', {'object': i})


class DeleteInvitationView(CommunityMixin, DeleteView):

    required_permission = 'community.invite_member'

    model = models.Invitation

    def get_queryset(self):
        return self.model.objects.filter(community=self.community)

    def get(self, request, *args, **kwargs):
        return HttpResponse("?")

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        return HttpResponse("OK")


class AcceptInvitationView(DetailView):

    slug_field = 'code'
    slug_url_kwarg = 'code'
    model = models.Invitation

    form = None

    def get_form(self):
        return QuickSignupForm(self.request.POST if
                                    self.request.method == "POST" else None)

    def get_context_data(self, **kwargs):
        d = super(AcceptInvitationView, self).get_context_data(**kwargs)
        d['user_exists'] = OCUser.objects.filter(email=self.get_object().email
                                                 ).exists()
        d['path'] = self.request.path
        d['login_path'] = reverse('login') + "?next=" + self.request.path
        d['form'] = self.form if self.form else self.get_form()
        return d

    def post(self, request, *args, **kwargs):

        i = self.get_object()

        def create_membership(user):
            try:
                m = Membership.objects.get(user=user, community=i.community)
            except Membership.DoesNotExist:
                m = Membership.objects.create(user=user, community=i.community,
                                  default_group_name=i.default_group_name,
                                      invited_by=i.created_by)
            i.delete()
            return m

        if request.user.is_authenticated():
            if 'join' in request.POST:
                m = create_membership(request.user)
                return redirect(m.community.get_absolute_url())

        else:
            if 'signup' in request.POST:
                self.form = self.get_form()
                if self.form.is_valid():
                    # Quickly create a user :-)
                    self.form.instance.email = i.email
                    u = self.form.save()
                    m = create_membership(u)
                    # TODO Send email with details
                    user = authenticate(email=self.form.instance.email,
                                password=self.form.cleaned_data['password1'])
                    login(request, user)
                    return redirect(m.community.get_absolute_url())

        messages.warning(request,
                  _("Oops. Something went wrong. Please try again."))
        return self.get(request, *args, **kwargs)


        
class AutocompleteMemberName(MembershipMixin, ListView):

    required_permission = 'issues.editopen_issue'
    
    def get_queryset(self):
        members = super(AutocompleteMemberName, self).get_queryset()
        q = self.request.GET.get('q', '')
        if q:
            members = members.filter(
                            user__is_active=True,
                            user__display_name__istartswith=q)
        else:
            members = members.filter(user__is_active=True)
            if members.count() > 75:
                return None

        return members

        
    def get(self, request, *args, **kwargs):
        
        def _cmp_func(a, b):
            res = cmp(a['board'], b['board']) * -1
            if res == 0:
                return cmp(a['value'], b['value'])
            else:
                return res

                
        members = self.get_queryset()
        if not members:
            return HttpResponse(json.dumps({}))
        else:
            
            members = list(members.values('user__display_name', 'user__id',
                                            'default_group_name'))
            for m in members:
                m['tokens'] = [m['user__display_name'],]
                m['value'] = m['user__display_name']
                m['board'] = m['default_group_name'] != 'member'
                 
            members.sort(_cmp_func)
            context = self.get_context_data(object_list=members)
            return HttpResponse(json.dumps(members), {'content_type': 'application/json'})

        
class MemberProfile(MembershipMixin, DetailView):
    
    model = models.Membership
    template_name = "users/member_profile.html"
    
    def get_context_data(self, **kwargs):
       
        d = super(MemberProfile, self).get_context_data(**kwargs)
        d['form'] = ""
        return d


class ImportInvitationsView(MembershipMixin, FormView):
    form_class = ImportInvitationsForm
    template_name = 'users/import_invitations.html'        
       
    def get(self, request, *args, **kwargs):
        return self.render_to_response(self.get_context_data(import_invitation_form=self.get_form(self.form_class)))


    def form_valid(self, form):
        msg = 'def message'
        def_enc = 'windows-1255'
        uploaded = form.cleaned_data['csv_file'] 
        sent = 0
        for chunk in uploaded.chunks():
            rows = chunk.split('\n')
            for i, row in enumerate(rows):
                words = row.split(',')
                # print ' -- ', words[0], ' -- '
                if i == 0:
                    msg = words[0]
                    try:
                        msg = msg.decode(def_enc)
                    except UnicodeDecodeError:
                        def_enc = 'utf-8'
                        msg = msg.decode(def_enc)
                elif len(words) > 1:
                    # print ' - '.join(row.split(','))
                    name = words[0].decode(def_enc)
                    email = words[1].decode(def_enc)
                    role = words[2].strip().decode(def_enc)
                    v_err = self.validate_invitation(email)
                    if v_err:
                        continue
                    invitation = Invitation.objects.create( 
                        community=self.community,
                        email=email,
                        created_by=self.request.user,
                        default_group_name=role,
                        message=msg) 
                    try:
                        invitation.send(sender=self.request.user, recipient_name=name)
                        # reduce email sending rate
                        time.sleep(4)
                        sent += 1
                    except:
                      pass

        messages.success(self.request, _('%d Invitations sent') % (sent,))           
        return redirect(reverse('members', kwargs={'community_id': self.community.id}))


    @method_decorator(permission_required('is_superuser'))
    def dispatch(self, *args, **kwargs):
        return super(ImportInvitationsView, self).dispatch(*args, **kwargs)
