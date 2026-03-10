from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    Group, Expense, Profile, Notification, LeaveRequest,
    GroupChatMessage, ChatRoom, PrivateChatMessage, Settlement
)


def landingview(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "auth/landing.html")


def loginview(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error = None
    if request.method == "POST":
        email_or_username = (request.POST.get("email") or "").strip()
        password = request.POST.get("password") or ""

        username = email_or_username
        try:
            u = User.objects.get(email=email_or_username)
            username = u.username
        except User.DoesNotExist:
            pass

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get("next") or "dashboard"
            return redirect(next_url)
        error = "Invalid username/email or password."

    return render(request, "auth/login.html", {"error": error})


def signupview(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    error = None
    if request.method == "POST":
        email = (request.POST.get("email") or "").strip()
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        if not email:
            error = "Email is required."
        elif not username:
            error = "Username is required."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif User.objects.filter(email=email).exists():
            error = "Email already in use."
        elif User.objects.filter(username=username).exists():
            error = "Username already in use."
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            Profile.objects.get_or_create(user=user)
            return redirect("login")

    return render(request, "auth/signup.html", {"error": error})


def logoutview(request):
    logout(request)
    return redirect("landing")


@login_required
def profileview(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    saved = False

    if request.method == "POST":
        profile.fullname = (request.POST.get("fullname") or "").strip()
        dob = request.POST.get("dateofbirth") or None
        profile.dateofbirth = dob or None
        profile.email = (request.POST.get("email") or "").strip()
        profile.mobile = (request.POST.get("mobile") or "").strip()
        if "image" in request.FILES:
            profile.image = request.FILES["image"]
        profile.save()
        saved = True

    return render(request, "auth/profile.html", {"profile": profile, "saved": saved})


@login_required
def dashboard(request):
    groups = Group.objects.filter(members=request.user).order_by("name")
    return render(request, "auth/dashboard.html", {"groups": groups})


# ------------------- GROUPS -------------------

@login_required
def creategroup(request):
    error = None
    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        image = request.FILES.get("image")

        if not name:
            error = "Group name is required."
        else:
            group = Group.objects.create(name=name, createdby=request.user, image=image)
            group.members.add(request.user)
            return redirect("groupdetail", groupid=group.id)

    return render(request, "group/create_group.html", {"error": error})


@login_required
def update_group_photo(request, groupid):
    group = get_object_or_404(Group, id=groupid)

    if request.user not in group.members.all():
        return redirect("dashboard")
    if request.user != group.createdby:
        messages.error(request, "Only the group admin can update the group photo.")
        return redirect("groupinfo", groupid=group.id)

    if request.method == "POST":
        img = request.FILES.get("image")
        if not img:
            messages.error(request, "Please choose an image.")
            return redirect("groupinfo", groupid=group.id)

        group.image = img
        group.save()
        messages.success(request, "Group photo updated.")
        return redirect("groupinfo", groupid=group.id)

    return redirect("groupinfo", groupid=group.id)


@login_required
def joingroup(request):
    error = None
    if request.method == "POST":
        code = (request.POST.get("groupcode") or "").strip()
        try:
            group = Group.objects.get(groupcode=code)

            if request.user in group.members.all():
                return redirect("groupdetail", groupid=group.id)

            group.members.add(request.user)

            for member in group.members.exclude(id=request.user.id):
                Notification.objects.create(
                    user=member,
                    group=group,
                    fromuser=request.user,
                    message=f"{request.user.username} joined the group {group.name}.",
                    type="joined",
                )
            return redirect("groupdetail", groupid=group.id)

        except Group.DoesNotExist:
            error = "Group not found with that code."

    return render(request, "group/join_group.html", {"error": error})


@login_required
def groupdetail(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user not in group.members.all():
        return redirect("dashboard")

    expenses = Expense.objects.filter(group=group, isdeleted=False).order_by("-createdat")
    return render(request, "group/group_detail.html", {"group": group, "expenses": expenses})


@login_required
def groupinfo(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user not in group.members.all():
        return redirect("dashboard")

    members = group.members.all().order_by("username")
    membersdata = []
    for m in members:
        p = Profile.objects.filter(user=m).first()
        membersdata.append({
            "id": m.id,
            "username": m.username,
            "email": (p.email if p and p.email else (m.email or "Not provided")),
            "mobile": (p.mobile if p and p.mobile else "Not provided"),
            "imageurl": (p.image.url if p and p.image else ""),
            "isme": (m.id == request.user.id),
        })

    leaverequests = None
    if request.user == group.createdby:
        leaverequests = LeaveRequest.objects.filter(group=group, status="pending").select_related("user")

    myleaverequest = LeaveRequest.objects.filter(group=group, user=request.user).first()

    return render(request, "group/group_info.html", {
        "group": group,
        "membersdata": membersdata,
        "leaverequests": leaverequests,
        "myleaverequest": myleaverequest,
    })


@login_required
def addexpense(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user not in group.members.all():
        return redirect("dashboard")

    error = None
    if request.method == "POST":
        description = (request.POST.get("description") or "").strip()
        amount = (request.POST.get("amount") or "0").strip()
        receipt = request.FILES.get("receipt")

        if not description:
            error = "Description is required."
        else:
            Expense.objects.create(
                group=group, description=description, amount=amount,
                paidby=request.user, receipt=receipt
            )
            return redirect("groupdetail", groupid=group.id)

    return render(request, "group/add_expense.html", {"group": group, "error": error})


@login_required
def exitgroup(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.method != "POST":
        return redirect("groupinfo", groupid=group.id)

    if request.user not in group.members.all():
        return redirect("dashboard")

    if request.user == group.createdby:
        return redirect("groupinfo", groupid=group.id)

    lr = LeaveRequest.objects.filter(group=group, user=request.user).first()
    if lr and lr.status == "pending":
        return redirect("groupinfo", groupid=group.id)
    if lr and lr.status == "approved":
        return redirect("dashboard")

    if lr and lr.status == "rejected":
        lr.status = "pending"
        lr.decidedat = None
        lr.decidedby = None
        lr.save()
    elif not lr:
        lr = LeaveRequest.objects.create(group=group, user=request.user)

    Notification.objects.create(
        user=group.createdby,
        group=group,
        fromuser=request.user,
        message=f"{request.user.username} requested to leave {group.name}.",
        type="leaverequest",
    )

    return redirect("groupinfo", groupid=group.id)


@login_required
def approveleave(request, groupid, requestid):
    group = get_object_or_404(Group, id=groupid)
    if request.user != group.createdby:
        return redirect("dashboard")
    if request.method != "POST":
        return redirect("groupinfo", groupid=group.id)

    lr = get_object_or_404(LeaveRequest, id=requestid, group=group)
    lr.status = "approved"
    lr.decidedat = timezone.now()
    lr.decidedby = request.user
    lr.save()

    if lr.user in group.members.all():
        group.members.remove(lr.user)

    Notification.objects.create(
        user=lr.user,
        group=group,
        fromuser=request.user,
        message=f"Admin approved your leave request for {group.name}. You have left the group.",
        type="leaveapproved",
    )

    for member in group.members.all():
        Notification.objects.create(
            user=member,
            group=group,
            fromuser=lr.user,
            message=f"{lr.user.username} left the group {group.name}.",
            type="left",
        )

    return redirect("groupinfo", groupid=group.id)


@login_required
def rejectleave(request, groupid, requestid):
    group = get_object_or_404(Group, id=groupid)
    if request.user != group.createdby:
        return redirect("dashboard")
    if request.method != "POST":
        return redirect("groupinfo", groupid=group.id)

    lr = get_object_or_404(LeaveRequest, id=requestid, group=group)
    lr.status = "rejected"
    lr.decidedat = timezone.now()
    lr.decidedby = request.user
    lr.save()

    Notification.objects.create(
        user=lr.user,
        group=group,
        fromuser=request.user,
        message=f"Admin rejected your leave request for {group.name}.",
        type="leaverejected",
    )
    return redirect("groupinfo", groupid=group.id)


@login_required
def deletegroup(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.method != "POST":
        return redirect("groupinfo", groupid=group.id)
    if request.user != group.createdby:
        return redirect("groupinfo", groupid=group.id)
    group.delete()
    return redirect("dashboard")


# ------------------- SPLIT DETAILS (kept as-is from your app) -------------------

@login_required
def splitdetails(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user not in group.members.all():
        return redirect("dashboard")

    members = list(group.members.all())
    expenses = Expense.objects.filter(group=group, isdeleted=False)
    total = expenses.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    total = Decimal(total)

    count = len(members)
    share = total / Decimal(count) if count else Decimal("0")

    paid = {m.id: Decimal("0") for m in members}
    for e in expenses:
        paid[e.paidby_id] = paid.get(e.paidby_id, Decimal("0")) + Decimal(e.amount)

    balances = {m: paid.get(m.id, Decimal("0")) - share for m in members}

    # apply already-settled
    settledpayments = Settlement.objects.filter(group=group, issettled=True).select_related("fromuser", "touser")
    for s in settledpayments:
        if s.fromuser:
            balances[s.fromuser] = balances.get(s.fromuser, Decimal("0")) + Decimal(s.amount)
        if s.touser:
            balances[s.touser] = balances.get(s.touser, Decimal("0")) - Decimal(s.amount)

    debtors = []
    creditors = []
    for m, net in balances.items():
        if net < 0:
            debtors.append((m, -net))
        elif net > 0:
            creditors.append((m, net))

    Settlement.objects.filter(group=group, issettled=False).delete()

    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor, damt = debtors[i]
        creditor, camt = creditors[j]
        payamt = min(damt, camt)

        Settlement.objects.create(
            group=group,
            fromuser=debtor,
            touser=creditor,
            amount=Decimal(str(round(payamt, 2))),
            issettled=False
        )

        damt -= payamt
        camt -= payamt
        debtors[i] = (debtor, damt)
        creditors[j] = (creditor, camt)
        if damt == 0:
            i += 1
        if camt == 0:
            j += 1

    settlements = Settlement.objects.filter(group=group).select_related("fromuser", "touser").order_by("-createdat")

    personal = []
    for s in settlements:
        if s.fromuser == request.user:
            personal.append({"type": "owe", "other": s.touser, "amount": s.amount})
        elif s.touser == request.user:
            personal.append({"type": "get", "other": s.fromuser, "amount": s.amount})

    rows = []
    for m in members:
        rows.append({
            "user": m,
            "paid": round(paid.get(m.id, Decimal("0")), 2),
            "net": round(balances.get(m, Decimal("0")), 2),
        })

    return render(request, "group/split_details.html", {
        "group": group,
        "total": round(total, 2),
        "share": round(share, 2),
        "rows": rows,
        "settlements": settlements,
        "personal": personal,
    })


@login_required
def marksettlementsettled(request, groupid, settlementid):
    group = get_object_or_404(Group, id=groupid)
    if request.user not in group.members.all():
        return redirect("dashboard")

    settlement = get_object_or_404(Settlement, id=settlementid, group=group)
    if request.user != settlement.touser:
        messages.error(request, "Only the receiver can mark this as settled.")
        return redirect("splitdetails", groupid=group.id)

    if request.method == "POST":
        if not settlement.issettled:
            settlement.issettled = True
            settlement.save()
            messages.success(request, f"{settlement.fromuser.username} paid {settlement.touser.username} ₹{settlement.amount}.")
    return redirect("splitdetails", groupid=group.id)


# ------------------- NOTIFICATIONS -------------------

@login_required
def notificationsview(request):
    notifications = Notification.objects.filter(user=request.user).order_by("-createdat")

    if request.method == "POST":
        Notification.objects.filter(user=request.user, isread=False).update(isread=True)

    unreadcount = Notification.objects.filter(user=request.user, isread=False).count()

    return render(request, "auth/notifications.html", {
        "notifications": notifications,
        "unreadcount": unreadcount,
    })


@login_required
def acceptinvite(request, notificationid):
    n = get_object_or_404(Notification, id=notificationid, user=request.user, type="invite")
    if not n.group:
        n.delete()
        return redirect("notifications")
    group = n.group

    if request.method != "POST":
        return redirect("notifications")

    if request.user not in group.members.all():
        group.members.add(request.user)
        for member in group.members.exclude(id=request.user.id):
            Notification.objects.create(
                user=member,
                group=group,
                fromuser=request.user,
                message=f"{request.user.username} joined the group {group.name}.",
                type="joined",
            )

    n.delete()
    return redirect("notifications")


@login_required
def rejectinvite(request, notificationid):
    n = get_object_or_404(Notification, id=notificationid, user=request.user, type="invite")
    if request.method != "POST":
        return redirect("notifications")

    if n.group:
        Notification.objects.create(
            user=n.group.createdby,
            group=n.group,
            fromuser=request.user,
            message=f"{request.user.username} rejected the invite to join {n.group.name}.",
            type="invite",
        )
    n.delete()
    return redirect("notifications")


@login_required
def sendinvite(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user != group.createdby:
        return redirect("groupinfo", groupid=groupid)

    if request.method == "POST":
        searchterm = (request.POST.get("searchuser") or "").strip()
        targetuser = None

        try:
            targetuser = User.objects.get(username__iexact=searchterm)
        except User.DoesNotExist:
            try:
                targetuser = User.objects.get(email__iexact=searchterm)
            except User.DoesNotExist:
                targetuser = None

        if targetuser and targetuser != request.user and targetuser not in group.members.all():
            Notification.objects.create(
                user=targetuser,
                group=group,
                fromuser=request.user,
                message=f"{request.user.username} invited you to join {group.name}. Code: {group.groupcode}",
                type="invite",
            )

    return redirect("groupinfo", groupid=groupid)


# ------------------- CHATS -------------------

@login_required
def chatslist(request):
    # GROUP chats
    groups = Group.objects.filter(members=request.user).order_by("-id")

    group_chat_data = []
    for group in groups:
        latest = (
            GroupChatMessage.objects
            .filter(group=group)
            .select_related("user")
            .order_by("-createdat")
            .first()
        )

        if latest:
            preview = (latest.message or "").strip() or "Photo"
            latest_time = latest.createdat
        else:
            preview = "No messages yet"
            latest_time = None

        last_seen = request.user.last_login or timezone.now()
        unread_count = (
            GroupChatMessage.objects
            .filter(group=group, createdat__gt=last_seen)
            .exclude(user=request.user)
            .count()
        )

        group_chat_data.append({
            "title": group.name,
            "image": (group.image.url if group.image else ""),
            "latest_message": (preview[:50] + "…") if len(preview) > 50 else preview,
            "latest_time": latest_time,
            "unread_count": unread_count,
            "url_name": "chatroom",
            "url_id": group.id,
        })

    # PRIVATE chats
    rooms = ChatRoom.objects.filter(users=request.user).order_by("-createdat")

    private_chat_data = []
    for room in rooms:
        other = room.otheruser(request.user)

        latest = (
            PrivateChatMessage.objects
            .filter(room=room)
            .select_related("user")
            .order_by("-createdat")
            .first()
        )

        if latest:
            preview = (latest.message or "").strip() or "Photo"
            latest_time = latest.createdat
        else:
            preview = "No messages yet"
            latest_time = None

        last_seen = request.user.last_login or timezone.now()
        unread_count = (
            PrivateChatMessage.objects
            .filter(room=room, createdat__gt=last_seen)
            .exclude(user=request.user)
            .count()
        )

        other_img = ""
        if other and hasattr(other, "profile") and other.profile and other.profile.image:
            other_img = other.profile.image.url

        private_chat_data.append({
            "title": other.username if other else "Private chat",
            "image": other_img,
            "latest_message": (preview[:50] + "…") if len(preview) > 50 else preview,
            "latest_time": latest_time,
            "unread_count": unread_count,
            "url_name": "privatechatroom",
            "url_id": room.id,
        })

    all_chats = group_chat_data + private_chat_data
    all_chats.sort(key=lambda x: (x["latest_time"] is None, x["latest_time"]), reverse=True)

    return render(request, "chat/chats_list.html", {"all_chats": all_chats})


@login_required
def chatroom(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user not in group.members.all():
        return redirect("dashboard")

    if request.method == "POST":
        text = (request.POST.get("message") or "").strip()
        img = request.FILES.get("image")

        if text or img:
            msg = GroupChatMessage.objects.create(group=group, user=request.user, message=text, image=img)

            # Notify other members about a new message
            for member in group.members.exclude(id=request.user.id):
                Notification.objects.create(
                    user=member,
                    group=group,
                    fromuser=request.user,
                    message=f"New message in {group.name}",
                    type="groupchat",
                )

            return redirect("chatroom", groupid=group.id)

    chatmessages = (
        GroupChatMessage.objects
        .filter(group=group)
        .select_related("user")
        .order_by("-createdat")[:100]
    )
    chatmessages = reversed(list(chatmessages))

    return render(request, "chat/chat_room.html", {"group": group, "messages": chatmessages})


@login_required
def startprivatechat(request, userid):
    otheruser = get_object_or_404(User, id=userid)
    if otheruser == request.user:
        return redirect("chatslist")

    room = ChatRoom.getorcreateprivateroom(request.user, otheruser)
    return redirect("privatechatroom", roomid=room.id)


@login_required
def privatechatroom(request, roomid):
    room = get_object_or_404(ChatRoom, id=roomid)
    if request.user not in room.users.all():
        return redirect("chatslist")

    otheruser = room.otheruser(request.user)

    if request.method == "POST":
        text = (request.POST.get("message") or "").strip()
        img = request.FILES.get("image")

        if text or img:
            msg = PrivateChatMessage.objects.create(room=room, user=request.user, message=text, image=img)

            # Notify the other user
            if otheruser:
                Notification.objects.create(
                    user=otheruser,
                    group=None,
                    fromuser=request.user,
                    message=f"New message from {request.user.username}",
                    type="privatechat",
                )

            return redirect("privatechatroom", roomid=room.id)

    msgs = (
        PrivateChatMessage.objects
        .filter(room=room)
        .select_related("user")
        .order_by("-createdat")[:100]
    )
    msgs = reversed(list(msgs))

    return render(request, "chat/private_room.html", {
        "room": room,
        "otheruser": otheruser,
        "messages": msgs
    })


# ------------------- EXPENSE DELETE -------------------

@login_required
def deleteexpense(request, groupid, expenseid):
    group = get_object_or_404(Group, id=groupid)
    expense = get_object_or_404(Expense, id=expenseid, group=group)

    if request.user != group.createdby and request.user != expense.paidby:
        messages.error(request, "You cannot delete this expense.")
        return redirect("groupdetail", groupid=group.id)

    if request.method == "POST":
        expense.isdeleted = True
        expense.deletedby = request.user
        expense.deletedat = timezone.now()
        expense.save()

        deleterprofile, _ = Profile.objects.get_or_create(user=request.user)
        deletername = (deleterprofile.fullname or "").strip() or request.user.username

        for member in group.members.exclude(id=request.user.id):
            Notification.objects.create(
                user=member,
                group=group,
                fromuser=request.user,
                message=f"{expense.description} (₹{expense.amount}) was deleted by {deletername}.",
                type="expensedeleted",
            )

        messages.success(request, "Expense deleted successfully.")
        return redirect("groupdetail", groupid=group.id)

    return render(request, "group/confirm_delete.html", {"group": group, "expense": expense})
@login_required
@require_POST
def updategroupphoto(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user != group.createdby:
        messages.error(request, "Only admin can change group photo.")
        return redirect("groupinfo", groupid=group.id)

    img = request.FILES.get("image")
    if not img:
        messages.error(request, "Please select an image.")
        return redirect("groupinfo", groupid=group.id)

    group.image = img
    group.save()
    messages.success(request, "Group photo updated.")
    return redirect("groupinfo", groupid=group.id)


@login_required
@require_POST
def removegroupphoto(request, groupid):
    group = get_object_or_404(Group, id=groupid)
    if request.user != group.createdby:
        messages.error(request, "Only admin can remove group photo.")
        return redirect("groupinfo", groupid=group.id)

    if group.image:
        group.image.delete(save=False)
        group.image = None
        group.save()

    messages.success(request, "Group photo removed.")
    return redirect("groupinfo", groupid=group.id)
