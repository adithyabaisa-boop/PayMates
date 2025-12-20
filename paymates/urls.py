from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

from core.views import (
    signup_view, login_view, logout_view,
    dashboard, create_group, join_group,
    group_detail, add_expense,
    split_bill, settle_up
)

def home(request):
    return redirect('/login/')

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),

    path('signup/', signup_view),
    path('login/', login_view),
    path('logout/', logout_view),

    path('dashboard/', dashboard),

    path('group/create/', create_group),
    path('group/join/', join_group),
    path('group/<int:group_id>/', group_detail),
    path('group/<int:group_id>/add-expense/', add_expense),
    path('group/<int:group_id>/split/', split_bill),
    path('group/<int:group_id>/settle/<int:from_user_id>/<int:to_user_id>/', settle_up),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
