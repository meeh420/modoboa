# coding: utf-8
import re
from django.shortcuts import render
from django.utils.translation import ugettext as _
from django.contrib.auth.decorators import (
    login_required, user_passes_test, permission_required
)
from modoboa.lib import events
from modoboa.lib.exceptions import BadRequest, PermDeniedException, NotFound
from modoboa.lib.webutils import (
    _render_to_string, render_to_json_response
)
from modoboa.extensions.admin.models import (
    Domain
)
from modoboa.extensions.stats.grapher import periods, str2Time, Grapher


@login_required
@permission_required("admin.view_mailboxes")
def index(request):
    """
    FIXME: how to select a default graph set ?
    """
    deflocation = "graphs/?gset=mailtraffic"
    if not request.user.is_superuser:
        if not Domain.objects.get_for_admin(request.user).count():
            raise NotFound(_("No statistics available"))

    period = request.GET.get("period", "day")
    graph_sets = events.raiseDictEvent('GetGraphSets')
    return render(request, 'stats/index.html', {
        "periods": periods,
        "period": period,
        "selection": "stats",
        "deflocation": deflocation,
        "graph_sets": graph_sets
    })


@login_required
@user_passes_test(lambda u: u.group != "SimpleUsers")
def graphs(request):
    gset = request.GET.get("gset", None)
    gsets = events.raiseDictEvent("GetGraphSets")
    if not gset in gsets:
        raise NotFound(_("Unknown graphic set"))
    searchq = request.GET.get("searchquery", None)
    period = request.GET.get("period", "day")
    tplvars = dict(graphs=[], period=period)
    if searchq in [None, "global"]:
        if not request.user.is_superuser:
            if not Domain.objects.get_for_admin(request.user).count():
                return render_to_json_response({})
            tplvars.update(
                domain=Domain.objects.get_for_admin(request.user)[0].name
            )
        else:
            tplvars.update(domain="global")
    else:
        domain = Domain.objects.filter(name__contains=searchq)
        if domain.count() != 1:
            return render_to_json_response({})
        if not request.user.can_access(domain[0]):
            raise PermDeniedException
        tplvars.update(domain=domain[0].name)

    if period == "custom":
        if not "start" in request.GET or not "end" in request.GET:
            raise BadRequest(_("Bad custom period"))
        start = request.GET["start"]
        end = request.GET["end"]
        G = Grapher()
        expr = re.compile(r'[:\- ]')
        period_name = "%s_%s" % (expr.sub('', start), expr.sub('', end))
        for tpl in gsets[gset].get_graphs():
            tplvars['graphs'].append(tpl.display_name)
            G.process(
                tplvars["domain"], period_name, str2Time(*expr.split(start)),
                str2Time(*expr.split(end)), tpl
            )
        tplvars["period_name"] = period_name
        tplvars["start"] = start
        tplvars["end"] = end
    else:
        tplvars['graphs'] = gsets[gset].get_graph_names()

    return render_to_json_response({
        'content': _render_to_string(request, "stats/graphs.html", tplvars)
    })
