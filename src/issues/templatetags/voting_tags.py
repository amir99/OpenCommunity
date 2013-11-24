from django import template
from django.shortcuts import get_object_or_404
from django.core.urlresolvers import reverse
from issues.models import Proposal, ProposalVote, VoteResult
from meetings.models import Meeting

register = template.Library()

@register.filter
def voted_on(u, proposal_id):
    voted = ProposalVote.objects.filter(
                            proposal_id=proposal_id,
                            user_id=u.id).exists()
    return voted

    
@register.filter
def vote_percentage(proposal):
    if proposal.votes_pro is None:
        return 'undefined'
    votes = proposal.votes_pro + proposal.votes_con
    print votes ,proposal.community_members
    percentage = (float(votes) / float(proposal.community_members)) * 100.0
    return round(percentage, 1)

    
@register.simple_tag(takes_context=True)
def user_votes_on_issue(context):
    issue = context['i']
    user_id = context['user'].id
    proposals = Proposal.objects.open().filter(issue_id=issue.id)
    votes_cnt = ProposalVote.objects.filter(
        proposal__in=proposals,
        user_id=user_id).count()
    # return "<span class='votes_count'>{0}</span>/<span class='proposal_count'>{1}</span>".format(votes_cnt, proposals.count())
    return "{0}/{1}".format(votes_cnt, proposals.count())

        
@register.filter
def prev_straw_results_link(proposal, meeting_id=None):
    link_args = {
        'community_id': proposal.issue.community_id,
        'pk': proposal.id,
        }
    url = reverse('vote_results_panel', kwargs=link_args)
    if meeting_id:
        cur_meeting = get_object_or_404(Meeting, id=meeting_id)
        prev_res = VoteResult.objects.filter(proposal=proposal,
                            meeting__held_at__lt=cur_meeting.held_at) \
                            .order_by('-meeting__held_at')
                        
        if prev_res.count():
            return '{0}?meeting_id={1}&dir=prev'.format( \
                     url, prev_res[0].meeting_id)
    else:
        # get meeting from last VoteResult object
        try:
            result = VoteResult.objects.filter(proposal=proposal) \
                                       .latest('meeting__held_at')
            return '{0}?meeting_id={1}&dir=prev'.format( \
                     url, result.meeting.id)
        except VoteResult.DoesNotExist:
            pass

    return ''

    
@register.filter
def next_straw_results_link(proposal, meeting_id):   
    link_args = {
        'community_id': proposal.issue.community_id,
        'pk': proposal.id,
        }
    url = reverse('vote_results_panel', kwargs=link_args)
    if meeting_id:
        cur_meeting = get_object_or_404(Meeting, id=meeting_id)
        next_res = VoteResult.objects.filter(proposal=proposal,
                            meeting__held_at__gt=cur_meeting.held_at) \
                            .order_by('meeting__held_at')
        if next_res.count():
            return '{0}?meeting_id={1}&dir=next'.format( \
                     url, next_res[0].meeting_id)
        elif proposal.can_show_straw_votes:
            return '{0}?meeting_id=&dir=next'.format(url)
            
    else:
        pass
    return ''
   
        
@register.filter    
def subtract(value, arg):
    if arg is None:
        return value
    return value - arg