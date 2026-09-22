import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .models import ConsultationSession, ConsultationMessage, Profile
from .services import get_ai_response
from .artikel import fetch_articles
from .bmkg import BmkgError, get_forecast, search_locations
from .storage import (
    MAX_AVATAR_BYTES,
    ALLOWED_CONTENT_TYPES,
    AvatarError,
    delete_avatar,
    upload_avatar,
    upload_chat_image,
)

DEFAULT_MODE = "triase_lengkap"
VALID_MODES = {"triase_lengkap", "konsultasi_cepat", "tanya_obat"}
CONSULT_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_CONSULT_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


def _validate_avatar(upload):
    """Return an error string if the uploaded file isn't a valid avatar, else None."""
    if not upload:
        return None
    content_type = getattr(upload, "content_type", "") or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        return "PFP hanya JPG, PNG, WebP, atau GIF."
    if upload.size > MAX_AVATAR_BYTES:
        return "PFP maksimal 5 MB."
    return None


def landing_page(request):
    """Default route '/': marketing landing page for Lestari."""
    return render(request, "konsultasi/landing.html")


def login_page(request):
    """Render the login form (GET) or authenticate (POST)."""
    if request.user.is_authenticated:
        return redirect("konsultasi:index")

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect("konsultasi:index")
        return render(request, "konsultasi/auth.html", {
            "active_tab": "login",
            "login_email": email,
            "login_error": "Email atau password tidak valid. Silakan coba lagi.",
        })

    return render(request, "konsultasi/auth.html", {"active_tab": "login"})


def signup_page(request):
    """Render the sign up form (GET) or create an account (POST)."""
    if request.user.is_authenticated:
        return redirect("konsultasi:index")

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "")
        confirm = request.POST.get("confirm_password", "")

        context = {
            "active_tab": "signup",
            "signup_name": name,
            "signup_email": email,
        }

        error = None
        avatar = request.FILES.get("avatar")
        if not name or not email or not password:
            error = "Semua lapangan (nama, email, password) wajib dibutuhkan."
        elif "@" not in email or "." not in email:
            error = "Format email tidak valid."
        elif password != confirm:
            error = "Konfirmasi password tidak berpasang dengan password."
        elif len(password) < 8:
            error = "Password minimal 8 karakter."
        elif User.objects.filter(username=email).exists():
            error = "Email sudah reketster. Silakan login."
        elif _validate_avatar(avatar):
            error = _validate_avatar(avatar)

        if error is None:
            try:
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=name,
                )
                if avatar:
                    try:
                        profile = user.profile
                        profile.avatar_url = upload_avatar(user.id, avatar)
                        profile.save(update_fields=["avatar_url"])
                    except AvatarError as exc:
                        user.delete()
                        error = str(exc)
                if error is None:
                    login(request, user)
                    return redirect("konsultasi:index")
            except Exception:
                error = "Gagal reketster akun. Silakan coba lagi."

        context["signup_error"] = error
        return render(request, "konsultasi/auth.html", context)

    return render(request, "konsultasi/auth.html", {"active_tab": "signup"})


