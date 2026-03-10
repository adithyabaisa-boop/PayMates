from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.landingview, name="landing"),
    path("login/", views.loginview, name="login"),
    path("signup/", views.signupview, name="signup"),
    path("logout/", views.logoutview, name="logout"),

    path("account/", views.profileview, name="profile"),
    path("dashboard/", views.dashboard, name="dashboard"),

    # Groups
    path("group/create/", views.creategroup, name="creategroup"),
    path("group/join/", views.joingroup, name="joingroup"),
    path("group/<int:groupid>/", views.groupdetail, name="groupdetail"),
    path("group/<int:groupid>/info/", views.groupinfo, name="groupinfo"),
    path("group/<int:groupid>/add-expense/", views.addexpense, name="addexpense"),
    path("group/<int:groupid>/split/", views.splitdetails, name="splitdetails"),
    path("group/<int:groupid>/exit/", views.exitgroup, name="exitgroup"),
    path("group/<int:groupid>/delete/", views.deletegroup, name="deletegroup"),
    path("group/<int:groupid>/invite/", views.sendinvite, name="sendinvite"),

    # NEW: update group photo (admin only)
    path("group/<int:groupid>/photo/", views.update_group_photo, name="update_group_photo"),

    path("group/<int:groupid>/leave-requests/<int:requestid>/approve/", views.approveleave, name="approveleave"),
    path("group/<int:groupid>/leave-requests/<int:requestid>/reject/", views.rejectleave, name="rejectleave"),
    path("group/<int:groupid>/settlement/<int:settlementid>/settle/", views.marksettlementsettled, name="marksettlementsettled"),
    path("group/<int:groupid>/photo/update/", views.updategroupphoto, name="updategroupphoto"),
    path("group/<int:groupid>/photo/remove/", views.removegroupphoto, name="removegroupphoto"),

    # Expenses
    path("group/<int:groupid>/expense/<int:expenseid>/delete/", views.deleteexpense, name="deleteexpense"),

    # Notifications
    path("notifications/", views.notificationsview, name="notifications"),
    path("notifications/invite/<int:notificationid>/accept/", views.acceptinvite, name="acceptinvite"),
    path("notifications/invite/<int:notificationid>/reject/", views.rejectinvite, name="rejectinvite"),

    # Chats
    path("chats/", views.chatslist, name="chatslist"),
    path("chats/group/<int:groupid>/", views.chatroom, name="chatroom"),

    path("chats/private/start/<int:userid>/", views.startprivatechat, name="startprivatechat"),
    path("chats/private/<int:roomid>/", views.privatechatroom, name="privatechatroom"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
