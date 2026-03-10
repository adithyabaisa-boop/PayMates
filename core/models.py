from django.db import models
from django.contrib.auth.models import User
import random
import string


def generate_group_code(length=6):
    return ''.join(random.choices(string.digits, k=length))


class Group(models.Model):
    name = models.CharField(max_length=100)
    groupcode = models.CharField(max_length=20, unique=True)

    # TEMP nullable to allow migration on existing DB rows
    createdby = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="createdgroups",
        null=True,
        blank=True,
    )

    members = models.ManyToManyField(
        User,
        related_name="paymatesgroups",
        related_query_name="paymatesgroup",
        blank=True,
    )

    image = models.ImageField(upload_to="grouppics", null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.groupcode:
            code = generate_group_code()
            while Group.objects.filter(groupcode=code).exists():
                code = generate_group_code()
            self.groupcode = code
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Expense(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="expenses")
    paidby = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255)
    receipt = models.ImageField(upload_to="receipts", null=True, blank=True)
    createdat = models.DateTimeField(auto_now_add=True)

    isdeleted = models.BooleanField(default=False)
    deletedby = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deletedexpenses",
    )
    deletedat = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.description} - {self.amount}"


class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE)

    # IMPORTANT: keep unique related_name (do NOT use sentnotifications here)
    fromuser = models.ForeignKey(
        User,
        related_name="settlementsmade",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    touser = models.ForeignKey(
        User,
        related_name="settlementsreceived",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    issettled = models.BooleanField(default=False)
    createdat = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    TYPE_CHOICES = [
        ("invite", "Group Invite"),
        ("joined", "User Joined"),
        ("left", "User Left"),
        ("leaverequest", "Leave Request"),
        ("leaveapproved", "Leave Approved"),
        ("leaverejected", "Leave Rejected"),
        ("expensedeleted", "Expense Deleted"),

        # NEW: chat-related notifications
        ("groupchat", "Group Chat Message"),
        ("privatechat", "Private Chat Message"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, null=True, blank=True)

    # TEMP nullable to allow migration on existing notification rows
    fromuser = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sentnotifications",
        null=True,
        blank=True,
    )

    message = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    isread = models.BooleanField(default=False)
    createdat = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-createdat"]

    def __str__(self):
        return f"{self.type} - {self.user.username}"


class GroupChatMessage(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="chatmessages")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chatmessages")
    message = models.TextField(blank=True)
    image = models.ImageField(upload_to="chatimages", null=True, blank=True)
    createdat = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["createdat"]


class LeaveRequest(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="leaverequests")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leaverequests")
    createdat = models.DateTimeField(auto_now_add=True)

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    decidedat = models.DateTimeField(null=True, blank=True)
    decidedby = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leaverequestsdecided",
    )

    class Meta:
        unique_together = ("group", "user")

    def __str__(self):
        return f"{self.user.username} leave request for {self.group.name} ({self.status})"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    fullname = models.CharField(max_length=100, null=True, blank=True)
    dateofbirth = models.DateField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    mobile = models.CharField(max_length=15, null=True, blank=True)
    image = models.ImageField(upload_to="profilepics", null=True, blank=True)

    def __str__(self):
        return f"Profile of {self.user.username}"


class ChatRoom(models.Model):
    users = models.ManyToManyField(User, related_name="privatechatrooms")
    createdat = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def getorcreateprivateroom(user1, user2):
        if user1 == user2:
            raise ValueError("Cannot create a private chat with yourself.")
        existing = ChatRoom.objects.filter(users=user1).filter(users=user2)
        if existing.exists():
            return existing.first()
        room = ChatRoom.objects.create()
        room.users.add(user1, user2)
        return room

    def otheruser(self, me):
        return self.users.exclude(id=me.id).first()

    def __str__(self):
        usernames = ", ".join(self.users.values_list("username", flat=True))
        return f"ChatRoom({usernames})"


class PrivateChatMessage(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name="messages")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="privatemessages")
    message = models.TextField(blank=True)
    image = models.ImageField(upload_to="privatechatimages", null=True, blank=True)
    createdat = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["createdat"]
