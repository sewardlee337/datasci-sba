from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from api_server.models import SbaRegionLevel


@require_GET
def regions(request):
    """API endpoint returning list of regions"""
    result = {
        'status': 'success',
        # use comprehension to convert from queryset to list of dicts, otherwise json lib can't serialize it
        'data': [x for x in SbaRegionLevel.objects.values()],
    }
    return JsonResponse(result)
