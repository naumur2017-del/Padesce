from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from App_PADESCE.messaging.models import SupportAlarm, SupportMessage


def _is_manager(user) -> bool:
    return user.groups.filter(name__in=["manager_cga", "manager_padesce"]).exists()


class SupportConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.user = user
        self.user_group = f"support_user_{user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(self.user_group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = str(content.get("action") or "").strip()
        if action == "send_chat":
            await self._handle_send_chat(content)
        elif action == "send_alarm":
            await self._handle_send_alarm(content)
        elif action == "mark_alarm_seen":
            await self._handle_mark_alarm_seen(content)
        else:
            await self.send_json({"type": "error", "error": "Action inconnue."})

    async def support_event(self, event):
        await self.send_json(event["payload"])

    async def _handle_send_chat(self, content):
        recipient_id = content.get("recipient_id")
        body = str(content.get("body") or "").strip()
        if not recipient_id or not str(recipient_id).isdigit() or not body:
            await self.send_json({"type": "error", "error": "Message invalide."})
            return
        recipient = await self._get_user_by_id(int(recipient_id))
        if not recipient:
            await self.send_json({"type": "error", "error": "Destinataire introuvable."})
            return
        allowed = await self._can_message(self.user, recipient)
        if not allowed:
            await self.send_json({"type": "error", "error": "Destinataire non autorise."})
            return

        message = await self._create_message(self.user.id, recipient.id, body, SupportMessage.KIND_CHAT)
        payload = {
            "type": "chat_message",
            "message": message,
        }
        await self.channel_layer.group_send(f"support_user_{self.user.id}", {"type": "support.event", "payload": payload})
        await self.channel_layer.group_send(f"support_user_{recipient.id}", {"type": "support.event", "payload": payload})

    async def _handle_send_alarm(self, content):
        module = str(content.get("module") or "").strip()
        title = str(content.get("title") or "").strip()
        details = str(content.get("details") or "").strip()
        if not title:
            await self.send_json({"type": "error", "error": "Titre d'alarme requis."})
            return
        alarm = await self._create_alarm(self.user.id, module, title, details)
        admin_users = await self._get_superusers()
        for admin_user in admin_users:
            if admin_user.id != self.user.id:
                await self._create_message(
                    self.user.id,
                    admin_user.id,
                    f"[ALARM] {title}\nModule: {module or '-'}\n{details}",
                    SupportMessage.KIND_ALARM,
                )
            await self.channel_layer.group_send(
                f"support_user_{admin_user.id}",
                {
                    "type": "support.event",
                    "payload": {
                        "type": "alarm_created",
                        "alarm": alarm,
                    },
                },
            )
        await self.send_json({"type": "alarm_sent", "alarm": alarm})

    async def _handle_mark_alarm_seen(self, content):
        if not self.user.is_superuser:
            await self.send_json({"type": "error", "error": "Action reservee au superadmin."})
            return
        alarm_id = content.get("alarm_id")
        if not alarm_id or not str(alarm_id).isdigit():
            await self.send_json({"type": "error", "error": "Identifiant d'alarme invalide."})
            return
        alarm = await self._mark_alarm_seen(int(alarm_id), self.user.id)
        if not alarm:
            await self.send_json({"type": "error", "error": "Alerte introuvable."})
            return
        await self.send_json({"type": "alarm_seen", "alarm": alarm})

    @database_sync_to_async
    def _get_user_by_id(self, user_id: int):
        return get_user_model().objects.filter(pk=user_id).first()

    @database_sync_to_async
    def _get_superusers(self):
        return list(get_user_model().objects.filter(is_superuser=True))

    @database_sync_to_async
    def _can_message(self, sender, recipient) -> bool:
        sender_is_agent = sender.is_superuser or _is_manager(sender)
        recipient_is_agent = recipient.is_superuser or _is_manager(recipient)
        if sender_is_agent:
            return sender.id != recipient.id
        return recipient_is_agent and sender.id != recipient.id

    @database_sync_to_async
    def _create_message(self, sender_id: int, recipient_id: int, body: str, kind: str):
        msg = SupportMessage.objects.create(
            sender_id=sender_id,
            recipient_id=recipient_id,
            body=body,
            kind=kind,
            is_read=False,
        )
        return {
            "id": msg.id,
            "sender_id": msg.sender_id,
            "sender_username": msg.sender.get_username(),
            "recipient_id": msg.recipient_id,
            "recipient_username": msg.recipient.get_username(),
            "body": msg.body,
            "kind": msg.kind,
            "kind_label": msg.get_kind_display(),
            "created_at": msg.created_at.isoformat(),
        }

    @database_sync_to_async
    def _create_alarm(self, reporter_id: int, module: str, title: str, details: str):
        alarm = SupportAlarm.objects.create(
            reporter_id=reporter_id,
            module=module,
            title=title,
            details=details,
            is_seen=False,
            is_resolved=False,
        )
        return {
            "id": alarm.id,
            "reporter_id": alarm.reporter_id,
            "reporter_username": alarm.reporter.get_username(),
            "module": alarm.module,
            "title": alarm.title,
            "details": alarm.details,
            "is_seen": alarm.is_seen,
            "created_at": alarm.created_at.isoformat(),
        }

    @database_sync_to_async
    def _mark_alarm_seen(self, alarm_id: int, user_id: int):
        alarm = SupportAlarm.objects.filter(pk=alarm_id).first()
        if not alarm:
            return None
        if not alarm.is_seen:
            alarm.is_seen = True
            alarm.seen_by_id = user_id
            alarm.seen_at = timezone.now()
            alarm.save(update_fields=["is_seen", "seen_by", "seen_at", "updated_at"])
        return {
            "id": alarm.id,
            "is_seen": alarm.is_seen,
            "seen_by": alarm.seen_by.get_username() if alarm.seen_by else "",
            "seen_at": alarm.seen_at.isoformat() if alarm.seen_at else "",
        }
