from django.urls import path

from . import views

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("forgot-password/", views.forgot_password_view, name="forgot-password"),
    path(
        "reset-password/<str:token>/",
        views.password_reset_confirm_view,
        name="password-reset-confirm",
    ),
    path("logout/", views.logout_view, name="logout"),
    path(
        "activate/<uidb64>/<token>/",
        views.activate_account_view,
        name="activate-account",
    ),
    path(
        "activate/resend/",
        views.resend_activation_email_view,
        name="resend-activation-email",
    ),
    path(
        "activate/success/",
        views.activation_success_view,
        name="activation-success",
    ),
    path("profile/", views.profile_settings_view, name="profile-settings"),
]
