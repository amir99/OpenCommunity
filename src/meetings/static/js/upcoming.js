"use strict";

$(function() {

    function reorderIssues(li, val, callback) {
        $('#agenda-container').addClass('loading');
        var l = $('#agenda li').map(function() {
            return $(this).data('issue');
        }).get();
        $.post('', {
            issues : l,
        }, function(data) {
            $('#agenda-container').removeClass('loading');
        }).fail(function() {
            alert('Server Error. Please refresh your browser and try again');
        });
    }

    function toggleIssue(li, val, callback) {
        $.post('', {
            issue : li.data('issue'),
            set : val
        }, function(data) {
            li.removeClass('loading');
        }).fail(function() {
            alert('Server Error. Please refresh your browser and try again');
        });
    }

    $('#agenda').on('click', '.addremove', function() {
        $(this).find('.ui-icon-minus').removeClass('ui-icon-minus').addClass('ui-icon-plus');
        var el = $(this).parent();
        el.addClass('loading');
        $("#available").append(el);
        toggleIssue(el, 1);
    }).sortable({
        'containment': $('#agenda').parent().parent(),
        'opacity': 0.6,
        cursorAt: { top: 25 },
        handle: ".grab",
        update: function(event, ui) {
            reorderIssues();
        }
    }).removeClass('ui-corner-all').filter('li').removeClass('ui-corner-bottom');

    $('#available').on('click', '.addremove', function() {
        $(this).find('.ui-icon-plus').removeClass('ui-icon-plus').addClass('ui-icon-minus');
        var el = $(this).parent();
        el.addClass('loading');
        $("#agenda").append(el);
        toggleIssue(el, 0);
    });


});