@require_POST
def api_upload_avatar(request):
    """Replace the current user's profile picture and return the new URL."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Sesion expired. Silakan login ulang."}, status=401)

    avatar = request.FILES.get("avatar")
    error = _validate_avatar(avatar)
    if error:
        return JsonResponse({"error": error}, status=400)

    try:
        # get_or_create so accounts created before the Profile feature work too.
        profile, _ = Profile.objects.get_or_create(user=request.user)
        old_url = profile.avatar_url
        new_url = upload_avatar(request.user.id, avatar)
        profile.avatar_url = new_url
        profile.save(update_fields=["avatar_url"])
    except AvatarError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    if old_url:
        delete_avatar(old_url)

    return JsonResponse({
        "avatar_url": new_url,
        "name": request.user.first_name,
        "email": request.user.email,
    })


@require_POST
def logout_view(request):
    """Log the user out and return to the landing page."""
    logout(request)
    return redirect("konsultasi:landing")


@login_required
@ensure_csrf_cookie
def index(request):
    """'Konsultasi AI' new consultation view (only for logged-in users)."""
    return render(request, "konsultasi/index.html")


@login_required
def session_page(request, session_id):
    """Deep-linkable page for one consultation session (/konsultasi/<id>/)."""
    get_object_or_404(ConsultationSession, id=session_id)
    return render(request, "konsultasi/index.html")


@login_required
def cuaca_page(request):
    """Weather forecast page (/cuaca/)."""
    return render(request, "konsultasi/cuaca.html")


@login_required
def artikel_page(request):
    """Health articles page (/artikel/)."""
    return render(request, "konsultasi/artikel.html")


@login_required
def api_artikel(request):
    """Return health articles for a query (cached Google News search)."""
    q = (request.GET.get("q") or "").strip() or "kesehatan"
    return JsonResponse({"articles": fetch_articles(q)})


@login_required
def api_cuaca_search(request):
    """Resolve a place name to BMKG village codes (level-4 / adm4)."""
    q = (request.GET.get("q") or "").strip()
    if len(q) < 2:
        return JsonResponse({"results": []})
    try:
        return JsonResponse({"results": search_locations(q)})
    except BmkgError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


@login_required
def api_cuaca_forecast(request):
    """Return a cached/upstream 3-day forecast for an adm4 code."""
    adm4 = (request.GET.get("adm4") or "").strip()
    if not adm4:
        return JsonResponse({"error": "Parameter adm4 wajib."}, status=400)
    try:
        return JsonResponse(get_forecast(adm4))
    except BmkgError as exc:
        return JsonResponse({"error": str(exc)}, status=502)


@login_required
@require_POST
def api_send_message(request):
    """Receive a user prompt (and optional image), consult Gemini, persist, and return the reply."""
    image = None

    if request.content_type == "application/json":
        try:
            payload = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)
        message = (payload.get("message") or "").strip()
        mode = payload.get("mode") or DEFAULT_MODE
        session_id = payload.get("session_id")
    else:
        message = (request.POST.get("message") or "").strip()
        mode = request.POST.get("mode") or DEFAULT_MODE
        session_id = request.POST.get("session_id")
        upload = request.FILES.get("image")
        if upload:
            content_type = getattr(upload, "content_type", "") or ""
            if content_type not in CONSULT_IMAGE_TYPES:
                return JsonResponse({"error": "Hanya JPG, PNG, WebP, atau GIF."}, status=400)
            if upload.size > MAX_CONSULT_IMAGE_BYTES:
                return JsonResponse({"error": "Foto maksimal 10 MB."}, status=400)
            image = {"data": upload.read(), "mime_type": content_type}

    if not message:
        return JsonResponse({"error": "Pesan tidak boleh kosong."}, status=400)
    if mode not in VALID_MODES:
        mode = DEFAULT_MODE

    # Persist the attached image to storage so it can be shown in chat history.
    image_url = ""
    if image:
        try:
            image_url = upload_chat_image(request.user.id, image["data"], image["mime_type"])
        except AvatarError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    if session_id:
        session = get_object_or_404(ConsultationSession, id=session_id)
    else:
        session = ConsultationSession.objects.create(mode=mode)

    user_msg = ConsultationMessage.objects.create(
        session=session,
        role=ConsultationMessage.Role.USER,
        content=message,
        image_url=image_url,
    )

    # Send the full conversation so follow-up questions keep context.
    history = session.messages.order_by("created_at")
    conversation_text = "\n\n".join(
        f"{'User' if m.role == ConsultationMessage.Role.USER else 'Lestari AI'}: {m.content}"
        for m in history
    )

    result = get_ai_response(conversation_text, mode=mode, image=image)

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
            "image_url": user_msg.image_url,
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
                "image_url": m.image_url,
                "is_emergency": m.is_emergency,
            }
            for m in session.messages.all()
        ],
    }


@login_required
def api_sessions(request):
    """List all consultation sessions (for the 'Sesi Terakhir' sidebar)."""
    sessions = ConsultationSession.objects.all()
    return JsonResponse({"sessions": [_session_to_dict(s) for s in sessions]})


@login_required
def api_session_detail(request, session_id):
    session = get_object_or_404(ConsultationSession, id=session_id)
    return JsonResponse(_session_to_dict(session))
