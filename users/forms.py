from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
import re

from .models import ContactMessage, UserProfile


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    full_name = forms.CharField(max_length=150, required=False, label="Full name (optional)")
    avatar = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("username", "email", "full_name", "password1", "password2", "avatar")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"].strip().lower()
        user.first_name = self.cleaned_data.get("full_name", "").strip()
        if commit:
            user.save()
            avatar = self.cleaned_data.get("avatar")
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if avatar:
                profile.avatar = avatar
                profile.save(update_fields=["avatar"])
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=150, label="Username or email")

    def clean(self):
        identifier = str(self.cleaned_data.get("username", "")).strip()
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
            if user is not None:
                self.cleaned_data["username"] = user.username
        return super().clean()


class ForgotPasswordForm(forms.Form):
    identifier = forms.CharField(max_length=254, label="Username or email")


class AvatarUploadForm(forms.Form):
    avatar = forms.ImageField(required=True)


class ProfileSettingsForm(forms.Form):
    username = forms.CharField(max_length=150)
    full_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)
    avatar = forms.ImageField(required=False)
    new_password1 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="New password",
    )
    new_password2 = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Confirm new password",
    )

    def __init__(self, *args, user: User, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if not self.is_bound:
            self.initial["username"] = user.username
            self.initial["full_name"] = user.first_name
            self.initial["email"] = user.email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username__iexact=username).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.user.pk)
        if qs.exists():
            raise forms.ValidationError("This email is already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        password_1 = cleaned.get("new_password1", "")
        password_2 = cleaned.get("new_password2", "")

        if password_1 or password_2:
            if password_1 != password_2:
                raise forms.ValidationError("New password fields must match.")
            if len(password_1) < 8:
                raise forms.ValidationError("New password must be at least 8 characters.")

        return cleaned

    def email_changed(self) -> bool:
        return (
            self.cleaned_data.get("email", "").strip().lower()
            != self.user.email.lower()
        )

    def save(self):
        self.user.username = self.cleaned_data["username"]
        self.user.first_name = self.cleaned_data["full_name"].strip()

        profile, _ = UserProfile.objects.get_or_create(user=self.user)

        new_email = self.cleaned_data["email"].strip().lower()
        if new_email.lower() != self.user.email.lower():
            profile.pending_email = new_email
            profile.save(update_fields=["pending_email"])
        else:
            self.user.email = new_email

        self.user.save(update_fields=["username", "first_name", "email"])

        avatar = self.cleaned_data.get("avatar")
        if avatar:
            profile.avatar = avatar
            profile.save(update_fields=["avatar"])

        new_password = self.cleaned_data.get("new_password1", "")
        if new_password:
            self.user.set_password(new_password)
            self.user.save(update_fields=["password"])

        return self.user


class ContactUsForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    subject = forms.CharField(max_length=200)
    description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 7}),
        max_length=5000,
    )

    _code_like_pattern = re.compile(
        r"(<\s*script|javascript:|on\w+\s*=|<\?php|\{\{|\{%|</?\w+)",
        flags=re.IGNORECASE,
    )
    _control_chars_pattern = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

        if user is not None and getattr(user, "is_authenticated", False):
            self.fields["name"].required = False
            self.fields["email"].required = False
            display_name = (user.first_name or user.username or "").strip()
            self.initial["name"] = display_name
            self.initial["email"] = (user.email or "").strip().lower()

    def _validate_safe_text(self, value: str, field_label: str) -> str:
        cleaned = str(value or "").strip()
        if self._control_chars_pattern.search(cleaned):
            raise forms.ValidationError(
                f"{field_label} contains unsupported control characters."
            )
        if "<" in cleaned or ">" in cleaned:
            raise forms.ValidationError(
                f"{field_label} cannot contain HTML or markup."
            )
        if self._code_like_pattern.search(cleaned):
            raise forms.ValidationError(
                f"{field_label} contains blocked code-like content."
            )
        return cleaned

    def clean_name(self):
        value = self._validate_safe_text(
            self.cleaned_data.get("name", ""),
            "Name",
        )
        if self.user is not None and getattr(self.user, "is_authenticated", False):
            return (self.user.first_name or self.user.username or value).strip()
        return value

    def clean_email(self):
        value = str(self.cleaned_data.get("email", "")).strip().lower()
        if "\n" in value or "\r" in value:
            raise forms.ValidationError("Email contains invalid characters.")
        if self.user is not None and getattr(self.user, "is_authenticated", False):
            user_email = (self.user.email or "").strip().lower()
            if not user_email:
                raise forms.ValidationError(
                    "Your account does not have an email address. "
                    "Please add one in profile settings first."
                )
            return user_email
        return value

    def clean_subject(self):
        value = self._validate_safe_text(
            self.cleaned_data.get("subject", ""),
            "Subject",
        )
        if "\n" in value or "\r" in value:
            raise forms.ValidationError("Subject contains invalid characters.")
        return value

    def clean_description(self):
        return self._validate_safe_text(
            self.cleaned_data.get("description", ""),
            "Description",
        )

    def save(self) -> ContactMessage:
        linked_user = None
        if self.user is not None and getattr(self.user, "is_authenticated", False):
            linked_user = self.user

        return ContactMessage.objects.create(
            user=linked_user,
            name=self.cleaned_data["name"],
            email=self.cleaned_data["email"],
            subject=self.cleaned_data["subject"],
            description=self.cleaned_data["description"],
            status=ContactMessage.STATUS_RECEIVED,
        )
