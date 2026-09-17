import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import ConsultationSession, ConsultationMessage
from .services import get_ai_response

DEFAULT_MODE = "triase_lengkap"
VALID_MODES = {"triase_lengkap", "konsultasi_cepat", "tanya_obat"}


@ensure_csrf_cookie
def index(request):
    """Landing page = 'Konsultasi AI' new consultation view."""
    return render(request, "konsultasi/index.html")


def session_page(request, session_id):
    """Deep-linkable page for one consultation session (/konsultasi/<id>/)."""
    get_object_or_404(ConsultationSession, id=session_id)
    return render(request, "konsultasi/index.html")


@require_POST
def api_send_message(request):
    """Receive a user prompt, consult Gemini, persist, and return the reply."""
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    message = (payload.get("message") or "").strip()
    mode = payload.get("mode") or DEFAULT_MODE
    if not message:
        return JsonResponse({"error": "Pesan tidak boleh kosong."}, status=400)
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE

    session_id = payload.get("session_id")
    if session_id:
        session = get_object_or_404(ConsultationSession, id=session_id)
    else:
        session = ConsultationSession.objects.create(mode=mode)

    user_msg = ConsultationMessage.objects.create(
        session=session,
        role=ConsultationMessage.Role.USER,
        content=message,
    )

    # Send the full conversation so follow-up questions keep context.
    history = session.messages.order_by("created_at")
    conversation_text = "\n\n".join(
        f"{'User' if m.role == ConsultationMessage.Role.USER else 'Lestari AI'}: {m.content}"
        for m in history
    )

    result = get_ai_response(conversation_text, mode=mode)

    ai_msg = ConsultationMessage.objects.create(
        session=session,
        role=ConsultationMessage.Role.AI,
        content=result["text"],
        is_emergency=result["is_emergency"],
    )

    if not session.title:
        session.title = message[:100]
        session.save()

    return JsonResponse({
        "session_id": session.id,
        "title": session.title,
        "user_message": {
            "role": "user",
            "content": user_msg.content,
            "is_emergency": user_msg.is_emergency,
        },
        "ai_message": {
            "role": "ai",
            "content": ai_msg.content,
            "is_emergency": ai_msg.is_emergency,
        },
        "error": result["error"],
    })


def _session_to_dict(session):
    return {
        "id": session.id,
        "title": session.title or f"Konsultasi #{session.id}",
        "updated_at": session.updated_at.isoformat(),
        "messages": [
            {
                "role": m.role,
                "content": m.content,
                "is_emergency": m.is_emergency,
            }
            for m in session.messages.all()
        ],
    }


def api_sessions(request):
    """List all consultation sessions (for the 'Sesi Terakhir' sidebar)."""
    sessions = ConsultationSession.objects.all()
    return JsonResponse({"sessions": [_session_to_dict(s) for s in sessions]})


def api_session_detail(request, session_id):
    session = get_object_or_404(ConsultationSession, id=session_id)
    return JsonResponse(_session_to_dict(session))
