"""Views for Package Monitor."""

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from app_utils.views import link_html, yesnonone_str

from . import __title__
from .app_settings import (
    PACKAGE_MONITOR_INCLUDE_PACKAGES,
    PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
)
from .models import Distribution

PACKAGE_LIST_FILTER_PARAM = "filter"


@login_required
@permission_required("package_monitor.basic_access")
def index(request):
    """Main view."""
    obj = Distribution.objects.first()
    updated_at = obj.updated_at if obj else None
    distributions_qs = Distribution.objects.filter_visible()
    my_filter = request.GET.get(PACKAGE_LIST_FILTER_PARAM)
    if not my_filter:
        app_count = Distribution.objects.filter_visible().outdated_count()
        my_filter = "outdated" if app_count and app_count > 0 else "current"
    outdated_install_command = (
        Distribution.objects.filter_visible()
        .filter(is_outdated=True)
        .order_by("name")
        .build_install_command()
    )
    page_title = {
        "all": "All Packages",
        "current": "Current",
        "outdated": "Update Available",
        "unknown": "No Information",
    }
    context = {
        "app_title": __title__,
        "updated_at": updated_at,
        "filter": my_filter,
        "page_title": page_title[my_filter],
        "all_count": distributions_qs.count(),
        "current_count": distributions_qs.filter(is_outdated=False).count(),
        "outdated_count": distributions_qs.outdated_count(),
        "unknown_count": distributions_qs.filter(is_outdated__isnull=True).count(),
        "include_packages": PACKAGE_MONITOR_INCLUDE_PACKAGES,
        "show_all_packages": PACKAGE_MONITOR_SHOW_ALL_PACKAGES,
        "outdated_install_command": outdated_install_command,
    }
    return render(request, "package_monitor/index.html", context)


@login_required
@permission_required("package_monitor.basic_access")
def package_list_data(request) -> JsonResponse:
    """Return the packages as list in JSON.
    Specify different subsets with the "filter" GET parameter
    """
    my_filter = request.GET.get(PACKAGE_LIST_FILTER_PARAM, "")
    distributions_qs = Distribution.objects.filter_visible()
    if my_filter == "outdated":
        distributions_qs = distributions_qs.filter(is_outdated=True)
    elif my_filter == "current":
        distributions_qs = distributions_qs.filter(is_outdated=False)
    elif my_filter == "unknown":
        distributions_qs = distributions_qs.filter(is_outdated__isnull=True)

    data = []
    for dist in distributions_qs.order_by("name"):
        dist: Distribution
        name_link_html = (
            link_html(dist.website_url, dist.name) if dist.website_url else dist.name
        )
        if dist.is_outdated:
            name_link_html += (
                '&nbsp;<i class="fas fa-exclamation-circle" '
                f'title="{_("Update available")}"></i>'
            )

        if dist.apps:
            _lst = list(dist.apps)
            apps_html = "<br>".join(_lst) if _lst else "-"
        else:
            apps_html = ""

        if dist.used_by:
            used_by_sorted = sorted(dist.used_by, key=lambda k: k["name"])
            used_by_html = "<br>".join(
                [
                    format_html(
                        '<span title="{}" class="text-nowrap;">{}</span>',
                        (
                            ", ".join(row["requirements"])
                            if row["requirements"]
                            else "ANY"
                        ),
                        (
                            link_html(row["homepage_url"], row["name"])
                            if row["homepage_url"]
                            else row["name"]
                        ),
                    )
                    for row in used_by_sorted
                ]
            )
        else:
            used_by_html = ""

        if not dist.latest_version:
            latest_html = "?"
        else:
            command = f"pip install {dist.pip_install_version}"
            latest_html = (
                f'<span class="copy_to_clipboard" '
                f'title="{command}"'
                f' data-clipboard-text="{command}">'
                f"{dist.latest_version}"
                '&nbsp;&nbsp;<i class="far fa-copy"></i></span>'
            )

        description = dist.description
        if dist.is_editable:
            description += f" [{_('EDITABLE')}]"
        data.append(
            {
                "name": dist.name,
                "name_link": name_link_html,
                "apps": apps_html,
                "used_by": used_by_html,
                "current": dist.installed_version,
                "latest": latest_html,
                "is_outdated": dist.is_outdated,
                "is_outdated_str": yesnonone_str(dist.is_outdated),
                "description": description,
            }
        )

    return JsonResponse(data, safe=False)


@login_required
@permission_required("package_monitor.basic_access")
def refresh_distributions(request):
    """Ajax view for refreshing all distributions."""
    Distribution.objects.update_all()
    return HttpResponse("ok")
